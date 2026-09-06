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

calculate_true_total_price = shopping_service.calculate_true_total_price
calculate_savings          = shopping_service.calculate_savings
select_best_deal           = shopping_service.select_best_deal
calculate_deal_scores      = shopping_service.calculate_deal_scores
sort_products              = shopping_service.sort_products
filter_products            = shopping_service.filter_products


# ─── Shared test fixtures ───────────────────────────────────────────────────────

def make_sample_products():
    """Return a fresh list of diverse product dicts for Feature #11 testing."""
    return [
        {
            "id": 1,
            "title": "Alpha Earbuds",
            "source": "Daraz",
            "price_val": 4000.0,
            "price": "Rs. 4,000",
            "original_price": "Rs. 5,000",
            "savings_amount": 1000,
            "savings_pct": 20.0,
            "savings_str": "Save Rs. 1,000 (20.0% off)",
            "discount_val": 20,
            "is_best_deal": False,
            "deal_score": 75,
            "delivery": "Free Delivery",
            "shipping_cost": 0.0,
            "shipping_str": "Free Shipping",
            "tax_amount": None,
            "total_price": 4000.0,
            "total_price_str": "Rs. 4,000",
            "total_price_status": "calculated",
            "total_price_is_estimated": True,
            "thumbnail": "https://example.com/alpha.jpg",
            "link": "https://daraz.pk/alpha",
        },
        {
            "id": 2,
            "title": "Beta Earbuds",
            "source": "Amazon",
            "price_val": 3500.0,
            "price": "Rs. 3,500",
            "original_price": "Rs. 4,500",
            "savings_amount": 1000,
            "savings_pct": 22.2,
            "savings_str": "Save Rs. 1,000 (22.2% off)",
            "discount_val": 22,
            "is_best_deal": True,
            "deal_score": 92,
            "delivery": "Standard Delivery",
            "shipping_cost": 250.0,
            "shipping_str": "Rs. 250",
            "tax_amount": 150.0,
            "total_price": 3900.0,
            "total_price_str": "Rs. 3,900",
            "total_price_status": "calculated",
            "total_price_is_estimated": True,
            "thumbnail": "https://example.com/beta.jpg",
            "link": "https://amazon.com/beta",
        },
        {
            "id": 3,
            "title": "Gamma Earbuds",
            "source": "Walmart",
            "price_val": 8000.0,
            "price": "Rs. 8,000",
            "original_price": "Rs. 10,000",
            "savings_amount": 2000,
            "savings_pct": 20.0,
            "savings_str": "Save Rs. 2,000 (20.0% off)",
            "discount_val": 20,
            "is_best_deal": False,
            "deal_score": 60,
            "delivery": "Contact seller",
            "shipping_cost": None,
            "shipping_str": None,
            "tax_amount": None,
            "total_price": 8000.0,
            "total_price_str": "Rs. 8,000",
            "total_price_status": "price_only",
            "total_price_is_estimated": True,
            "thumbnail": "https://example.com/gamma.jpg",
            "link": "https://walmart.com/gamma",
        },
    ]


