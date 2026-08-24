from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Expense, Budget, Subscription, User
from app.receipt_scanner import scan_receipt_image
from app.analytics import calculate_financial_health_score
from app.db_sync import save_db_backup
from datetime import datetime, date, timedelta
import re
import pandas as pd

features_bp = Blueprint('features', __name__)

# ========== 1. RECEIPT SCANNER API ==========
@features_bp.route('/api/scan-receipt', methods=['POST'])
@login_required
def api_scan_receipt():
    """Upload receipt image and return extracted expense details"""
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No receipt image uploaded."}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Selected file is empty."}), 400

    try:
        image_bytes = file.read()
        mime_type = file.content_type or "image/jpeg"
        result = scan_receipt_image(image_bytes, mime_type=mime_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ========== 2. VOICE TO EXPENSE NLP PARSER ==========
@features_bp.route('/api/parse-voice-expense', methods=['POST'])
@login_required
def api_parse_voice():
    """Parse spoken voice transcript into structured expense fields"""
    data = request.get_json() or {}
    text = data.get('text', '').strip()

    if not text:
        return jsonify({"status": "error", "message": "Voice text is empty."}), 400

    # Heuristic & Regex extraction for amount, category, and note
    # Example: "spent 1200 on petrol", "500 for lunch at KFC"
    amount = None
    category = "Other"
    note = text

    # Extract numerical amount
    amounts_found = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", text.replace(',', ''))
    if amounts_found:
        amount = float(amounts_found[0])

    lower_text = text.lower()
    if any(w in lower_text for w in ['food', 'lunch', 'dinner', 'breakfast', 'pizza', 'burger', 'kfc', 'mcdonald', 'coffee', 'tea', 'cafe', 'restaurant', 'biryani', 'grocery', 'supermarket']):
        category = "Food"
    elif any(w in lower_text for w in ['fuel', 'petrol', 'diesel', 'uber', 'careem', 'taxi', 'bus', 'train', 'flight', 'ticket', 'transport', 'car', 'bike', 'parking']):
        category = "Transport"
    elif any(w in lower_text for w in ['rent', 'house', 'apartment', 'electricity', 'gas', 'water', 'wifi', 'utility', 'bill']):
        category = "Rent"
    elif any(w in lower_text for w in ['movie', 'netflix', 'game', 'gaming', 'cinema', 'party', 'concert', 'entertainment']):
        category = "Entertainment"
    elif any(w in lower_text for w in ['shopping', 'clothes', 'shoes', 'shirt', 'dress', 'mall', 'amazon', 'daraz', 'watch']):
        category = "Shopping"
    elif any(w in lower_text for w in ['doctor', 'medicine', 'hospital', 'pharmacy', 'health', 'clinic', 'dentist']):
        category = "Healthcare"
    elif any(w in lower_text for w in ['book', 'course', 'fees', 'school', 'college', 'university', 'tuition', 'education']):
        category = "Education"

    return jsonify({
        "status": "success",
        "amount": amount or 0.0,
        "category": category,
        "date": datetime.today().strftime('%Y-%m-%d'),
        "note": note[:100]
    })


@features_bp.route('/api/transcribe-voice-audio', methods=['POST'])
@login_required
def api_transcribe_voice_audio():
    """Transcribe and parse raw audio file from Firefox/MediaRecorder"""
    if 'audio' not in request.files:
        return jsonify({"status": "error", "message": "No audio data received"}), 400

    audio_file = request.files['audio']
    audio_bytes = audio_file.read()
    mime_type = audio_file.mimetype or 'audio/webm'

    try:
        import google.generativeai as genai
        import json
        api_key = Config.GEMINI_API_KEY
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = """
            You are a financial voice assistant. Listen to this user audio recording of an expense.
            Extract the numerical amount, expense category, and note description.
            Valid categories: 'Food', 'Transport', 'Rent', 'Entertainment', 'Shopping', 'Healthcare', 'Education', 'Other'.
            
            Return ONLY a valid JSON object matching this schema:
            {
                "amount": 1500.0,
                "category": "Food",
                "note": "dinner with friends",
                "transcript": "Spent 1500 on dinner with friends"
            }
            """
            response = model.generate_content([
                {"mime_type": mime_type, "data": audio_bytes},
                prompt
            ])
            text = response.text.strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                res = json.loads(match.group(0))
                return jsonify({
                    "status": "success",
                    "amount": float(res.get("amount", 0.0)),
                    "category": res.get("category", "Other"),
                    "date": datetime.today().strftime('%Y-%m-%d'),
                    "note": res.get("note", "Voice Expense"),
                    "transcript": res.get("transcript", "")
                })
    except Exception as e:
        print(f"Gemini audio transcription error: {e}")

    return jsonify({
        "status": "success",
        "amount": 0.0,
        "category": "Other",
        "date": datetime.today().strftime('%Y-%m-%d'),
        "note": "Voice Recorded Expense",
        "transcript": "Audio received"
    })



# ========== 3. CATEGORY BUDGETS ==========
@features_bp.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets_page():
    """View and configure monthly category budgets"""
    categories = ['Food', 'Transport', 'Rent', 'Entertainment', 'Shopping', 'Healthcare', 'Education', 'Other']
    
    if request.method == 'POST':
        for cat in categories:
            limit_val = request.form.get(f'limit_{cat}')
            if limit_val is not None and limit_val.strip() != '':
                try:
                    limit_float = float(limit_val)
                    budget = Budget.query.filter_by(user_id=current_user.id, category=cat).first()
                    if limit_float > 0:
                        if not budget:
                            budget = Budget(category=cat, monthly_limit=limit_float, user_id=current_user.id)
                            db.session.add(budget)
                        else:
                            budget.monthly_limit = limit_float
                    elif budget:
                        db.session.delete(budget)
                except ValueError:
                    pass
        db.session.commit()
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup sync error: {e}")
        flash('Category budgets updated successfully! 🎯', 'success')
        return redirect(url_for('features.budgets_page'))

    # Calculate current month spend vs budget
    now = datetime.now()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    df = pd.DataFrame([(e.amount, e.category, e.date) for e in expenses], columns=['amount', 'category', 'date'])
    
    spend_by_cat = {}
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        current_df = df[(df['date'].dt.month == now.month) & (df['date'].dt.year == now.year)]
        if not current_df.empty:
            spend_by_cat = current_df.groupby('category')['amount'].sum().to_dict()

    user_budgets = {b.category: b.monthly_limit for b in Budget.query.filter_by(user_id=current_user.id).all()}
    
    budget_cards = []
    for cat in categories:
        limit = user_budgets.get(cat, 0.0)
        spent = float(spend_by_cat.get(cat, 0.0))
        percentage = round((spent / limit * 100), 1) if limit > 0 else 0
        
        status = "safe"
        if limit > 0:
            if spent >= limit:
                status = "danger"
            elif spent >= 0.75 * limit:
                status = "warning"

        budget_cards.append({
            "category": cat,
            "limit": limit,
            "spent": spent,
            "remaining": max(0.0, limit - spent) if limit > 0 else 0.0,
            "percentage": min(100, percentage),
            "raw_percentage": percentage,
            "status": status
        })

    return render_template('budgets.html', budget_cards=budget_cards, user_currency=getattr(current_user, 'currency', None) or '₹')


# ========== 4. RECURRING SUBSCRIPTIONS ==========
@features_bp.route('/subscriptions', methods=['GET', 'POST'])
@login_required
def subscriptions_page():
    """Manage recurring bills & subscriptions"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        amount = float(request.form.get('amount', 0))
        category = request.form.get('category', 'Entertainment')
        billing_cycle = request.form.get('billing_cycle', 'Monthly')
        due_date_str = request.form.get('next_due_date')

        if name and amount > 0 and due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            sub = Subscription(
                name=name,
                amount=amount,
                category=category,
                billing_cycle=billing_cycle,
                next_due_date=due_date,
                user_id=current_user.id
            )
            db.session.add(sub)
            db.session.commit()
            try:
                save_db_backup(db, User, Expense, Budget, Subscription)
            except Exception as e:
                print(f"Backup sync error: {e}")
            flash(f'Subscription "{name}" added successfully! 🔄', 'success')
            return redirect(url_for('features.subscriptions_page'))

    subs = Subscription.query.filter_by(user_id=current_user.id).order_by(Subscription.next_due_date.asc()).all()
    today = date.today()
    
    total_monthly_recurring = sum(s.amount if s.billing_cycle == 'Monthly' else (s.amount / 12) for s in subs)
    
    formatted_subs = []
    for s in subs:
        due_date = datetime.strptime(str(s.next_due_date), '%Y-%m-%d').date() if isinstance(s.next_due_date, str) else s.next_due_date
        days_left = (due_date - today).days
        formatted_subs.append({
            "id": s.id,
            "name": s.name,
            "amount": s.amount,
            "category": s.category,
            "billing_cycle": s.billing_cycle,
            "next_due_date": due_date,
            "days_left": days_left,
            "is_urgent": 0 <= days_left <= 3
        })

    return render_template('subscriptions.html', 
                           subscriptions=formatted_subs, 
                           total_monthly=round(total_monthly_recurring, 2),
                           user_currency=getattr(current_user, 'currency', None) or '₹')


@features_bp.route('/subscriptions/delete/<int:id>', methods=['POST'])
@login_required
def delete_subscription(id):
    sub = Subscription.query.get_or_404(id)
    if sub.user_id == current_user.id:
        db.session.delete(sub)
        db.session.commit()
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup sync error: {e}")
        flash('Subscription deleted! 🗑️', 'info')
    return redirect(url_for('features.subscriptions_page'))


# ========== 5. MULTI-CURRENCY SETTER ==========
@features_bp.route('/api/set-currency', methods=['POST'])
@login_required
def set_currency():
    """Switch preferred user currency (₹, Rs., $, €, £, AED, SAR)"""
    data = request.get_json() or {}
    currency = data.get('currency', '₹').strip()
    
    valid_currencies = ['₹', 'Rs.', '$', '€', '£', 'AED', 'SAR']
    if currency in valid_currencies:
        user = User.query.get(current_user.id)
        user.currency = currency
        db.session.commit()
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup sync error: {e}")
        return jsonify({"status": "success", "currency": currency})
    return jsonify({"status": "error", "message": "Invalid currency symbol"}), 400


# ========== 6. PRINTABLE / PDF STATEMENT ==========
@features_bp.route('/statement/pdf')
@login_required
def statement_pdf():
    """Render print-ready high fidelity monthly statement"""
    now = datetime.now()
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    
    current_expenses = [e for e in expenses if e.date.month == now.month and e.date.year == now.year]
    total_spent = sum(e.amount for e in current_expenses)
    
    health_score = calculate_financial_health_score(current_user.id)
    
    # Category totals
    cat_totals = {}
    for e in current_expenses:
        cat_totals[e.category] = cat_totals.get(e.category, 0) + e.amount

    return render_template('statement_pdf.html',
                           current_user=current_user,
                           expenses=current_expenses,
                           total_spent=total_spent,
                           cat_totals=cat_totals,
                           health_score=health_score,
                           user_currency=getattr(current_user, 'currency', None) or '₹',
                           statement_date=now.strftime('%B %Y'))
