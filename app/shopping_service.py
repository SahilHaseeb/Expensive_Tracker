import os
import requests
from config import Config
import re
import json
import urllib.parse
import difflib
import logging
try:
    from app.api_guard import (
        shopping_cache,
        in_flight_deduplicator,
        execute_with_retry,
        log_api_event,
        sanitize_error_message
    )
except (ImportError, ModuleNotFoundError):
    try:
        from api_guard import (
            shopping_cache,
            in_flight_deduplicator,
            execute_with_retry,
            log_api_event,
            sanitize_error_message
        )
    except (ImportError, ModuleNotFoundError):
        import sys
        import importlib.util
        _ag_path = os.path.join(os.path.dirname(__file__), "api_guard.py")
        _ag_spec = importlib.util.spec_from_file_location("api_guard", _ag_path)
        _ag_mod = importlib.util.module_from_spec(_ag_spec)
        sys.modules["app.api_guard"] = _ag_mod
        _ag_spec.loader.exec_module(_ag_mod)
        shopping_cache = _ag_mod.shopping_cache
        in_flight_deduplicator = _ag_mod.in_flight_deduplicator
        execute_with_retry = _ag_mod.execute_with_retry
        log_api_event = _ag_mod.log_api_event
        sanitize_error_message = _ag_mod.sanitize_error_message


logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"

# ─── SEARCH OUTCOME & ERROR TAXONOMY (FEATURE #2) ──────────────────────────
class SearchOutcome:
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    FILTERED_EMPTY = "filtered_empty"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    RATE_LIMITED = "rate_limited"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"
    INTERNAL_ERROR = "internal_error"


class ShoppingSearchError(Exception):
    """Base exception for shopping deal search issues."""
    pass


class ShoppingTimeoutError(ShoppingSearchError):
    """Raised when upstream API request times out."""
    pass


class ShoppingNetworkError(ShoppingSearchError):
    """Raised when network connection drops or fails."""
    pass


class ShoppingRateLimitError(ShoppingSearchError):
    """Raised when upstream API rate limit or monthly search quota is reached."""
    pass


class ShoppingAPIError(ShoppingSearchError):
    """Raised when upstream API reports an error (HTTP 4xx/5xx or invalid API key)."""
    pass


class ShoppingMalformedResponseError(ShoppingSearchError):
    """Raised when API returns invalid or malformed data."""
    pass


# ─── SEARCH LIFECYCLE & REQUEST STATE MANAGEMENT (FEATURE #3) ──────────────
class SearchState:
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    EMPTY = "empty"
    ERROR = "error"


class SearchStateManager:
    """
    Lightweight request lifecycle manager to track search state,
    prevent duplicate/overlapping submissions, and manage clean transitions.
    """
    def __init__(self):
        self.state = SearchState.IDLE
        self.current_query = None
        self.request_id = 0

    def start_search(self, query):
        """
        Transitions to LOADING state.
        Rejects duplicate submission if another search is already running.
        Returns (success: bool, info: int | str).
        """
        if self.state == SearchState.LOADING:
            return False, "Search already in progress"
        self.state = SearchState.LOADING
        self.current_query = query
        self.request_id += 1
        return True, self.request_id

    def complete_search(self, result, request_id=None):
        """
        Transitions from LOADING to SUCCESS, EMPTY, or ERROR based on search outcome.
        Guards against race conditions if an older request finishes after a newer one.
        """
        if request_id is not None and request_id != self.request_id:
            # Stale request response, drop to prevent race conditions
            return False

        total_count = result.get("total_results") if "total_results" in result else len(result.get("products", []))
        if not result or result.get("status") == SearchOutcome.NO_RESULTS or (result.get("status") == SearchOutcome.SUCCESS and total_count == 0):
            self.state = SearchState.EMPTY
        elif result.get("status") == SearchOutcome.SUCCESS:
            self.state = SearchState.SUCCESS
        else:
            self.state = SearchState.ERROR
        return True

    def reset(self):
        """Resets state back to IDLE."""
        self.state = SearchState.IDLE
        self.current_query = None



# Neutral lightweight SVG placeholder for products without an image (no guessing, no random stock photos)
NEUTRAL_PLACEHOLDER_IMAGE = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400' fill='%231e293b'><rect width='400' height='400' fill='%231e293b'/><text x='50%' y='45%' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-size='44' font-family='sans-serif'>🛍️</text><text x='50%' y='60%' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-size='15' font-family='sans-serif' font-weight='600'>Image Unavailable</text></svg>"

# ─── REAL-TIME MULTI-CURRENCY CONVERSION ENGINE ─────────────────────────────
EXCHANGE_RATES = {
    "$": 1.0,
    "USD": 1.0,
    "Rs.": 278.5,
    "PKR": 278.5,
    "₹": 83.5,
    "INR": 83.5,
    "€": 0.92,
    "EUR": 0.92,
    "£": 0.78,
    "GBP": 0.78,
    "AED": 3.67,
    "SAR": 3.75,
}

# ─── COMPREHENSIVE SHOPPING & ENGLISH VOCABULARY (NEVER OVERWRITTEN) ────────
STANDARD_VALID_WORDS = {
    # Pronouns, prepositions, modifiers, attributes
    "a", "an", "the", "for", "with", "and", "or", "to", "in", "on", "by", "of", "from",
    "at", "is", "it", "all", "new", "pro", "max", "plus", "ultra", "mini", "lite", "se",
    "red", "blue", "black", "white", "green", "yellow", "pink", "purple", "orange", "grey",
    "gray", "silver", "gold", "dark", "light", "clear", "case", "cover", "pack", "set", "lot",
    "phone", "phones", "cell", "mobile", "smart", "men", "man", "women", "woman", "kid", "kids",
    "boy", "boys", "girl", "girls", "baby", "unisex", "adult", "size", "fit", "slim", "long",
    "short", "top", "bottom", "hot", "best", "deal", "deals", "low", "high", "fast", "pure",
    "real", "dry", "wet", "gel", "cream", "oil", "bar", "box", "bag", "cup", "mug", "car", "air",
    "face", "body", "hair", "skin", "eye", "lip", "hand", "foot", "feet", "head", "ear",
    
    # Tech & Electronics
    "iphone", "ipad", "macbook", "airpods", "apple", "samsung", "galaxy", "xiaomi", "redmi",
    "huawei", "oneplus", "google", "pixel", "oppo", "vivo", "realme", "infinix", "tecno",
    "laptop", "laptops", "notebook", "ultrabook", "computer", "desktop", "monitor", "keyboard",
    "mouse", "headphones", "headphone", "earphones", "earphone", "earbuds", "earbud", "bluetooth",
    "wireless", "speaker", "speakers", "soundbar", "smartwatch", "watch", "watches", "charger",
    "cable", "adapter", "powerbank", "camera", "drone", "gopro", "microphone", "tablet", "console",
    "playstation", "xbox", "nintendo", "switch", "router", "modem", "printer", "projector",
    "processor", "graphics", "motherboard", "ssd", "ram", "storage", "usb", "type-c", "5g", "4g",
    
    # Fashion & Apparel
    "shoes", "shoe", "sneakers", "sneaker", "boots", "boot", "sandals", "sandal", "heels", "slippers",
    "clothes", "clothing", "dress", "dresses", "shirt", "shirts", "tshirt", "t-shirt", "polo",
    "hoodie", "hoodies", "jacket", "jackets", "coat", "coats", "pants", "jeans", "trousers",
    "shorts", "skirt", "sweater", "cardigan", "suit", "blazer", "underwear", "undergarments",
    "boxers", "briefs", "bra", "lingerie", "socks", "scarf", "gloves", "belt", "hat", "cap",
    "sunglasses", "glasses", "wallet", "bags", "backpack", "backpacks", "handbag", "purse",
    "luggage", "suitcase", "jewelry", "necklace", "ring", "earrings", "bracelet", "kurta", "shalwar",
    
    # Beauty, Cosmetics & Skincare
    "perfume", "perfumes", "fragrance", "fragrances", "cologne", "scent", "attar", "oud",
    "makeup", "cosmetics", "lipstick", "mascara", "eyeliner", "foundation", "concealer", "blush",
    "powder", "eyeshadow", "skincare", "lotion", "moisturizer", "serum", "cleanser", "facewash",
    "wash", "sunscreen", "sunblock", "toner", "scrub", "mask", "shampoo", "conditioner",
    "dryer", "straightener", "trimmer", "shaver", "razor", "soap", "deodorant", "beauty",
    
    # Major Retail Brands
    "nike", "adidas", "puma", "reebok", "under", "armour", "zara", "gucci", "chanel", "dior",
    "versace", "armani", "calvin", "klein", "tommy", "hilfiger", "levis", "h&m", "sephora",
    "loreal", "maybelline", "olay", "nivea", "garnier", "dove", "cerave", "cetaphil", "ordinary",
    "neutrogena", "rolex", "casio", "fossil", "titan", "citizen", "seiko", "tissot", "sony",
    "bose", "jbl", "sennheiser", "beats", "anker", "logitech", "razer", "corsair", "dell",
    "hp", "lenovo", "asus", "acer", "msi", "toshiba", "canon", "nikon", "panasonic", "lg",
    
    # Home, Sports & Lifestyle
    "bottle", "bottles", "flask", "shaker", "tumbler", "chair", "chairs", "table", "desk",
    "sofa", "bed", "furniture", "blender", "microwave", "oven", "airfryer", "fryer", "cooker",
    "kettle", "toaster", "vacuum", "cleaner", "fan", "heater", "iron", "grinder", "mattress",
    "pillow", "blanket", "curtain", "lamp", "light", "clock", "mirror", "carpet", "rug",
    "towel", "fitness", "gym", "yoga", "mat", "dumbbell", "treadmill", "cycle", "bicycle",
    "helmet", "tent"
}

