from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.shopping_service import search_shopping_deals

shopping_bp = Blueprint('shopping', __name__)

@shopping_bp.route('/shopping')
@login_required
def index():
    """Render the Live Shopping Price Comparison and Deals Finder page"""
    query = request.args.get('q', 'wireless earbuds').strip()
    sort_by = request.args.get('sort', 'price_low').strip()
    
    results = search_shopping_deals(query, sort_by=sort_by)
    return render_template('shopping.html', results=results, current_query=query, current_sort=sort_by)


@shopping_bp.route('/api/shopping/search', methods=['GET'])
@login_required
def api_search():
    """AJAX API endpoint for live price search"""
    query = request.args.get('q', '').strip()
    sort_by = request.args.get('sort', 'price_low').strip()
    
    results = search_shopping_deals(query, sort_by=sort_by)
    return jsonify(results)
