from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Expense, Budget, Subscription, User
from app.ml_utils import predict_next_month, delete_model
from app.analytics import calculate_financial_health_score
from app.db_sync import save_db_backup
from datetime import datetime, date, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import plotly.utils
import json

main = Blueprint('main', __name__)

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('landing.html')

@main.route('/dashboard')
@login_required
def dashboard():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    user_currency = getattr(current_user, 'currency', None) or '₹'

    # Current period statistics
    now = datetime.now()
    this_month = now.month
    this_year = now.year
    month_name = now.strftime('%B %Y')
    
    # Previous period for Month-over-Month comparison
    prev_month = 12 if this_month == 1 else this_month - 1
    prev_year = this_year - 1 if this_month == 1 else this_year

    monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
    prev_month_expenses = [e for e in expenses if e.date.month == prev_month and e.date.year == prev_year]

    total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
    total_prev_month = round(sum(e.amount for e in prev_month_expenses), 2)

    # MoM Velocity
    mom_change = round(total_this_month - total_prev_month, 2)
    mom_pct = round((mom_change / total_prev_month * 100), 1) if total_prev_month > 0 else 0.0
    has_prev_data = total_prev_month > 0
    
    # Category totals for cards and charts
    df = pd.DataFrame([(e.amount, e.category, e.date) for e in expenses], 
                      columns=['amount', 'category', 'date'])
    
    # Category Colors Map for Rich Visuals
    CATEGORY_COLORS = {
        'Food': '#10B981',           # Emerald Green
        'Shopping': '#EC4899',       # Vibrant Pink
        'Rent': '#6366F1',           # Electric Indigo
        'Transport': '#F59E0B',      # Golden Amber
        'Entertainment': '#8B5CF6',  # Violet Purple
        'Healthcare': '#06B6D4',     # Bright Cyan
        'Utilities': '#3B82F6',      # Sky Blue
        'Education': '#14B8A6',      # Teal
        'Groceries': '#84CC16',      # Lime
        'Personal Care': '#F43F5E',  # Rose
        'Other': '#94A3B8'           # Slate Grey
    }

    # 1. Category Breakdown Donut Chart
    pie_chart_json = None
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        current_df = df[(df['date'].dt.month == this_month) & (df['date'].dt.year == this_year)]
        if not current_df.empty:
            cat_sum = current_df.groupby('category')['amount'].sum().reset_index()
            colors = [CATEGORY_COLORS.get(cat, '#6366F1') for cat in cat_sum['category']]
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=cat_sum['category'],
                values=cat_sum['amount'],
                hole=0.52,
                marker=dict(colors=colors, line=dict(color='#0F172A', width=2)),
                textposition='inside',
                textinfo='percent+label',
                textfont=dict(family='Plus Jakarta Sans, sans-serif', size=12, color='#FFFFFF'),
                hovertemplate='<b>%{label}</b><br>💰 Spent: <b>' + user_currency + '%{value:,.2f}</b><br>📊 Share: <b>%{percent}</b><extra></extra>'
            )])
            
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Plus Jakarta Sans, sans-serif', color='#94A3B8'),
                margin=dict(t=15, b=15, l=15, r=15),
                height=320,
                showlegend=True,
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=-0.22,
                    xanchor='center',
                    x=0.5,
                    font=dict(size=11, color='#94A3B8')
                )
            )
            pie_chart_json = json.dumps(fig_pie, cls=plotly.utils.PlotlyJSONEncoder)
    
    # 2. Spending Trend Smooth Spline Area Chart
    line_chart_json = None
    if not df.empty:
        df['period'] = df['date'].dt.strftime('%b %Y')
        df['sort_key'] = df['date'].dt.to_period('M')
        
        monthly_trend = df.groupby(['sort_key', 'period'])['amount'].sum().reset_index()
        monthly_trend = monthly_trend.sort_values('sort_key').tail(6)
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=monthly_trend['period'], 
            y=monthly_trend['amount'],
            mode='lines+markers',
            line=dict(color='#6366F1', width=3.5, shape='spline', smoothing=1.3),
            marker=dict(size=10, color='#8B5CF6', line=dict(color='#FFFFFF', width=2)),
            fill='tozeroy',
            fillcolor='rgba(99, 102, 241, 0.18)',
            name='Monthly Total',
            hovertemplate='<b>📅 Month: %{x}</b><br>💰 Total Spent: <b>' + user_currency + '%{y:,.2f}</b><extra></extra>'
        ))
        
        fig_line.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Plus Jakarta Sans, sans-serif', color='#94A3B8'),
            margin=dict(t=20, b=20, l=15, r=15),
            height=320,
            xaxis=dict(
                showgrid=False,
                color='#94A3B8',
                tickfont=dict(size=12, family='Plus Jakarta Sans, sans-serif')
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255, 255, 255, 0.08)',
                color='#94A3B8',
                tickprefix=user_currency,
                tickformat=',.0f',
                tickfont=dict(size=11, family='Plus Jakarta Sans, sans-serif')
            )
        )
        line_chart_json = json.dumps(fig_line, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Category breakdown for cards
    category_totals = {}
    if not df.empty:
        current_df = df[(pd.to_datetime(df['date']).dt.month == this_month)]
        category_totals = current_df.groupby('category')['amount'].sum().to_dict()
    
    # Number of transactions this month
    transaction_count = len(monthly_expenses)
    
    # Average transaction
    avg_transaction = round(total_this_month / transaction_count, 2) if transaction_count > 0 else 0.0
    
    # ML Prediction
    predicted = predict_next_month(current_user.id, expenses)

    # 1. Financial Health Score
    health_score = calculate_financial_health_score(current_user.id)

    # 2. Category Budgets & Overall Monthly Budget Overview
    all_user_budgets = Budget.query.filter_by(user_id=current_user.id).all()
    user_budgets = {b.category: float(b.monthly_limit) for b in all_user_budgets}
    
    total_budget = round(sum(b.monthly_limit for b in all_user_budgets), 2)
    total_budget_spent = round(sum(category_totals.get(cat, 0.0) for cat in user_budgets), 2) if user_budgets else 0.0
    total_budget_remaining = round(max(0.0, total_budget - total_budget_spent), 2) if total_budget > 0 else 0.0
    total_budget_overage = round(max(0.0, total_budget_spent - total_budget), 2) if total_budget_spent > total_budget else 0.0
    overall_budget_pct = round((total_budget_spent / total_budget * 100), 1) if total_budget > 0 else 0.0
    is_overall_over = total_budget_spent > total_budget if total_budget > 0 else False
    is_overall_warning = (0.75 * total_budget <= total_budget_spent <= total_budget) if total_budget > 0 else False

    overall_budget_summary = {
        "total_budget": total_budget,
        "total_budget_spent": total_budget_spent,
        "total_budget_remaining": total_budget_remaining,
        "total_budget_overage": total_budget_overage,
        "overall_budget_pct": overall_budget_pct,
        "is_overall_over": is_overall_over,
        "is_overall_warning": is_overall_warning,
        "has_budgets": bool(all_user_budgets)
    }

    budget_progress = []
    for cat, limit in user_budgets.items():
        spent = float(category_totals.get(cat, 0.0))
        pct = round((spent / limit * 100), 1) if limit > 0 else 0.0
        budget_progress.append({
            "category": cat,
            "limit": limit,
            "spent": spent,
            "remaining": round(limit - spent, 2),
            "percentage": min(100, int(round(pct))),
            "raw_percentage": int(round(pct)),
            "is_over": spent > limit,
            "is_warning": 0.75 * limit <= spent <= limit,
            "is_healthy": spent < 0.75 * limit
        })

    # 3. Upcoming Bill Reminders (due in next 5 days)
    today = date.today()
    all_subs = Subscription.query.filter_by(user_id=current_user.id).all()
    upcoming_bills = []
    for s in all_subs:
        due_date = datetime.strptime(str(s.next_due_date), '%Y-%m-%d').date() if isinstance(s.next_due_date, str) else s.next_due_date
        days_left = (due_date - today).days
        if 0 <= days_left <= 5:
            upcoming_bills.append({
                "name": s.name,
                "amount": s.amount,
                "days_left": days_left,
                "is_urgent": days_left <= 2
            })

    # 4. Verified Smart AI Insights Preview
    smart_insights = []
    try:
        from app.ai_advisor import get_user_financial_context
        financial_context = get_user_financial_context(current_user.id)
        smart_insights = financial_context.get('smart_insights', [])[:3]
    except Exception as e:
        smart_insights = []
    
    return render_template('dashboard.html',
                           month_name=month_name,
                           total_this_month=total_this_month,
                           total_prev_month=total_prev_month,
                           mom_change=mom_change,
                           mom_pct=mom_pct,
                           has_prev_data=has_prev_data,
                           transaction_count=transaction_count,
                           avg_transaction=avg_transaction,
                           overall_budget_summary=overall_budget_summary,
                           total_budget=total_budget,
                           total_budget_spent=total_budget_spent,
                           total_budget_remaining=total_budget_remaining,
                           total_budget_overage=total_budget_overage,
                           overall_budget_pct=overall_budget_pct,
                           is_overall_over=is_overall_over,
                           is_overall_warning=is_overall_warning,
                           has_budgets=bool(all_user_budgets),
                           total_spent=total_this_month,
                           budget=total_budget,
                           remaining_budget=total_budget_remaining,
                           budget_percentage=overall_budget_pct,
                           category_totals=category_totals,
                           pie_chart_json=pie_chart_json,
                           line_chart_json=line_chart_json,
                           predicted=predicted,
                           health_score=health_score,
                           budget_progress=budget_progress,
                           smart_insights=smart_insights,
                           upcoming_bills=upcoming_bills,
                           user_currency=user_currency,
                           expenses=expenses[:10],
                           recent_expenses=expenses[:10],
                           total_expenses_count=len(expenses))

@main.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        date_str = request.form['date']
        note = request.form.get('note', '')
        expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        expense = Expense(amount=amount, category=category, date=expense_date, 
                         note=note, user_id=current_user.id)
        db.session.add(expense)
        db.session.commit()
        delete_model(current_user.id)
        
        # Save snapshot
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup sync error: {e}")

        flash('Expense added successfully! ✅', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('add_expense.html', user_currency=getattr(current_user, 'currency', None) or '₹')

@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        expense.amount = float(request.form['amount'])
        expense.category = request.form['category']
        expense.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        expense.note = request.form.get('note', '')
        db.session.commit()
        delete_model(current_user.id)
        
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Backup sync error: {e}")

        flash('Expense updated! ✏️', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('edit_expense.html', expense=expense, user_currency=getattr(current_user, 'currency', None) or '₹')

@main.route('/delete/<int:id>')
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('main.dashboard'))
    db.session.delete(expense)
    db.session.commit()
    delete_model(current_user.id)
    
    try:
        save_db_backup(db, User, Expense, Budget, Subscription)
    except Exception as e:
        print(f"Backup sync error: {e}")

    flash('Expense deleted! 🗑️', 'success')
    return redirect(url_for('main.dashboard'))

@main.route('/export')
@login_required
def export_csv():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    df = pd.DataFrame([(e.date, e.amount, e.category, e.note) for e in expenses],
                      columns=['Date', 'Amount', 'Category', 'Note'])
    
    import io
    from flask import Response
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    
    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=expenses.csv'}
    )

@main.route('/contact', methods=['POST'])
def contact_submit():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not email or not message:
        flash('Please fill in all required fields (Name, Email, Message).', 'error')
        return redirect(url_for('main.index') + '#contact')

    try:
        import os
        import json
        data_dir = 'storage'
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, 'contact_inquiries.json')
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                inquiries = json.load(f)
        else:
            inquiries = []

        inquiries.append({
            'name': name,
            'email': email,
            'phone': phone,
            'subject': subject or 'General Inquiry',
            'message': message,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip': request.remote_addr
        })

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(inquiries, f, indent=4)

        flash(f'Thank you {name}! Your message has been received. We will contact you at {email} shortly. ✉️', 'success')
    except Exception as e:
        print(f"Error saving contact message: {e}")
        flash('Thank you! Your message has been noted.', 'success')

    return redirect(url_for('main.index') + '#contact')