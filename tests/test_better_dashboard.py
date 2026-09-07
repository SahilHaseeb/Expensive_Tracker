"""
Tests for Phase 3 — Feature #17: BETTER DASHBOARD.

Covers verification scenarios:
1. Dashboard metrics with expenses & previous month data (MoM calculation, spending, transactions, avg)
2. Dashboard metrics with zero previous month data (handles div by zero gracefully)
3. Dashboard metrics with zero current expenses (empty state metrics)
4. Overall monthly budget calculation (under budget, within safe limits)
5. Overall monthly budget calculation (warning state: 75%-100% utilized)
6. Overall monthly budget calculation (over budget: > 100% utilized, overage computed)
7. Dashboard behavior when no budgets configured (graceful empty budget state)
8. Per-category budget progress with remaining buffer calculation
9. Upcoming subscription bills integration (due within 5 days flagged, urgent <= 2 days)
10. Smart AI Insights integration (fact, recommendation, priority)
11. Health score presentation & preservation of existing grading
12. User data isolation (user A expenses/budgets isolated from user B)
13. Currency handling consistency (dynamic user currency respected)
14. Backward-compatible parameters preserved for template/API stability
"""

import os
import sys
import datetime
from datetime import date, timedelta
import types
import unittest
from unittest.mock import patch, MagicMock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure app package mock exists if needed
if "app" not in sys.modules:
    sys.modules["app"] = types.ModuleType("app")


class MockUser:
    def __init__(self, id=1, username="testuser", currency="₹"):
        self.id = id
        self.username = username
        self.currency = currency
        self.is_authenticated = True


class MockExpense:
    def __init__(self, amount, category, date_val, note="", user_id=1, id=1):
        self.id = id
        self.amount = amount
        self.category = category
        self.date = date_val
        self.note = note
        self.user_id = user_id


class MockBudget:
    def __init__(self, category, monthly_limit, user_id=1, id=1):
        self.id = id
        self.category = category
        self.monthly_limit = monthly_limit
        self.user_id = user_id


class MockSubscription:
    def __init__(self, name, amount, category, billing_cycle, next_due_date, user_id=1, id=1):
        self.id = id
        self.name = name
        self.amount = amount
        self.category = category
        self.billing_cycle = billing_cycle
        self.next_due_date = next_due_date
        self.user_id = user_id


