import os
import sys
import types
import unittest
from unittest.mock import patch
import importlib.util

# ─── Module bootstrap ──────────────────────────────────────────────────────────
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

sort_products    = shopping_service.sort_products
filter_products  = shopping_service.filter_products
select_best_deal = shopping_service.select_best_deal
apply_sorting_and_badges = shopping_service.apply_sorting_and_badges


# ─── Shared test fixtures ───────────────────────────────────────────────────────

def make_sample_products():
    """Return a fresh list of diverse product dicts for sorting tests."""
    return [
        {
            "id": 1,
            "title": "Alpha Earbuds",
            "source": "Daraz",
            "price_val": 5000.0,
            "price": "Rs. 5,000",
            "savings_amount": 2000,
            "savings_pct": 28.6,
            "savings_str": "Save Rs. 2,000 (28.6% off)",
            "discount_val": 28,
            "is_best_deal": False,
            "rating": 4.5,
        },
        {
            "id": 2,
            "title": "Beta Earbuds",
            "source": "Amazon",
            "price_val": 1500.0,
            "price": "Rs. 1,500",
            "savings_amount": 500,
            "savings_pct": 25.0,
            "savings_str": "Save Rs. 500 (25.0% off)",
            "discount_val": 25,
            "is_best_deal": True,
            "rating": 4.8,
        },
        {
            "id": 3,
            "title": "Gamma Earbuds",
            "source": "AliExpress",
            "price_val": 20000.0,
            "price": "Rs. 20,000",
            "savings_amount": 8000,
            "savings_pct": 28.6,
            "savings_str": "Save Rs. 8,000 (28.6% off)",
            "discount_val": 28,
            "is_best_deal": False,
            "rating": 4.2,
        },
        {
            "id": 4,
            "title": "Delta Earbuds",
            "source": "Walmart",
            "price_val": 300.0,
            "price": "Rs. 300",
            "savings_amount": None,
            "savings_pct": None,
            "savings_str": None,
            "discount_val": None,
            "is_best_deal": False,
            "rating": 3.9,
        },
    ]