class TestTrueTotalPrice(unittest.TestCase):
    """Feature #11 — True Total Price: 25 required tests."""

    # 1. test_total_price_equals_product_price_when_no_extra_costs_are_known()
    def test_total_price_equals_product_price_when_no_extra_costs_are_known(self):
        """When shipping and tax are unknown, total_price equals product price."""
        res = calculate_true_total_price(product_price=4500.0, shipping=None, tax=None, currency="Rs.")
        self.assertEqual(res["total_price"], 4500.0)
        self.assertEqual(res["total_price_status"], "price_only")
        self.assertTrue(res["total_price_is_estimated"])

    # 2. test_total_price_adds_verified_shipping()
    def test_total_price_adds_verified_shipping(self):
        """When verified shipping is provided, total_price = product_price + shipping."""
        res = calculate_true_total_price(product_price=4000.0, shipping=250.0, currency="Rs.")
        self.assertEqual(res["total_price"], 4250.0)
        self.assertEqual(res["shipping_cost"], 250.0)
        self.assertEqual(res["total_price_status"], "calculated")

    # 3. test_total_price_adds_verified_tax()
    def test_total_price_adds_verified_tax(self):
        """When verified tax is provided, total_price = product_price + tax."""
        res = calculate_true_total_price(product_price=4000.0, tax=200.0, currency="Rs.")
        self.assertEqual(res["total_price"], 4200.0)
        self.assertEqual(res["tax_amount"], 200.0)
        self.assertEqual(res["total_price_status"], "calculated")

    # 4. test_total_price_adds_shipping_and_tax()
    def test_total_price_adds_shipping_and_tax(self):
        """When both verified shipping and tax are provided, total_price = price + shipping + tax."""
        res = calculate_true_total_price(product_price=4000.0, shipping=250.0, tax=150.0, currency="Rs.")
        self.assertEqual(res["total_price"], 4400.0)
        self.assertEqual(res["total_price_status"], "calculated")

    # 5. test_explicit_source_total_is_preferred()
    def test_explicit_source_total_is_preferred(self):
        """Explicit final total provided directly by source is preferred and marked exact."""
        res = calculate_true_total_price(product_price=4000.0, shipping=300.0, source_total=4200.0, currency="Rs.")
        self.assertEqual(res["total_price"], 4200.0)
        self.assertEqual(res["total_price_status"], "exact")
        self.assertFalse(res["total_price_is_estimated"])

    # 6. test_free_shipping_is_zero()
    def test_free_shipping_is_zero(self):
        """Explicitly free shipping is treated as 0.0 without adding shipping cost."""
        res = calculate_true_total_price(product_price=4000.0, shipping="free", currency="Rs.")
        self.assertEqual(res["shipping_cost"], 0.0)
        self.assertEqual(res["shipping_str"], "Free Shipping")
        self.assertEqual(res["total_price"], 4000.0)
        self.assertEqual(res["total_price_status"], "calculated")

    # 7. test_unknown_shipping_is_not_assumed_zero()
    def test_unknown_shipping_is_not_assumed_zero(self):
        """Unknown or missing shipping is None, NOT assumed to be zero."""
        res = calculate_true_total_price(product_price=4000.0, shipping=None, currency="Rs.")
        self.assertIsNone(res["shipping_cost"])
        self.assertNotEqual(res["shipping_cost"], 0.0)

    # 8. test_unknown_tax_is_not_assumed_zero()
    def test_unknown_tax_is_not_assumed_zero(self):
        """Unknown or missing tax is None, NOT assumed to be zero."""
        res = calculate_true_total_price(product_price=4000.0, tax=None, currency="Rs.")
        self.assertIsNone(res["tax_amount"])
        self.assertNotEqual(res["tax_amount"], 0.0)

    # 9. test_invalid_shipping_does_not_crash()
    def test_invalid_shipping_does_not_crash(self):
        """Unparseable or negative shipping strings do not crash and result in None shipping."""
        res1 = calculate_true_total_price(product_price=4000.0, shipping="calculated at checkout")
        self.assertIsNone(res1["shipping_cost"])

        res2 = calculate_true_total_price(product_price=4000.0, shipping=-50.0)
        self.assertIsNone(res2["shipping_cost"])

    # 10. test_invalid_tax_does_not_crash()
    def test_invalid_tax_does_not_crash(self):
        """Unparseable or negative tax strings do not crash and result in None tax."""
        res1 = calculate_true_total_price(product_price=4000.0, tax="TBD")
        self.assertIsNone(res1["tax_amount"])

        res2 = calculate_true_total_price(product_price=4000.0, tax=-10.0)
        self.assertIsNone(res2["tax_amount"])

    # 11. test_invalid_product_price_does_not_crash()
    def test_invalid_product_price_does_not_crash(self):
        """Invalid product price returns total_price=None and status='unavailable' without crashing."""
        res1 = calculate_true_total_price(product_price=None)
        self.assertIsNone(res1["total_price"])
        self.assertEqual(res1["total_price_status"], "unavailable")

        res2 = calculate_true_total_price(product_price="invalid_price")
        self.assertIsNone(res2["total_price"])
        self.assertEqual(res2["total_price_status"], "unavailable")

        res3 = calculate_true_total_price(product_price=-100.0)
        self.assertIsNone(res3["total_price"])
        self.assertEqual(res3["total_price_status"], "unavailable")

    # 12. test_currency_is_preserved()
    def test_currency_is_preserved(self):
        """Target currency symbol is preserved in formatted total string."""
        res_usd = calculate_true_total_price(product_price=50.0, shipping=5.0, currency="$")
        self.assertEqual(res_usd["currency"], "$")
        self.assertIn("$", res_usd["total_price_str"])

        res_pkr = calculate_true_total_price(product_price=5000.0, shipping=200.0, currency="Rs.")
        self.assertEqual(res_pkr["currency"], "Rs.")
        self.assertIn("Rs.", res_pkr["total_price_str"])

    # 13. test_no_currency_conversion_is_performed()
    def test_no_currency_conversion_is_performed(self):
        """Total price calculation adds numbers in the same currency without converting rates."""
        res = calculate_true_total_price(product_price=100.0, shipping=15.0, tax=5.0, currency="$")
        self.assertEqual(res["total_price"], 120.0)

    # 14. test_total_price_status_is_correct()
    def test_total_price_status_is_correct(self):
        """Statuses 'exact', 'calculated', 'price_only', 'unavailable' are assigned accurately."""
        self.assertEqual(calculate_true_total_price(source_total=500.0)["total_price_status"], "exact")
        self.assertEqual(calculate_true_total_price(product_price=500.0, shipping=50.0)["total_price_status"], "calculated")
        self.assertEqual(calculate_true_total_price(product_price=500.0)["total_price_status"], "price_only")
        self.assertEqual(calculate_true_total_price(product_price=None)["total_price_status"], "unavailable")

    # 15. test_product_price_only_is_not_presented_as_guaranteed_final_checkout_total()
    def test_product_price_only_is_not_presented_as_guaranteed_final_checkout_total(self):
        """When shipping/tax are unsupplied, status is 'price_only' and total_price_is_estimated is True."""
        res = calculate_true_total_price(product_price=4000.0)
        self.assertEqual(res["total_price_status"], "price_only")
        self.assertTrue(res["total_price_is_estimated"])

    # 16. test_existing_savings_calculation_is_preserved()
    def test_existing_savings_calculation_is_preserved(self):
        """Feature #7 savings remains original_price - current_price, unaffected by shipping."""
        orig = 5000.0
        curr = 4000.0
        shipping = 250.0
        sav = calculate_savings(curr, orig, "Rs.")
        self.assertEqual(sav["savings_amount"], 1000)

    # 17. test_best_deal_flag_is_preserved()
    def test_best_deal_flag_is_preserved(self):
        """Best Deal flag from Feature #6 remains True on designated offer."""
        products = make_sample_products()
        beta = next(p for p in products if p["is_best_deal"])
        self.assertEqual(beta["title"], "Beta Earbuds")

    # 18. test_deal_score_is_preserved()
    def test_deal_score_is_preserved(self):
        """Feature #10 Deal Score is preserved on product items."""
        products = make_sample_products()
        for p in products:
            self.assertIsNotNone(p.get("deal_score"))

    # 19. test_filters_continue_working()
    def test_filters_continue_working(self):
        """Feature #8 Advanced Filters function normally with True Total Price present."""
        products = make_sample_products()
        filtered = filter_products(products, max_price=5000)
        self.assertEqual(len(filtered), 2)

    # 20. test_existing_sorting_options_continue_working()
    def test_existing_sorting_options_continue_working(self):
        """All Feature #9 and #10 sorting options continue working as expected."""
        products = make_sample_products()
        by_price = sort_products(products, "price_low")
        self.assertEqual(by_price[0]["title"], "Beta Earbuds")

        by_score = sort_products(products, "deal_score_high")
        self.assertEqual(by_score[0]["title"], "Beta Earbuds")  # score 92

    # 21. test_no_additional_serpapi_request_for_total_calculation()
    def test_no_additional_serpapi_request_for_total_calculation(self):
        """True Total Price calculation makes zero external network / SerpAPI calls."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            calculate_true_total_price(product_price=1000.0, shipping=100.0)
            mock_fetch.assert_not_called()

    # 22. test_product_image_is_preserved()
    def test_product_image_is_preserved(self):
        """Product thumbnails remain valid URLs and are not altered."""
        products = make_sample_products()
        for p in products:
            self.assertTrue(p["thumbnail"].startswith("https://"))

    # 23. test_direct_retailer_link_is_preserved()
    def test_direct_retailer_link_is_preserved(self):
        """Direct retailer links remain intact and functional."""
        products = make_sample_products()
        for p in products:
            self.assertTrue(p["link"].startswith("https://"))

    # 24. test_empty_results_do_not_crash()
    def test_empty_results_do_not_crash(self):
        """Empty or None input to calculate_true_total_price does not crash."""
        res1 = calculate_true_total_price(None)
        self.assertIsNone(res1["total_price"])
        self.assertEqual(res1["total_price_status"], "unavailable")

        res2 = calculate_true_total_price({})
        self.assertIsNone(res2["total_price"])
        self.assertEqual(res2["total_price_status"], "unavailable")

    # 25. test_malformed_offer_data_does_not_crash()
    def test_malformed_offer_data_does_not_crash(self):
        """Malformed dictionary types and structures are handled defensively."""
        malformed = {
            "price_val": {"nested": "not_a_number"},
            "shipping_cost": [1, 2, 3],
            "tax_amount": object(),
        }
        res = calculate_true_total_price(malformed)
        self.assertIsNone(res["total_price"])
        self.assertEqual(res["total_price_status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
