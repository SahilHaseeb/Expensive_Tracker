from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.shopping_service import search_shopping_deals
from app.api_guard import rate_limited, sanitize_error_message
from config import Config
import logging

logger = logging.getLogger(__name__)

shopping_bp = Blueprint('shopping', __name__)

@shopping_bp.route('/shopping')
@login_required
@rate_limited(limit=Config.RATE_LIMIT_SHOPPING, window=60, action='shopping_page', is_json=False)
def index():
    """Render the Live Shopping Price Comparison and Deals Finder page"""
    query = request.args.get('q', 'wireless earbuds').strip()
    sort_by = request.args.get('sort', 'relevance').strip()
    user_currency = getattr(current_user, 'currency', None) or '₹'
    
    try:
        results = search_shopping_deals(query, sort_by=sort_by, currency=user_currency)
    except Exception as e:
        logger.error(f"Shopping index route unexpected error: {e}", exc_info=True)
        results = {
            "success": False,
            "status": "internal_error",
            "error_type": "internal_error",
            "user_message": "An unexpected error occurred while searching for deals. Please try again.",
            "retryable": True,
            "products": [],
            "total_results": 0,
            "query": query,
            "corrected_query": None,
            "source_type": "Live Shopping Deals"
        }
    return render_template('shopping.html', results=results, current_query=query, current_sort=sort_by, user_currency=user_currency)


@shopping_bp.route('/api/shopping/search', methods=['GET'])
@login_required
@rate_limited(limit=Config.RATE_LIMIT_SHOPPING, window=60, action='shopping_search', is_json=True)
def api_search():
    """AJAX API endpoint for live price search"""
    query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'relevance').strip()
    user_currency = getattr(current_user, 'currency', None) or '₹'
    
    try:
        results = search_shopping_deals(query, sort_by=sort_by, currency=user_currency)
        status_code = 200
        headers = {}
        if results.get("status") in ["timeout", "network_error"]:
            status_code = 504
        elif results.get("status") == "rate_limited":
            status_code = 429
            headers["Retry-After"] = "30"
        elif results.get("status") in ["api_error", "internal_error", "invalid_response"]:
            status_code = 502
        return jsonify(results), status_code, headers
    except Exception as e:
        safe_err = sanitize_error_message(e)
        logger.error(f"Shopping API search route error: {safe_err}", exc_info=True)
        return jsonify({
            "success": False,
            "status": "internal_error",
            "error_type": "internal_error",
            "user_message": "An unexpected error occurred while searching for deals. Please try again.",
            "retryable": True,
            "products": [],
            "total_results": 0,
            "query": query,
            "corrected_query": None,
            "source_type": "Live Shopping Deals"
        }), 500

