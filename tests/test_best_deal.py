import os
import sys
import types
import unittest
from unittest.mock import patch
import importlib.util

# Set root directory in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Mock app package to avoid executing app/__init__.py (which requires Flask runtime)
if "app" not in sys.modules:
    sys.modules["app"] = types.ModuleType("app")

spec = importlib.util.spec_from_file_location(
    "shopping_service", 
    os.path.join(ROOT_DIR, "app", "shopping_service.py")
)
shopping_service = importlib.util.module_from_spec(spec)
sys.modules["app.shopping_service"] = shopping_service
spec.loader.exec_module(shopping_service)

select_best_deal = shopping_service.select_best_deal
search_shopping_deals = shopping_service.search_shopping_deals
extract_direct_retailer_url = shopping_service.extract_direct_retailer_url
_process_serpapi_results = shopping_service._process_serpapi_results


class TestBestDealBadge(unittest.TestCase):

    def setUp(self):
        self.sample_products = [
            {
                "title": "Wireless Earbuds Pro",
                "source": "Daraz",
                "price": "Rs. 2,499",
                "price_val": 2499.0,
                "original_price": "Rs. 3,000",
                "discount": "16% OFF",
                "discount_val": 16,
                "link": "https://www.daraz.pk/products/earbuds-pro-i123.html",
                "thumbnail": "https://img.daraz.pk/earbuds.jpg",
                "rating": 4.5,
                "reviews": 120,
                "delivery": "Free Delivery",
                "badge": None,
                "is_best_deal": False
            },
            {
                "title": "Wireless Bluetooth Earbuds",
                "source": "PriceOye",
                "price": "Rs. 1,899",
                "price_val": 1899.0,
                "original_price": "Rs. 2,500",
                "discount": "24% OFF",
                "discount_val": 24,
                "link": "https://priceoye.pk/wireless-earbuds/earbuds",
                "thumbnail": "https://images.priceoye.pk/earbuds.jpg",
                "rating": 4.7,
                "reviews": 340,
                "delivery": "Standard Delivery",
                "badge": None,
                "is_best_deal": False
            },
            {
                "title": "TWS True Wireless Earbuds",
                "source": "Telemart",
                "price": "Rs. 3,100",
                "price_val": 3100.0,
                "original_price": "Rs. 3,500",
                "discount": "11% OFF",
                "discount_val": 11,
                "link": "https://www.telemart.pk/earbuds-tws.html",
                "thumbnail": "https://telemart.pk/media/earbuds.jpg",
                "rating": 4.2,
                "reviews": 45,
                "delivery": "Standard Delivery",
                "badge": None,
                "is_best_deal": False
            }
        ]

    def test_best_deal_selected_from_valid_results(self):
        """1. A valid search with multiple offers identifies a valid BEST DEAL."""
        results = select_best_deal(self.sample_products)
        best_deals = [p for p in results if p.get("is_best_deal") is True]
        self.assertEqual(len(best_deals), 1)
        self.assertEqual(best_deals[0]["source"], "PriceOye")
        self.assertEqual(best_deals[0]["price_val"], 1899.0)

    def test_only_one_best_deal_is_selected(self):
        """2. Ensure exactly ONE product is marked with is_best_deal=True, others are False."""
        results = select_best_deal(self.sample_products)
        true_count = sum(1 for p in results if p.get("is_best_deal") is True)
        false_count = sum(1 for p in results if p.get("is_best_deal") is False)
        
        self.assertEqual(true_count, 1)
        self.assertEqual(false_count, len(self.sample_products) - 1)

    def test_lowest_valid_price_gets_best_deal(self):
        """3. The lowest valid final price is given priority, and tie-breakers work deterministically."""
        # Scenario A: Distinct prices
        items = [
            {"title": "Product A", "price_val": 4500.0, "source": "Store A"},
            {"title": "Product B", "price_val": 2100.0, "source": "Store B"},
            {"title": "Product C", "price_val": 3200.0, "source": "Store C"},
        ]
        res = select_best_deal(items)
        best = [p for p in res if p.get("is_best_deal")]
        self.assertEqual(len(best), 1)
        self.assertEqual(best[0]["title"], "Product B")

        # Scenario B: Tied prices broken by discount %
        tied_items = [
            {"title": "Item 1", "price_val": 1500.0, "discount_val": 10, "source": "Store 1"},
            {"title": "Item 2", "price_val": 1500.0, "discount_val": 30, "source": "Store 2"},
        ]
        res_tied = select_best_deal(tied_items)
        best_tied = [p for p in res_tied if p.get("is_best_deal")]
        self.assertEqual(len(best_tied), 1)
        self.assertEqual(best_tied[0]["title"], "Item 2")

    def test_invalid_price_is_not_selected(self):
        """4. Invalid/missing/zero prices are never selected as BEST DEAL."""
        items = [
            {"title": "Zero Price", "price_val": 0, "price": "Rs. 0"},
            {"title": "Negative Price", "price_val": -50.0, "price": "-Rs. 50"},
            {"title": "None Price", "price_val": None, "price": None},
            {"title": "Malformed String", "price": "Price on request"},
            {"title": "Valid Price Product", "price_val": 1200.0, "price": "Rs. 1,200", "source": "Store X"}
        ]
        res = select_best_deal(items)
        best = [p for p in res if p.get("is_best_deal")]
        self.assertEqual(len(best), 1)
        self.assertEqual(best[0]["title"], "Valid Price Product")

        # When all products are invalid, no best deal should be selected
        all_invalid = [
            {"title": "Zero Price", "price_val": 0},
            {"title": "Malformed", "price": "Call for price"}
        ]
        res_all_invalid = select_best_deal(all_invalid)
        best_none = [p for p in res_all_invalid if p.get("is_best_deal")]
        self.assertEqual(len(best_none), 0)

    def test_missing_price_does_not_crash(self):
        """5. Safely handle missing price keys, malformed price types, and empty strings without crashing."""
        edge_items = [
            {},
            {"title": "No Price Field"},
            {"price": None, "price_val": None},
            {"price": ""},
            {"price_val": "invalid_number_type"},
            {"title": "Valid One", "price_val": 999.0}
        ]
        try:
            res = select_best_deal(edge_items)
            best = [p for p in res if p.get("is_best_deal")]
            self.assertEqual(len(best), 1)
            self.assertEqual(best[0]["title"], "Valid One")
        except Exception as e:
            self.fail(f"select_best_deal raised an exception on missing price: {e}")

    def test_empty_results_do_not_crash(self):
        """6. Empty results or non-list inputs return safely without crashing."""
        self.assertEqual(select_best_deal([]), [])
        self.assertEqual(select_best_deal(None), None)
        self.assertEqual(select_best_deal("invalid"), "invalid")

    def test_best_deal_flag_is_returned(self):
        """7. is_best_deal boolean flag is attached to all returned products."""
        res = select_best_deal(self.sample_products)
        for p in res:
            self.assertIn("is_best_deal", p)
            self.assertIsInstance(p["is_best_deal"], bool)

    def test_existing_direct_retailer_links_still_work(self):
        """8. Direct retailer link unpacking remains fully intact and functioning."""
        # 1. Direct retailer link
        url1 = "https://www.daraz.pk/products/watch-i100.html"
        extracted1 = extract_direct_retailer_url(url1)
        self.assertEqual(extracted1, url1)

        # 2. Wrapped Google adurl link
        url2 = "https://www.google.com/aclk?sa=l&ai=DChcSEwi&adurl=https%3A%2F%2Fwww.daraz.pk%2Fproducts%2Fwatch-direct.html"
        extracted2 = extract_direct_retailer_url(url2)
        self.assertEqual(extracted2, "https://www.daraz.pk/products/watch-direct.html")

    @patch.object(shopping_service, "_fetch_serpapi_shopping")
    def test_existing_search_results_still_work(self, mock_fetch):
        """9. Existing search pipeline works end-to-end, returns proper structure and marks BEST DEAL."""
        mock_fetch.return_value = [
            {
                "title": "Mock Smartphone Pro 128GB",
                "source": "Daraz",
                "extracted_price": 45000,
                "price": "Rs. 45,000",
                "link": "https://www.daraz.pk/products/mock-phone.html",
                "thumbnail": "https://img.daraz.pk/phone.jpg",
                "rating": 4.8,
                "reviews": 150
            },
            {
                "title": "Mock Smartphone Pro 128GB",
                "source": "PriceOye",
                "extracted_price": 42500,
                "price": "Rs. 42,500",
                "link": "https://priceoye.pk/mock-phone",
                "thumbnail": "https://images.priceoye.pk/phone.jpg",
                "rating": 4.6,
                "reviews": 85
            }
        ]

        result = search_shopping_deals("mock smartphone")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_results"], 2)
        self.assertEqual(len(result["products"]), 2)

        # Check that exactly one best deal is identified
        best_deals = [p for p in result["products"] if p.get("is_best_deal") is True]
        self.assertEqual(len(best_deals), 1)
        self.assertEqual(best_deals[0]["source"], "PriceOye")

        # Verify direct link and thumbnail are preserved
        self.assertEqual(best_deals[0]["link"], "https://priceoye.pk/mock-phone")
        self.assertEqual(best_deals[0]["thumbnail"], "https://images.priceoye.pk/phone.jpg")


if __name__ == "__main__":
    unittest.main()
