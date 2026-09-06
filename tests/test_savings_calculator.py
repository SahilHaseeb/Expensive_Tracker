import os
import sys
import types
import unittest
from unittest.mock import patch
import importlib.util

# ─── Module bootstrap (mirrors test_best_deal.py setup) ─────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if "app" not in sys.modules:
    sys.modules["app"] = types.ModuleType("app")

spec = importlib.util.spec_from_file_location(
    "shopping_service",
    os.path.join(ROOT_DIR, "app", "shopping_service.py")
)
shopping_service = importlib.util.module_from_spec(spec)
sys.modules["app.shopping_service"] = shopping_service
spec.loader.exec_module(shopping_service)

calculate_savings        = shopping_service.calculate_savings
select_best_deal         = shopping_service.select_best_deal
_process_serpapi_results = shopping_service._process_serpapi_results


class TestSavingsCalculator(unittest.TestCase):
    """Feature #7 — Savings Calculator: unit & integration tests."""

    # ── 1. Savings amount ──────────────────────────────────────────────

    def test_savings_amount_calculation(self):
        """savings_amount = original_price - current_price, rounded per currency."""
        # Non-decimal currency (Rs.) -> rounded to nearest integer
        result = calculate_savings(2499.0, 3000.0, "Rs.")
        self.assertIsNotNone(result)
        self.assertEqual(result["savings_amount"], 501)        # round(3000-2499)

        # Decimal currency ($) -> rounded to 2 dp
        result_usd = calculate_savings(79.99, 99.99, "$")
        self.assertIsNotNone(result_usd)
        self.assertAlmostEqual(result_usd["savings_amount"], 20.0, places=2)

        # Euro (€) also decimal
        result_eur = calculate_savings(50.0, 75.0, "€")
        self.assertIsNotNone(result_eur)
        self.assertAlmostEqual(result_eur["savings_amount"], 25.0, places=2)

    # ── 2. Savings percentage ──────────────────────────────────────────

    def test_savings_percentage_calculation(self):
        """savings_pct = (savings / original) x 100, rounded to 1 decimal."""
        # 500 off from 3000 = 16.666...% -> 16.7%
        result = calculate_savings(2500.0, 3000.0, "Rs.")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["savings_pct"], 16.7, places=1)

        # 20 off from 100 = 20.0%
        result2 = calculate_savings(80.0, 100.0, "$")
        self.assertIsNotNone(result2)
        self.assertAlmostEqual(result2["savings_pct"], 20.0, places=1)

        # 1 off from 4 = 25.0%
        result3 = calculate_savings(3.0, 4.0, "£")
        self.assertIsNotNone(result3)
        self.assertAlmostEqual(result3["savings_pct"], 25.0, places=1)

    # ── 3. Missing original price ───────────────────────────────────────────

    def test_no_savings_when_original_price_missing(self):
        """Returns None when original_price_val is None."""
        self.assertIsNone(calculate_savings(2000.0, None, "Rs."))
        self.assertIsNone(calculate_savings(2000.0, None, "$"))

    # ── 4. Missing current price ───────────────────────────────────────────

    def test_no_savings_when_current_price_missing(self):
        """Returns None when price_val is None."""
        self.assertIsNone(calculate_savings(None, 3000.0, "Rs."))
        self.assertIsNone(calculate_savings(None, 3000.0, "$"))

    # ── 5. Original not greater than current ────────────────────────────────────

    def test_no_savings_when_original_price_not_greater(self):
        """Returns None when original <= current (no genuine saving)."""
        self.assertIsNone(calculate_savings(2000.0, 2000.0, "Rs."))   # equal
        self.assertIsNone(calculate_savings(3000.0, 2500.0, "Rs."))   # original < current
        self.assertIsNone(calculate_savings(100.0, 80.0, "$"))

    # ── 6. Zero original price ─────────────────────────────────────────────────

    def test_zero_original_price_does_not_crash(self):
        """Returns None (not an exception) when original_price_val is zero."""
        self.assertIsNone(calculate_savings(2000.0, 0, "Rs."))
        self.assertIsNone(calculate_savings(2000.0, 0.0, "$"))

    # ── 7. Invalid / non-numeric price ────────────────────────────────────────

    def test_invalid_price_does_not_crash(self):
        """Never raises an exception on non-numeric input; always returns None."""
        self.assertIsNone(calculate_savings("not a price", 3000.0, "Rs."))
        self.assertIsNone(calculate_savings(2000.0, "call for price", "Rs."))
        self.assertIsNone(calculate_savings(None, None, "Rs."))
        self.assertIsNone(calculate_savings(-100.0, 3000.0, "Rs."))   # negative current
        self.assertIsNone(calculate_savings(2000.0, -500.0, "Rs."))   # negative original

    # ── 8. Currency is preserved ────────────────────────────────────────────

    def test_currency_is_preserved(self):
        """savings_str uses the same currency symbol passed to calculate_savings()."""
        for symbol in ("$", "€", "£"):
            result = calculate_savings(80.0, 100.0, symbol)
            self.assertIsNotNone(result)
            self.assertIn(symbol, result["savings_str"])
            self.assertNotIn("Rs.", result["savings_str"])

        result_pkr = calculate_savings(2500.0, 3000.0, "Rs.")
        self.assertIsNotNone(result_pkr)
        self.assertIn("Rs.", result_pkr["savings_str"])
        self.assertNotIn("$", result_pkr["savings_str"])

        result_inr = calculate_savings(800.0, 1000.0, "₹")
        self.assertIsNotNone(result_inr)
        self.assertIn("₹", result_inr["savings_str"])

    # ── 9. Savings fields present in processed product ──────────────────────────

    def test_savings_data_returned_in_product(self):
        """savings_amount, savings_pct, savings_str are always present in products."""
        mock_with_old_price = [{
            "title": "Test Phone With Old Price",
            "source": "Daraz",
            "extracted_price": 35000,
            "extracted_old_price": 42000,   # real original price from SerpAPI
            "price": "Rs. 35,000",
            "link": "https://www.daraz.pk/test-phone",
            "thumbnail": "https://img.daraz.pk/phone.jpg",
            "rating": 4.5,
            "reviews": 200,
        }]
        products = _process_serpapi_results(mock_with_old_price, "test phone", "Rs.")
        self.assertEqual(len(products), 1)
        p = products[0]

        # All three savings keys must be present
        self.assertIn("savings_amount", p)
        self.assertIn("savings_pct", p)
        self.assertIn("savings_str", p)

        # With genuine old price (42000 > 35000), savings must be valid
        self.assertIsNotNone(p["savings_amount"])
        self.assertIsNotNone(p["savings_pct"])
        self.assertIsNotNone(p["savings_str"])
        self.assertGreater(p["savings_amount"], 0)
        self.assertIn("Save", p["savings_str"])

    # ── 10. Best Deal + Savings coexist ──────────────────────────────────────

    def test_best_deal_and_savings_work_together(self):
        """A product can simultaneously carry is_best_deal=True and valid savings."""
        products = [
            {
                "title": "Cheapest With Savings",
                "source": "Amazon",
                "price_val": 2000.0,
                "savings_amount": 500,
                "savings_pct": 20.0,
                "savings_str": "Save Rs. 500 (20.0% off)",
                "is_best_deal": False,
                "delivery": "Free Delivery",
            },
            {
                "title": "More Expensive No Savings",
                "source": "Daraz",
                "price_val": 3500.0,
                "savings_amount": None,
                "savings_pct": None,
                "savings_str": None,
                "is_best_deal": False,
                "delivery": "Standard Delivery",
            },
        ]
        select_best_deal(products)

        best = [p for p in products if p.get("is_best_deal")]
        self.assertEqual(len(best), 1)
        self.assertEqual(best[0]["title"], "Cheapest With Savings")

        # Savings data stays intact on the best deal product
        self.assertEqual(best[0]["savings_amount"], 500)
        self.assertIn("Save", best[0]["savings_str"])

        # Non-best product keeps savings_str=None (no fabrication)
        others = [p for p in products if not p.get("is_best_deal")]
        self.assertIsNone(others[0]["savings_str"])

    # ── 11. No fake discount when original price absent ─────────────────────────

    def test_products_without_savings_do_not_show_fake_discount(self):
        """When SerpAPI returns no old_price/extracted_old_price, savings are None."""
        mock_no_old_price = [{
            "title": "No Original Price Item",
            "source": "Amazon",
            "extracted_price": 5000,
            "price": "Rs. 5,000",
            # intentionally NO old_price / extracted_old_price
            "link": "https://www.amazon.com/test",
            "thumbnail": "https://img.amazon.com/test.jpg",
            "rating": 4.2,
            "reviews": 80,
        }]
        products = _process_serpapi_results(mock_no_old_price, "item", "Rs.")
        self.assertEqual(len(products), 1)
        p = products[0]

        # All savings fields must be None -- no fabricated savings
        self.assertIsNone(p["savings_amount"])
        self.assertIsNone(p["savings_pct"])
        self.assertIsNone(p["savings_str"])


