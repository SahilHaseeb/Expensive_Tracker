from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Expense, Budget, Subscription
from app.ml_utils import predict_next_month, delete_model
from app.analytics import calculate_financial_health_score
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

    # Statistics
    now = datetime.now()
    this_month = now.month
    this_year = now.year
    
    monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
    total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
    
    # Category totals for cards
    df = pd.DataFrame([(e.amount, e.category, e.date) for e in expenses], 
                      columns=['amount', 'category', 'date'])
    
    # Pie chart
    pie_chart_json = None
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        current_df = df[(df['date'].dt.month == this_month) & (df['date'].dt.year == this_year)]
        if not current_df.empty:
            cat_sum = current_df.groupby('category')['amount'].sum().reset_index()
            fig_pie = px.pie(cat_sum, values='amount', names='category', 
                            title='Category Distribution',
                            color_discrete_sequence=px.colors.sequential.RdBu,
                            hole=0.4)
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Plus Jakarta Sans, sans-serif', color='#64748b'),
                margin=dict(t=30, b=0, l=0, r=0),
                height=340
            )
            pie_chart_json = json.dumps(fig_pie, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Line chart (Monthly trend)
    line_chart_json = None
    if not df.empty:
        df['month_year'] = df['date'].dt.to_period('M')
        monthly_total = df.groupby('month_year')['amount'].sum().reset_index()
        monthly_total['month_year'] = monthly_total['month_year'].astype(str)
        monthly_total = monthly_total.tail(6)
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=monthly_total['month_year'], 
            y=monthly_total['amount'],
            mode='lines+markers',
            line=dict(color='#6366F1', width=3),
            marker=dict(size=9, color='#6366F1', line=dict(color='white', width=2)),
            fill='tozeroy',
            fillcolor='rgba(99, 102, 241, 0.12)',
            name='Monthly Spend'
        ))
        fig_line.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Plus Jakarta Sans, sans-serif', color='#64748b'),
            margin=dict(t=30, b=0, l=0, r=0),
            height=340,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.05)')
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

    # 2. Category Budgets for Dashboard Widget
    user_budgets = {b.category: b.monthly_limit for b in Budget.query.filter_by(user_id=current_user.id).all()}
    budget_progress = []
    for cat, limit in user_budgets.items():
        spent = float(category_totals.get(cat, 0.0))
        pct = round((spent / limit * 100), 1) if limit > 0 else 0
        budget_progress.append({
            "category": cat,
            "limit": limit,
            "spent": spent,
            "percentage": min(100, pct),
            "raw_percentage": pct,
            "is_over": spent > limit,
            "is_warning": spent >= 0.75 * limit and spent <= limit
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
    
    return render_template('dashboard.html',
                           total_this_month=total_this_month,
                           transaction_count=transaction_count,
                           avg_transaction=avg_transaction,
                           category_totals=category_totals,
                           pie_chart_json=pie_chart_json,
                           line_chart_json=line_chart_json,
                           predicted=predicted,
                           health_score=health_score,
                           budget_progress=budget_progress,
                           upcoming_bills=upcoming_bills,
                           user_currency=user_currency,
                           expenses=expenses[:10])

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