import os
import sys
import types
import unittest
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

filter_products  = shopping_service.filter_products
select_best_deal = shopping_service.select_best_deal


# ─── Shared test fixtures ───────────────────────────────────────────────────────

def make_products():
    """Return a fresh list of diverse product dicts for filter testing."""
    return [
        {
            "title": "Budget Phone",
            "source": "Daraz",
            "price_val": 15000.0,
            "savings_amount": 2000,
            "savings_pct": 11.8,
            "savings_str": "Save Rs. 2,000 (11.8% off)",
            "discount_val": 12,
            "is_best_deal": False,
            "delivery": "Free Delivery",
        },
        {
            "title": "Mid-Range Phone",
            "source": "Amazon",
            "price_val": 45000.0,
            "savings_amount": None,
            "savings_pct": None,
            "savings_str": None,
            "discount_val": 15,
            "is_best_deal": True,
            "delivery": "Standard Delivery",
        },
        {
            "title": "Premium Phone",
            "source": "Sephora",
            "price_val": 120000.0,
            "savings_amount": 10000,
            "savings_pct": 7.7,
            "savings_str": "Save Rs. 10,000 (7.7% off)",
            "discount_val": 10,
            "is_best_deal": False,
            "delivery": "Available on Sephora",
        },
        {
            "title": "Out of Stock Item",
            "source": "eBay",
            "price_val": 30000.0,
            "savings_amount": None,
            "savings_pct": None,
            "savings_str": None,
            "discount_val": 5,
            "is_best_deal": False,
            "delivery": "Out of Stock",
        },
        {
            "title": "No Price Item",
            "source": "Daraz",
            "price_val": 0.0,
            "savings_amount": None,
            "savings_pct": None,
            "savings_str": None,
            "discount_val": None,
            "is_best_deal": False,
            "delivery": "Contact seller",
        },
    ]