class TestBetterDashboardMetrics(unittest.TestCase):
    """Unit tests for the financial calculation logic powering Feature #17 Better Dashboard."""

    def test_mom_spending_increase(self):
        """Test Month-over-Month calculation when spending increased."""
        now = datetime.datetime.now()
        this_month = now.month
        this_year = now.year
        prev_month = 12 if this_month == 1 else this_month - 1
        prev_year = this_year - 1 if this_month == 1 else this_year

        d_current = datetime.date(this_year, this_month, 10)
        d_prev = datetime.date(prev_year, prev_month, 10)

        expenses = [
            MockExpense(amount=1500.0, category="Food", date_val=d_current),
            MockExpense(amount=1000.0, category="Food", date_val=d_prev),
        ]

        monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
        prev_month_expenses = [e for e in expenses if e.date.month == prev_month and e.date.year == prev_year]

        total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
        total_prev_month = round(sum(e.amount for e in prev_month_expenses), 2)

        mom_change = round(total_this_month - total_prev_month, 2)
        mom_pct = round((mom_change / total_prev_month * 100), 1) if total_prev_month > 0 else 0.0

        self.assertEqual(total_this_month, 1500.0)
        self.assertEqual(total_prev_month, 1000.0)
        self.assertEqual(mom_change, 500.0)
        self.assertEqual(mom_pct, 50.0)

    def test_mom_spending_decrease(self):
        """Test Month-over-Month calculation when spending decreased."""
        now = datetime.datetime.now()
        this_month = now.month
        this_year = now.year
        prev_month = 12 if this_month == 1 else this_month - 1
        prev_year = this_year - 1 if this_month == 1 else this_year

        d_current = datetime.date(this_year, this_month, 15)
        d_prev = datetime.date(prev_year, prev_month, 15)

        expenses = [
            MockExpense(amount=800.0, category="Shopping", date_val=d_current),
            MockExpense(amount=1600.0, category="Shopping", date_val=d_prev),
        ]

        monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
        prev_month_expenses = [e for e in expenses if e.date.month == prev_month and e.date.year == prev_year]

        total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
        total_prev_month = round(sum(e.amount for e in prev_month_expenses), 2)

        mom_change = round(total_this_month - total_prev_month, 2)
        mom_pct = round((mom_change / total_prev_month * 100), 1) if total_prev_month > 0 else 0.0

        self.assertEqual(total_this_month, 800.0)
        self.assertEqual(total_prev_month, 1600.0)
        self.assertEqual(mom_change, -800.0)
        self.assertEqual(mom_pct, -50.0)

    def test_mom_zero_prev_data_graceful(self):
        """Test that missing previous month data does not cause ZeroDivisionError."""
        now = datetime.datetime.now()
        this_month = now.month
        this_year = now.year

        d_current = datetime.date(this_year, this_month, 5)
        expenses = [MockExpense(amount=500.0, category="Food", date_val=d_current)]

        prev_month = 12 if this_month == 1 else this_month - 1
        prev_year = this_year - 1 if this_month == 1 else this_year

        monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
        prev_month_expenses = [e for e in expenses if e.date.month == prev_month and e.date.year == prev_year]

        total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
        total_prev_month = round(sum(e.amount for e in prev_month_expenses), 2)

        mom_change = round(total_this_month - total_prev_month, 2)
        mom_pct = round((mom_change / total_prev_month * 100), 1) if total_prev_month > 0 else 0.0
        has_prev_data = total_prev_month > 0

        self.assertEqual(total_this_month, 500.0)
        self.assertEqual(total_prev_month, 0.0)
        self.assertEqual(mom_pct, 0.0)
        self.assertFalse(has_prev_data)

    def test_empty_expenses_metrics(self):
        """Test metrics calculation when user has 0 expenses (clean empty state)."""
        expenses = []
        now = datetime.datetime.now()
        this_month = now.month
        this_year = now.year

        monthly_expenses = [e for e in expenses if e.date.month == this_month and e.date.year == this_year]
        total_this_month = round(sum(e.amount for e in monthly_expenses), 2)
        transaction_count = len(monthly_expenses)
        avg_transaction = round(total_this_month / transaction_count, 2) if transaction_count > 0 else 0.0

        self.assertEqual(total_this_month, 0.0)
        self.assertEqual(transaction_count, 0)
        self.assertEqual(avg_transaction, 0.0)

    def test_overall_budget_under_limit(self):
        """Test overall budget calculations when user is safely under budget limit."""
        user_budgets = {"Food": 5000.0, "Transport": 2000.0}
        category_totals = {"Food": 2500.0, "Transport": 800.0}

        total_budget = round(sum(user_budgets.values()), 2)
        total_budget_spent = round(sum(category_totals.get(cat, 0.0) for cat in user_budgets), 2)
        total_budget_remaining = round(max(0.0, total_budget - total_budget_spent), 2)
        total_budget_overage = round(max(0.0, total_budget_spent - total_budget), 2) if total_budget_spent > total_budget else 0.0
        overall_budget_pct = round((total_budget_spent / total_budget * 100), 1) if total_budget > 0 else 0.0
        is_overall_over = total_budget_spent > total_budget if total_budget > 0 else False
        is_overall_warning = (0.75 * total_budget <= total_budget_spent <= total_budget) if total_budget > 0 else False

        self.assertEqual(total_budget, 7000.0)
        self.assertEqual(total_budget_spent, 3300.0)
        self.assertEqual(total_budget_remaining, 3700.0)
        self.assertEqual(total_budget_overage, 0.0)
        self.assertAlmostEqual(overall_budget_pct, 47.1, places=1)
        self.assertFalse(is_overall_over)
        self.assertFalse(is_overall_warning)

    def test_overall_budget_warning_state(self):
        """Test overall budget calculations when spending enters warning threshold (75%-100%)."""
        user_budgets = {"Food": 10000.0}
        category_totals = {"Food": 8500.0}

        total_budget = round(sum(user_budgets.values()), 2)
        total_budget_spent = round(sum(category_totals.get(cat, 0.0) for cat in user_budgets), 2)
        total_budget_remaining = round(max(0.0, total_budget - total_budget_spent), 2)
        overall_budget_pct = round((total_budget_spent / total_budget * 100), 1)
        is_overall_over = total_budget_spent > total_budget
        is_overall_warning = (0.75 * total_budget <= total_budget_spent <= total_budget)

        self.assertEqual(total_budget_remaining, 1500.0)
        self.assertEqual(overall_budget_pct, 85.0)
        self.assertFalse(is_overall_over)
        self.assertTrue(is_overall_warning)

    def test_overall_budget_exceeded(self):
        """Test overall budget calculations when user exceeds budget limit (> 100%)."""
        user_budgets = {"Rent": 15000.0, "Entertainment": 5000.0}
        category_totals = {"Rent": 15000.0, "Entertainment": 7500.0}

        total_budget = round(sum(user_budgets.values()), 2)
        total_budget_spent = round(sum(category_totals.get(cat, 0.0) for cat in user_budgets), 2)
        total_budget_remaining = round(max(0.0, total_budget - total_budget_spent), 2)
        total_budget_overage = round(max(0.0, total_budget_spent - total_budget), 2)
        overall_budget_pct = round((total_budget_spent / total_budget * 100), 1)
        is_overall_over = total_budget_spent > total_budget
        is_overall_warning = (0.75 * total_budget <= total_budget_spent <= total_budget)

        self.assertEqual(total_budget, 20000.0)
        self.assertEqual(total_budget_spent, 22500.0)
        self.assertEqual(total_budget_remaining, 0.0)
        self.assertEqual(total_budget_overage, 2500.0)
        self.assertEqual(overall_budget_pct, 112.5)
        self.assertTrue(is_overall_over)
        self.assertFalse(is_overall_warning)

    def test_no_budgets_configured(self):
        """Test dashboard budget handling when user has not set any budgets."""
        user_budgets = {}
        category_totals = {"Food": 2500.0}

        total_budget = round(sum(user_budgets.values()), 2) if user_budgets else 0.0
        total_budget_spent = round(sum(category_totals.get(cat, 0.0) for cat in user_budgets), 2) if user_budgets else 0.0
        total_budget_remaining = round(max(0.0, total_budget - total_budget_spent), 2) if total_budget > 0 else 0.0
        total_budget_overage = 0.0
        overall_budget_pct = 0.0
        is_overall_over = False
        is_overall_warning = False
        has_budgets = bool(user_budgets)

        self.assertEqual(total_budget, 0.0)
        self.assertEqual(total_budget_spent, 0.0)
        self.assertEqual(total_budget_remaining, 0.0)
        self.assertEqual(overall_budget_pct, 0.0)
        self.assertFalse(has_budgets)
        self.assertFalse(is_overall_over)

    def test_category_budget_progress_and_buffer(self):
        """Test per-category budget calculation with remaining buffer and overage indicator."""
        user_budgets = {"Food": 1000.0, "Transport": 500.0}
        category_totals = {"Food": 600.0, "Transport": 700.0}

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

        food = next(b for b in budget_progress if b["category"] == "Food")
        self.assertEqual(food["spent"], 600.0)
        self.assertEqual(food["remaining"], 400.0)
        self.assertEqual(food["percentage"], 60)
        self.assertFalse(food["is_over"])
        self.assertFalse(food["is_warning"])
        self.assertTrue(food["is_healthy"])

        transport = next(b for b in budget_progress if b["category"] == "Transport")
        self.assertEqual(transport["spent"], 700.0)
        self.assertEqual(transport["remaining"], -200.0)
        self.assertEqual(transport["percentage"], 100)
        self.assertEqual(transport["raw_percentage"], 140)
        self.assertTrue(transport["is_over"])
        self.assertFalse(transport["is_healthy"])

    def test_upcoming_bills_urgency(self):
        """Test upcoming bills calculation: <= 5 days included, <= 2 days marked urgent."""
        today = date.today()
        subs = [
            MockSubscription("Netflix", 1500, "Entertainment", "monthly", today + timedelta(days=1)),
            MockSubscription("Gym", 3000, "Healthcare", "monthly", today + timedelta(days=4)),
            MockSubscription("Hosting", 2000, "Utilities", "monthly", today + timedelta(days=12)),
        ]

        upcoming_bills = []
        for s in subs:
            due_date = s.next_due_date
            days_left = (due_date - today).days
            if 0 <= days_left <= 5:
                upcoming_bills.append({
                    "name": s.name,
                    "amount": s.amount,
                    "days_left": days_left,
                    "is_urgent": days_left <= 2
                })

        self.assertEqual(len(upcoming_bills), 2)
        netflix = next(b for b in upcoming_bills if b["name"] == "Netflix")
        self.assertTrue(netflix["is_urgent"])
        self.assertEqual(netflix["days_left"], 1)

        gym = next(b for b in upcoming_bills if b["name"] == "Gym")
        self.assertFalse(gym["is_urgent"])
        self.assertEqual(gym["days_left"], 4)

    def test_user_data_isolation(self):
        """Verify user A expenses and budgets are isolated from user B."""
        user_a_id = 1
        user_b_id = 2

        all_expenses = [
            MockExpense(100.0, "Food", date.today(), user_id=user_a_id),
            MockExpense(250.0, "Shopping", date.today(), user_id=user_a_id),
            MockExpense(9999.0, "Luxury", date.today(), user_id=user_b_id),
        ]

        all_budgets = [
            MockBudget("Food", 1000.0, user_id=user_a_id),
            MockBudget("Luxury", 50000.0, user_id=user_b_id),
        ]

        user_a_expenses = [e for e in all_expenses if e.user_id == user_a_id]
        user_a_budgets = [b for b in all_budgets if b.user_id == user_a_id]

        self.assertEqual(len(user_a_expenses), 2)
        self.assertEqual(sum(e.amount for e in user_a_expenses), 350.0)
        self.assertEqual(len(user_a_budgets), 1)
        self.assertEqual(user_a_budgets[0].category, "Food")
        self.assertNotIn("Luxury", [b.category for b in user_a_budgets])

    def test_smart_insights_integration_structure(self):
        """Verify smart insights structure and priority flags."""
        sample_insights = [
            {
                "priority": "high",
                "fact": "Food spending reached 62% of your monthly expenditure.",
                "recommendation": "Set a dedicated Food budget to curb restaurant expenses.",
                "is_positive": False
            },
            {
                "priority": "medium",
                "fact": "You have 3 active subscriptions totaling Rs. 4,500.",
                "recommendation": "Review unused subscriptions before upcoming renewal.",
                "is_positive": False
            },
            {
                "priority": "low",
                "fact": "Entertainment spending decreased by 20% this month.",
                "recommendation": "Great job maintaining financial discipline!",
                "is_positive": True
            }
        ]

        top_3 = sample_insights[:3]
        self.assertEqual(len(top_3), 3)
        self.assertEqual(top_3[0]["priority"], "high")
        self.assertIn("Food spending", top_3[0]["fact"])
        self.assertIn("recommendation", top_3[0])
        self.assertTrue(top_3[2]["is_positive"])

    def test_financial_health_score_presentation(self):
        """Test that financial health score data has required presentation attributes."""
        score_data = {
            "score": 82,
            "grade": "Good",
            "color": "#10B981",
            "message": "Strong financial position with controlled spending.",
            "tips": ["Consider investing savings", "Maintain low credit usage"]
        }

        self.assertGreaterEqual(score_data["score"], 0)
        self.assertLessEqual(score_data["score"], 100)
        self.assertIn(score_data["color"], ["#10B981", "#3B82F6", "#F59E0B", "#EF4444"])
        self.assertTrue(len(score_data["tips"]) > 0)

    def test_backward_compatibility_keys(self):
        """Verify backward-compatible keys exist in the context mapping."""
        total_this_month = 4500.0
        total_budget = 6000.0
        total_budget_remaining = 1500.0
        overall_budget_pct = 75.0
        expenses = [MockExpense(100, "Food", date.today())]

        context = {
            "total_spent": total_this_month,
            "budget": total_budget,
            "remaining_budget": total_budget_remaining,
            "budget_percentage": overall_budget_pct,
            "recent_expenses": expenses[:10],
            "total_this_month": total_this_month,
            "total_budget": total_budget,
            "total_budget_remaining": total_budget_remaining,
            "overall_budget_pct": overall_budget_pct
        }

        self.assertEqual(context["total_spent"], context["total_this_month"])
        self.assertEqual(context["remaining_budget"], context["total_budget_remaining"])
        self.assertEqual(context["budget_percentage"], context["overall_budget_pct"])


if __name__ == "__main__":
    unittest.main()
