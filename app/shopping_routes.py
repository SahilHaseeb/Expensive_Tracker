from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.shopping_service import search_shopping_deals

shopping_bp = Blueprint('shopping', __name__)

@shopping_bp.route('/shopping')
@login_required
def index():
    """Render the Live Shopping Price Comparison and Deals Finder page"""
    query = request.args.get('q', 'wireless earbuds').strip()
    sort_by = request.args.get('sort', 'price_low').strip()
    user_currency = getattr(current_user, 'currency', None) or '₹'
    
    results = search_shopping_deals(query, sort_by=sort_by, currency=user_currency)
    return render_template('shopping.html', results=results, current_query=query, current_sort=sort_by, user_currency=user_currency)


@shopping_bp.route('/api/shopping/search', methods=['GET'])
@login_required
def api_search():
    """AJAX API endpoint for live price search"""
    query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'price_low').strip()
    user_currency = getattr(current_user, 'currency', None) or '₹'
    
    results = search_shopping_deals(query, sort_by=sort_by, currency=user_currency)
    return jsonify(results)
