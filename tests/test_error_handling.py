import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock
import requests
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

search_shopping_deals           = shopping_service.search_shopping_deals
_fetch_serpapi_shopping         = shopping_service._fetch_serpapi_shopping
_process_serpapi_results        = shopping_service._process_serpapi_results
filter_products                 = shopping_service.filter_products
sort_products                   = shopping_service.sort_products
SearchOutcome                   = shopping_service.SearchOutcome
ShoppingSearchError             = shopping_service.ShoppingSearchError
ShoppingTimeoutError            = shopping_service.ShoppingTimeoutError
ShoppingNetworkError            = shopping_service.ShoppingNetworkError
ShoppingRateLimitError          = shopping_service.ShoppingRateLimitError
ShoppingAPIError                = shopping_service.ShoppingAPIError
ShoppingMalformedResponseError  = shopping_service.ShoppingMalformedResponseError

from config import Config


class TestErrorHandling(unittest.TestCase):
    """
    Test suite for Phase 1 Feature #2: Zero Results / Error Handling.
    Covers all 23 acceptance criteria and edge cases.
    """

    # 1. test_successful_search_returns_products()
    def test_successful_search_returns_products(self):
        """Successful search returns products with status='success' and success=True."""
        mock_raw = [
            {"title": "Product A", "price": "$29.99", "source": "Amazon", "link": "https://amazon.com/a"},
            {"title": "Product B", "price": "$39.99", "source": "BestBuy", "link": "https://bestbuy.com/b"}
        ]
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=mock_raw):
            res = search_shopping_deals("wireless earbuds")
            self.assertEqual(res["status"], SearchOutcome.SUCCESS)
            self.assertTrue(res["success"])
            self.assertEqual(len(res["products"]), 2)
            self.assertEqual(res["total_results"], 2)
            self.assertIsNone(res["error_type"])
            self.assertIsNone(res["user_message"])
            self.assertFalse(res["retryable"])

    # 2. test_successful_search_with_zero_results_returns_no_results_status()
    def test_successful_search_with_zero_results_returns_no_results_status(self):
        """When query completes cleanly with 0 results, status is 'no_results' and success is False."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]):
            res = search_shopping_deals("rare unfindable gizmo 999")
            self.assertEqual(res["status"], SearchOutcome.NO_RESULTS)
            self.assertFalse(res["success"])
            self.assertEqual(res["error_type"], SearchOutcome.NO_RESULTS)
            self.assertEqual(res["products"], [])
            self.assertEqual(res["total_results"], 0)
            self.assertIn("rare unfindable gizmo 999", res["user_message"])
            self.assertFalse(res["retryable"])

    # 3. test_corrected_query_with_results_returns_products()
    def test_corrected_query_with_results_returns_products(self):
        """When original query has 0 results but spelling-corrected query succeeds, returns products."""
        mock_raw = [{"title": "Face Wash for Women", "price": "$12.00", "source": "Sephora", "link": "https://sephora.com/f"}]
        # 1st call returns [], 2nd call (corrected) returns product
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=[[], mock_raw]):
            res = search_shopping_deals("fce wsh")
            self.assertEqual(res["status"], SearchOutcome.SUCCESS)
            self.assertTrue(res["success"])
            self.assertEqual(len(res["products"]), 1)
            self.assertIsNotNone(res["corrected_query"])

    # 4. test_all_spelling_fallback_attempts_with_zero_results()
    def test_all_spelling_fallback_attempts_with_zero_results(self):
        """When all fallback query attempts return 0 results, returns 'no_results' cleanly."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]) as mock_fetch:
            res = search_shopping_deals("fce wsh for wmen")
            self.assertEqual(res["status"], SearchOutcome.NO_RESULTS)
            self.assertFalse(res["success"])
            self.assertEqual(res["products"], [])
            # Assert controlled attempts: at most 3
            self.assertLessEqual(mock_fetch.call_count, 3)
            self.assertGreaterEqual(mock_fetch.call_count, 1)

    # 5. test_no_fake_products_on_zero_results()
    def test_no_fake_products_on_zero_results(self):
        """Zero-result searches never invent or return placeholder/filler items."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]):
            res = search_shopping_deals("ghost product 404")
            self.assertEqual(res["products"], [])
            self.assertEqual(res["total_results"], 0)

    # 6. test_filtered_empty_is_distinct_from_search_zero_results()
    def test_filtered_empty_is_distinct_from_search_zero_results(self):
        """Filtered empty (where initial search had products) is distinct from search zero results."""
        products = [
            {"title": "Shirt", "price_val": 500.0, "is_best_deal": False, "savings_amount": None, "source": "StoreA", "delivery": "in stock"},
            {"title": "Pants", "price_val": 800.0, "is_best_deal": False, "savings_amount": None, "source": "StoreB", "delivery": "in stock"}
        ]
        # Active filter: min_price 2000 removes all items
        filtered = filter_products(products, min_price=2000.0)
        self.assertEqual(len(filtered), 0)
        # Verify original collection is preserved
        self.assertEqual(len(products), 2)

    # 7. test_reset_filters_restores_original_results()
    def test_reset_filters_restores_original_results(self):
        """Resetting filters restores full original product list without mutation."""
        products = [
            {"title": "Item 1", "price_val": 100.0, "is_best_deal": False, "source": "StoreA", "delivery": "in stock"},
            {"title": "Item 2", "price_val": 200.0, "is_best_deal": True, "source": "StoreB", "delivery": "in stock"}
        ]
        # Restricting filter:
        filtered = filter_products(products, min_price=150.0)
        self.assertEqual(len(filtered), 1)

        # Resetting filter:
        restored = filter_products(products)
        self.assertEqual(len(restored), 2)

    # 8. test_reset_filters_does_not_call_serpapi_again()
    def test_reset_filters_does_not_call_serpapi_again(self):
        """Resetting filters operates entirely locally and makes 0 calls to _fetch_serpapi_shopping."""
        products = [{"title": "Item", "price_val": 100.0, "is_best_deal": False, "source": "StoreA", "delivery": "in stock"}]
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            restored = filter_products(products)
            self.assertEqual(len(restored), 1)
            mock_fetch.assert_not_called()

    # 9. test_api_error_returns_safe_message()
    def test_api_error_returns_safe_message(self):
        """API errors return status='api_error' with friendly, non-technical user message."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=ShoppingAPIError("HTTP 500 Upstream")):
            res = search_shopping_deals("laptop")
            self.assertEqual(res["status"], SearchOutcome.API_ERROR)
            self.assertFalse(res["success"])
            self.assertTrue(res["retryable"])
            self.assertEqual(res["user_message"], "We couldn't fetch live deals right now. Please try again.")

    # 10. test_api_error_does_not_expose_api_key()
    def test_api_error_does_not_expose_api_key(self):
        """API keys are NEVER exposed in results, error messages, or returned dictionaries."""
        secret_key = "secret_super_private_serpapi_key_12345"
        with patch.object(Config, "SERPAPI_API_KEY", secret_key):
            with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=ShoppingAPIError(f"Unauthorized with {secret_key}")):
                res = search_shopping_deals("laptop")
                self.assertNotIn(secret_key, str(res))
                self.assertNotIn(secret_key, res["user_message"])

    # 11. test_api_error_does_not_expose_stack_trace()
    def test_api_error_does_not_expose_stack_trace(self):
        """Tracebacks and internal file paths are never exposed to the frontend."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=ValueError("Traceback (most recent call last):\n  File 'shopping.py'")):
            res = search_shopping_deals("watch")
            self.assertNotIn("Traceback", res["user_message"])
            self.assertNotIn(".py", res["user_message"])
            self.assertEqual(res["status"], SearchOutcome.INTERNAL_ERROR)

    # 12. test_timeout_is_classified_correctly()
    def test_timeout_is_classified_correctly(self):
        """Timeouts are classified as status='timeout' with connection advice."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=requests.exceptions.Timeout("Read timeout")):
            res = search_shopping_deals("headphones")
            self.assertEqual(res["status"], SearchOutcome.TIMEOUT)
            self.assertFalse(res["success"])
            self.assertTrue(res["retryable"])
            self.assertIn("connection", res["user_message"].lower())

    # 13. test_network_error_is_classified_correctly()
    def test_network_error_is_classified_correctly(self):
        """Connection errors are classified as status='network_error'."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=requests.exceptions.ConnectionError("DNS failure")):
            res = search_shopping_deals("shoes")
            self.assertEqual(res["status"], SearchOutcome.NETWORK_ERROR)
            self.assertFalse(res["success"])
            self.assertTrue(res["retryable"])
            self.assertIn("connection", res["user_message"].lower())

    # 14. test_rate_limit_is_classified_correctly()
    def test_rate_limit_is_classified_correctly(self):
        """Rate limit / 429 quota exhaustion is classified as status='rate_limited'."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=ShoppingRateLimitError("Monthly limit reached")):
            res = search_shopping_deals("perfume")
            self.assertEqual(res["status"], SearchOutcome.RATE_LIMITED)
            self.assertFalse(res["success"])
            self.assertTrue(res["retryable"])
            self.assertIn("busy", res["user_message"].lower())

    # 15. test_malformed_response_does_not_crash()
    def test_malformed_response_does_not_crash(self):
        """Malformed response is classified as status='invalid_response' without crashing."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=ShoppingMalformedResponseError("Invalid JSON")):
            res = search_shopping_deals("camera")
            self.assertEqual(res["status"], SearchOutcome.INVALID_RESPONSE)
            self.assertFalse(res["success"])
            self.assertTrue(res["retryable"])
            self.assertIn("unexpected response", res["user_message"].lower())

    # 16. test_missing_result_fields_do_not_crash()
    def test_missing_result_fields_do_not_crash(self):
        """Items with completely missing fields process safely using defaults."""
        incomplete_items = [
            {},
            {"title": None},
            {"price": None},
            {"source": None, "link": None, "thumbnail": None}
        ]
        products = _process_serpapi_results(incomplete_items, "sample")
        self.assertEqual(len(products), 4)
        for p in products:
            self.assertTrue(p["title"])
            self.assertTrue(p["source"])
            self.assertTrue(p["price"])

    # 17. test_none_result_data_does_not_crash()
    def test_none_result_data_does_not_crash(self):
        """Non-dict or None items in result list are safely skipped without crash."""
        malformed_list = [None, "invalid_string_item", 42, {"title": "Valid Item", "price": "$10"}]
        products = _process_serpapi_results(malformed_list, "sample")
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["title"], "Valid Item")

    # 18. test_invalid_result_collection_does_not_crash()
    def test_invalid_result_collection_does_not_crash(self):
        """Passing non-list collection to _process_serpapi_results returns [] without crashing."""
        self.assertEqual(_process_serpapi_results(None, "sample"), [])
        self.assertEqual(_process_serpapi_results("not_a_list", "sample"), [])
        self.assertEqual(_process_serpapi_results(12345, "sample"), [])
        self.assertEqual(_process_serpapi_results({"error": "broken"}, "sample"), [])

    # 19. test_retry_uses_same_query()
    def test_retry_uses_same_query(self):
        """Retrying preserves the exact search query."""
        target_query = "mechanical keyboard rgb"
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]):
            res = search_shopping_deals(target_query)
            self.assertEqual(res["query"], target_query)
            # Re-running same query
            res2 = search_shopping_deals(res["query"])
            self.assertEqual(res2["query"], target_query)

    # 20. test_retry_does_not_duplicate_results()
    def test_retry_does_not_duplicate_results(self):
        """Retrying does not duplicate product cards or results."""
        mock_raw = [{"title": "Item A", "price": "$15"}, {"title": "Item B", "price": "$25"}]
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=mock_raw):
            res1 = search_shopping_deals("mouse")
            res2 = search_shopping_deals("mouse")
            self.assertEqual(len(res1["products"]), 2)
            self.assertEqual(len(res2["products"]), 2)

    # 21. test_no_infinite_retry_loop()
    def test_no_infinite_retry_loop(self):
        """Query fallback attempts are strictly bounded to at most 3 calls."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]) as mock_fetch:
            search_shopping_deals("ultra complicated multi word query for testing loops")
            self.assertLessEqual(mock_fetch.call_count, 3)

    # 22. test_failed_search_does_not_corrupt_previous_results()
    def test_failed_search_does_not_corrupt_previous_results(self):
        """A failed subsequent search does not alter previously received successful results."""
        mock_raw = [{"title": "Previous Item", "price": "$50"}]
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=mock_raw):
            previous_res = search_shopping_deals("tablet")
            self.assertEqual(previous_res["status"], SearchOutcome.SUCCESS)
            self.assertEqual(len(previous_res["products"]), 1)

        # Subsequent search fails with timeout
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=requests.exceptions.Timeout("Timeout")):
            failed_res = search_shopping_deals("tablet")
            self.assertEqual(failed_res["status"], SearchOutcome.TIMEOUT)

        # Verify previous_res is completely intact
        self.assertEqual(previous_res["status"], SearchOutcome.SUCCESS)
        self.assertEqual(len(previous_res["products"]), 1)
        self.assertEqual(previous_res["products"][0]["title"], "Previous Item")

    # 23. test_existing_features_remain_compatible()
    def test_existing_features_remain_compatible(self):
        """Features #6 Best Deal, #7 Savings, #8 Filters, #9 Sorting, #10 Deal Score, #11 True Total work seamlessly."""
        mock_raw = [
            {
                "title": "Cheap Item",
                "price": "$20",
                "extracted_old_price": 40.0,
                "extracted_shipping": 5.0,
                "source": "StoreA",
                "link": "https://storea.com/cheap",
                "thumbnail": "https://storea.com/img.jpg",
                "rating": 4.8,
                "reviews": 200
            },
            {
                "title": "Expensive Item",
                "price": "$100",
                "source": "StoreB",
                "link": "https://storeb.com/exp",
                "thumbnail": "https://storeb.com/img2.jpg",
                "rating": 4.2,
                "reviews": 50
            }
        ]
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=mock_raw):
            res = search_shopping_deals("gadget", currency="$")
            self.assertEqual(res["status"], SearchOutcome.SUCCESS)
            products = res["products"]
            self.assertEqual(len(products), 2)

            # Feature #6: Best Deal badge
            best_deals = [p for p in products if p.get("is_best_deal")]
            self.assertEqual(len(best_deals), 1)

            # Feature #7: Savings Calculator
            cheap_item = next(p for p in products if p["title"] == "Cheap Item")
            self.assertIsNotNone(cheap_item.get("savings_amount"))
            self.assertGreater(cheap_item["savings_amount"], 0)

            # Feature #10: Deal Score
            for p in products:
                self.assertIsNotNone(p.get("deal_score"))
                self.assertGreaterEqual(p["deal_score"], 0)
                self.assertLessEqual(p["deal_score"], 100)

            # Feature #11: True Total Price
            self.assertIsNotNone(cheap_item.get("total_price"))
            self.assertEqual(cheap_item.get("total_price_status"), "calculated")

            # Feature #8: Filters
            filtered = filter_products(products, max_price=50.0)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["title"], "Cheap Item")

            # Feature #9: Sorting
            sorted_by_price = sort_products(products, sort_by="price_low")
            self.assertEqual(sorted_by_price[0]["title"], "Cheap Item")


if __name__ == "__main__":
    unittest.main()