class TestAdvancedFilters(unittest.TestCase):
    """Feature #8 — Advanced Filters: unit tests for filter_products()."""

    # ── 1. Price range ───────────────────────────────────────────────────

    def test_price_range_filter(self):
        """Products whose price_val is outside [min, max] are excluded."""
        products = make_products()
        result = filter_products(products, min_price=10000, max_price=50000)
        titles = [p["title"] for p in result]
        self.assertIn("Budget Phone", titles)       # 15000 in range
        self.assertIn("Mid-Range Phone", titles)    # 45000 in range
        self.assertNotIn("Premium Phone", titles)   # 120000 > max
        # Out-of-Stock has price 30000 (in range) but no savings
        self.assertIn("Out of Stock Item", titles)
        # No Price Item has price_val=0 -> missing -> fails
        self.assertNotIn("No Price Item", titles)

    def test_minimum_price_filter(self):
        """Only min_price set: excludes products cheaper than threshold."""
        products = make_products()
        result = filter_products(products, min_price=40000)
        titles = [p["title"] for p in result]
        self.assertNotIn("Budget Phone", titles)    # 15000 < 40000
        self.assertIn("Mid-Range Phone", titles)    # 45000 >= 40000
        self.assertIn("Premium Phone", titles)      # 120000 >= 40000

    def test_maximum_price_filter(self):
        """Only max_price set: excludes products more expensive than threshold."""
        products = make_products()
        result = filter_products(products, max_price=50000)
        titles = [p["title"] for p in result]
        self.assertIn("Budget Phone", titles)       # 15000 <= 50000
        self.assertIn("Mid-Range Phone", titles)    # 45000 <= 50000
        self.assertNotIn("Premium Phone", titles)   # 120000 > 50000

    # ── 2. Store filter ─────────────────────────────────────────────────

    def test_store_filter(self):
        """Filtering by a single store returns only products from that store."""
        products = make_products()
        result = filter_products(products, stores=["daraz"])
        self.assertTrue(all(p["source"].lower() == "daraz" for p in result))
        self.assertGreater(len(result), 0)

    def test_multiple_store_filter(self):
        """Multiple stores use OR logic: product from ANY selected store passes."""
        products = make_products()
        result = filter_products(products, stores=["daraz", "amazon"])
        titles = [p["title"] for p in result]
        self.assertIn("Budget Phone", titles)       # Daraz
        self.assertIn("Mid-Range Phone", titles)    # Amazon
        self.assertNotIn("Premium Phone", titles)   # Sephora
        self.assertNotIn("Out of Stock Item", titles)  # eBay

    # ── 3. Discount filter ──────────────────────────────────────────────

    def test_discount_filter(self):
        """Products with discount < min_discount are excluded."""
        products = make_products()
        result = filter_products(products, min_discount=11)
        titles = [p["title"] for p in result]
        # Budget Phone: savings_pct=11.8 >= 11 -> passes
        self.assertIn("Budget Phone", titles)
        # Mid-Range: no savings_pct, falls back to discount_val=15 >= 11 -> passes
        self.assertIn("Mid-Range Phone", titles)
        # Premium Phone: savings_pct=7.7 < 11 -> fails
        self.assertNotIn("Premium Phone", titles)
        # No Price Item: discount_val=None -> fails
        self.assertNotIn("No Price Item", titles)

    # ── 4. Best Deal filter ─────────────────────────────────────────────

    def test_best_deal_filter(self):
        """best_deal_only=True returns exactly the one product with is_best_deal=True."""
        products = make_products()
        result = filter_products(products, best_deal_only=True)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["is_best_deal"])
        self.assertEqual(result[0]["title"], "Mid-Range Phone")

    # ── 5. Savings filter ─────────────────────────────────────────────

    def test_savings_filter(self):
        """Products whose savings_amount < min_savings (or None) are excluded."""
        products = make_products()
        result = filter_products(products, min_savings=5000)
        titles = [p["title"] for p in result]
        # Budget: 2000 < 5000 -> fails
        self.assertNotIn("Budget Phone", titles)
        # Premium: 10000 >= 5000 -> passes
        self.assertIn("Premium Phone", titles)
        # Mid-Range: savings_amount=None -> fails
        self.assertNotIn("Mid-Range Phone", titles)

    # ── 6. AND logic between categories ──────────────────────────────────

    def test_multiple_filters_use_and_logic(self):
        """All active filter categories must ALL pass (AND logic)."""
        products = make_products()
        # Store = Daraz AND min_price = 10000
        result = filter_products(products, stores=["daraz"], min_price=10000)
        titles = [p["title"] for p in result]
        self.assertIn("Budget Phone", titles)         # Daraz + price 15000 -> pass
        self.assertNotIn("Mid-Range Phone", titles)   # Amazon -> fails store
        self.assertNotIn("No Price Item", titles)      # price=0 -> fails price

    def test_multiple_stores_use_or_logic(self):
        """Within the stores filter, OR logic applies."""
        products = make_products()
        result = filter_products(products, stores=["daraz", "sephora"])
        titles = [p["title"] for p in result]
        # Daraz sources
        self.assertIn("Budget Phone", titles)
        # Sephora source
        self.assertIn("Premium Phone", titles)
        # Amazon source -> excluded
        self.assertNotIn("Mid-Range Phone", titles)

    # ── 7. Robustness: bad/missing data ──────────────────────────────────

    def test_invalid_price_does_not_crash(self):
        """Products with missing/invalid price_val never crash the filter."""
        bad = [
            {"title": "A", "price_val": None, "source": "X", "is_best_deal": False},
            {"title": "B", "price_val": "not a number", "source": "X", "is_best_deal": False},
            {"title": "C", "price_val": -500.0, "source": "X", "is_best_deal": False},
        ]
        # Should not raise; all fail the price filter cleanly
        result = filter_products(bad, min_price=100)
        self.assertEqual(result, [])

    def test_missing_discount_does_not_crash(self):
        """Product with no discount data silently fails the discount filter."""
        p = [{"title": "A", "price_val": 1000.0, "source": "X",
              "savings_pct": None, "discount_val": None, "is_best_deal": False}]
        result = filter_products(p, min_discount=5)
        self.assertEqual(result, [])

    def test_missing_store_does_not_crash(self):
        """Product with no source field silently fails the store filter."""
        p = [{"title": "A", "price_val": 1000.0, "is_best_deal": False}]
        result = filter_products(p, stores=["amazon"])
        self.assertEqual(result, [])

    # ── 8. Empty results ──────────────────────────────────────────────────

    def test_empty_filtered_results(self):
        """Returns an empty list (not None) when no products match."""
        products = make_products()
        result = filter_products(products, min_price=999999)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    # ── 9. Reset = no filters ─────────────────────────────────────────────

    def test_reset_filters(self):
        """With no active filters, all products are returned unchanged."""
        products = make_products()
        result = filter_products(products)   # all defaults = None/False
        self.assertEqual(len(result), len(products))

    # ── 10. Result count ────────────────────────────────────────────────

    def test_result_count_after_filtering(self):
        """len(filtered) accurately reflects how many products passed all filters."""
        products = make_products()
        # Only Daraz products with price >= 10000
        result = filter_products(products, stores=["daraz"], min_price=10000)
        # Budget Phone (Daraz, 15000) passes; No Price Item (Daraz, 0) fails
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Budget Phone")

    # ── 11. Best Deal flag preserved after filtering ───────────────────────

    def test_best_deal_flag_preserved_after_filtering(self):
        """is_best_deal is never modified by filter_products()."""
        products = make_products()
        # filter to just Amazon products
        result = filter_products(products, stores=["amazon"])
        amazon_prod = [p for p in result if p["source"] == "Amazon"]
        self.assertEqual(len(amazon_prod), 1)
        self.assertTrue(amazon_prod[0]["is_best_deal"],
                        "is_best_deal must be preserved as-is")

    # ── 12. Savings data preserved after filtering ──────────────────────

    def test_savings_data_preserved_after_filtering(self):
        """savings_amount / savings_pct / savings_str are never modified."""
        products = make_products()
        result = filter_products(products, stores=["daraz"])
        budget = [p for p in result if p["title"] == "Budget Phone"][0]
        self.assertEqual(budget["savings_amount"], 2000)
        self.assertAlmostEqual(budget["savings_pct"], 11.8, places=1)
        self.assertIn("Save", budget["savings_str"])


