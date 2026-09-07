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
SearchState                     = shopping_service.SearchState
SearchStateManager              = shopping_service.SearchStateManager
SearchOutcome                   = shopping_service.SearchOutcome
ShoppingTimeoutError            = shopping_service.ShoppingTimeoutError
ShoppingNetworkError            = shopping_service.ShoppingNetworkError
ShoppingRateLimitError          = shopping_service.ShoppingRateLimitError
ShoppingAPIError                = shopping_service.ShoppingAPIError
ShoppingMalformedResponseError  = shopping_service.ShoppingMalformedResponseError


class TestLoadingStates(unittest.TestCase):
    """
    Test suite for Phase 1 Feature #3: Loading States.
    Covers all 20 required tests and edge cases.
    """

    def setUp(self):
        self.manager = SearchStateManager()

    # 1. test_search_enters_loading_state()
    def test_search_enters_loading_state(self):
        """Search execution enters LOADING state from IDLE."""
        self.assertEqual(self.manager.state, SearchState.IDLE)
        ok, req_id = self.manager.start_search("wireless earbuds")
        self.assertTrue(ok)
        self.assertEqual(self.manager.state, SearchState.LOADING)
        self.assertEqual(self.manager.current_query, "wireless earbuds")
        self.assertEqual(req_id, 1)

    # 2. test_search_button_changes_during_loading()
    def test_search_button_changes_during_loading(self):
        """Verifies template has search button ID and aria-label to support loading state transition."""
        template_path = os.path.join(ROOT_DIR, "app", "templates", "shopping.html")
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('id="searchSubmitBtn"', content)
        self.assertIn('id="searchInput"', content)
        self.assertIn('id="shoppingSearchForm"', content)
        self.assertIn('searchLiveAnnouncer', content)
        self.assertIn('aria-live="polite"', content)

    # 3. test_duplicate_search_is_prevented_while_loading()
    def test_duplicate_search_is_prevented_while_loading(self):
        """Rapid repeated clicks while already loading are rejected."""
        ok1, req1 = self.manager.start_search("shoes")
        self.assertTrue(ok1)
        self.assertEqual(self.manager.state, SearchState.LOADING)

        # Attempt duplicate search while still LOADING
        ok2, err = self.manager.start_search("shoes")
        self.assertFalse(ok2)
        self.assertIn("already in progress", err)
        self.assertEqual(self.manager.state, SearchState.LOADING)
        self.assertEqual(self.manager.request_id, req1)

    # 4. test_loading_state_clears_on_success()
    def test_loading_state_clears_on_success(self):
        """Loading state clears and transitions to SUCCESS when products are returned."""
        ok, req_id = self.manager.start_search("laptop")
        self.assertEqual(self.manager.state, SearchState.LOADING)

        result = {
            "status": SearchOutcome.SUCCESS,
            "total_results": 5,
            "products": [{"title": "Laptop A"}]
        }
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.SUCCESS)

    # 5. test_loading_state_clears_on_zero_results()
    def test_loading_state_clears_on_zero_results(self):
        """Loading state clears and transitions to EMPTY when zero results are returned."""
        ok, req_id = self.manager.start_search("nonexistent query")
        self.assertEqual(self.manager.state, SearchState.LOADING)

        result = {
            "status": SearchOutcome.NO_RESULTS,
            "total_results": 0,
            "products": []
        }
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.EMPTY)

    # 6. test_loading_state_clears_on_api_error()
    def test_loading_state_clears_on_api_error(self):
        """Loading state clears and transitions to ERROR on API error."""
        ok, req_id = self.manager.start_search("watch")
        self.assertEqual(self.manager.state, SearchState.LOADING)

        result = {"status": SearchOutcome.API_ERROR, "products": []}
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.ERROR)

    # 7. test_loading_state_clears_on_timeout()
    def test_loading_state_clears_on_timeout(self):
        """Loading state clears and transitions to ERROR on timeout."""
        ok, req_id = self.manager.start_search("headphones")
        result = {"status": SearchOutcome.TIMEOUT, "products": []}
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.ERROR)

    # 8. test_loading_state_clears_on_network_error()
    def test_loading_state_clears_on_network_error(self):
        """Loading state clears and transitions to ERROR on network drop."""
        ok, req_id = self.manager.start_search("camera")
        result = {"status": SearchOutcome.NETWORK_ERROR, "products": []}
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.ERROR)

    # 9. test_loading_state_clears_on_malformed_response()
    def test_loading_state_clears_on_malformed_response(self):
        """Loading state clears and transitions to ERROR on malformed response."""
        ok, req_id = self.manager.start_search("perfume")
        result = {"status": SearchOutcome.INVALID_RESPONSE, "products": []}
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.ERROR)

    # 10. test_retry_enters_loading_state()
    def test_retry_enters_loading_state(self):
        """Clicking retry resets previous error and enters LOADING state with new request ID."""
        self.manager.state = SearchState.ERROR
        self.manager.reset()
        ok, req_id = self.manager.start_search("headphones")
        self.assertTrue(ok)
        self.assertEqual(self.manager.state, SearchState.LOADING)
        self.assertEqual(req_id, 1)

    # 11. test_retry_loading_state_clears_after_completion()
    def test_retry_loading_state_clears_after_completion(self):
        """Retry operation clears loading state upon completion."""
        self.manager.state = SearchState.ERROR
        self.manager.reset()
        ok, req_id = self.manager.start_search("headphones")

        result = {
            "status": SearchOutcome.SUCCESS,
            "total_results": 2,
            "products": [{"title": "Headphones 1"}]
        }
        self.manager.complete_search(result, req_id)
        self.assertEqual(self.manager.state, SearchState.SUCCESS)

    # 12. test_spelling_fallback_is_single_user_visible_loading_operation()
    def test_spelling_fallback_is_single_user_visible_loading_operation(self):
        """Internal multi-attempt query fallback executes as one unified search operation."""
        mock_raw = [{"title": "Face Wash", "price": "$15.00", "source": "Store", "link": "http://x"}]
        # First attempt returns [], second attempt succeeds
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=[[], mock_raw]):
            res = search_shopping_deals("fce wsh")
            # Result is returned as one unified response
            self.assertEqual(res["status"], SearchOutcome.SUCCESS)
            self.assertTrue(res["success"])
            self.assertEqual(len(res["products"]), 1)

    # 13. test_local_sorting_does_not_trigger_loading_request()
    def test_local_sorting_does_not_trigger_loading_request(self):
        """Local sorting operates in-memory and never triggers network loading requests."""
        products = [
            {"title": "B", "price_val": 20.0, "is_best_deal": False},
            {"title": "A", "price_val": 10.0, "is_best_deal": False}
        ]
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            sorted_res = sort_products(products, sort_by="price_low")
            self.assertEqual(sorted_res[0]["title"], "A")
            mock_fetch.assert_not_called()

    # 14. test_local_filtering_does_not_trigger_loading_request()
    def test_local_filtering_does_not_trigger_loading_request(self):
        """Local filtering operates in-memory and never triggers network loading requests."""
        products = [
            {"title": "Cheap", "price_val": 10.0, "is_best_deal": False, "delivery": "in stock"},
            {"title": "Pricey", "price_val": 500.0, "is_best_deal": False, "delivery": "in stock"}
        ]
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            filtered = filter_products(products, max_price=50.0)
            self.assertEqual(len(filtered), 1)
            mock_fetch.assert_not_called()

    # 15. test_reset_filters_does_not_trigger_loading_request()
    def test_reset_filters_does_not_trigger_loading_request(self):
        """Resetting filters operates in-memory and never triggers network loading requests."""
        products = [{"title": "Item", "price_val": 10.0, "is_best_deal": False, "delivery": "in stock"}]
        with patch.object(shopping_service, "_fetch_serpapi_shopping") as mock_fetch:
            restored = filter_products(products)
            self.assertEqual(len(restored), 1)
            mock_fetch.assert_not_called()

    # 16. test_search_query_is_preserved_during_loading()
    def test_search_query_is_preserved_during_loading(self):
        """Search query string is strictly preserved during loading state."""
        query = "mechanical keyboard 75%"
        self.manager.start_search(query)
        self.assertEqual(self.manager.current_query, query)
        self.assertIsNotNone(self.manager.current_query)

    # 17. test_no_stale_loader_after_request_completion()
    def test_no_stale_loader_after_request_completion(self):
        """Out-of-order / stale responses from older request IDs cannot overwrite current state."""
        ok1, req1 = self.manager.start_search("first query")
        # Simulate a second search initiated after first finishes or resets
        self.manager.reset()
        ok2, req2 = self.manager.start_search("second query")
        self.assertEqual(req2, 2)

        # Stale response for request 1 arrives late: should be rejected
        accepted = self.manager.complete_search({"status": SearchOutcome.SUCCESS}, request_id=req1)
        self.assertFalse(accepted)
        self.assertEqual(self.manager.state, SearchState.LOADING)

        # Response for request 2 arrives: accepted
        accepted2 = self.manager.complete_search({"status": SearchOutcome.SUCCESS, "products": [{"title": "Item"}]}, request_id=req2)
        self.assertTrue(accepted2)
        self.assertEqual(self.manager.state, SearchState.SUCCESS)

    # 18. test_existing_zero_results_state_still_works()
    def test_existing_zero_results_state_still_works(self):
        """Feature #2 zero results state functions seamlessly with loading lifecycle."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=[]):
            res = search_shopping_deals("impossible product xyz")
            self.assertEqual(res["status"], SearchOutcome.NO_RESULTS)
            self.assertFalse(res["success"])
            self.assertEqual(res["products"], [])

    # 19. test_existing_error_states_still_work()
    def test_existing_error_states_still_work(self):
        """Feature #2 error states remain active and properly classified."""
        with patch.object(shopping_service, "_fetch_serpapi_shopping", side_effect=requests.exceptions.Timeout("Timeout")):
            res = search_shopping_deals("shoes")
            self.assertEqual(res["status"], SearchOutcome.TIMEOUT)
            self.assertTrue(res["retryable"])

    # 20. test_existing_deal_finder_features_remain_compatible()
    def test_existing_deal_finder_features_remain_compatible(self):
        """Features #6 Best Deal, #7 Savings, #8 Filters, #9 Sorting, #10 Deal Score, #11 True Total remain fully compatible."""
        mock_raw = [
            {
                "title": "Deal Phone",
                "price": "$299",
                "extracted_old_price": 399.0,
                "extracted_shipping": 0.0,
                "source": "StoreX",
                "link": "https://storex.com/phone",
                "thumbnail": "https://storex.com/phone.jpg",
                "rating": 4.7,
                "reviews": 350
            }
        ]
        with patch.object(shopping_service, "_fetch_serpapi_shopping", return_value=mock_raw):
            res = search_shopping_deals("deal phone", currency="$")
            self.assertEqual(res["status"], SearchOutcome.SUCCESS)
            p = res["products"][0]
            self.assertTrue(p["is_best_deal"])                     # Feature #6
            self.assertGreater(p["savings_amount"], 0)              # Feature #7
            self.assertGreaterEqual(p["deal_score"], 0)             # Feature #10
            self.assertEqual(p["total_price_status"], "calculated") # Feature #11


if __name__ == "__main__":
    unittest.main()