class TestBetterSorting(unittest.TestCase):
    """Feature #9 — Better Sorting: comprehensive unit & integration tests."""

    def test_sort_by_price_low_to_high(self):
        """Price: Low to High puts smallest valid price first."""
        products = make_sample_products()
        result = sort_products(products, "price_low")
        prices = [p["price_val"] for p in result]
        self.assertEqual(prices, [300.0, 1500.0, 5000.0, 20000.0])

    def test_sort_by_price_high_to_low(self):
        """Price: High to Low puts largest valid price first."""
        products = make_sample_products()
        result = sort_products(products, "price_high")
        prices = [p["price_val"] for p in result]
        self.assertEqual(prices, [20000.0, 5000.0, 1500.0, 300.0])

    def test_sort_by_highest_discount(self):
        """Highest Discount sorts by verified discount percentage descending."""
        products = [
            {"title": "D10", "discount_val": 10},
            {"title": "D20", "discount_val": 20},
            {"title": "D5",  "discount_val": 5},
            {"title": "D15", "savings_pct": 15.0},
        ]
        result = sort_products(products, "discount_high")
        titles = [p["title"] for p in result]
        self.assertEqual(titles, ["D20", "D15", "D10", "D5"])

    def test_sort_by_highest_savings(self):
        """Highest Savings sorts by verified savings_amount descending."""
        products = [
            {"title": "S5k",  "savings_amount": 5000},
            {"title": "S20k", "savings_amount": 20000},
            {"title": "S15k", "savings_amount": 15000},
            {"title": "S0",   "savings_amount": None},
        ]
        result = sort_products(products, "savings_high")
        titles = [p["title"] for p in result]
        self.assertEqual(titles, ["S20k", "S15k", "S5k", "S0"])

    def test_sort_best_deal_first(self):
        """Best Deal First places the product with is_best_deal=True first."""
        products = [
            {"title": "Item A", "is_best_deal": False},
            {"title": "Item B", "is_best_deal": True},
            {"title": "Item C", "is_best_deal": False},
        ]
        result = sort_products(products, "best_deal")
        self.assertEqual(result[0]["title"], "Item B")
        self.assertTrue(result[0]["is_best_deal"])
        # Remaining items retain relative order
        self.assertEqual(result[1]["title"], "Item A")
        self.assertEqual(result[2]["title"], "Item C")

    def test_missing_price_sorted_safely(self):
        """Products with missing/None price are placed at the end, not treated as 0."""
        products = [
            {"title": "No Price", "price_val": None},
            {"title": "Expensive", "price_val": 10000.0},
            {"title": "Cheap", "price_val": 200.0},
        ]
        # Low to High
        res_asc = sort_products(products, "price_low")
        self.assertEqual([p["title"] for p in res_asc], ["Cheap", "Expensive", "No Price"])

        # High to Low
        res_desc = sort_products(products, "price_high")
        self.assertEqual([p["title"] for p in res_desc], ["Expensive", "Cheap", "No Price"])

    def test_invalid_price_sorted_safely(self):
        """Products with zero, negative, or malformed prices placed safely at the end."""
        products = [
            {"title": "Zero Price", "price_val": 0.0},
            {"title": "Negative Price", "price_val": -50.0},
            {"title": "Malformed Price", "price_val": "invalid", "price": "Contact Store"},
            {"title": "Valid Cheap", "price_val": 150.0},
            {"title": "Valid Mid", "price_val": 800.0},
        ]
        res_asc = sort_products(products, "price_low")
        self.assertEqual(res_asc[0]["title"], "Valid Cheap")
        self.assertEqual(res_asc[1]["title"], "Valid Mid")
        # All 3 invalid items at the end
        invalid_titles = [p["title"] for p in res_asc[2:]]
        self.assertIn("Zero Price", invalid_titles)
        self.assertIn("Negative Price", invalid_titles)
        self.assertIn("Malformed Price", invalid_titles)

        # High to Low
        res_desc = sort_products(products, "price_high")
        self.assertEqual(res_desc[0]["title"], "Valid Mid")
        self.assertEqual(res_desc[1]["title"], "Valid Cheap")
        invalid_desc_titles = [p["title"] for p in res_desc[2:]]
        self.assertIn("Zero Price", invalid_desc_titles)
        self.assertIn("Negative Price", invalid_desc_titles)
        self.assertIn("Malformed Price", invalid_desc_titles)

    def test_missing_discount_sorted_safely(self):
        """Products without valid discount placed after products with valid discounts."""
        products = [
            {"title": "No Discount 1", "discount_val": None, "savings_pct": None},
            {"title": "Has 10%", "discount_val": 10},
            {"title": "No Discount 2", "discount": "No discount"},
            {"title": "Has 30%", "savings_pct": 30.0},
        ]
        result = sort_products(products, "discount_high")
        self.assertEqual(result[0]["title"], "Has 30%")
        self.assertEqual(result[1]["title"], "Has 10%")
        self.assertIn(result[2]["title"], ["No Discount 1", "No Discount 2"])
        self.assertIn(result[3]["title"], ["No Discount 1", "No Discount 2"])

    def test_missing_savings_sorted_safely(self):
        """Products without valid savings placed after products with valid savings."""
        products = [
            {"title": "No Savings", "savings_amount": None},
            {"title": "Save 500", "savings_amount": 500},
            {"title": "Save 1500", "savings_amount": 1500},
        ]
        result = sort_products(products, "savings_high")
        self.assertEqual([p["title"] for p in result], ["Save 1500", "Save 500", "No Savings"])

    def test_default_order_preserved(self):
        """Relevance / default sort preserves exact original search order."""
        products = make_sample_products()
        original_titles = [p["title"] for p in products]

        res_rel = sort_products(products, "relevance")
        self.assertEqual([p["title"] for p in res_rel], original_titles)

        res_def = sort_products(products, "default")
        self.assertEqual([p["title"] for p in res_def], original_titles)

        res_none = sort_products(products, None)
        self.assertEqual([p["title"] for p in res_none], original_titles)

    def test_sorting_after_filters(self):
        """Filtered products are sorted correctly according to selected sort option."""
        products = make_sample_products()
        # Filter products <= 6000 (Alpha: 5000, Beta: 1500, Delta: 300)
        filtered = filter_products(products, max_price=6000)
        self.assertEqual(len(filtered), 3)

        # Sort filtered by price high to low
        sorted_res = sort_products(filtered, "price_high")
        titles = [p["title"] for p in sorted_res]
        self.assertEqual(titles, ["Alpha Earbuds", "Beta Earbuds", "Delta Earbuds"])

    def test_sorting_does_not_reset_filters(self):
        """Applying sort to filtered products does not bring back excluded products."""
        products = make_sample_products()
        filtered = filter_products(products, stores=["Daraz"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["source"], "Daraz")

        # Sort by price low
        sorted_res = sort_products(filtered, "price_low")
        self.assertEqual(len(sorted_res), 1)
        self.assertEqual(sorted_res[0]["title"], "Alpha Earbuds")

    def test_sorting_does_not_trigger_new_search(self):
        """Sorting does not invoke SerpAPI or any network search function."""
        products = make_sample_products()
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_serp:
            sort_products(products, "price_low")
            sort_products(products, "price_high")
            sort_products(products, "discount_high")
            sort_products(products, "savings_high")
            sort_products(products, "best_deal")
            mock_serp.assert_not_called()

    def test_stable_sorting(self):
        """Items with identical sort values preserve their original relative order."""
        products = [
            {"id": 1, "title": "Item A", "price_val": 1000.0},
            {"id": 2, "title": "Item B", "price_val": 500.0},
            {"id": 3, "title": "Item C", "price_val": 1000.0},
            {"id": 4, "title": "Item D", "price_val": 1000.0},
        ]
        result = sort_products(products, "price_low")
        # Item B (500) first, then A, C, D in their original sequence
        self.assertEqual(result[0]["title"], "Item B")
        self.assertEqual([p["id"] for p in result[1:]], [1, 3, 4])

    def test_empty_results_do_not_crash(self):
        """Empty list, None, and non-list inputs are handled safely without crashing."""
        self.assertEqual(sort_products([]), [])
        self.assertEqual(sort_products(None), [])
        self.assertEqual(sort_products("not-a-list"), [])

    def test_best_deal_flag_preserved(self):
        """is_best_deal flag remains True on the designated product after sorting."""
        products = make_sample_products()
        for sort_opt in ["price_low", "price_high", "discount_high", "savings_high", "relevance"]:
            sorted_res = sort_products(products, sort_opt)
            best_items = [p for p in sorted_res if p.get("is_best_deal")]
            self.assertEqual(len(best_items), 1)
            self.assertEqual(best_items[0]["title"], "Beta Earbuds")

    def test_savings_data_preserved(self):
        """Feature #7 savings fields (savings_amount, savings_pct, savings_str) are preserved."""
        products = make_sample_products()
        sorted_res = sort_products(products, "price_low")
        alpha = next(p for p in sorted_res if p["title"] == "Alpha Earbuds")
        self.assertEqual(alpha["savings_amount"], 2000)
        self.assertEqual(alpha["savings_pct"], 28.6)
        self.assertEqual(alpha["savings_str"], "Save Rs. 2,000 (28.6% off)")

    def test_no_best_deal_retains_default_order(self):
        """When no product is best deal, 'best_deal' sort preserves default order."""
        products = [
            {"title": "P1", "is_best_deal": False},
            {"title": "P2", "is_best_deal": False},
            {"title": "P3", "is_best_deal": False},
        ]
        result = sort_products(products, "best_deal")
        self.assertEqual([p["title"] for p in result], ["P1", "P2", "P3"])

    def test_apply_sorting_and_badges_mutates_in_place(self):
        """apply_sorting_and_badges updates list in-place and assigns badges."""
        products = make_sample_products()
        apply_sorting_and_badges(products, "price_low")
        self.assertEqual(products[0]["price_val"], 300.0)
        self.assertEqual(products[0]["badge"], "🔥 Lowest Price Deal")
        self.assertTrue(products[0]["is_best_price"])


if __name__ == "__main__":
    unittest.main()