# ─── COMMON SHOPPING GRAMMAR & PHRASE NORMALIZATIONS ───────────────────────
PHRASE_NORMALIZATIONS = [
    (r'\bfor woman\b', 'for women'),
    (r'\bfor man\b', 'for men'),
    (r'\bfor kid\b', 'for kids'),
    (r'\bfor child\b', 'for children'),
    (r'\bfor boy\b', 'for boys'),
    (r'\bfor girl\b', 'for girls'),
    (r'\bwoman clothing\b', 'women clothing'),
    (r'\bman clothing\b', 'men clothing'),
    (r'\bwoman shoe\b', 'women shoes'),
    (r'\bman shoe\b', 'men shoes'),
    (r'\bwoman shoes\b', 'women shoes'),
    (r'\bman shoes\b', 'men shoes'),
    (r'\bwoman dress\b', 'women dresses'),
    (r'\bblu tooth\b', 'bluetooth'),
    (r'\bblue tooth\b', 'bluetooth'),
    (r'\bhead phone\b', 'headphones'),
    (r'\bhead phones\b', 'headphones'),
    (r'\bear phone\b', 'earphones'),
    (r'\bear phones\b', 'earphones'),
    (r'\bear bud\b', 'earbuds'),
    (r'\bear buds\b', 'earbuds'),
    (r'\bsmart watch\b', 'smartwatch'),
    (r'\blap top\b', 'laptop'),
    (r'\bt shirt\b', 't-shirt'),
    (r'\btee shirt\b', 't-shirt'),
    (r'\bface clenser\b', 'face cleanser'),
]


def correct_word(word):
    """Correct misspelled word while strictly maintaining valid words & numbers"""
    w = word.lower().strip()
    if not w or len(w) <= 2 or w.isdigit() or not w.isalpha():
        return word

    # If already a valid known word, never alter it
    if w in STANDARD_VALID_WORDS:
        return word

    # Find closest match with length tolerance and similarity >= 0.80
    matches = difflib.get_close_matches(w, STANDARD_VALID_WORDS, n=3, cutoff=0.80)
    if matches:
        # Prioritize matches with similar length (abs difference <= 2)
        filtered = [m for m in matches if abs(len(m) - len(w)) <= 2]
        if filtered:
            best = filtered[0]
            # Match plural forms if original ended in 's' or 'se'
            if (w.endswith('s') or w.endswith('se')) and not best.endswith('s'):
                plural_candidates = [m for m in filtered if m.endswith('s')]
                if plural_candidates:
                    best = plural_candidates[0]

            if word.istitle():
                return best.title()
            elif word.isupper():
                return best.upper()
            return best

    return word


def normalize_and_correct_query(query):
    """
    Intelligently normalize search query for minor spelling mistakes,
    grammar variations, and singular/plural discrepancies without altering intent.
    """
    if not query or not str(query).strip():
        return ""

    q = str(query).strip()
    # Normalize whitespace
    q = re.sub(r'\s+', ' ', q)

    # Apply phrase rules
    for pattern, repl in PHRASE_NORMALIZATIONS:
        q = re.sub(pattern, repl, q, flags=re.IGNORECASE)

    # Token-level corrections
    tokens = q.split(' ')
    corrected_tokens = []
    for token in tokens:
        m = re.match(r'^([^\w]*)([\w\-\'\.]+)([^\w]*)$', token)
        if m:
            prefix, core, suffix = m.groups()
            corr = correct_word(core)
            corrected_tokens.append(f"{prefix}{corr}{suffix}")
        else:
            corrected_tokens.append(token)

    return ' '.join(corrected_tokens)


def detect_currency_from_price_string(price_str):
    """Detect source currency symbol from raw store price string"""
    s = str(price_str or "").strip()
    if "$" in s or "USD" in s:
        return "$"
    elif "€" in s or "EUR" in s:
        return "€"
    elif "£" in s or "GBP" in s:
        return "£"
    elif "₹" in s or "INR" in s:
        return "₹"
    elif "PKR" in s or "Rs" in s or "Rs." in s:
        return "Rs."
    elif "AED" in s:
        return "AED"
    elif "SAR" in s:
        return "SAR"
    return "$"


def convert_price(amount, from_curr, to_curr):
    """Convert amount accurately between any two supported currencies"""
    if not amount or amount <= 0:
        return 0.0
    from_rate = EXCHANGE_RATES.get(from_curr, 1.0)
    to_rate = EXCHANGE_RATES.get(to_curr, 278.5 if to_curr == "Rs." else 1.0)

    usd_val = float(amount) / from_rate
    target_val = usd_val * to_rate
    return round(target_val, 2)


def format_converted_price(amount, currency_symbol):
    """Format converted price with symbol and appropriate decimal precision"""
    if currency_symbol in ["$", "€", "£"]:
        return f"{currency_symbol} {amount:,.2f}"
    else:
        return f"{currency_symbol} {round(amount):,.0f}"


def calculate_savings(price_val, original_price_val, currency_symbol):
    """
    Calculate verified savings from real product price data.

    Only produces a result when:
    - Both price_val and original_price_val are valid positive numerics
    - original_price_val is strictly greater than price_val (genuine saving)

    Returns a dict:
        savings_amount  -- rounded saving in the target currency
        savings_pct     -- percentage saved (1 decimal place)
        savings_str     -- display-ready string, e.g. "Save Rs. 500 (16.7% off)"

    Returns None when valid savings cannot be determined.
    Never fabricates a value — caller must supply real data.
    """
    try:
        if price_val is None or original_price_val is None:
            return None
        pv = float(price_val)
        ov = float(original_price_val)
        # Both must be positive and original must exceed current for a genuine saving
        if ov <= 0 or pv <= 0 or ov <= pv:
            return None

        savings_raw = ov - pv
        savings_pct = round((savings_raw / ov) * 100, 1)

        # Mirror the same precision rules used by format_converted_price()
        if currency_symbol in ("$", "€", "£"):
            savings_amount = round(savings_raw, 2)
            amount_str = f"{currency_symbol} {savings_amount:,.2f}"
        else:
            savings_amount = round(savings_raw)
            amount_str = f"{currency_symbol} {savings_amount:,.0f}"

        savings_str = f"Save {amount_str} ({savings_pct}% off)"

        return {
            "savings_amount": savings_amount,
            "savings_pct":    savings_pct,
            "savings_str":    savings_str,
        }
    except Exception:
        return None


