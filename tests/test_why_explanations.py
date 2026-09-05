import sys
import os
import datetime
import types
import unittest
import pandas as pd

# Setup mocks for app dependencies so unit tests run independently and reliably
mock_models = types.ModuleType("app.models")
class MockUser:
    def __init__(self, id, username, currency='₹'):
        self.id = id
        self.username = username
        self.currency = currency

class MockExpense:
    date = types.SimpleNamespace(desc=lambda: "date desc")
    def __init__(self, amount, category, date_val, note, user_id):
        self.amount = amount
        self.category = category
        self.date = date_val
        self.note = note
        self.user_id = user_id

class MockBudget:
    def __init__(self, category, monthly_limit, user_id):
        self.category = category
        self.monthly_limit = monthly_limit
        self.user_id = user_id

class MockSubscription:
    next_due_date = types.SimpleNamespace(asc=lambda: "next_due_date asc")
    def __init__(self, name, amount, category, billing_cycle, next_due_date, user_id):
        self.name = name
        self.amount = amount
        self.category = category
        self.billing_cycle = billing_cycle
        self.next_due_date = next_due_date
        self.user_id = user_id

mock_models.User = MockUser
mock_models.Expense = MockExpense
mock_models.Budget = MockBudget
mock_models.Subscription = MockSubscription

mock_analytics = types.ModuleType("app.analytics")
mock_analytics.calculate_financial_health_score = lambda uid: {
    "score": 74,
    "grade": "Disciplined Spender ⭐",
    "tier": "Good",
    "message": "Healthy spending habits with disciplined budget control.",
    "tips": ["Keep eye on Shopping budget", "Review unused subscriptions"]
}

mock_config = types.ModuleType("config")
class MockConfig:
    GEMINI_API_KEY = None
mock_config.Config = MockConfig

sys.modules["app"] = types.ModuleType("app")
sys.modules["app.models"] = mock_models
sys.modules["app.analytics"] = mock_analytics
sys.modules["config"] = mock_config

import importlib.util
spec = importlib.util.spec_from_file_location("ai_advisor", os.path.join(os.path.dirname(__file__), "..", "app", "ai_advisor.py"))
ai_advisor_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_advisor_mod)

calculate_why_explanations = ai_advisor_mod.calculate_why_explanations
get_smart_fallback_response = ai_advisor_mod.get_smart_fallback_response
get_user_financial_context = ai_advisor_mod.get_user_financial_context


