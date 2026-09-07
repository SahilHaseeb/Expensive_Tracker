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

# Mock app package to avoid executing app/__init__.py (which requires Flask runtime in standalone test runs)
if "app" not in sys.modules:
    sys.modules["app"] = types.ModuleType("app")

spec = importlib.util.spec_from_file_location(
    "shopping_service",
    os.path.join(ROOT_DIR, "app", "shopping_service.py")
)
shopping_service = importlib.util.module_from_spec(spec)
sys.modules["app.shopping_service"] = shopping_service
spec.loader.exec_module(shopping_service)

# Import helpers from shopping_service
is_search_or_category_url = shopping_service.is_search_or_category_url
extract_domain_tokens = shopping_service.extract_domain_tokens
normalize_merchant_name = shopping_service.normalize_merchant_name
match_merchant_to_url = shopping_service.match_merchant_to_url
unpack_google_redirect_url = shopping_service.unpack_google_redirect_url
extract_direct_retailer_url = shopping_service.extract_direct_retailer_url
validate_product_offer_identity = shopping_service.validate_product_offer_identity
extract_item_image = shopping_service.extract_item_image
_process_serpapi_results = shopping_service._process_serpapi_results
search_shopping_deals = shopping_service.search_shopping_deals
select_best_deal = shopping_service.select_best_deal
apply_sorting_and_badges = shopping_service.apply_sorting_and_badges
NEUTRAL_PLACEHOLDER_IMAGE = shopping_service.NEUTRAL_PLACEHOLDER_IMAGE