class TestSavingsCalculatorEdgeCases(unittest.TestCase):
    """Additional edge-case coverage for calculate_savings()."""

    def test_savings_str_is_clean_for_integer_currency(self):
        """savings_str for Rs. must show a clean integer amount, no trailing decimals."""
        result = calculate_savings(2499.0, 3000.0, "Rs.")
        self.assertIsNotNone(result)
        # The amount portion after 'Rs.' should not contain a decimal point
        amount_part = result["savings_str"].split("Rs. ")[1].split(" ")[0].replace(",", "")
        self.assertNotIn(".", amount_part)

    def test_savings_str_has_decimals_for_usd(self):
        """savings_str for $ uses 2 decimal places."""
        result = calculate_savings(79.99, 99.99, "$")
        self.assertIsNotNone(result)
        amount_part = result["savings_str"].split("$ ")[1].split(" ")[0].replace(",", "")
        self.assertIn(".", amount_part)

    def test_old_price_string_field_is_used(self):
        """old_price string field (not just extracted_old_price) also yields savings."""
        mock_with_old_price_str = [{
            "title": "Item With String Old Price",
            "source": "eBay",
            "extracted_price": 60,
            "price": "$ 60",
            "old_price": "$ 80",   # string-only original price
            "link": "https://www.ebay.com/itm/123",
            "thumbnail": "https://img.ebay.com/item.jpg",
        }]
        products = _process_serpapi_results(mock_with_old_price_str, "item", "$")
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertIsNotNone(p["savings_str"])
        self.assertIn("Save", p["savings_str"])
        self.assertGreater(p["savings_amount"], 0)

    def test_empty_product_list_does_not_crash(self):
        """An empty SerpAPI result list returns an empty product list without error."""
        products = _process_serpapi_results([], "item", "Rs.")
        self.assertEqual(products, [])


if __name__ == "__main__":
    unittest.main()
