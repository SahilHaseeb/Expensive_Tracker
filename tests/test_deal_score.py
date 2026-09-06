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

calculate_single_deal_score = shopping_service.calculate_single_deal_score
calculate_deal_scores       = shopping_service.calculate_deal_scores
sort_products               = shopping_service.sort_products
filter_products             = shopping_service.filter_products
select_best_deal            = shopping_service.select_best_deal
calculate_savings           = shopping_service.calculate_savings


# ─── Shared test fixtures ───────────────────────────────────────────────────────

def make_sample_products():
    """Return a fresh list of diverse product dicts for Deal Score testing."""
    return [
        {
            "id": 1,
            "title": "Alpha Earbuds",
            "source": "Daraz",
            "price_val": 2000.0,
            "price": "Rs. 2,000",
            "savings_amount": 1000,
            "savings_pct": 33.3,
            "savings_str": "Save Rs. 1,000 (33.3% off)",
            "discount_val": 33,
            "is_best_deal": False,
            "delivery": "Free Delivery",
            "rating": 4.5,
            "thumbnail": "https://example.com/alpha.jpg",
            "link": "https://daraz.pk/product/alpha",
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
            "delivery": "Standard Delivery",
            "rating": 4.8,
            "thumbnail": "https://example.com/beta.jpg",
            "link": "https://amazon.com/product/beta",
        },
        {
            "id": 3,
            "title": "Gamma Earbuds",
            "source": "AliExpress",
            "price_val": 8000.0,
            "price": "Rs. 8,000",
            "savings_amount": 4000,
            "savings_pct": 33.3,
            "savings_str": "Save Rs. 4,000 (33.3% off)",
            "discount_val": 33,
            "is_best_deal": False,
            "delivery": "Express Shipping",
            "rating": 4.2,
            "thumbnail": "https://example.com/gamma.jpg",
            "link": "https://aliexpress.com/product/gamma",
        },
        {
            "id": 4,
            "title": "Delta Earbuds",
            "source": "Walmart",
            "price_val": None,
            "price": "Price Unavailable",
            "savings_amount": None,
            "savings_pct": None,
            "savings_str": None,
            "discount_val": None,
            "is_best_deal": False,
            "delivery": "Out of Stock",
            "rating": 3.5,
            "thumbnail": "https://example.com/delta.jpg",
            "link": "https://walmart.com/product/delta",
        },
    ]