class TestProductIdentity(unittest.TestCase):

    def test_1_exact_product_url_and_matching_merchant_accepted(self):
        """1. Exact direct retailer product URL matching merchant is accepted as verified."""
        item = {
            "title": "Oscar de la Renta Allium Printed Cardigan",
            "source": "Moda Operandi",
            "price": "$645.00",
            "extracted_price": 645.0,
            "link": "https://www.modaoperandi.com/products/allium-printed-cardigan-odlr-101",
            "thumbnail": "https://images.modaoperandi.com/odlr-cardigan.jpg"
        }
        res = validate_product_offer_identity(item)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["identity_status"], "verified")
        self.assertTrue(res["is_direct_deal"])
        self.assertEqual(res["verified_link"], "https://www.modaoperandi.com/products/allium-printed-cardigan-odlr-101")

        # Process through _process_serpapi_results
        products = _process_serpapi_results([item], "cardigan")
        self.assertEqual(len(products), 1)
        p = products[0]
        self.assertEqual(p["title"], "Oscar de la Renta Allium Printed Cardigan")
        self.assertEqual(p["source"], "Moda Operandi")
        self.assertEqual(p["merchant"], "Moda Operandi")
        self.assertEqual(p["link"], "https://www.modaoperandi.com/products/allium-printed-cardigan-odlr-101")
        self.assertEqual(p["product_url"], "https://www.modaoperandi.com/products/allium-printed-cardigan-odlr-101")
        self.assertEqual(p["thumbnail"], "https://images.modaoperandi.com/odlr-cardigan.jpg")
        self.assertEqual(p["image"], "https://images.modaoperandi.com/odlr-cardigan.jpg")
        self.assertEqual(p["identity_status"], "verified")
        self.assertTrue(p["is_direct_deal"])

    def test_2_product_a_with_retailer_search_url_for_product_b_rejected(self):
        """2. Retailer search query URL for another product is rejected as direct product URL."""
        item = {
            "title": "Oscar de la Renta Allium Printed Cardigan",
            "source": "Moda Operandi",
            "price": "$645.00",
            "link": "https://www.modaoperandi.com/search?q=knitted+sweater+blue",
            "thumbnail": "https://images.modaoperandi.com/odlr-cardigan.jpg"
        }
        extracted = extract_direct_retailer_url(item, source_store="Moda Operandi", product_title=item["title"])
        self.assertIsNone(extracted)

        val = validate_product_offer_identity(item)
        self.assertNotEqual(val["identity_status"], "verified")
        self.assertFalse(val["is_direct_deal"])

    def test_3_product_title_from_merchant_a_with_url_from_merchant_b_rejected(self):
        """3. Merchant mismatch (e.g. Moda Operandi title/merchant + Amazon URL) is rejected."""
        item = {
            "title": "Oscar de la Renta Allium Printed Cardigan",
            "source": "Moda Operandi",
            "price": "$645.00",
            "link": "https://www.amazon.com/dp/B08XYZ1234",
            "thumbnail": "https://images.modaoperandi.com/odlr-cardigan.jpg"
        }
        # Merchant is Moda Operandi, URL is Amazon -> MUST BE REJECTED
        extracted = extract_direct_retailer_url(item, source_store="Moda Operandi", product_title=item["title"])
        self.assertIsNone(extracted)

        val = validate_product_offer_identity(item)
        self.assertNotEqual(val["identity_status"], "verified")
        self.assertFalse(val["is_direct_deal"])

    def test_4_image_fallback_never_uses_another_products_image(self):
        """4. Product A without image uses neutral placeholder; never steals Product B's image."""
        item_a = {
            "title": "Product A Without Image",
            "source": "Store A",
            "price": "$20.00",
            "link": "https://www.storea.com/products/item-a"
            # No thumbnail or image field
        }
        item_b = {
            "title": "Product B With Image",
            "source": "Store B",
            "price": "$50.00",
            "link": "https://www.storeb.com/products/item-b",
            "thumbnail": "https://images.storeb.com/item-b.jpg"
        }
        products = _process_serpapi_results([item_a, item_b], "query")
        self.assertEqual(len(products), 2)
        # Product A must have neutral placeholder, NOT Product B's image!
        self.assertEqual(products[0]["thumbnail"], NEUTRAL_PLACEHOLDER_IMAGE)
        self.assertEqual(products[0]["image"], NEUTRAL_PLACEHOLDER_IMAGE)
        self.assertNotIn("item-b.jpg", products[0]["thumbnail"])
        # Product B retains its authentic image
        self.assertEqual(products[1]["thumbnail"], "https://images.storeb.com/item-b.jpg")

    def test_5_product_a_price_never_contaminates_product_b(self):
        """5. Product prices and savings are strictly 1-to-1 and never cross-pollinate."""
        item_a = {
            "title": "Luxury Watch",
            "source": "WatchStore",
            "price": "$5,000.00",
            "extracted_price": 5000.0,
            "link": "https://www.watchstore.com/products/luxury-watch"
        }
        item_b = {
            "title": "Budget Watch",
            "source": "BudgetStore",
            "price": "$50.00",
            "extracted_price": 50.0,
            "link": "https://www.budgetstore.com/products/budget-watch"
        }
        products = _process_serpapi_results([item_a, item_b], "watch", target_curr="USD")
        self.assertGreater(products[0]["price_val"], 4000)
        self.assertLess(products[1]["price_val"], 200)

    def test_6_google_redirect_resolving_to_merchant_product_url_accepted(self):
        """6. Google adurl/url redirect unpacking to exact merchant product URL is accepted."""
        item = {
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "source": "Best Buy",
            "price": "$399.99",
            "extracted_price": 399.99,
            "link": "https://www.google.com/aclk?sa=l&ai=DChcSEwi&adurl=https%3A%2F%2Fwww.bestbuy.com%2Fsite%2Fsony-wh-1000xm5%2F6505727.p",
            "thumbnail": "https://pisces.bbystatic.com/sony-xm5.jpg"
        }
        val = validate_product_offer_identity(item)
        self.assertTrue(val["is_valid"])
        self.assertEqual(val["identity_status"], "verified")
        self.assertTrue(val["is_direct_deal"])
        self.assertEqual(val["verified_link"], "https://www.bestbuy.com/site/sony-wh-1000xm5/6505727.p")

    def test_7_google_search_url_rejected_as_direct_retailer_url(self):
        """7. Google search or unresolvable internal URLs are rejected as direct product URLs."""
        item = {
            "title": "Wireless Mouse",
            "source": "Logitech",
            "price": "$29.99",
            "link": "https://www.google.com/search?q=logitech+wireless+mouse"
        }
        extracted = extract_direct_retailer_url(item, source_store="Logitech", product_title=item["title"])
        self.assertIsNone(extracted)

    def test_8_retailer_search_urls_rejected_as_direct_product_urls(self):
        """8. Retailer search URLs (/search?q=..., /s?k=..., etc.) are rejected."""
        search_urls = [
            "https://www.amazon.com/s?k=wireless+earbuds",
            "https://www.walmart.com/search?q=laptop",
            "https://www.daraz.pk/catalog/?q=shoes",
            "https://www.ebay.com/sch/i.html?_nkw=watch",
            "https://www.target.com/s?searchTerm=blender",
            "https://www.bestbuy.com/site/searchpage.jsp?st=tv",
            "https://www.shein.com/pdsearch/dress/",
            "https://www.samsclub.com/s/coffee"
        ]
        for url in search_urls:
            self.assertTrue(
                is_search_or_category_url(url),
                f"URL should have been detected as search URL: {url}"
            )
            item = {"title": "Test Item", "source": "Store", "link": url}
            extracted = extract_direct_retailer_url(item, source_store="Store", product_title="Test Item")
            self.assertIsNone(extracted, f"Search URL was not rejected: {url}")

    def test_9_missing_direct_product_url_handled_without_inventing_urls(self):
        """9. Missing direct product URL never invents a synthetic search link; marks status unverified or partially verified."""
        # Case A: Has Google Shopping product_link -> partially_verified
        item_a = {
            "title": "Specialty Item",
            "source": "Boutique Store",
            "price": "$120.00",
            "product_id": "123456789",
            "product_link": "https://www.google.com/shopping/product/123456789?gl=us"
        }
        val_a = validate_product_offer_identity(item_a)
        self.assertEqual(val_a["identity_status"], "partially_verified")
        self.assertFalse(val_a["is_direct_deal"])
        self.assertEqual(val_a["verified_link"], "https://www.google.com/shopping/product/123456789?gl=us")

        # Case B: No URL fields at all -> unverified, link is None (no fake Amazon search URL!)
        item_b = {
            "title": "Moda Operandi Cardigan",
            "source": "Moda Operandi",
            "price": "$500.00"
        }
        val_b = validate_product_offer_identity(item_b)
        self.assertEqual(val_b["identity_status"], "unverified")
        self.assertFalse(val_b["is_direct_deal"])
        self.assertIsNone(val_b["verified_link"])

    def test_10_missing_image_uses_neutral_placeholder_only(self):
        """10. Missing image produces neutral SVG placeholder, never an inferred/guessed image."""
        item = {"title": "Item Without Image", "source": "Store"}
        img = extract_item_image(item)
        self.assertEqual(img, NEUTRAL_PLACEHOLDER_IMAGE)
        self.assertIn("<svg", img)

    def test_11_merchant_and_final_url_domain_mismatch_rejected(self):
        """11. Mismatch between merchant and URL host domain is strictly rejected."""
        mismatches = [
            ("Moda Operandi", "https://www.amazon.com/s?k=cardigan"),
            ("Best Buy", "https://www.walmart.com/ip/12345"),
            ("Daraz", "https://priceoye.pk/product/123"),
            ("Nike", "https://www.adidas.com/us/shoes"),
            ("Apple", "https://www.samsung.com/galaxy")
        ]
        for merchant, url in mismatches:
            self.assertFalse(
                match_merchant_to_url(merchant, url),
                f"Expected mismatch for merchant '{merchant}' and url '{url}'"
            )

    def test_12_existing_features_continue_working_on_validated_offer_objects(self):
        """12. Best Deal, Savings, Sorting, Deal Score, and True Total Price work on validated objects."""
        items = [
            {
                "title": "Wireless Earbuds Pro",
                "source": "Daraz",
                "price": "$50.00",
                "extracted_price": 50.0,
                "old_price": "$100.00",
                "extracted_old_price": 100.0,
                "link": "https://www.daraz.pk/products/earbuds-pro-i101.html",
                "thumbnail": "https://img.daraz.pk/earbuds.jpg"
            },
            {
                "title": "Wireless Earbuds Standard",
                "source": "Daraz",
                "price": "$80.00",
                "extracted_price": 80.0,
                "link": "https://www.daraz.pk/products/earbuds-std-i102.html",
                "thumbnail": "https://img.daraz.pk/earbuds-std.jpg"
            }
        ]
        products = _process_serpapi_results(items, "earbuds", target_curr="Rs.")
        self.assertEqual(len(products), 2)

        # Feature #7: Savings Calculator
        self.assertIsNotNone(products[0]["savings_amount"])
        self.assertGreater(products[0]["savings_amount"], 0)

        # Feature #11: True Total Price
        self.assertIn("total_price", products[0])
        self.assertIn("total_price_status", products[0])

        # Feature #6 & #10: Best Deal Badge and Deal Score
        shopping_service.calculate_deal_scores(products)
        apply_sorting_and_badges(products, sort_by="relevance")
        self.assertEqual(len(products), 2)
        best_deals = [p for p in products if p.get("is_best_deal")]
        self.assertEqual(len(best_deals), 1)
        self.assertEqual(best_deals[0]["title"], "Wireless Earbuds Pro")
        self.assertIsNotNone(best_deals[0]["deal_score"])

    @patch.object(shopping_service, "_fetch_serpapi_shopping")
    def test_13_smart_search_and_spelling_correction_still_works(self, mock_fetch):
        """13. Smart search and spelling correction continue operating end-to-end."""
        mock_fetch.return_value = [
            {
                "title": "Apple iPhone 15 Pro",
                "source": "Apple",
                "price": "$999.00",
                "extracted_price": 999.0,
                "link": "https://www.apple.com/shop/buy-iphone/iphone-15-pro",
                "thumbnail": "https://apple.com/iphone15.jpg"
            }
        ]
        # Query with deliberate typo
        result = search_shopping_deals("iphne 15")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["products"]), 1)
        self.assertEqual(result["products"][0]["source"], "Apple")
        self.assertEqual(result["products"][0]["identity_status"], "verified")

    def test_14_multiple_products_from_same_merchant_remain_separate(self):
        """14. Multiple items from the same merchant do not accidentally share links, images, or prices."""
        items = [
            {
                "title": "Nike Air Max 90",
                "source": "Nike",
                "price": "$130.00",
                "extracted_price": 130.0,
                "link": "https://www.nike.com/t/air-max-90-shoes-101",
                "thumbnail": "https://static.nike.com/airmax90.jpg"
            },
            {
                "title": "Nike Pegasus 40",
                "source": "Nike",
                "price": "$140.00",
                "extracted_price": 140.0,
                "link": "https://www.nike.com/t/pegasus-40-running-shoes-102",
                "thumbnail": "https://static.nike.com/pegasus40.jpg"
            }
        ]
        products = _process_serpapi_results(items, "nike")
        self.assertEqual(len(products), 2)
        # Check distinct identity fields
        self.assertNotEqual(products[0]["link"], products[1]["link"])
        self.assertNotEqual(products[0]["thumbnail"], products[1]["thumbnail"])
        self.assertNotEqual(products[0]["price_val"], products[1]["price_val"])
        self.assertEqual(products[0]["link"], "https://www.nike.com/t/air-max-90-shoes-101")
        self.assertEqual(products[1]["link"], "https://www.nike.com/t/pegasus-40-running-shoes-102")

    def test_15_results_from_different_merchants_never_cross_contaminate(self):
        """15. Different merchants never cross-contaminate product titles, prices, or links."""
        items = [
            {
                "title": "Dyson V15 Detect Vacuum",
                "source": "Target",
                "price": "$749.99",
                "extracted_price": 749.99,
                "link": "https://www.target.com/p/dyson-v15-detect/-/A-82467812",
                "thumbnail": "https://target.scene7.com/dyson15.jpg"
            },
            {
                "title": "Dyson V15 Detect Cordless Vacuum",
                "source": "Best Buy",
                "price": "$749.99",
                "extracted_price": 749.99,
                "link": "https://www.bestbuy.com/site/dyson-v15-detect/6451368.p",
                "thumbnail": "https://pisces.bbystatic.com/dyson15.jpg"
            }
        ]
        products = _process_serpapi_results(items, "dyson")
        self.assertEqual(products[0]["source"], "Target")
        self.assertIn("target.com", products[0]["link"])
        self.assertEqual(products[1]["source"], "Best Buy")
        self.assertIn("bestbuy.com", products[1]["link"])

    def test_16_multi_category_exact_consistency_simulation(self):
        """
        16. Verifies 1-to-1 consistency across multiple diverse product categories:
        Fashion, Electronics, Household, and Apparel.
        For every card:
        APP TITLE == SOURCE TITLE
        APP IMAGE == SOURCE IMAGE
        APP PRICE == SOURCE PRICE
        APP MERCHANT == SOURCE MERCHANT
        VIEW DEAL URL == EXACT SOURCE PRODUCT/OFFER
        """
        category_samples = [
            # 1. Fashion Product
            {
                "title": "Oscar de la Renta Allium Printed Cardigan",
                "source": "Moda Operandi",
                "price": "$1,290.00",
                "extracted_price": 1290.0,
                "link": "https://www.modaoperandi.com/products/allium-printed-cardigan-odlr",
                "thumbnail": "https://images.modaoperandi.com/odlr-allium-cardigan.jpg",
                "product_id": "MODA_ODLR_001"
            },
            # 2. Electronics Product
            {
                "title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
                "source": "Best Buy",
                "price": "$399.99",
                "extracted_price": 399.99,
                "link": "https://www.bestbuy.com/site/sony-wh-1000xm5/6505727.p",
                "thumbnail": "https://pisces.bbystatic.com/sony-wh1000xm5.jpg",
                "product_id": "BB_SONY_XM5"
            },
            # 3. Household Product
            {
                "title": "Dyson V15 Detect Extra Cordless Vacuum",
                "source": "Target",
                "price": "$749.99",
                "extracted_price": 749.99,
                "link": "https://www.target.com/p/dyson-v15-detect-extra/-/A-82467812",
                "thumbnail": "https://target.scene7.com/dyson-v15-target.jpg",
                "product_id": "TARGET_DYSON_V15"
            },
            # 4. Apparel Product
            {
                "title": "Nike Air Max 270 Men's Shoes",
                "source": "Nike",
                "price": "$160.00",
                "extracted_price": 160.0,
                "link": "https://www.nike.com/t/air-max-270-mens-shoes-KkLcGR/AH8050-002",
                "thumbnail": "https://static.nike.com/air-max-270-black.jpg",
                "product_id": "NIKE_AM270_002"
            }
        ]

        products = _process_serpapi_results(category_samples, "multi-category")
        self.assertEqual(len(products), 4)

        for original_sample, processed_card in zip(category_samples, products):
            # 1. APP TITLE == SOURCE PRODUCT TITLE
            self.assertEqual(processed_card["title"], original_sample["title"])

            # 2. APP IMAGE == SOURCE PRODUCT IMAGE
            self.assertEqual(processed_card["thumbnail"], original_sample["thumbnail"])
            self.assertEqual(processed_card["image"], original_sample["thumbnail"])

            # 3. APP MERCHANT == SOURCE MERCHANT
            self.assertEqual(processed_card["source"], original_sample["source"])
            self.assertEqual(processed_card["merchant"], original_sample["source"])

            # 4. VIEW DEAL URL == EXACT SOURCE PRODUCT/OFFER
            self.assertEqual(processed_card["link"], original_sample["link"])
            self.assertEqual(processed_card["product_url"], original_sample["link"])
            self.assertEqual(processed_card["identity_status"], "verified")
            self.assertTrue(processed_card["is_direct_deal"])

            # 5. PRODUCT IDENTIFIERS PRESERVED
            self.assertEqual(processed_card["product_id"], original_sample["product_id"])


if __name__ == "__main__":
    unittest.main()
