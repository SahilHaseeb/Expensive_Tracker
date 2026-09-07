"""
API Guard — Centralized Rate Limiting, Request Protection, Caching, and Error Sanitization.

Provides:
- Thread-safe sliding-window rate limiter per user / IP
- In-flight request deduplication (stampede / double-click prevention)
- Short-lived TTL cache for non-sensitive public queries (e.g., shopping deals)
- Controlled retry mechanism with exponential backoff & Retry-After respect
- Error sanitization to prevent leaking API keys, file paths, or internal URLs
- Safe structured logging without sensitive data
"""

import time
import threading
import logging
import re
from functools import wraps

try:
    from flask import request, jsonify, flash, redirect, url_for
    from flask_login import current_user
    FLASK_AVAILABLE = True
except ImportError:
    request = None
    jsonify = None
    flash = None
    redirect = None
    url_for = None
    current_user = None
    FLASK_AVAILABLE = False

logger = logging.getLogger('app.api_guard')


# ============================================================================
# 1. ERROR SANITIZATION & SAFE LOGGING
# ============================================================================

def sanitize_error_message(error, default_msg="The service is temporarily unavailable. Please try again shortly."):
    """
    Remove sensitive details (API keys, file paths, auth headers, URLs)
    and return a clean, user-friendly message.
    """
    if error is None:
        return default_msg

    raw_str = str(error)

    # Check for known categories and return polite user-facing messages
    lower = raw_str.lower()
    if any(k in lower for k in ["rate limit", "quota", "too many requests", "429", "resourceexhausted"]):
        return "You've made several requests quickly or service is busy. Please wait a moment and try again."
    if any(k in lower for k in ["timeout", "timed out", "deadlineexceeded", "504"]):
        return "The request took too long to complete. Please try again."
    if any(k in lower for k in ["connection", "network", "connecterror", "connectionerror", "failed to establish"]):
        return "Unable to connect to the external service. Please check your network and try again."
    if any(k in lower for k in ["unauthorized", "authentication", "api key", "forbidden", "401", "403"]):
        return "Service configuration or authentication issue. Please try again later."
    if any(k in lower for k in ["500", "502", "503", "service unavailable", "bad gateway"]):
        return "The external service is temporarily unavailable. Please try again shortly."

    # Strip potential API keys (hex or alphanumeric strings of 20+ chars)
    sanitized = re.sub(r'(api[_-]?key[=:\s]+)[a-zA-Z0-9_\-]{16,}', r'\1[PROTECTED]', raw_str, flags=re.IGNORECASE)
    sanitized = re.sub(r'(key[=:\s]+)[a-zA-Z0-9_\-]{16,}', r'\1[PROTECTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'bearer\s+[a-zA-Z0-9_\-\.]{16,}', 'Bearer [PROTECTED]', sanitized, flags=re.IGNORECASE)
    # Strip local filesystem paths
    sanitized = re.sub(r'[A-Za-z]:\\[^:\s]+', '[PATH]', sanitized)
    sanitized = re.sub(r'/[a-zA-Z0-9_\.\-]+/[a-zA-Z0-9_\.\-/]+', '[PATH]', sanitized)
    # Strip full URLs with query parameters
    sanitized = re.sub(r'https?://[^\s\?]+\?[^\s]+', '[URL]', sanitized)

    # If the sanitized string is still technical or empty, return default
    if any(tech in sanitized.lower() for tech in ["traceback", "exception", "syntaxerror", "internal server error"]):
        return default_msg

    return sanitized or default_msg


def log_api_event(service_name, endpoint, status, duration_ms=None, error=None, retry_attempt=0):
    """
    Log external API events safely without leaking API keys, authorization tokens,
    or sensitive user financial data.
    """
    duration_str = f" in {duration_ms:.1f}ms" if duration_ms is not None else ""
    retry_str = f" [retry #{retry_attempt}]" if retry_attempt > 0 else ""

    if status == "SUCCESS":
        logger.info(f"[{service_name}] {endpoint} completed successfully{duration_str}{retry_str}")
    elif status in ("TIMEOUT", "NETWORK_ERROR", "RATE_LIMITED"):
        safe_err = sanitize_error_message(error, "External error") if error else "Transient issue"
        logger.warning(f"[{service_name}] {endpoint} failed with {status}{duration_str}{retry_str}: {safe_err}")
    else:
        safe_err = sanitize_error_message(error, "Unknown error") if error else "Unknown"
        logger.error(f"[{service_name}] {endpoint} failed with {status}{duration_str}{retry_str}: {safe_err}")


# ============================================================================
# 2. SLIDING-WINDOW RATE LIMITER
# ============================================================================

class RateLimiter:
    """
    Thread-safe in-memory sliding-window rate limiter.
    Limits requests per key (user_id or client_ip + action) within a given window (seconds).
    """
    def __init__(self, max_keys=10000):
        self._lock = threading.Lock()
        self._requests = {}  # key -> list of float timestamps
        self._max_keys = max_keys

    def is_allowed(self, key, limit, window=60):
        """
        Check if a request under `key` is allowed.
        Returns (allowed: bool, remaining: int, retry_after: int).
        """
        now = time.time()
        cutoff = now - window

        with self._lock:
            # Clean up old timestamps
            timestamps = self._requests.get(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= limit:
                # Rate limit exceeded
                oldest = valid_timestamps[0]
                retry_after = max(1, int(oldest + window - now) + 1)
                self._requests[key] = valid_timestamps
                return False, 0, retry_after

            # Allowed: record this request
            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps

            # Memory housekeeping if dictionary grows excessively
            if len(self._requests) > self._max_keys:
                self._cleanup_stale_keys(now, window)

            remaining = max(0, limit - len(valid_timestamps))
            return True, remaining, 0

    def reset_key(self, key):
        """Reset history for a specific key (useful in testing)"""
        with self._lock:
            self._requests.pop(key, None)

    def clear(self):
        """Clear all rate limit tracking"""
        with self._lock:
            self._requests.clear()

    def _cleanup_stale_keys(self, now, window):
        """Prune keys with no active timestamps in the window"""
        cutoff = now - window
        stale = [k for k, ts in self._requests.items() if not ts or ts[-1] <= cutoff]
        for k in stale:
            del self._requests[k]


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_identifier():
    """Determine client identifier: authenticated user ID or remote IP"""
    if current_user and getattr(current_user, 'is_authenticated', False):
        return f"user:{current_user.id}"
    
    if request is not None:
        try:
            forwarded = request.headers.get('X-Forwarded-For') if hasattr(request, 'headers') else None
            if forwarded:
                client_ip = forwarded.split(',')[0].strip()
            else:
                client_ip = getattr(request, 'remote_addr', '127.0.0.1') or '127.0.0.1'
            return f"ip:{client_ip}"
        except Exception:
            return "ip:127.0.0.1"
    return "ip:127.0.0.1"


def rate_limited(limit, window=60, action="api", is_json=True):
    """
    Route decorator to enforce server-side rate limits.
    Returns standard HTTP 429 with 'Retry-After' header and user-friendly message.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not FLASK_AVAILABLE or request is None:
                return f(*args, **kwargs)

            client_id = get_client_identifier()
            rate_key = f"{action}:{client_id}"

            allowed, remaining, retry_after = rate_limiter.is_allowed(rate_key, limit, window)
            if not allowed:
                log_api_event("RateLimiter", f"{action} ({client_id})", "RATE_LIMITED", 
                              error=f"Limit {limit}/{window}s exceeded. Retry after {retry_after}s")
                
                if is_json and jsonify is not None:
                    resp = jsonify({
                        "success": False,
                        "status": "rate_limited",
                        "error_type": "rate_limited",
                        "message": "You've made several requests quickly. Please wait a moment and try again.",
                        "user_message": "You've made several requests quickly. Please wait a moment and try again.",
                        "retryable": True,
                        "retry_after": retry_after
                    })
                    resp.status_code = 429
                    resp.headers['Retry-After'] = str(retry_after)
                    resp.headers['X-RateLimit-Limit'] = str(limit)
                    resp.headers['X-RateLimit-Remaining'] = "0"
                    return resp
                else:
                    if flash is not None:
                        flash(f"You've made several requests quickly. Please wait {retry_after} seconds before trying again.", "warning")
                    if redirect is not None and url_for is not None:
                        resp = redirect(request.referrer or url_for('main.dashboard'))
                        resp.headers['Retry-After'] = str(retry_after)
                        return resp
                    return "Too Many Requests", 429

            # Execute the route and append rate limit headers
            result = f(*args, **kwargs)
            if hasattr(result, 'headers'):
                result.headers['X-RateLimit-Limit'] = str(limit)
                result.headers['X-RateLimit-Remaining'] = str(remaining)
            return result
        return wrapped
    return decorator


# ============================================================================
# 3. SHORT-LIVED IN-MEMORY TTL CACHE
# ============================================================================

class SimpleTTLCache:
    """
    Thread-safe, lightweight in-memory cache with Time-To-Live (TTL).
    Strictly for non-sensitive public queries (e.g. shopping searches).
    DO NOT use for private user financial records!
    """
    def __init__(self, max_entries=500):
        self._lock = threading.Lock()
        self._store = {}  # key -> (value, expire_at)
        self._max_entries = max_entries

    def get(self, key):
        """Retrieve value if present and unexpired, else None"""
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            val, expire_at = item
            if now > expire_at:
                del self._store[key]
                return None
            return val

    def set(self, key, value, ttl_seconds=300):
        """Store value with TTL in seconds"""
        now = time.time()
        with self._lock:
            # Enforce max size via simple eviction
            if len(self._store) >= self._max_entries:
                # Evict expired items first
                expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
                for k in expired_keys:
                    del self._store[k]
                # If still at max capacity, evict oldest 10%
                if len(self._store) >= self._max_entries:
                    sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k][1])
                    for k in sorted_keys[:max(1, len(sorted_keys) // 10)]:
                        del self._store[k]

            self._store[key] = (value, now + ttl_seconds)

    def delete(self, key):
        """Remove a specific key"""
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        """Clear all entries"""
        with self._lock:
            self._store.clear()

    def size(self):
        """Return number of currently active entries"""
        now = time.time()
        with self._lock:
            return sum(1 for _, exp in self._store.values() if now <= exp)


# Global shopping search cache (5 minute default TTL)
shopping_cache = SimpleTTLCache(max_entries=300)


# ============================================================================
# 4. IN-FLIGHT REQUEST DEDUPLICATION (STAMPEDE PROTECTION)
# ============================================================================

class InFlightDeduplicator:
    """
    Prevents duplicate simultaneous identical requests from hammering upstream APIs.
    If multiple threads/requests ask for the exact same key at the same time,
    only ONE upstream call is made; the other requests wait and receive the same result.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._in_flight = {}  # key -> threading.Event

    def execute_deduped(self, key, func, *args, **kwargs):
        """
        Execute `func(*args, **kwargs)` with deduplication for `key`.
        If `key` is already running, wait up to timeout and fetch from cache.
        """
        with self._lock:
            if key in self._in_flight:
                event = self._in_flight[key]
                is_leader = False
            else:
                event = threading.Event()
                self._in_flight[key] = event
                is_leader = True

        if not is_leader:
            # Wait for leader to finish (max 15 seconds)
            event.wait(timeout=15.0)
            # Fetch result from cache if available
            cached = shopping_cache.get(key)
            if cached is not None:
                return cached
            # If not in cache or leader failed, fall back to fresh call
            return func(*args, **kwargs)

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            with self._lock:
                event.set()
                self._in_flight.pop(key, None)


in_flight_deduplicator = InFlightDeduplicator()


# ============================================================================
# 5. CONTROLLED RETRY MECHANISM WITH EXPONENTIAL BACKOFF
# ============================================================================

def execute_with_retry(
    func,
    *args,
    max_retries=2,
    base_delay=0.5,
    backoff_factor=2.0,
    retryable_exceptions=(),
    retryable_statuses=(502, 503, 504),
    service_name="ExternalAPI",
    endpoint="call",
    **kwargs
):
    """
    Execute callable with controlled exponential backoff for transient errors.
    
    Rules:
    - Never retries indefinitely (max_retries defaults to 2, total 3 attempts).
    - Does NOT retry authentication (401/403) or client input (400/404) errors.
    - Carefully handles 429: if response provides 'Retry-After' <= 2.0s, waits and retries once;
      otherwise fails fast without burning useless retries.
    """
    attempts = 0
    delay = base_delay

    while True:
        attempts += 1
        t0 = time.time()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - t0) * 1000
            if attempts > 1:
                log_api_event(service_name, endpoint, "SUCCESS", duration_ms=duration_ms, retry_attempt=attempts - 1)
            return result

        except Exception as e:
            duration_ms = (time.time() - t0) * 1000

            # Check if exception is considered transient & retryable
            is_retryable_exc = isinstance(e, retryable_exceptions)
            
            # Check response status code if available (e.g. requests.Response or custom exception)
            status_code = getattr(e, 'status_code', None)
            if status_code is None and hasattr(e, 'response') and e.response is not None:
                status_code = getattr(e.response, 'status_code', None)

            is_retryable_status = status_code in retryable_statuses

            # Handle 429 specifically
            is_429 = status_code == 429 or "429" in str(e)
            retry_after_sec = None
            if is_429 and hasattr(e, 'response') and e.response is not None:
                retry_after_hdr = e.response.headers.get('Retry-After')
                if retry_after_hdr:
                    try:
                        retry_after_sec = float(retry_after_hdr)
                    except (ValueError, TypeError):
                        retry_after_sec = None

            # Don't retry if maximum attempts reached or error is permanent
            if attempts > max_retries or (not is_retryable_exc and not is_retryable_status and not is_429):
                log_api_event(service_name, endpoint, "FAILED", duration_ms=duration_ms, error=e, retry_attempt=attempts - 1)
                raise

            # If 429 with long Retry-After (> 2.0s), fail fast to avoid blocking the worker thread
            if is_429:
                if retry_after_sec and retry_after_sec > 2.0:
                    log_api_event(service_name, endpoint, "RATE_LIMITED", duration_ms=duration_ms, error=e, retry_attempt=attempts - 1)
                    raise
                wait_time = retry_after_sec if retry_after_sec is not None else delay
            else:
                wait_time = delay

            log_api_event(service_name, endpoint, "RETRYING", duration_ms=duration_ms, 
                          error=f"Attempt {attempts} failed: {e}. Waiting {wait_time:.2f}s...", retry_attempt=attempts)
            time.sleep(wait_time)
            delay *= backoff_factor