class TestWhyExplanations(unittest.TestCase):
    def setUp(self):
        self.currency = "Rs."
        self.username = "Alice"

        self.rich_expenses = pd.DataFrame([
            {"amount": 12000.0, "category": "Shopping", "date": datetime.date(2026, 8, 10), "note": "Clothes"},
            {"amount": 5000.0, "category": "Shopping", "date": datetime.date(2026, 8, 12), "note": "Shoes"},
            {"amount": 15000.0, "category": "Food", "date": datetime.date(2026, 8, 5), "note": "Groceries"},
            {"amount": 25000.0, "category": "Rent", "date": datetime.date(2026, 8, 1), "note": "Rent"},
            {"amount": 8000.0, "category": "Transport", "date": datetime.date(2026, 8, 15), "note": "Fuel"},
            {"amount": 2000.0, "category": "Entertainment", "date": datetime.date(2026, 8, 20), "note": "Movies"}
        ])

        self.prev_expenses = pd.DataFrame([
            {"amount": 8500.0, "category": "Shopping", "date": datetime.date(2026, 7, 10), "note": ""},
            {"amount": 14000.0, "category": "Food", "date": datetime.date(2026, 7, 5), "note": ""},
            {"amount": 25000.0, "category": "Rent", "date": datetime.date(2026, 7, 1), "note": ""},
            {"amount": 7500.0, "category": "Transport", "date": datetime.date(2026, 7, 15), "note": ""}
        ])

        self.budgets = [MockBudget("Shopping", 10000.0, 1), MockBudget("Food", 18000.0, 1)]
        self.category_summary = {"Shopping": 17000.0, "Food": 15000.0, "Rent": 25000.0, "Transport": 8000.0, "Entertainment": 2000.0}
        self.prev_category_summary = {"Shopping": 8500.0, "Food": 14000.0, "Rent": 25000.0, "Transport": 7500.0}
        self.total_this_month = 67000.0
        self.total_prev_month = 55000.0
        self.health_score_data = {"score": 74, "grade": "Disciplined Spender ⭐"}
        self.hist_avg_map = {"Shopping": 9000.0, "Food": 14500.0, "Rent": 25000.0, "Transport": 7800.0}

        self.why_data = calculate_why_explanations(
            self.rich_expenses,
            self.prev_expenses,
            self.budgets,
            self.category_summary,
            self.prev_category_summary,
            self.total_this_month,
            self.total_prev_month,
            self.currency,
            self.health_score_data,
            self.hist_avg_map
        )

        self.payload = {
            "currency": self.currency,
            "total_this_month": self.total_this_month,
            "total_prev_month": self.total_prev_month,
            "mom_change": 12000.0,
            "mom_pct": 21.8,
            "category_summary": self.category_summary,
            "prev_category_summary": self.prev_category_summary,
            "category_percentages": {"Rent": 37.3, "Shopping": 25.4, "Food": 22.4, "Transport": 11.9, "Entertainment": 3.0},
            "budget_details": [
                {"category": "Shopping", "limit": 10000.0, "spent": 17000.0, "remaining": -7000.0, "usage_pct": 170.0, "status_text": "OVER BUDGET by Rs. 7,000.00 (Usage: 170.0%)"},
                {"category": "Food", "limit": 18000.0, "spent": 15000.0, "remaining": 3000.0, "usage_pct": 83.3, "status_text": "Approaching Cap (83.3% used, Rs. 3,000.00 remaining)"}
            ],
            "budget_evaluations": [],
            "overbudget_categories": [
                {"category": "Shopping", "limit": 10000.0, "spent": 17000.0, "excess": 7000.0, "usage_pct": 170.0}
            ],
            "approaching_categories": [
                {"category": "Food", "limit": 18000.0, "spent": 15000.0, "remaining": 3000.0, "usage_pct": 83.3}
            ],
            "within_categories": [],
            "total_monthly_subs": 4000.0,
            "active_subscriptions": [{"name": "Netflix", "amount": 1500.0}, {"name": "Gym", "amount": 2500.0}],
            "largest_transaction": {"amount": 25000.0, "category": "Rent", "note": "Apartment"},
            "avg_transaction": 11166.67,
            "top_category": "Rent",
            "top_category_amount": 25000.0,
            "health_score": 74,
            "health_grade": "Disciplined Spender ⭐",
            "why_data": self.why_data,
            "smart_insights": []
        }

    def test_why_health_score_low(self):
        """User asks 'Why is my health score low?' -> response explains the actual factors."""
        reply = get_smart_fallback_response("Why is my health score low?", self.payload, self.username)
        self.assertIn("74/100", reply)
        self.assertIn("Shopping", reply)
        self.assertIn("What Happened", reply)
        self.assertIn("Why", reply)
        self.assertIn("What You Can Do", reply)

    def test_why_expenses_increased(self):
        """Compares current vs previous month and identifies top contributors to the increase."""
        reply = get_smart_fallback_response("Why did my expenses increase?", self.payload, self.username)
        self.assertIn("Shopping", reply)
        self.assertIn("8,500.00", reply)
        self.assertIn("70.8%", reply)
        self.assertIn("What Happened", reply)
        self.assertIn("Why", reply)

        # Also verify if expenses decreased, it does NOT claim an increase
        decreased_payload = dict(self.payload)
        decreased_payload["total_this_month"] = 45000.0
        decreased_payload["total_prev_month"] = 55000.0
        decreased_payload["mom_change"] = -10000.0
        decreased_payload["mom_pct"] = -18.2
        reply_dec = get_smart_fallback_response("Why did my expenses increase?", decreased_payload, self.username)
        self.assertIn("did not increase", reply_dec.lower())

    def test_why_over_budget(self):
        """Explains actual budget limits and spending and distinguishes FACT from RECOMMENDATION."""
        reply = get_smart_fallback_response("Why am I over budget?", self.payload, self.username)
        self.assertIn("Shopping", reply)
        self.assertIn("7,000.00", reply)
        self.assertIn("FACT", reply)
        self.assertIn("RECOMMENDATION", reply)

    def test_why_score_changed_with_history(self):
        """Only claims a historical score change if historical score data actually exists."""
        payload_with_history = dict(self.payload)
        payload_with_history["prev_health_score"] = 85
        reply = get_smart_fallback_response("Why did my financial health score go down?", payload_with_history, self.username)
        self.assertIn("decreased from 85/100 to 74/100", reply)

    def test_why_score_changed_without_history(self):
        """Without historical score data, explains current factors without inventing a previous score."""
        payload_no_history = dict(self.payload)
        payload_no_history.pop("prev_health_score", None)
        reply = get_smart_fallback_response("Why did my financial health score go down?", payload_no_history, self.username)
        self.assertIn("Past scores are not stored historically", reply)
        self.assertNotIn("decreased from 85", reply)

    def test_recommendation_has_data_based_reason(self):
        """Every recommendation has a data-based reason and uses clear labels for FACT vs RECOMMENDATION."""
        reply = get_smart_fallback_response("Why should I reduce my spending?", self.payload, self.username)
        self.assertIn("FACT", reply)
        self.assertIn("RECOMMENDATION", reply)
        self.assertIn("Shopping", reply)
        self.assertIn("7,000.00 above budget", reply)

    def test_insufficient_data_does_not_hallucinate(self):
        """If there is not enough historical data, explicitly says so without fabricating trends."""
        no_history_why = calculate_why_explanations(
            self.rich_expenses,
            pd.DataFrame(columns=['amount', 'category', 'date', 'note']),
            self.budgets,
            self.category_summary,
            {},
            self.total_this_month,
            0.0,
            self.currency,
            self.health_score_data,
            self.hist_avg_map
        )
        no_hist_payload = dict(self.payload)
        no_hist_payload["total_prev_month"] = 0.0
        no_hist_payload["mom_change"] = 0.0
        no_hist_payload["why_data"] = no_history_why

        reply = get_smart_fallback_response("Why did my expenses increase?", no_hist_payload, self.username)
        self.assertIn("don't have recorded expenses from last month", reply)
        self.assertNotIn("increased by", reply)

    def test_current_user_data_only(self):
        """Ensures queries filter strictly by user_id and never mix users' records."""
        today = datetime.date.today()
        user1_expenses = [
            MockExpense(1000.0, "Food", today, "User 1 Lunch", 1)
        ]
        user2_expenses = [
            MockExpense(99999.0, "Luxury", today, "User 2 Car", 2)
        ]

        def mock_expense_filter(user_id):
            class FilterQuery:
                def __init__(self, uid):
                    self.uid = uid
                def order_by(self, *args):
                    return self
                def all(self):
                    return user1_expenses if self.uid == 1 else user2_expenses
            return FilterQuery(user_id)

        mock_models.Expense.query = types.SimpleNamespace(filter_by=mock_expense_filter)
        mock_models.Budget.query = types.SimpleNamespace(filter_by=lambda user_id: types.SimpleNamespace(all=lambda: []))
        mock_models.Subscription.query = types.SimpleNamespace(filter_by=lambda user_id: types.SimpleNamespace(order_by=lambda *args: types.SimpleNamespace(all=lambda: [])))
        mock_models.User.query = types.SimpleNamespace(get=lambda uid: MockUser(uid, f"User{uid}", "₹"))

        ctx_user1 = get_user_financial_context(1)
        ctx_user2 = get_user_financial_context(2)

        self.assertEqual(ctx_user1["total_this_month"], 1000.0)
        self.assertEqual(ctx_user2["total_this_month"], 99999.0)
        self.assertNotIn("Luxury", ctx_user1["category_summary"])
        self.assertNotIn("User 2", ctx_user1["summary_text"])

    def test_existing_ai_advisor_features_still_work(self):
        """Verifies AI Advisor #1, #2, and #3 continue to function seamlessly."""
        q1 = get_smart_fallback_response("How am I doing financially?", self.payload, self.username)
        self.assertIn("74/100", q1)
        self.assertIn(self.username, q1)

        q2 = get_smart_fallback_response("Where am I spending the most?", self.payload, self.username)
        self.assertIn("Rent", q2)
        self.assertIn(self.username, q2)

        q3 = get_smart_fallback_response("Am I staying within my budget?", self.payload, self.username)
        self.assertIn("Shopping", q3)
        self.assertIn(self.username, q3)

        q4 = get_smart_fallback_response("How should I set my budget next month?", self.payload, self.username)
        self.assertIn("Suggested Target", q4)
        self.assertIn(self.username, q4)


if __name__ == "__main__":
    unittest.main()