class TestAdvancedFiltersEdgeCases(unittest.TestCase):
    """Edge cases for filter_products()."""

    def test_empty_input_returns_empty_list(self):
        """Empty input always returns an empty list."""
        self.assertEqual(filter_products([]), [])
        self.assertEqual(filter_products(None), [])

    def test_non_dict_items_are_skipped(self):
        """Non-dict items in the list are silently skipped."""
        mixed = [
            {"title": "OK", "price_val": 5000.0, "source": "X", "is_best_deal": False},
            "not a dict",
            42,
            None,
        ]
        result = filter_products(mixed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "OK")

    def test_filter_does_not_mutate_original_list(self):
        """filter_products() must return a new list without modifying the input."""
        products = make_products()
        original_len = len(products)
        filter_products(products, min_price=50000)
        self.assertEqual(len(products), original_len,
                         "Original list must not be mutated")

    def test_in_stock_only_excludes_oos(self):
        """in_stock_only=True excludes products with out-of-stock delivery strings."""
        products = make_products()
        result = filter_products(products, in_stock_only=True)
        titles = [p["title"] for p in result]
        self.assertNotIn("Out of Stock Item", titles)
        self.assertIn("Budget Phone", titles)       # clearly in-stock
        self.assertIn("Mid-Range Phone", titles)

    def test_stores_empty_list_passes_all(self):
        """Passing an empty stores list is equivalent to no store filter."""
        products = make_products()
        result_all  = filter_products(products)
        result_empty = filter_products(products, stores=[])
        self.assertEqual(len(result_all), len(result_empty))


if __name__ == "__main__":
    unittest.main()