class TestDealScore(unittest.TestCase):
    """Feature #10 — Deal Score: 22 required unit and integration tests."""

    # 1. test_deal_score_exists_for_valid_offer()
    def test_deal_score_exists_for_valid_offer(self):
        """A valid offer with verified price receives a numeric Deal Score."""
        product = {"price_val": 2500.0, "source": "Daraz", "rating": 4.5}
        score = calculate_single_deal_score(product)
        self.assertIsNotNone(score)
        self.assertIsInstance(score, (int, float))

    # 2. test_deal_score_is_between_0_and_100()
    def test_deal_score_is_between_0_and_100(self):
        """Deal Score is always within the 0–100 scale."""
        products = make_sample_products()
        calculate_deal_scores(products)
        for p in products:
            if p["deal_score"] is not None:
                self.assertGreaterEqual(p["deal_score"], 0)
                self.assertLessEqual(p["deal_score"], 100)

    # 3. test_higher_discount_generally_improves_score()
    def test_higher_discount_generally_improves_score(self):
        """An offer with higher verified discount receives a higher score (ceteris paribus)."""
        p_low = {"price_val": 2000.0, "discount_val": 10, "source": "Store A"}
        p_high = {"price_val": 2000.0, "discount_val": 40, "source": "Store A"}
        score_low = calculate_single_deal_score(p_low)
        score_high = calculate_single_deal_score(p_high)
        self.assertGreater(score_high, score_low)

    # 4. test_lower_price_generally_improves_score()
    def test_lower_price_generally_improves_score(self):
        """In a returned offer batch, a lower valid price improves Deal Score."""
        products = [
            {"title": "Low Price", "price_val": 1000.0, "source": "Store A"},
            {"title": "High Price", "price_val": 5000.0, "source": "Store A"},
        ]
        calculate_deal_scores(products)
        self.assertGreater(products[0]["deal_score"], products[1]["deal_score"])

    # 5. test_higher_valid_savings_improves_score()
    def test_higher_valid_savings_improves_score(self):
        """An offer with higher verified savings amount improves Deal Score."""
        p_low = {"price_val": 3000.0, "savings_amount": 500, "source": "Store A"}
        p_high = {"price_val": 3000.0, "savings_amount": 3000, "source": "Store A"}
        score_low = calculate_single_deal_score(p_low)
        score_high = calculate_single_deal_score(p_high)
        self.assertGreater(score_high, score_low)

    # 6. test_missing_price_is_handled_safely()
    def test_missing_price_is_handled_safely(self):
        """Missing or None price returns None deal_score without crashing."""
        p = {"price_val": None, "source": "Store A"}
        score = calculate_single_deal_score(p)
        self.assertIsNone(score)

    # 7. test_missing_discount_is_handled_safely()
    def test_missing_discount_is_handled_safely(self):
        """Missing discount is handled with a neutral baseline and does not crash or zero the score."""
        p = {"price_val": 2000.0, "discount_val": None, "savings_pct": None, "source": "Store A"}
        score = calculate_single_deal_score(p)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    # 8. test_missing_savings_is_handled_safely()
    def test_missing_savings_is_handled_safely(self):
        """Missing savings is handled safely and produces a valid Deal Score."""
        p = {"price_val": 2000.0, "savings_amount": None, "source": "Store A"}
        score = calculate_single_deal_score(p)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    # 9. test_invalid_numeric_values_do_not_crash()
    def test_invalid_numeric_values_do_not_crash(self):
        """Non-numeric, zero, or negative numbers do not crash the calculator."""
        p = {
            "price_val": "invalid_price",
            "discount_val": -20,
            "savings_amount": "not_a_number",
            "rating": "five_stars"
        }
        score = calculate_single_deal_score(p)
        self.assertIsNone(score)

    # 10. test_missing_score_is_not_treated_as_zero_unless_valid()
    def test_missing_score_is_not_treated_as_zero_unless_valid(self):
        """When an offer lacks essential price data, deal_score is None, NOT 0."""
        products = [{"price_val": None, "source": "Store A"}]
        calculate_deal_scores(products)
        self.assertIsNone(products[0]["deal_score"])
        self.assertNotEqual(products[0]["deal_score"], 0)

    # 11. test_best_deal_flag_is_preserved()
    def test_best_deal_flag_is_preserved(self):
        """Calculating Deal Score never overwrites or alters the Feature #6 is_best_deal flag."""
        products = make_sample_products()
        select_best_deal(products)
        best_initial = next(p for p in products if p["is_best_deal"])
        best_title = best_initial["title"]

        calculate_deal_scores(products)
        best_after = next(p for p in products if p["is_best_deal"])
        self.assertEqual(best_after["title"], best_title)

    # 12. test_savings_calculation_is_preserved()
    def test_savings_calculation_is_preserved(self):
        """Feature #7 savings fields (savings_amount, savings_pct, savings_str) remain intact."""
        products = make_sample_products()
        calculate_deal_scores(products)
        alpha = next(p for p in products if p["title"] == "Alpha Earbuds")
        self.assertEqual(alpha["savings_amount"], 1000)
        self.assertEqual(alpha["savings_pct"], 33.3)
        self.assertEqual(alpha["savings_str"], "Save Rs. 1,000 (33.3% off)")

    # 13. test_deal_score_sorting_high_to_low()
    def test_deal_score_sorting_high_to_low(self):
        """Sorting by 'deal_score_high' orders highest Deal Score first."""
        products = [
            {"title": "C", "deal_score": 50},
            {"title": "A", "deal_score": 95},
            {"title": "B", "deal_score": 80},
        ]
        sorted_p = sort_products(products, "deal_score_high")
        self.assertEqual([p["title"] for p in sorted_p], ["A", "B", "C"])

    # 14. test_missing_scores_sort_after_valid_scores()
    def test_missing_scores_sort_after_valid_scores(self):
        """Offers with deal_score=None safely sort after all scored offers."""
        products = [
            {"title": "No Score 1", "deal_score": None},
            {"title": "Score 60",   "deal_score": 60},
            {"title": "Score 90",   "deal_score": 90},
            {"title": "No Score 2", "deal_score": None},
        ]
        sorted_p = sort_products(products, "deal_score_high")
        self.assertEqual(sorted_p[0]["title"], "Score 90")
        self.assertEqual(sorted_p[1]["title"], "Score 60")
        self.assertIn(sorted_p[2]["title"], ["No Score 1", "No Score 2"])
        self.assertIn(sorted_p[3]["title"], ["No Score 1", "No Score 2"])

    # 15. test_existing_price_sorting_still_works()
    def test_existing_price_sorting_still_works(self):
        """Feature #9 price sorting (low-to-high, high-to-low) remains functional with deal scores present."""
        products = make_sample_products()
        calculate_deal_scores(products)
        asc = sort_products(products, "price_low")
        self.assertEqual(asc[0]["title"], "Beta Earbuds")  # 1500

        desc = sort_products(products, "price_high")
        self.assertEqual(desc[0]["title"], "Gamma Earbuds") # 8000

    # 16. test_existing_discount_sorting_still_works()
    def test_existing_discount_sorting_still_works(self):
        """Feature #9 discount sorting remains functional with deal scores present."""
        products = make_sample_products()
        calculate_deal_scores(products)
        sorted_p = sort_products(products, "discount_high")
        self.assertIn(sorted_p[0]["title"], ["Alpha Earbuds", "Gamma Earbuds"])  # 33%

    # 17. test_existing_savings_sorting_still_works()
    def test_existing_savings_sorting_still_works(self):
        """Feature #9 savings sorting remains functional with deal scores present."""
        products = make_sample_products()
        calculate_deal_scores(products)
        sorted_p = sort_products(products, "savings_high")
        self.assertEqual(sorted_p[0]["title"], "Gamma Earbuds")  # 4000 savings

    # 18. test_filter_then_deal_score_sorting()
    def test_filter_then_deal_score_sorting(self):
        """Filtering products and then sorting by deal score works smoothly."""
        products = make_sample_products()
        calculate_deal_scores(products)
        # Filter products with price <= 5000 (Alpha: 2000, Beta: 1500)
        filtered = filter_products(products, max_price=5000)
        self.assertEqual(len(filtered), 2)

        sorted_res = sort_products(filtered, "deal_score_high")
        self.assertEqual(len(sorted_res), 2)
        self.assertGreaterEqual(sorted_res[0]["deal_score"], sorted_res[1]["deal_score"])

    # 19. test_sorting_does_not_trigger_new_api_request()
    def test_sorting_does_not_trigger_new_api_request(self):
        """Sorting by Deal Score does not make any external SerpAPI network calls."""
        products = make_sample_products()
        calculate_deal_scores(products)
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            sort_products(products, "deal_score_high")
            mock_fetch.assert_not_called()

    # 20. test_product_image_and_direct_link_are_preserved()
    def test_product_image_and_direct_link_are_preserved(self):
        """Thumbnail and direct retailer links remain 100% intact after score calculation & sorting."""
        products = make_sample_products()
        calculate_deal_scores(products)
        sorted_p = sort_products(products, "deal_score_high")
        for p in sorted_p:
            self.assertTrue(p["thumbnail"].startswith("https://example.com/"))
            self.assertTrue(p["link"].startswith("https://"))

    # 21. test_empty_results_do_not_crash()
    def test_empty_results_do_not_crash(self):
        """Empty or None lists are handled safely without errors."""
        self.assertEqual(calculate_deal_scores([]), [])
        self.assertEqual(calculate_deal_scores(None), [])
        self.assertEqual(sort_products([], "deal_score_high"), [])

    # 22. test_existing_features_remain_compatible()
    def test_existing_features_remain_compatible(self):
        """Features #6, #7, #8, #9, and #10 operate together harmoniously in a complete pipeline."""
        products = make_sample_products()
        # 1. Best Deal (#6)
        select_best_deal(products)
        # 2. Deal Score (#10)
        calculate_deal_scores(products)
        # 3. Advanced Filters (#8)
        filtered = filter_products(products, in_stock_only=True)
        # 4. Better Sorting (#9 + #10)
        sorted_res = sort_products(filtered, "deal_score_high")

        self.assertTrue(any(p.get("is_best_deal") for p in sorted_res))
        for p in sorted_res:
            self.assertIsNotNone(p.get("deal_score"))
            self.assertIn("delivery", p)


if __name__ == "__main__":
    unittest.main()