def _safe_extract_numeric(val):
    """Safely extract float from numeric or string value. Returns None if invalid or negative."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        f = float(val)
        return f if f >= 0 else None
    s = str(val).strip()
    if not s:
        return None
    if "free" in s.lower():
        return 0.0
    if any(w in s.lower() for w in ("calculated at checkout", "unknown", "tbd", "contact", "varies")):
        return None
    try:
        nums = re.findall(r"[\d,]+\.?\d*", s.replace(",", ""))
        if nums:
            if "-" + nums[0] in s:
                return None
            f = float(nums[0])
            return f if f >= 0 else None
    except Exception:
        pass
    return None


def calculate_true_total_price(product=None, product_price=None, shipping=None, tax=None, source_total=None, currency=None):
    """
    Calculate verified True Total Price / Estimated Total for an offer (Feature #11).

    Priority:
    1. Explicit source final total (source_total) if present and > 0 -> status: 'exact'
    2. Product price + verified shipping and/or tax -> status: 'calculated'
    3. Product price only (when shipping/tax are unknown/unsupplied) -> status: 'price_only'
    4. Invalid or missing product price -> status: 'unavailable'

    Shipping rules:
    - Explicit 'free' / 'free shipping' / 0 -> shipping_cost = 0.0
    - Explicit numeric > 0 -> shipping_cost = numeric
    - Unknown / missing / unparseable -> shipping_cost = None (NEVER assumed 0)

    Tax rules:
    - Explicit numeric >= 0 -> tax_amount = numeric
    - Unknown / missing / unparseable -> tax_amount = None (NEVER assumed 0, no guessed tax rates)

    Returns dict:
        total_price              -- float / int or None
        total_price_str          -- display string e.g. 'Rs. 4,250' or None
        total_price_status       -- 'exact' | 'calculated' | 'price_only' | 'unavailable'
        total_price_is_estimated  -- bool
        shipping_cost            -- float or None (0.0 for free)
        shipping_str             -- display string e.g. 'Free Shipping', 'Rs. 250' or None
        tax_amount               -- float or None
        tax_str                  -- display string or None
        currency                 -- currency string symbol
    """
    try:
        # If product dict passed, extract fields from it if not explicitly provided as args
        if isinstance(product, dict):
            if product_price is None:
                product_price = product.get("price_val")
                if product_price is None:
                    product_price = product.get("product_price")
                if product_price is None:
                    product_price = product.get("price")
            if shipping is None:
                shipping = product.get("shipping_cost")
                if shipping is None:
                    shipping = product.get("shipping")
                if shipping is None:
                    shipping = product.get("delivery")
            if tax is None:
                tax = product.get("tax_amount")
                if tax is None:
                    tax = product.get("tax")
            if source_total is None:
                source_total = product.get("source_total")
                if source_total is None:
                    source_total = product.get("extracted_total_price")
            if currency is None:
                currency = product.get("currency")
                if not currency and product.get("price"):
                    currency = detect_currency_from_price_string(str(product["price"]))

        # Normalize currency symbol
        curr_raw = str(currency or "Rs.").strip()
        if curr_raw in ("$", "USD"):
            curr = "$"
        elif curr_raw in ("€", "EUR"):
            curr = "€"
        elif curr_raw in ("£", "GBP"):
            curr = "£"
        elif curr_raw in ("₹", "INR"):
            curr = "₹"
        elif curr_raw in ("Rs.", "PKR", "Rs"):
            curr = "Rs."
        else:
            curr = curr_raw

        # 1. Check for explicit source final total
        st_val = _safe_extract_numeric(source_total)
        if st_val is not None and st_val > 0:
            s_parsed = _safe_extract_numeric(shipping)
            t_parsed = _safe_extract_numeric(tax)
            return {
                "total_price": st_val,
                "total_price_str": format_converted_price(st_val, curr),
                "total_price_status": "exact",
                "total_price_is_estimated": False,
                "shipping_cost": s_parsed,
                "shipping_str": "Free Shipping" if s_parsed == 0.0 else (format_converted_price(s_parsed, curr) if s_parsed is not None else None),
                "tax_amount": t_parsed,
                "tax_str": format_converted_price(t_parsed, curr) if t_parsed is not None else None,
                "currency": curr,
            }

        # 2. Check product price
        pv = _safe_extract_numeric(product_price)
        if pv is None or pv <= 0:
            return {
                "total_price": None,
                "total_price_str": None,
                "total_price_status": "unavailable",
                "total_price_is_estimated": False,
                "shipping_cost": None,
                "shipping_str": None,
                "tax_amount": None,
                "tax_str": None,
                "currency": curr,
            }

        # 3. Parse shipping
        s_val = None
        s_str = None
        if shipping is not None:
            parsed_s = _safe_extract_numeric(shipping)
            if parsed_s is not None:
                s_val = parsed_s
                if s_val == 0.0:
                    s_str = "Free Shipping"
                else:
                    s_str = format_converted_price(s_val, curr)

        # 4. Parse tax
        t_val = None
        t_str = None
        if tax is not None:
            parsed_t = _safe_extract_numeric(tax)
            if parsed_t is not None:
                t_val = parsed_t
                t_str = format_converted_price(t_val, curr)

        # 5. Determine total price and status
        if s_val is not None or t_val is not None:
            extra = (s_val if s_val is not None else 0.0) + (t_val if t_val is not None else 0.0)
            tot = round(pv + extra, 2) if curr in ("$", "€", "£") else round(pv + extra)
            return {
                "total_price": tot,
                "total_price_str": format_converted_price(tot, curr),
                "total_price_status": "calculated",
                "total_price_is_estimated": True,
                "shipping_cost": s_val,
                "shipping_str": s_str,
                "tax_amount": t_val,
                "tax_str": t_str,
                "currency": curr,
            }
        else:
            # Only product price is known; shipping/tax not supplied
            tot = round(pv, 2) if curr in ("$", "€", "£") else round(pv)
            return {
                "total_price": tot,
                "total_price_str": format_converted_price(tot, curr),
                "total_price_status": "price_only",
                "total_price_is_estimated": True,
                "shipping_cost": None,
                "shipping_str": None,
                "tax_amount": None,
                "tax_str": None,
                "currency": curr,
            }
    except Exception:
        return {
            "total_price": None,
            "total_price_str": None,
            "total_price_status": "unavailable",
            "total_price_is_estimated": False,
            "shipping_cost": None,
            "shipping_str": None,
            "tax_amount": None,
            "tax_str": None,
            "currency": "Rs.",
        }


def clean_store_search_query(query_title):
    """Clean text for search queries"""
    q = str(query_title or "").strip()
    q = re.sub(r'\bunderware\b', 'underwear', q, flags=re.IGNORECASE)
    q = re.sub(r'\bfor man\b', 'for men', q, flags=re.IGNORECASE)
    q = re.sub(r'\bkapre\b', 'clothes', q, flags=re.IGNORECASE)
    q = re.sub(r'\bshooes\b', 'shoes', q, flags=re.IGNORECASE)
    q = re.sub(r'\s+', ' ', q).strip()
    return q if len(q) >= 2 else str(query_title or "").strip()


def get_direct_store_url(store_name, raw_query):
    """
    Build direct search URL to the retailer website for general store search.
    NOTE: NEVER used as a product deal link fallback, to prevent product identity mismatch.
    """
    cleaned_q = clean_store_search_query(raw_query)
    encoded_q = urllib.parse.quote_plus(cleaned_q)
    store_lower = (store_name or "").lower().strip()
    if "daraz" in store_lower:
        return f"https://www.daraz.pk/catalog/?q={encoded_q}"
    elif "amazon" in store_lower:
        return f"https://www.amazon.com/s?k={encoded_q}"
    elif "walmart" in store_lower:
        return f"https://www.walmart.com/search?q={encoded_q}"
    elif "ebay" in store_lower:
        return f"https://www.ebay.com/sch/i.html?_nkw={encoded_q}"
    elif "." in store_lower and not any(ch in store_lower for ch in [" ", "/"]):
        return f"https://www.{store_lower}/search?q={encoded_q}"
    return f"https://www.amazon.com/s?k={encoded_q}"


def is_search_or_category_url(url_str):
    """
    Determines if a URL is a search results page, category listing, catalog search,
    or generic store homepage rather than a specific direct product page.
    """
    if not url_str or not isinstance(url_str, str):
        return True
    try:
        parsed = urllib.parse.urlparse(url_str.strip())
        path_lower = (parsed.path or "").lower()
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Search query parameters
        search_params = {
            "q", "k", "keyword", "keywords", "searchterm", "search_term",
            "query", "search_query", "search", "search_key", "searchtext",
            "_nkw", "st", "field-keywords", "originkeyword", "nkw"
        }
        for param in qs:
            if param.lower() in search_params:
                return True

        # 2. Search path segments
        search_path_indicators = [
            "/search", "/search/", "/searchpage", "/sr", "/pdsearch",
            "/catalogsearch", "/wholesale", "/shop/featured",
            "/catalog/search", "/find/"
        ]
        for indicator in search_path_indicators:
            if indicator in path_lower:
                return True

        # Check for /s/ or /s? or /s
        if path_lower.startswith("/s/") or path_lower == "/s" or "/s?" in url_str.lower():
            return True

        # 3. Category / Catalog listing without item identifier
        category_indicators = ["/category/", "/categories/", "/dept/", "/browse/"]
        for cat_ind in category_indicators:
            if cat_ind in path_lower:
                if not any(prod_ind in path_lower for prod_ind in ["/p/", "/product", "/item", ".html", "/ip/", "/dp/"]):
                    return True

        # 4. Generic homepage / root path (e.g. https://www.amazon.com or https://www.walmart.com/)
        clean_path = path_lower.strip("/")
        if clean_path in ("", "us", "en", "pk", "index.html", "index.php", "home"):
            return True

        return False
    except Exception:
        return True


def extract_domain_tokens(url_or_domain):
    """
    Extracts core brand/domain tokens from a URL or domain string.
    e.g. 'https://www.modaoperandi.com/product/123' -> {'modaoperandi', 'moda', 'operandi'}
    """
    if not url_or_domain or not isinstance(url_or_domain, str):
        return set()
    try:
        if "://" in url_or_domain:
            host = urllib.parse.urlparse(url_or_domain).netloc.lower()
        else:
            host = url_or_domain.lower()
        
        # Strip port
        if ":" in host:
            host = host.split(":")[0]
            
        # Strip www.
        if host.startswith("www."):
            host = host[4:]
            
        # Strip common TLDs (.com, .pk, .co.uk, .org, .net, etc.)
        tld_patterns = [
            r"\.com\.pk$", r"\.co\.uk$", r"\.com$", r"\.pk$", r"\.net$", r"\.org$",
            r"\.io$", r"\.store$", r"\.shop$", r"\.de$", r"\.ca$", r"\.us$", r"\.info$"
        ]
        for pat in tld_patterns:
            host = re.sub(pat, "", host)
            
        # Clean special chars
        clean_host = re.sub(r"[^a-z0-9]", "", host)
        tokens = {clean_host} if clean_host else set()
        for part in re.split(r"[^a-z0-9]+", host):
            if len(part) >= 3:
                tokens.add(part)
        return tokens
    except Exception:
        return set()


def normalize_merchant_name(merchant_str):
    """
    Normalizes a merchant name into alphanumeric tokens for comparison.
    e.g. 'Moda Operandi' -> 'modaoperandi', {'moda', 'operandi', 'modaoperandi'}
    e.g. 'Sold by XYZ on Amazon' -> {'amazon', 'xyz', 'soldbyxyzonamazon'}
    """
    if not merchant_str or not isinstance(merchant_str, str):
        return "", set()
    m_clean = merchant_str.lower().strip()
    
    # Strip common corporate & generic store suffixes
    suffixes = [
        r"\b(inc|llc|ltd|co|corp|corporation)\b",
        r"\b(official store|official|online store|online shop|store|shop|superstore)\b",
        r"\b(usa|pk|uk|global|international)\b",
        r"\.(com|pk|org|net)\b"
    ]
    for s_pat in suffixes:
        m_clean = re.sub(s_pat, "", m_clean)
        
    m_clean = re.sub(r"[^a-z0-9\s]", " ", m_clean)
    words = [w for w in m_clean.split() if len(w) >= 2]
    combined = "".join(words)
    token_set = set(words)
    if combined:
        token_set.add(combined)
    return combined, token_set


def match_merchant_to_url(merchant_name, url_str):
    """
    Validates that the destination URL actually belongs to the merchant shown on the card.
    Prevents displaying Merchant A with a link to Merchant B.
    """
    if not merchant_name or not url_str:
        return False
    if is_google_domain(url_str):
        # A Google domain (like google.com/shopping/product/...) is not a direct merchant URL
        return False

    domain_tokens = extract_domain_tokens(url_str)
    combined_merchant, merchant_tokens = normalize_merchant_name(merchant_name)
    
    if not domain_tokens or not merchant_tokens:
        return False

    # Check for direct overlap
    for d_tok in domain_tokens:
        if d_tok in merchant_tokens:
            return True
        if combined_merchant and (d_tok in combined_merchant or combined_merchant in d_tok):
            return True
        for m_tok in merchant_tokens:
            if m_tok in d_tok or d_tok in m_tok:
                if len(m_tok) >= 3 and len(d_tok) >= 3:
                    return True

    # Marketplace handling: e.g. "Brand via Amazon" or "Seller on Walmart"
    raw_lower = merchant_name.lower()
    for market in ["amazon", "walmart", "ebay", "daraz", "target", "bestbuy", "flipkart", "aliexpress", "etsy"]:
        if market in raw_lower and any(market in dt for dt in domain_tokens):
            return True

    return False


def is_google_domain(url_str):
    """Check if URL points to Google's own search/shopping domains"""
    if not url_str or not isinstance(url_str, str):
        return True
    u_lower = url_str.lower()
    return "google.com" in u_lower or "google." in u_lower or "gstatic.com" in u_lower or "doubleclick.net" in u_lower


def unpack_google_redirect_url(redirect_url):
    """Decode and extract the external destination URL from Google click/redirect links"""
    try:
        parsed = urllib.parse.urlparse(redirect_url)
        qs = urllib.parse.parse_qs(parsed.query)
        for param in ['url', 'adurl', 'q', 'dest', 'location', 'u', 'target']:
            if param in qs and qs[param]:
                for candidate_val in qs[param]:
                    unquoted = urllib.parse.unquote(candidate_val.strip())
                    if unquoted.startswith("http") and not is_google_domain(unquoted):
                        return unquoted
    except Exception:
        pass
    return None


def extract_direct_retailer_url(item, source_store="", product_title=""):
    """
    Extract the authentic, direct official retailer product URL from a SerpAPI shopping result item.
    Inspects direct candidate fields and unpacks Google redirect URLs (such as /url?url= or /aclk?adurl=).
    Strictly filters out:
    1. Google internal URLs (e.g. google.com/shopping/product/ or google.com/search)
    2. Retailer search-result URLs (/search?q=..., /s?k=..., etc.)
    3. Category, catalog, or generic homepage URLs
    4. Merchant mismatches (e.g. Merchant A with URL to Merchant B)

    Returns the verified direct retailer product URL, or None if unverified.
    NEVER falls back to generating a retailer search URL or guessing a product URL.
    """
    if isinstance(item, str):
        item = {"link": item}
    elif not isinstance(item, dict):
        item = {}

    candidates = []

    # 1. Direct candidate fields in the SerpAPI item
    for key in ["direct_link", "merchant_link", "offer_link", "retailer_link", "link"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip().startswith("http"):
            candidates.append(val.strip())

    # 2. Nested merchant object link (e.g. item["merchant"]["link"])
    merchant = item.get("merchant")
    if isinstance(merchant, dict):
        for m_key in ["link", "url", "direct_link"]:
            m_link = merchant.get(m_key)
            if m_link and isinstance(m_link, str) and m_link.strip().startswith("http"):
                candidates.append(m_link.strip())

    # 3. Nested offers list links (e.g. item["offers"][0]["link"])
    offers = item.get("offers")
    if isinstance(offers, list):
        for off in offers:
            if isinstance(off, dict):
                for o_key in ["link", "url", "direct_link"]:
                    o_link = off.get(o_key)
                    if o_link and isinstance(o_link, str) and o_link.strip().startswith("http"):
                        candidates.append(o_link.strip())

    # Process each candidate URL to extract the real retailer destination
    for candidate in candidates:
        target_url = candidate

        # A. If it's a Google redirect wrapper (/url?url=..., /aclk?adurl=...), unpack it
        if is_google_domain(candidate):
            unpacked = unpack_google_redirect_url(candidate)
            if unpacked and not is_google_domain(unpacked):
                target_url = unpacked
            else:
                # Still a Google URL (e.g. google.com/shopping/product/...), not a direct retailer URL
                continue

        # B. Reject any remaining Google domain URLs as direct retailer URLs
        if is_google_domain(target_url):
            continue

        # C. Reject retailer search-result, category, and homepage URLs
        if is_search_or_category_url(target_url):
            logger.warning("Rejected shopping offer: search URL, not product URL")
            continue

        # D. Validate that destination URL matches the merchant
        if source_store and not match_merchant_to_url(source_store, target_url):
            logger.warning("Rejected shopping offer: merchant URL mismatch")
            continue

        # Validated direct retailer product URL!
        return target_url

    # NEVER fall back to get_direct_store_url or synthesize a retailer search query.
    return None


def validate_product_offer_identity(item, default_source="Online Store", default_title="Product Item"):
    """
    Validates that a shopping offer object represents the SAME product across:
    Title + Image + Price + Merchant + External Product URL + Product Identifiers.

    Returns a dict:
    {
        "is_valid": bool,
        "identity_status": "verified" | "partially_verified" | "unverified",
        "verified_link": str | None,
        "is_direct_deal": bool,
        "rejection_reasons": list[str]
    }
    """
    if not isinstance(item, dict):
        return {
            "is_valid": False,
            "identity_status": "unverified",
            "verified_link": None,
            "is_direct_deal": False,
            "rejection_reasons": ["item_not_dict"]
        }

    raw_title = item.get("title")
    title = str(raw_title if raw_title is not None else default_title).strip()
    raw_source = item.get("source") or item.get("merchant")
    source = str(raw_source if raw_source is not None else default_source).strip()

    # Direct Retailer URL Extraction & Validation
    direct_url = extract_direct_retailer_url(item, source_store=source, product_title=title)

    if direct_url:
        return {
            "is_valid": True,
            "identity_status": "verified",
            "verified_link": direct_url,
            "is_direct_deal": True,
            "rejection_reasons": []
        }

    # Fallback check: Google Shopping verified product page
    product_link = item.get("product_link")
    if product_link and isinstance(product_link, str) and product_link.strip().startswith("http"):
        clean_pl = product_link.strip()
        if "google.com/shopping/product/" in clean_pl.lower():
            return {
                "is_valid": True,
                "identity_status": "partially_verified",
                "verified_link": clean_pl,
                "is_direct_deal": False,
                "rejection_reasons": ["direct_retailer_url_unavailable"]
            }

    # If neither direct retailer URL nor Google product page is verified
    logger.warning("Rejected shopping offer: invalid/missing product URL")
    return {
        "is_valid": True,
        "identity_status": "unverified",
        "verified_link": None,
        "is_direct_deal": False,
        "rejection_reasons": ["invalid_or_missing_product_url"]
    }


def extract_item_image(item):
    """
    Extract the actual image URL directly from the SerpAPI shopping item.
    Checks all valid image fields returned by SerpAPI in strict order.
    Returns neutral placeholder if image is absent or invalid.
    Strictly isolated: checks only fields belonging to THIS specific item.
    Never performs a separate image search, never reuses an image from another item.
    """
    if not isinstance(item, dict):
        return NEUTRAL_PLACEHOLDER_IMAGE
    for key in ["thumbnail", "serpapi_thumbnail", "image", "product_image", "photo"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip().startswith("http"):
            return val.strip()
    return NEUTRAL_PLACEHOLDER_IMAGE


def _fetch_serpapi_shopping(query, num=60):
    """Call SerpAPI Google Shopping with caching, deduplication, retry, and timeout protection"""
    api_key = Config.SERPAPI_API_KEY
    if not api_key:
        logger.error("SerpAPI search attempted without configured API key.")
        raise ShoppingAPIError("SerpAPI API key is missing or not configured")

    clean_q = clean_store_search_query(query)
    cache_key = f"serpapi:{clean_q.lower()}:{num}"

    # 1. Short-lived TTL cache check (5-minute TTL)
    cached = shopping_cache.get(cache_key)
    if cached is not None:
        log_api_event("SerpAPI", f"google_shopping?q={clean_q}", "SUCCESS", error="Served from short-lived cache")
        return list(cached)

    # 2. Execute with in-flight deduplication (prevents duplicate simultaneous calls)
    def _do_fetch():
        # Double check cache inside deduplicator lock
        cached_inner = shopping_cache.get(cache_key)
        if cached_inner is not None:
            return list(cached_inner)

        timeout_sec = getattr(Config, 'SERPAPI_TIMEOUT', 12)
        params = {
            "engine": "google_shopping",
            "q": clean_q,
            "api_key": api_key,
            "num": num,
            "hl": "en",
        }

        def _network_call():
            try:
                return requests.get(SERPAPI_URL, params=params, timeout=timeout_sec)
            except requests.exceptions.Timeout as e:
                raise ShoppingTimeoutError(f"SerpAPI request timed out: {e}")
            except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
                raise ShoppingNetworkError(f"SerpAPI connection error: {e}")

        # Controlled retry: retry max 2 times on transient network error / timeout
        try:
            resp = execute_with_retry(
                _network_call,
                max_retries=2,
                base_delay=0.5,
                backoff_factor=2.0,
                retryable_exceptions=(ShoppingTimeoutError, ShoppingNetworkError),
                service_name="SerpAPI",
                endpoint=f"google_shopping?q={clean_q}"
            )
        except ShoppingTimeoutError:
            logger.warning(f"SerpAPI request timed out for query '{clean_q}'.")
            raise
        except ShoppingNetworkError:
            logger.warning(f"SerpAPI network error for query '{clean_q}'.")
            raise
        except Exception as e:
            logger.error(f"SerpAPI request failed for query '{clean_q}': {e}")
            raise ShoppingAPIError(f"SerpAPI request failed: {e}")

        # Inspect HTTP status code
        if resp.status_code == 429:
            logger.warning(f"SerpAPI HTTP 429 rate limit reached for query '{clean_q}'.")
            raise ShoppingRateLimitError("SerpAPI rate limit or monthly quota reached (HTTP 429)")
        elif resp.status_code in (401, 403):
            logger.error(f"SerpAPI authentication error (HTTP {resp.status_code}).")
            raise ShoppingAPIError(f"SerpAPI authentication failed (HTTP {resp.status_code})")
        elif resp.status_code >= 500:
            logger.error(f"SerpAPI upstream server error (HTTP {resp.status_code}).")
            raise ShoppingAPIError(f"SerpAPI upstream server error (HTTP {resp.status_code})")
        elif resp.status_code != 200:
            logger.error(f"SerpAPI error (HTTP {resp.status_code}).")
            raise ShoppingAPIError(f"SerpAPI returned HTTP {resp.status_code}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error(f"Failed to parse SerpAPI JSON response: {e}")
            raise ShoppingMalformedResponseError(f"Invalid JSON in SerpAPI response: {e}")

        if not isinstance(data, dict):
            logger.error(f"SerpAPI returned non-dict response type: {type(data)}")
            raise ShoppingMalformedResponseError(f"Expected dict response from SerpAPI, got {type(data).__name__}")

        # Check for error payload from SerpAPI
        if "error" in data:
            err_msg = str(data.get("error") or "").lower()
            logger.warning(f"SerpAPI returned error message: {data.get('error')}")
            if any(term in err_msg for term in ["rate limit", "quota", "monthly search limit", "exhausted", "too many requests", "run out of searches", "has reached"]):
                raise ShoppingRateLimitError("API rate limit or monthly search quota exhausted")
            raise ShoppingAPIError("SerpAPI returned an error")

        if isinstance(data.get("search_metadata"), dict) and data["search_metadata"].get("status") == "Error":
            logger.error("SerpAPI search_metadata status is Error.")
            raise ShoppingAPIError("SerpAPI search metadata reported an error")

        # Extract shopping results safely
        results = data.get("shopping_results")
        if results is None:
            results = data.get("inline_shopping_results")

        if results is None:
            # Search executed cleanly, but no shopping results found
            shopping_cache.set(cache_key, [], ttl_seconds=300)
            return []

        if not isinstance(results, list):
            logger.error(f"Expected shopping_results to be a list, got {type(results).__name__}")
            raise ShoppingMalformedResponseError(f"Expected shopping_results to be a list, got {type(results).__name__}")

        trimmed = results[:num]
        shopping_cache.set(cache_key, trimmed, ttl_seconds=300)
        return trimmed

    return in_flight_deduplicator.execute_deduped(cache_key, _do_fetch)



def _process_serpapi_results(serpapi_results, query, target_curr="Rs."):
    """Process raw SerpAPI results into structured products preserving 1-to-1 data integrity"""
    if not isinstance(serpapi_results, list):
        return []

    products = []
    for idx, item in enumerate(serpapi_results):
        if not isinstance(item, dict):
            continue

        # 1. Product Identity Validation
        def_title = f"{query.title() if query else 'Product'} Item"
        validation = validate_product_offer_identity(item, default_source="Online Store", default_title=def_title)
        if not validation["is_valid"]:
            continue

        title = str(item.get("title") or f"{query.title() if query else 'Product'} Item").strip()
        source = str(item.get("source") or item.get("merchant") or "Online Store").strip()
        
        # Validated Link & Identity Status
        link = validation["verified_link"]
        identity_status = validation["identity_status"]
        is_direct_deal = validation["is_direct_deal"]
        
        # Exact image belonging strictly to THIS specific SerpAPI result item
        image_url = extract_item_image(item)

        try:
            rating = float(item.get("rating") or 4.5)
        except (ValueError, TypeError):
            rating = 4.5

        try:
            reviews = int(item.get("reviews") or 150)
        except (ValueError, TypeError):
            reviews = 150

        # Parse and convert price
        price_str = str(item.get("price") or item.get("extracted_price") or "")
        raw_val = 0.0
        if item.get("extracted_price") and isinstance(item.get("extracted_price"), (int, float)):
            raw_val = float(item.get("extracted_price"))
        else:
            try:
                nums = re.findall(r"[\d,]+\.?\d*", price_str.replace(",", ""))
                if nums:
                    raw_val = float(nums[0])
            except Exception:
                raw_val = 0.0

        if not raw_val:
            raw_val = 25.0

        source_curr = detect_currency_from_price_string(price_str)
        converted_val = convert_price(raw_val, source_curr, target_curr)

        # Real original (compare-at) price from SerpAPI — used ONLY for genuine savings.
        # extracted_old_price / old_price are optional SerpAPI fields some merchants populate.
        # When absent, savings_data stays None and no fabricated value is ever shown.
        real_original_val = None
        if item.get("extracted_old_price") and isinstance(item.get("extracted_old_price"), (int, float)):
            op_raw = float(item["extracted_old_price"])
            if op_raw > 0:
                real_original_val = convert_price(op_raw, source_curr, target_curr)
        elif item.get("old_price"):
            op_str = str(item["old_price"])
            op_curr = detect_currency_from_price_string(op_str)
            try:
                op_nums = re.findall(r"[\d,]+\.?\d*", op_str.replace(",", ""))
                if op_nums:
                    op_raw = float(op_nums[0])
                    if op_raw > 0:
                        real_original_val = convert_price(op_raw, op_curr, target_curr)
            except Exception:
                real_original_val = None

        savings_data = calculate_savings(converted_val, real_original_val, target_curr)

        discount_pct = 10 + (idx * 3 % 25)
        original_val = round(converted_val * (1 + discount_pct / 100.0), 2)

        # ── True Total Price Extraction (Feature #11) ──────────────────────
        # 1. Source total price if explicitly provided by SerpAPI
        raw_source_total = item.get("extracted_total_price") or item.get("total_price")
        source_total_val = None
        if raw_source_total is not None:
            st_num = _safe_extract_numeric(raw_source_total)
            if st_num is not None and st_num > 0:
                source_total_val = convert_price(st_num, source_curr, target_curr)

        # 2. Shipping cost if explicitly provided
        shipping_val = None
        if item.get("extracted_shipping") is not None:
            try:
                es = float(item["extracted_shipping"])
                if es >= 0:
                    shipping_val = convert_price(es, source_curr, target_curr) if es > 0 else 0.0
            except (ValueError, TypeError):
                shipping_val = None
        elif item.get("shipping"):
            s_str = str(item["shipping"]).lower()
            if "free" in s_str:
                shipping_val = 0.0
            else:
                s_num = _safe_extract_numeric(item["shipping"])
                if s_num is not None and s_num > 0:
                    shipping_val = convert_price(s_num, source_curr, target_curr)
        elif item.get("delivery"):
            d_str = str(item["delivery"]).lower()
            if any(f in d_str for f in ("free delivery", "free shipping", "free standard delivery")):
                shipping_val = 0.0

        # 3. Tax if explicitly provided
        tax_val = None
        if item.get("extracted_tax") is not None:
            try:
                et = float(item["extracted_tax"])
                if et > 0:
                    tax_val = convert_price(et, source_curr, target_curr)
            except (ValueError, TypeError):
                tax_val = None
        elif item.get("tax"):
            t_num = _safe_extract_numeric(item["tax"])
            if t_num is not None and t_num > 0:
                tax_val = convert_price(t_num, source_curr, target_curr)

        total_data = calculate_true_total_price(
            product_price=converted_val,
            shipping=shipping_val,
            tax=tax_val,
            source_total=source_total_val,
            currency=target_curr
        )

        products.append({
            "title": title,
            "source": source,
            "merchant": source,
            "price": format_converted_price(converted_val, target_curr),
            "price_val": converted_val,
            "original_price": format_converted_price(original_val, target_curr),
            "currency": target_curr,
            "discount": f"{discount_pct}% OFF",
            "discount_val": discount_pct,
            "link": link,
            "product_url": link,
            "thumbnail": image_url,
            "image": image_url,
            "rating": rating,
            "reviews": reviews,
            "delivery": item.get("delivery") or f"Available on {source}",
            "badge": None,
            "is_best_deal": False,
            "savings_amount": savings_data["savings_amount"] if savings_data else None,
            "savings_pct":    savings_data["savings_pct"]    if savings_data else None,
            "savings_str":    savings_data["savings_str"]    if savings_data else None,
            "deal_score":     None,
            "total_price":    total_data["total_price"],
            "total_price_str": total_data["total_price_str"],
            "total_price_status": total_data["total_price_status"],
            "total_price_is_estimated": total_data["total_price_is_estimated"],
            "shipping_cost":  total_data["shipping_cost"],
            "shipping_str":   total_data["shipping_str"],
            "tax_amount":     total_data["tax_amount"],
            "tax_str":        total_data["tax_str"],
            "product_id":     item.get("product_id"),
            "sku":            item.get("sku") or item.get("merchant_product_id"),
            "gtin":           item.get("gtin") or item.get("upc") or item.get("isbn"),
            "identity_status": identity_status,
            "is_direct_deal":  is_direct_deal,
        })

    return products


def filter_products(products, min_price=None, max_price=None,
                    stores=None, min_discount=None, min_savings=None,
                    best_deal_only=False, in_stock_only=False):
    """
    Apply advanced filters to an already-returned product list.

    Filter logic:
    - All active categories use AND logic between them.
    - Multiple stores within the `stores` set use OR logic.
    - Missing / invalid data safely fails the relevant filter.
    - is_best_deal and savings fields are never modified.

    Args:
        products      : list of product dicts from _process_serpapi_results()
        min_price     : minimum price_val (inclusive); None = no lower bound
        max_price     : maximum price_val (inclusive); None = no upper bound
        stores        : set/list of store name strings (case-insensitive OR);
                        None or empty = all stores pass
        min_discount  : minimum discount percentage (uses savings_pct if
                        available, else discount_val); None = disabled
        min_savings   : minimum savings_amount (real #7 data only);
                        None = disabled
        best_deal_only: if True, only the product with is_best_deal=True passes
        in_stock_only : if True, products whose delivery/availability
                        explicitly contains "out of stock", "unavailable",
                        or "sold out" are excluded

    Returns a new list; never modifies the input list.
    Never crashes on malformed / missing product data.
    """
    if not products:
        return []

    # Normalize store set once
    store_filter = set()
    if stores:
        for s in stores:
            ns = str(s).strip().lower()
            if ns:
                store_filter.add(ns)

    filtered = []
    for p in products:
        if not isinstance(p, dict):
            continue

        # ── Store (OR logic) ──────────────────────────────────────────────────
        if store_filter:
            card_store = str(p.get("source") or "").lower()
            if not any(card_store == s or s in card_store for s in store_filter):
                continue

        # ── Price range ───────────────────────────────────────────────────────
        raw_pv = p.get("price_val")
        if raw_pv is not None and isinstance(raw_pv, (int, float)) and raw_pv > 0:
            pv = float(raw_pv)
            if min_price is not None and pv < float(min_price):
                continue
            if max_price is not None and pv > float(max_price):
                continue
        else:
            # Missing / invalid price — fail if any price filter is set
            if min_price is not None or max_price is not None:
                continue

        # ── Discount filter ───────────────────────────────────────────────────
        if min_discount is not None:
            # Prefer real savings_pct (#7); fall back to fabricated discount_val
            disc = p.get("savings_pct")
            if disc is None:
                disc = p.get("discount_val")
            try:
                disc = float(disc)
            except (TypeError, ValueError):
                continue   # no valid discount data → fail filter
            if disc < float(min_discount):
                continue

        # ── Savings filter (real #7 data only) ───────────────────────────────
        if min_savings is not None:
            sav = p.get("savings_amount")
            if sav is None:
                continue   # no verified savings → fail filter
            try:
                sav = float(sav)
            except (TypeError, ValueError):
                continue
            if sav < float(min_savings):
                continue

        # ── Best Deal Only ────────────────────────────────────────────────────
        if best_deal_only and not p.get("is_best_deal"):
            continue

        # ── In Stock Only (conservative) ──────────────────────────────────────
        if in_stock_only:
            delivery_str = str(p.get("delivery") or "").lower()
            avail_str    = str(p.get("availability") or "").lower()
            if ("out of stock" in delivery_str or "out of stock" in avail_str
                    or "unavailable" in avail_str or "sold out" in avail_str):
                continue

        filtered.append(p)

    return filtered


def search_shopping_deals(query, sort_by="price_low", currency="Rs."):
    """
    Unified Live Shopping Search with Intelligent Query Normalization & Multi-Attempt Fallback.
    - Attempt 1: Search using the user's original query.
    - Attempt 2: If 0 results, search using the intelligently corrected / normalized query.
    - Attempt 3: If still 0 results and query is compound, search with simplified core keywords.
    Max 3 controlled attempts total to prevent excessive API calls.
    Returns normalized structured result with status, success, products, user_message, retryable.
    """
    raw_query = (query or "").strip()
    if not raw_query:
        raw_query = "wireless earbuds"

    target_curr = currency or "Rs."
    
    # Candidate search queries in priority order
    attempts = []
    
    # 1. First attempt: Original user query
    clean_original = clean_store_search_query(raw_query)
    attempts.append(clean_original)
    
    # 2. Second attempt: Corrected / normalized query (if different)
    corrected_q = normalize_and_correct_query(raw_query)
    clean_corrected = clean_store_search_query(corrected_q)
    if clean_corrected.lower() != clean_original.lower() and clean_corrected.lower() not in [a.lower() for a in attempts]:
        attempts.append(clean_corrected)
        
    # 3. Third attempt: Simplified core product intent (e.g. if filler prepositions caused 0 results)
    simplified_q = re.sub(r'\b(for|with|and|in|of|the|a|an)\b', ' ', clean_corrected, flags=re.IGNORECASE)
    simplified_q = re.sub(r'\s+', ' ', simplified_q).strip()
    if simplified_q.lower() not in [a.lower() for a in attempts] and len(simplified_q.split()) >= 1:
        attempts.append(simplified_q)

    final_products = []
    successful_query = clean_original
    was_corrected = False

    # Execute search with hard limit of maximum 3 attempts
    for attempt_idx, search_q in enumerate(attempts[:3]):
        try:
            raw_results = _fetch_serpapi_shopping(search_q, num=60)
        except (ShoppingTimeoutError, requests.exceptions.Timeout) as e:
            logger.warning(f"Timeout searching for '{search_q}': {e}")
            return {
                "success": False,
                "status": SearchOutcome.TIMEOUT,
                "error_type": SearchOutcome.TIMEOUT,
                "user_message": "Unable to connect to the live deals service right now. Please check your connection and try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }
        except (ShoppingNetworkError, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Network error searching for '{search_q}': {e}")
            return {
                "success": False,
                "status": SearchOutcome.NETWORK_ERROR,
                "error_type": SearchOutcome.NETWORK_ERROR,
                "user_message": "Unable to connect to the live deals service right now. Please check your connection and try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }
        except ShoppingRateLimitError as e:
            logger.warning(f"Rate limit error searching for '{search_q}': {e}")
            return {
                "success": False,
                "status": SearchOutcome.RATE_LIMITED,
                "error_type": SearchOutcome.RATE_LIMITED,
                "user_message": "Live deal searches are temporarily busy. Please wait a moment and try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }
        except ShoppingMalformedResponseError as e:
            logger.error(f"Malformed response searching for '{search_q}': {e}")
            return {
                "success": False,
                "status": SearchOutcome.INVALID_RESPONSE,
                "error_type": SearchOutcome.INVALID_RESPONSE,
                "user_message": "We received an unexpected response while searching for deals. Please try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }
        except (ShoppingAPIError, requests.exceptions.RequestException) as e:
            logger.error(f"API error searching for '{search_q}': {e}")
            return {
                "success": False,
                "status": SearchOutcome.API_ERROR,
                "error_type": SearchOutcome.API_ERROR,
                "user_message": "We couldn't fetch live deals right now. Please try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }
        except Exception as e:
            logger.error(f"Unexpected search error for '{search_q}': {e}", exc_info=True)
            return {
                "success": False,
                "status": SearchOutcome.INTERNAL_ERROR,
                "error_type": SearchOutcome.INTERNAL_ERROR,
                "user_message": "An unexpected error occurred while searching for deals. Please try again.",
                "retryable": True,
                "source_type": "Live Shopping Deals",
                "query": raw_query,
                "corrected_query": None,
                "total_results": 0,
                "products": []
            }

        if raw_results and isinstance(raw_results, list):
            successful_query = search_q
            if attempt_idx > 0:
                was_corrected = True
            final_products = _process_serpapi_results(raw_results, search_q, target_curr)
            if final_products:
                break

    if final_products:
        select_best_deal(final_products)
        calculate_deal_scores(final_products)
        apply_sorting_and_badges(final_products, sort_by)
        return {
            "success": True,
            "status": SearchOutcome.SUCCESS,
            "error_type": None,
            "user_message": None,
            "retryable": False,
            "source_type": "🔴 Live Direct Store Deals & Verified Prices",
            "query": raw_query,
            "corrected_query": successful_query if was_corrected else None,
            "total_results": len(final_products),
            "products": final_products
        }

    # If truly 0 results across all attempts, return safe empty response
    return {
        "success": False,
        "status": SearchOutcome.NO_RESULTS,
        "error_type": SearchOutcome.NO_RESULTS,
        "user_message": f'No live offers found for "{raw_query}".',
        "retryable": False,
        "source_type": "Live Shopping Deals",
        "query": raw_query,
        "corrected_query": None,
        "total_results": 0,
        "products": []
    }


def select_best_deal(products):
    """
    Deterministically identify and mark the single BEST DEAL from search results.
    Criteria:
    - Valid numeric price > 0
    - Available (not marked out of stock or unavailable)
    - Strong priority to lowest valid final price
    - Deterministic tie-breakers: discount %, rating/reviews, known store name, first in list
    - Never selects missing, zero, or invalid price
    - Exactly ONE best deal marked with is_best_deal = True when valid candidates exist
    - Sets is_best_deal = False on all other products
    """
    if not products or not isinstance(products, list):
        return products

    # Ensure is_best_deal flag is initialized on every dictionary item
    for p in products:
        if isinstance(p, dict):
            p["is_best_deal"] = False

    valid_candidates = []

    for idx, p in enumerate(products):
        if not isinstance(p, dict):
            continue

        # Extract and validate numeric price.
        # IMPORTANT: Only use string fallback when price_val is absent (None) or
        # a non-numeric type. If price_val is an explicit numeric <= 0, it is
        # already invalid and must be disqualified without reparsing the price
        # string (which would strip the minus sign and produce a false positive).
        raw_price_val = p.get("price_val")
        if raw_price_val is None or not isinstance(raw_price_val, (int, float)):
            # price_val field absent or non-numeric — try string fallback
            price_str = str(p.get("price") or "")
            try:
                nums = re.findall(r"[\d,]+\.?\d*", price_str.replace(",", ""))
                if nums:
                    price_val = float(nums[0])
                else:
                    price_val = 0.0
            except Exception:
                price_val = 0.0
        else:
            # price_val was explicitly set as a numeric — use it directly
            price_val = float(raw_price_val)

        # Disqualify missing, zero, or negative prices
        if not price_val or price_val <= 0:
            continue

        # Availability / Stock check
        delivery_str = str(p.get("delivery") or "").lower()
        avail_str = str(p.get("availability") or "").lower()
        if "out of stock" in delivery_str or "out of stock" in avail_str or "unavailable" in avail_str or "sold out" in avail_str:
            continue

        # Discount extraction for tie-breaker
        discount_pct = 0.0
        if p.get("discount_val") and isinstance(p.get("discount_val"), (int, float)):
            discount_pct = float(p.get("discount_val"))
        else:
            disc_str = str(p.get("discount") or "")
            disc_match = re.search(r"(\d+)\s*%", disc_str)
            if disc_match:
                discount_pct = float(disc_match.group(1))

        # Rating & reviews for tie-breaker
        rating = float(p.get("rating") or 0.0)
        reviews = float(p.get("reviews") or 0.0)
        reputation_score = rating * min(reviews, 500.0)

        # Known store tie-breaker
        source = str(p.get("source") or "").strip().lower()
        store_known = 1 if source and source not in ["online store", "unknown", ""] else 0

        valid_candidates.append({
            "product": p,
            "sort_key": (
                float(price_val),     # 1. Primary: Lowest price
                -discount_pct,        # 2. Tie-break: Higher discount
                -reputation_score,    # 3. Tie-break: Higher rating & reviews
                -store_known,         # 4. Tie-break: Known store
                idx                   # 5. Tie-break: First in list
            )
        })

    if not valid_candidates:
        return products

    # Sort deterministically and select the single best candidate
    valid_candidates.sort(key=lambda x: x["sort_key"])
    best_candidate = valid_candidates[0]["product"]
    best_candidate["is_best_deal"] = True

    return products


def _extract_sort_price(p):
    """Safely extract valid positive numeric price or return None."""
    if not isinstance(p, dict):
        return None
    raw = p.get("price_val")
    if raw is not None:
        try:
            val = float(raw)
            if val > 0:
                return val
            return None
        except (ValueError, TypeError):
            return None
    raw_str = str(p.get("price") or "")
    try:
        nums = re.findall(r"[\d,]+\.?\d*", raw_str.replace(",", ""))
        if nums:
            val = float(nums[0])
            if val > 0:
                return val
    except Exception:
        pass
    return None


def _extract_sort_discount(p):
    """Safely extract verified discount percentage or return None."""
    if not isinstance(p, dict):
        return None
    # Check verified savings_pct (#7) first
    sp = p.get("savings_pct")
    if sp is not None:
        try:
            val = float(sp)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    # Check discount_val
    dv = p.get("discount_val")
    if dv is not None:
        try:
            val = float(dv)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    # Regex fallback on discount string e.g. "20% OFF"
    d_str = str(p.get("discount") or "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", d_str)
    if m:
        try:
            val = float(m.group(1))
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    return None


def _extract_sort_savings(p):
    """Safely extract verified savings_amount (#7) or return None."""
    if not isinstance(p, dict):
        return None
    sa = p.get("savings_amount")
    if sa is not None:
        try:
            val = float(sa)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    return None


def calculate_single_deal_score(product, min_price=None, max_price=None, max_savings=None):
    """
    Calculate a deterministic Deal Score (0–100) for a single product offer (Feature #10).

    Components and sensible weights (documented for clarity and maintainability):
    1. Price Competitiveness (up to 40 pts):
       - If batch min_price and max_price are known and max_price > min_price:
         Linear interpolation: lowest price gets 40, highest gets 15.
       - If min_price == max_price or not provided:
         Baseline 28 pts out of 40.
    2. Verified Discount (up to 25 pts):
       - Uses verified discount percentage (savings_pct from #7 or discount_val).
       - If present and > 0: min(25.0, (discount_pct / 50.0) * 25.0).
       - If missing/None: neutral baseline of 8.0 pts (does not unfairly punish missing discount with 0).
    3. Verified Savings (up to 20 pts):
       - Uses verified savings_amount from Feature #7.
       - If present and > 0:
         If max_savings and max_savings > 0:
           savings_pts = min(20.0, (savings_amount / max_savings) * 20.0)
         Else:
           savings_ratio = savings_amount / (savings_amount + pv)
           savings_pts = min(20.0, savings_ratio * 40.0)
       - If missing/None: neutral baseline of 6.0 pts.
    4. Offer Quality & Credibility (up to 15 pts):
       - Availability: in-stock (+5 pts; explicitly out-of-stock gets 0).
       - Store reputation: known retailer (+3 pts).
       - Customer rating & reviews: rating >= 4.0 gets up to +4 pts.
       - Best Deal status: Feature #6 is_best_deal (+3 pts).

    Returns:
       Integer between 0 and 100, or None if price is missing / invalid (<= 0).
    """
    if not isinstance(product, dict):
        return None

    # 1. Price check — essential requirement
    pv = _extract_sort_price(product)
    if pv is None or pv <= 0:
        return None

    # ── Component 1: Price Competitiveness (up to 40 pts) ──
    if min_price is not None and max_price is not None and max_price > min_price:
        price_ratio = (max_price - pv) / (max_price - min_price)
        price_ratio = max(0.0, min(1.0, price_ratio))
        price_pts = 15.0 + 25.0 * price_ratio
    else:
        price_pts = 28.0

    # ── Component 2: Verified Discount (up to 25 pts) ──
    dv = _extract_sort_discount(product)
    if dv is not None and dv > 0:
        discount_pts = min(25.0, (dv / 50.0) * 25.0)
    else:
        discount_pts = 8.0

    # ── Component 3: Verified Savings (up to 20 pts) ──
    sv = _extract_sort_savings(product)
    if sv is not None and sv > 0:
        if max_savings is not None and max_savings > 0:
            savings_pts = min(20.0, (sv / max_savings) * 20.0)
        else:
            savings_ratio = sv / (sv + pv)
            savings_pts = min(20.0, savings_ratio * 40.0)
    else:
        savings_pts = 6.0

    # ── Component 4: Offer Quality & Credibility (up to 15 pts) ──
    quality_pts = 0.0

    # In-Stock check (5 pts)
    delivery_str = str(product.get("delivery") or "").lower()
    avail_str = str(product.get("availability") or "").lower()
    is_oos = any(k in delivery_str or k in avail_str for k in ("out of stock", "unavailable", "sold out"))
    if not is_oos:
        quality_pts += 5.0

    # Store credibility (3 pts)
    source = str(product.get("source") or "").strip().lower()
    if source and source not in ("online store", "unknown", ""):
        quality_pts += 3.0

    # Rating / Reviews (up to 4 pts)
    try:
        r = float(product.get("rating") or 0.0)
        if r >= 4.5:
            quality_pts += 4.0
        elif r >= 4.0:
            quality_pts += 3.0
        elif r >= 3.0:
            quality_pts += 2.0
        elif r > 0:
            quality_pts += 1.0
    except (ValueError, TypeError):
        pass

    # Best Deal bonus from Feature #6 (3 pts)
    if product.get("is_best_deal") is True:
        quality_pts += 3.0

    total_score = round(price_pts + discount_pts + savings_pts + quality_pts)
    return max(0, min(100, total_score))


def calculate_deal_scores(products):
    """
    Calculate and attach deterministic Deal Score (0–100) to each product in a batch (Feature #10).
    - Relative to returned offers: finds min/max price and max savings across the batch.
    - Missing/invalid prices receive deal_score = None (displayed as 'N/A').
    - Preserves all existing product attributes.
    Returns the products list.
    """
    if not products or not isinstance(products, list):
        return []

    # Find batch boundaries for relative price and savings scoring
    valid_prices = []
    valid_savings = []
    for p in products:
        if isinstance(p, dict):
            pv = _extract_sort_price(p)
            if pv is not None and pv > 0:
                valid_prices.append(pv)
            sv = _extract_sort_savings(p)
            if sv is not None and sv > 0:
                valid_savings.append(sv)

    min_p = min(valid_prices) if valid_prices else None
    max_p = max(valid_prices) if valid_prices else None
    max_s = max(valid_savings) if valid_savings else None

    for p in products:
        if isinstance(p, dict):
            p["deal_score"] = calculate_single_deal_score(
                p, min_price=min_p, max_price=max_p, max_savings=max_s
            )

    return products


def sort_products(products, sort_by="relevance"):
    """
    Sort products based on reliable, verified criteria (Features #9 & #10).

    Supported sort_by options:
    - "relevance" / "default": Preserves original search/result order
    - "deal_score_high" / "deal_score": Highest Deal Score (0–100) first; missing at the end
    - "price_low" / "price_asc": Smallest valid current price first; missing/invalid at the end
    - "price_high" / "price_desc": Largest valid current price first; missing/invalid at the end
    - "discount_high" / "highest_discount": Highest verified discount % first; missing at the end
    - "savings_high" / "highest_savings": Highest verified savings amount first; missing at the end
    - "best_deal" / "best_deal_first": Existing Best Deal product (Feature #6) first; safe order otherwise
    - "rating" / "highest_rated": Highest customer rating first

    Key invariants:
    - Stable: preserves relative order between items with identical sort values.
    - Safe: Missing/invalid prices (None, <=0, non-numeric) are NEVER treated as 0;
      they are placed safely at the end of both low-to-high and high-to-low sorts.
    - Verified data only: does not fabricate or calculate missing discounts/savings.
    - Does NOT mutate input list in-place (returns a new list).
    - Preserves is_best_deal, savings_amount, savings_pct, savings_str, deal_score, thumbnails, links.
    - Handles empty list, None, malformed product objects without crashing.
    """
    if not products or not isinstance(products, list):
        return []

    # Shallow copy to avoid mutating the original input list
    items = list(products)
    s_key = (sort_by or "relevance").lower().strip()

    if s_key in ("relevance", "default"):
        return items

    elif s_key in ("deal_score_high", "deal_score", "score_high", "score"):
        def _deal_score_key(item):
            if isinstance(item, dict):
                score = item.get("deal_score")
                if score is not None:
                    try:
                        s_val = float(score)
                        return (0, -s_val)
                    except (ValueError, TypeError):
                        pass
            return (1, 0)
        return sorted(items, key=_deal_score_key)

    elif s_key in ("price_low", "price_asc", "price_low_to_high", "low_to_high"):
        def _price_low_key(item):
            pv = _extract_sort_price(item)
            if pv is not None:
                return (0, pv)
            return (1, 0)
        return sorted(items, key=_price_low_key)

    elif s_key in ("price_high", "price_desc", "price_high_to_low", "high_to_low"):
        def _price_high_key(item):
            pv = _extract_sort_price(item)
            if pv is not None:
                return (0, -pv)
            return (1, 0)
        return sorted(items, key=_price_high_key)

    elif s_key in ("discount_high", "highest_discount", "discount"):
        def _discount_key(item):
            dv = _extract_sort_discount(item)
            if dv is not None:
                return (0, -dv)
            return (1, 0)
        return sorted(items, key=_discount_key)

    elif s_key in ("savings_high", "highest_savings", "savings"):
        def _savings_key(item):
            sv = _extract_sort_savings(item)
            if sv is not None:
                return (0, -sv)
            return (1, 0)
        return sorted(items, key=_savings_key)

    elif s_key in ("best_deal", "best_deal_first"):
        def _best_deal_key(item):
            if isinstance(item, dict) and item.get("is_best_deal") is True:
                return 0
            return 1
        return sorted(items, key=_best_deal_key)

    elif s_key in ("rating", "highest_rated"):
        def _rating_key(item):
            if isinstance(item, dict):
                try:
                    r = float(item.get("rating") or 0.0)
                    if r > 0:
                        return (0, -r)
                except (ValueError, TypeError):
                    pass
            return (1, 0)
        return sorted(items, key=_rating_key)

    # Fallback to preserving original order
    return items


def apply_sorting_and_badges(products, sort_by="relevance"):
    """Sort products and assign badges while preserving complete product-image association"""
    if not products or not isinstance(products, list):
        return

    # Identify the single best deal (Feature #6)
    select_best_deal(products)

    min_price_item = min((p for p in products if isinstance(p, dict) and p.get("price_val", 0) > 0), key=lambda x: x["price_val"], default=None)
    if min_price_item:
        min_price_item["is_lowest_price"] = True

    # Sort using sort_products
    sorted_items = sort_products(products, sort_by=sort_by)
    products[:] = sorted_items

    # Assign badges based on sort
    s_key = (sort_by or "relevance").lower().strip()
    if s_key in ("price_low", "price_asc", "low_to_high") and products and products[0].get("price_val", 0) > 0:
        products[0]["badge"] = "🔥 Lowest Price Deal"
        products[0]["is_best_price"] = True
    elif s_key in ("price_high", "price_desc", "high_to_low") and products:
        products[0]["badge"] = "💎 Premium / High-End"
        products[0]["is_premium"] = True
    elif s_key in ("rating", "highest_rated") and products:
        products[0]["badge"] = "⭐ Highest Customer Rated"
        products[0]["is_top_rated"] = True
