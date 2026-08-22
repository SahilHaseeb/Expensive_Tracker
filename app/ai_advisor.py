import os
import datetime
import pandas as pd
from config import Config
from app.models import Expense

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def get_user_financial_context(user_id):
    """
    Extract current month financial context for user to provide to Gemini AI
    """
    now = datetime.datetime.now()
    this_month = now.month
    this_year = now.year

    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
    
    if not expenses:
        return {
            "has_data": False,
            "summary_text": "The user has not recorded any expenses yet in the database."
        }

    df = pd.DataFrame([(e.amount, e.category, e.date, e.note) for e in expenses],
                      columns=['amount', 'category', 'date', 'note'])
    df['date'] = pd.to_datetime(df['date'])

    current_month_df = df[(df['date'].dt.month == this_month) & (df['date'].dt.year == this_year)]
    
    total_this_month = float(current_month_df['amount'].sum()) if not current_month_df.empty else 0.0
    all_time_total = float(df['amount'].sum())
    total_transactions = len(current_month_df)

    category_summary = {}
    top_category = "None"
    top_category_amount = 0.0

    if not current_month_df.empty:
        cat_grouped = current_month_df.groupby('category')['amount'].sum().to_dict()
        category_summary = {k: round(float(v), 2) for k, v in cat_grouped.items()}
        if category_summary:
            top_category = max(category_summary, key=category_summary.get)
            top_category_amount = category_summary[top_category]

    recent_entries = []
    for e in expenses[:5]:
        recent_entries.append(f"- {e.date.strftime('%Y-%m-%d')}: ₹{e.amount} on {e.category} ({e.note or 'No note'})")

    summary_text = f"""
Current Month ({now.strftime('%B %Y')}):
- Total Spent This Month: ₹{total_this_month:.2f}
- Number of Transactions: {total_transactions}
- Highest Spending Category: {top_category} (₹{top_category_amount:.2f})
- Category Breakdown: {category_summary}
- All-Time Total Recorded Spending: ₹{all_time_total:.2f}
- Recent Transactions:
{chr(10).join(recent_entries) if recent_entries else 'None'}
"""
    return {
        "has_data": True,
        "total_this_month": total_this_month,
        "category_summary": category_summary,
        "top_category": top_category,
        "summary_text": summary_text.strip()
    }


def generate_ai_response(user_id, username, user_message, chat_history=None):
    """
    Generate financial advice response using Google Gemini API with fallback
    """
    api_key = Config.GEMINI_API_KEY or os.environ.get('GEMINI_API_KEY')
    financial_data = get_user_financial_context(user_id)

    system_instruction = f"""
You are "ExpenseAI Advisor", a friendly, highly competent, and empathetic personal financial advisor built into the Smart Expense Tracker web application.
You are talking to {username}.

The user's real-time financial data is:
{financial_data['summary_text']}

Guidelines:
1. Provide practical, encouraging, and tailored financial advice based on their real spending numbers shown above.
2. If they ask about saving money, cutting costs, budget plans, or category analysis, give concise, bulleted, actionable tips.
3. Be supportive and realistic. Use currency symbol ₹ (Rupees) when quoting their amounts.
4. Format your responses with clean Markdown (bold headings, bullet points).
5. If the user asks general financial/investing/budgeting questions, answer intelligently with clarity.
"""

    if not api_key:
        return get_smart_fallback_response(user_message, financial_data, username)

    if not GENAI_AVAILABLE:
        return "⚠️ Google Gemini SDK is not installed. Please add `google-generativeai` to requirements.txt."

    try:
        genai.configure(api_key=api_key)
        
        # Try gemini-1.5-flash for fastest, cost-free responses
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=system_instruction
        )

        # Build message history if provided
        contents = []
        if chat_history and isinstance(chat_history, list):
            for item in chat_history[-6:]: # keep last 3 turns
                role = "user" if item.get("sender") == "user" else "model"
                contents.append({"role": role, "parts": [item.get("text", "")]})

        contents.append({"role": "user", "parts": [user_message]})

        response = model.generate_content(contents)
        if response and response.text:
            return response.text
        else:
            return "I analyzed your request, but could not generate a detailed response. Please try rephrasing."

    except Exception as e:
        error_msg = str(e)
        # In case of API quota or model error, fallback smoothly
        fallback = get_smart_fallback_response(user_message, financial_data, username)
        return f"{fallback}\n\n*(Note: Live AI key encountered an issue: {error_msg[:90]}...)*"


def get_smart_fallback_response(user_message, financial_data, username):
    """
    Intelligent rule-based fallback when Gemini API key is not yet set
    """
    msg = user_message.lower()
    total = financial_data.get('total_this_month', 0)
    top_cat = financial_data.get('top_category', 'Food')
    cat_summary = financial_data.get('category_summary', {})

    if any(word in msg for word in ['save', 'saving', 'reduce', 'cut']):
        return f"""### 💡 Budget Optimization Tips for {username}

Based on your current records:
- **Total Spent This Month:** ₹{total:.2f}
- **Highest Category:** **{top_cat}**

**Action Plan:**
1. **Target {top_cat}:** Try setting a 15% reduction goal on `{top_cat}` next week. Small daily adjustments yield substantial monthly savings.
2. **50/30/20 Rule:** Allocate 50% of income to Needs (Rent, Utilities), 30% to Wants ({top_cat}, Entertainment), and 20% directly to Savings.
3. **Use the 48-Hour Rule:** For non-essential purchases, wait 48 hours before checking out to avoid impulse spending.

*Tip: Connect your Gemini API Key in Render Environment Variables for personalized AI deep-dives!*"""

    elif any(word in msg for word in ['analyze', 'analysis', 'summary', 'status', 'overview']):
        breakdown_lines = "\n".join([f"- **{k}:** ₹{v}" for k, v in cat_summary.items()]) or "- No category data yet."
        return f"""### 📊 Financial Health Snapshot for {username}

Here is a summary of your active spending:
- **Total This Month:** ₹{total:.2f}
- **Primary Spending Driver:** **{top_cat}**

**Category Breakdown:**
{breakdown_lines}

**Recommendation:**
Keep recording your daily expenses consistently. Our Machine Learning model will automatically project next month's forecast on your dashboard!"""

    elif any(word in msg for word in ['budget', 'plan', 'weekly']):
        weekly_budget = round(total / 4, 2) if total > 0 else 5000
        return f"""### 🎯 Suggested Weekly Budget Plan

Based on your monthly volume:
- **Recommended Weekly Target:** ~₹{weekly_budget} / week
- **Priority 1 (Essential):** Rent, Groceries & Transport (Target: 60%)
- **Priority 2 (Discretionary):** Dining & Entertainment (Target: 20%)
- **Priority 3 (Buffer/Savings):** Emergency Fund (Target: 20%)

Track each purchase immediately after spending to stay within your weekly cap!"""

    else:
        return f"""### 🤖 Hello {username}!

I am your **AI Financial Advisor**. I have direct access to your expense metrics (Total: **₹{total:.2f}**, Top Category: **{top_cat}**).

**You can ask me questions like:**
- *"How can I save ₹2,000 this month?"*
- *"Analyze my highest spending category"*
- *"Create a weekly grocery budget plan"*
- *"Where am I overspending?"*

How can I assist you with your budget today?"""
