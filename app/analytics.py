import datetime
import pandas as pd
from app.models import Expense, Budget

def calculate_financial_health_score(user_id):
    """
    Calculate Financial Health Score (0-100) based on real user data,
    category budgets adherence, and spending patterns.
    """
    now = datetime.datetime.now()
    this_month = now.month
    this_year = now.year

    expenses = Expense.query.filter_by(user_id=user_id).all()
    budgets = Budget.query.filter_by(user_id=user_id).all()

    if not expenses:
        return {
            "score": 85,
            "grade": "Clean Slate 🌟",
            "tier": "Optimal",
            "color": "#10B981",
            "message": "No expenses recorded this month yet. Start tracking to build your score!",
            "tips": [
                "Set category budgets under the Budgets tab to maximize your score.",
                "Record daily expenses promptly to keep accurate financial vision."
            ]
        }

    df = pd.DataFrame([(e.amount, e.category, e.date) for e in expenses],
                      columns=['amount', 'category', 'date'])
    df['date'] = pd.to_datetime(df['date'])

    current_month_df = df[(df['date'].dt.month == this_month) & (df['date'].dt.year == this_year)]
    
    if current_month_df.empty:
        return {
            "score": 80,
            "grade": "Fresh Month 🌟",
            "tier": "Optimal",
            "color": "#10B981",
            "message": "Zero spend recorded this month so far.",
            "tips": ["Set monthly savings targets early in the month."]
        }

    total_spent = float(current_month_df['amount'].sum())
    cat_totals = current_month_df.groupby('category')['amount'].sum().to_dict()

    # 1. Budget Adherence Score (40 points max)
    budget_score = 40
    if budgets:
        over_budget_count = 0
        for b in budgets:
            spent = cat_totals.get(b.category, 0)
            if spent > b.monthly_limit:
                over_budget_count += 1
                ratio = (spent - b.monthly_limit) / b.monthly_limit
                budget_score -= min(15, ratio * 15)
        budget_score = max(5, budget_score)
    else:
        # Default bonus if no overspending detected
        budget_score = 35

    # 2. Essential vs Discretionary Ratio (30 points max)
    essential_cats = {'Food', 'Rent', 'Healthcare', 'Education', 'Transport'}
    essential_spend = sum(v for k, v in cat_totals.items() if k in essential_cats)
    discretionary_spend = total_spent - essential_spend

    if total_spent > 0:
        essential_ratio = essential_spend / total_spent
        if essential_ratio >= 0.6:
            ratio_score = 30
        elif essential_ratio >= 0.4:
            ratio_score = 22
        else:
            ratio_score = 15
    else:
        ratio_score = 30

    # 3. Transaction Spread & Consistency (30 points max)
    num_tx = len(current_month_df)
    if num_tx >= 3:
        spread_score = 25
    else:
        spread_score = 20

    final_score = int(round(budget_score + ratio_score + spread_score))
    final_score = max(10, min(99, final_score))

    # Tiers and Tips
    if final_score >= 85:
        grade = "Elite Saver 🏆"
        tier = "Excellent"
        color = "#10B981"  # Emerald
        tips = [
            "Outstanding discipline! Your essential-to-wants ratio is highly healthy.",
            "Consider allocating extra surplus into long-term investments."
        ]
    elif final_score >= 70:
        grade = "Disciplined Spender ⭐"
        tier = "Good"
        color = "#6366F1"  # Indigo
        tips = [
            "Good financial control. Keep an eye on top categories before month-end.",
            "Review your subscriptions to eliminate unused recurring fees."
        ]
    elif final_score >= 50:
        grade = "Balanced 📊"
        tier = "Moderate"
        color = "#F59E0B"  # Amber
        tips = [
            "Spending is moderate, but some categories are approaching budget caps.",
            "Try waiting 24 hours before making any discretionary purchases over ₹1,000."
        ]
    else:
        grade = "Needs Attention ⚠️"
        tier = "Action Required"
        color = "#EF4444"  # Coral Red
        tips = [
            "Category limits exceeded. Immediate cutback on non-essential spending recommended.",
            "Use the AI Advisor to generate an emergency cutback plan."
        ]

    return {
        "score": final_score,
        "grade": grade,
        "tier": tier,
        "color": color,
        "message": f"Your current spending health rating is {final_score}/100.",
        "tips": tips
    }
