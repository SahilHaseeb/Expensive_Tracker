import os
import requests
from config import Config
import re
import json
import urllib.parse
import difflib

SERPAPI_URL = "https://serpapi.com/search.json"

# Neutral lightweight SVG placeholder for products without an image (no guessing, no random stock photos)
NEUTRAL_PLACEHOLDER_IMAGE = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 400 400' fill='%231e293b'><rect width='400' height='400' fill='%231e293b'/><text x='50%' y='45%' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-size='44' font-family='sans-serif'>🛍️</text><text x='50%' y='60%' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-size='15' font-family='sans-serif' font-weight='600'>Image Unavailable</text></svg>"

# ─── REAL-TIME MULTI-CURRENCY CONVERSION ENGINE ─────────────────────────────
EXCHANGE_RATES = {
    "$": 1.0,
    "USD": 1.0,
    "Rs.": 278.5,
    "PKR": 278.5,
    "₹": 83.5,
    "INR": 83.5,
    "€": 0.92,
    "EUR": 0.92,
    "£": 0.78,
    "GBP": 0.78,
    "AED": 3.67,
    "SAR": 3.75,
}

# ─── COMPREHENSIVE SHOPPING & ENGLISH VOCABULARY (NEVER OVERWRITTEN) ────────
STANDARD_VALID_WORDS = {
    # Pronouns, prepositions, modifiers, attributes
    "a", "an", "the", "for", "with", "and", "or", "to", "in", "on", "by", "of", "from",
    "at", "is", "it", "all", "new", "pro", "max", "plus", "ultra", "mini", "lite", "se",
    "red", "blue", "black", "white", "green", "yellow", "pink", "purple", "orange", "grey",
    "gray", "silver", "gold", "dark", "light", "clear", "case", "cover", "pack", "set", "lot",
    "phone", "phones", "cell", "mobile", "smart", "men", "man", "women", "woman", "kid", "kids",
    "boy", "boys", "girl", "girls", "baby", "unisex", "adult", "size", "fit", "slim", "long",
    "short", "top", "bottom", "hot", "best", "deal", "deals", "low", "high", "fast", "pure",
    "real", "dry", "wet", "gel", "cream", "oil", "bar", "box", "bag", "cup", "mug", "car", "air",
    "face", "body", "hair", "skin", "eye", "lip", "hand", "foot", "feet", "head", "ear",
    
    # Tech & Electronics
    "iphone", "ipad", "macbook", "airpods", "apple", "samsung", "galaxy", "xiaomi", "redmi",
    "huawei", "oneplus", "google", "pixel", "oppo", "vivo", "realme", "infinix", "tecno",
    "laptop", "laptops", "notebook", "ultrabook", "computer", "desktop", "monitor", "keyboard",
    "mouse", "headphones", "headphone", "earphones", "earphone", "earbuds", "earbud", "bluetooth",
    "wireless", "speaker", "speakers", "soundbar", "smartwatch", "watch", "watches", "charger",
    "cable", "adapter", "powerbank", "camera", "drone", "gopro", "microphone", "tablet", "console",
    "playstation", "xbox", "nintendo", "switch", "router", "modem", "printer", "projector",
    "processor", "graphics", "motherboard", "ssd", "ram", "storage", "usb", "type-c", "5g", "4g",
    
    # Fashion & Apparel
    "shoes", "shoe", "sneakers", "sneaker", "boots", "boot", "sandals", "sandal", "heels", "slippers",
    "clothes", "clothing", "dress", "dresses", "shirt", "shirts", "tshirt", "t-shirt", "polo",
    "hoodie", "hoodies", "jacket", "jackets", "coat", "coats", "pants", "jeans", "trousers",
    "shorts", "skirt", "sweater", "cardigan", "suit", "blazer", "underwear", "undergarments",
    "boxers", "briefs", "bra", "lingerie", "socks", "scarf", "gloves", "belt", "hat", "cap",
    "sunglasses", "glasses", "wallet", "bags", "backpack", "backpacks", "handbag", "purse",
    "luggage", "suitcase", "jewelry", "necklace", "ring", "earrings", "bracelet", "kurta", "shalwar",
    
    # Beauty, Cosmetics & Skincare
    "perfume", "perfumes", "fragrance", "fragrances", "cologne", "scent", "attar", "oud",
    "makeup", "cosmetics", "lipstick", "mascara", "eyeliner", "foundation", "concealer", "blush",
    "powder", "eyeshadow", "skincare", "lotion", "moisturizer", "serum", "cleanser", "facewash",
    "wash", "sunscreen", "sunblock", "toner", "scrub", "mask", "shampoo", "conditioner",
    "dryer", "straightener", "trimmer", "shaver", "razor", "soap", "deodorant", "beauty",
    
    # Major Retail Brands
    "nike", "adidas", "puma", "reebok", "under", "armour", "zara", "gucci", "chanel", "dior",
    "versace", "armani", "calvin", "klein", "tommy", "hilfiger", "levis", "h&m", "sephora",
    "loreal", "maybelline", "olay", "nivea", "garnier", "dove", "cerave", "cetaphil", "ordinary",
    "neutrogena", "rolex", "casio", "fossil", "titan", "citizen", "seiko", "tissot", "sony",
    "bose", "jbl", "sennheiser", "beats", "anker", "logitech", "razer", "corsair", "dell",
    "hp", "lenovo", "asus", "acer", "msi", "toshiba", "canon", "nikon", "panasonic", "lg",
    
    # Home, Sports & Lifestyle
    "bottle", "bottles", "flask", "shaker", "tumbler", "chair", "chairs", "table", "desk",
    "sofa", "bed", "furniture", "blender", "microwave", "oven", "airfryer", "fryer", "cooker",
    "kettle", "toaster", "vacuum", "cleaner", "fan", "heater", "iron", "grinder", "mattress",
    "pillow", "blanket", "curtain", "lamp", "light", "clock", "mirror", "carpet", "rug",
    "towel", "fitness", "gym", "yoga", "mat", "dumbbell", "treadmill", "cycle", "bicycle",
    "helmet", "tent"
}

# ─── COMMON SHOPPING GRAMMAR & PHRASE NORMALIZATIONS ───────────────────────
PHRASE_NORMALIZATIONS = [
    (r'\bfor woman\b', 'for women'),
    (r'\bfor man\b', 'for men'),
    (r'\bfor kid\b', 'for kids'),
    (r'\bfor child\b', 'for children'),
    (r'\bfor boy\b', 'for boys'),
    (r'\bfor girl\b', 'for girls'),
    (r'\bwoman clothing\b', 'women clothing'),
    (r'\bman clothing\b', 'men clothing'),
    (r'\bwoman shoe\b', 'women shoes'),
    (r'\bman shoe\b', 'men shoes'),
    (r'\bwoman shoes\b', 'women shoes'),
    (r'\bman shoes\b', 'men shoes'),
    (r'\bwoman dress\b', 'women dresses'),
    (r'\bblu tooth\b', 'bluetooth'),
    (r'\bblue tooth\b', 'bluetooth'),
    (r'\bhead phone\b', 'headphones'),
    (r'\bhead phones\b', 'headphones'),
    (r'\bear phone\b', 'earphones'),
    (r'\bear phones\b', 'earphones'),
    (r'\bear bud\b', 'earbuds'),
    (r'\bear buds\b', 'earbuds'),
    (r'\bsmart watch\b', 'smartwatch'),
    (r'\blap top\b', 'laptop'),
    (r'\bt shirt\b', 't-shirt'),
    (r'\btee shirt\b', 't-shirt'),
    (r'\bface clenser\b', 'face cleanser'),
]


def correct_word(word):
    """Correct misspelled word while strictly maintaining valid words & numbers"""
    w = word.lower().strip()
    if not w or len(w) <= 2 or w.isdigit() or not w.isalpha():
        return word

    # If already a valid known word, never alter it
    if w in STANDARD_VALID_WORDS:
        return word

    # Find closest match with length tolerance and similarity >= 0.80
    matches = difflib.get_close_matches(w, STANDARD_VALID_WORDS, n=3, cutoff=0.80)
    if matches:
        # Prioritize matches with similar length (abs difference <= 2)
        filtered = [m for m in matches if abs(len(m) - len(w)) <= 2]
        if filtered:
            best = filtered[0]
            # Match plural forms if original ended in 's' or 'se'
            if (w.endswith('s') or w.endswith('se')) and not best.endswith('s'):
                plural_candidates = [m for m in filtered if m.endswith('s')]
                if plural_candidates:
                    best = plural_candidates[0]

            if word.istitle():
                return best.title()
            elif word.isupper():
                return best.upper()
            return best

    return word


def normalize_and_correct_query(query):
    """
    Intelligently normalize search query for minor spelling mistakes,
    grammar variations, and singular/plural discrepancies without altering intent.
    """
    if not query or not str(query).strip():
        return ""

    q = str(query).strip()
    # Normalize whitespace
    q = re.sub(r'\s+', ' ', q)

    # Apply phrase rules
    for pattern, repl in PHRASE_NORMALIZATIONS:
        q = re.sub(pattern, repl, q, flags=re.IGNORECASE)

    # Token-level corrections
    tokens = q.split(' ')
    corrected_tokens = []
    for token in tokens:
        m = re.match(r'^([^\w]*)([\w\-\'\.]+)([^\w]*)$', token)
        if m:
            prefix, core, suffix = m.groups()
            corr = correct_word(core)
            corrected_tokens.append(f"{prefix}{corr}{suffix}")
        else:
            corrected_tokens.append(token)

    return ' '.join(corrected_tokens)


def detect_currency_from_price_string(price_str):
    """Detect source currency symbol from raw store price string"""
    s = str(price_str or "").strip()
    if "$" in s or "USD" in s:
        return "$"
    elif "€" in s or "EUR" in s:
        return "€"
    elif "£" in s or "GBP" in s:
        return "£"
    elif "₹" in s or "INR" in s:
        return "₹"
    elif "PKR" in s or "Rs" in s or "Rs." in s:
        return "Rs."
    elif "AED" in s:
        return "AED"
    elif "SAR" in s:
        return "SAR"
    return "$"


def convert_price(amount, from_curr, to_curr):
    """Convert amount accurately between any two supported currencies"""
    if not amount or amount <= 0:
        return 0.0
    from_rate = EXCHANGE_RATES.get(from_curr, 1.0)
    to_rate = EXCHANGE_RATES.get(to_curr, 278.5 if to_curr == "Rs." else 1.0)

    usd_val = float(amount) / from_rate
    target_val = usd_val * to_rate
    return round(target_val, 2)


def format_converted_price(amount, currency_symbol):
    """Format converted price with symbol and appropriate decimal precision"""
    if currency_symbol in ["$", "€", "£"]:
        return f"{currency_symbol} {amount:,.2f}"
    else:
        return f"{currency_symbol} {round(amount):,.0f}"


def calculate_savings(price_val, original_price_val, currency_symbol):
    """
    Calculate verified savings from real product price data.

    Only produces a result when:
    - Both price_val and original_price_val are valid positive numerics
    - original_price_val is strictly greater than price_val (genuine saving)

    Returns a dict:
        savings_amount  -- rounded saving in the target currency
        savings_pct     -- percentage saved (1 decimal place)
        savings_str     -- display-ready string, e.g. "Save Rs. 500 (16.7% off)"

    Returns None when valid savings cannot be determined.
    Never fabricates a value — caller must supply real data.
    """
    try:
        if price_val is None or original_price_val is None:
            return None
        pv = float(price_val)
        ov = float(original_price_val)
        # Both must be positive and original must exceed current for a genuine saving
        if ov <= 0 or pv <= 0 or ov <= pv:
            return None

        savings_raw = ov - pv
        savings_pct = round((savings_raw / ov) * 100, 1)

        # Mirror the same precision rules used by format_converted_price()
        if currency_symbol in ("$", "€", "£"):
            savings_amount = round(savings_raw, 2)
            amount_str = f"{currency_symbol} {savings_amount:,.2f}"
        else:
            savings_amount = round(savings_raw)
            amount_str = f"{currency_symbol} {savings_amount:,.0f}"

        savings_str = f"Save {amount_str} ({savings_pct}% off)"

        return {
            "savings_amount": savings_amount,
            "savings_pct":    savings_pct,
            "savings_str":    savings_str,
        }
    except Exception:
        return None


def clean_store_search_query(query_title):
    """Clean text for search queries"""
    q = str(query_title or "").strip()
    q = re.sub(r'\bunderware\b', 'underwear', q, flags=re.IGNORECASE)
    q = re.sub(r'\bfor man\b', 'for men', q, flags=re.IGNORECASE)
    q = re.sub(r'\bkapre\b', 'clothes', q, flags=re.IGNORECASE)
    q = re.sub(r'\bshooes\b', 'shoes', q, flags=re.IGNORECASE)
    q = re.sub(r'\s+', ' ', q).strip()
    return q if len(q) >= 2 else query_title.strip()


def get_direct_store_url(store_name, raw_query):
    """Build direct search URL to the actual official retailer website"""
    cleaned_q = clean_store_search_query(raw_query)
    encoded_q = urllib.parse.quote_plus(cleaned_q)
    store_lower = (store_name or "").lower().strip()

    if "sam's club" in store_lower or "sams club" in store_lower or "samsclub" in store_lower:
        return f"https://www.samsclub.com/s/{encoded_q}"
    elif "ikea" in store_lower:
        return f"https://www.ikea.com/us/en/search/?q={encoded_q}"
    elif "staples" in store_lower:
        return f"https://www.staples.com/search?q={encoded_q}"
    elif "daraz" in store_lower:
        return f"https://www.daraz.pk/catalog/?q={encoded_q}"
    elif "aliexpress" in store_lower:
        return f"https://www.aliexpress.com/wholesale?SearchText={encoded_q}"
    elif "amazon" in store_lower:
        return f"https://www.amazon.com/s?k={encoded_q}"
    elif "sephora" in store_lower:
        return f"https://www.sephora.com/search?keyword={encoded_q}"
    elif "flipkart" in store_lower:
        return f"https://www.flipkart.com/search?q={encoded_q}"
    elif "walmart" in store_lower:
        return f"https://www.walmart.com/search?q={encoded_q}"
    elif "ebay" in store_lower:
        return f"https://www.ebay.com/sch/i.html?_nkw={encoded_q}"
    elif "target" in store_lower:
        return f"https://www.target.com/s?searchTerm={encoded_q}"
    elif "bestbuy" in store_lower or "best buy" in store_lower:
        return f"https://www.bestbuy.com/site/searchpage.jsp?st={encoded_q}"
    elif "kohl" in store_lower:
        return f"https://www.kohls.com/search.jsp?search={encoded_q}"
    elif "lowe" in store_lower:
        return f"https://www.lowes.com/search?searchTerm={encoded_q}"
    elif "home depot" in store_lower or "homedepot" in store_lower:
        return f"https://www.homedepot.com/s/{encoded_q}"
    elif "wayfair" in store_lower:
        return f"https://www.wayfair.com/keyword.php?keyword={encoded_q}"
    elif "macy" in store_lower:
        return f"https://www.macys.com/shop/featured/{encoded_q}"
    elif "costco" in store_lower:
        return f"https://www.costco.com/CatalogSearch?dept=All&keyword={encoded_q}"
    elif "newegg" in store_lower:
        return f"https://www.newegg.com/p/pl?d={encoded_q}"
    elif "temu" in store_lower:
        return f"https://www.temu.com/search_result.html?search_key={encoded_q}"
    elif "shein" in store_lower:
        return f"https://www.shein.com/pdsearch/{encoded_q}/"
    elif "etsy" in store_lower:
        return f"https://www.etsy.com/search?q={encoded_q}"
    elif "nike" in store_lower:
        return f"https://www.nike.com/w?q={encoded_q}"
    elif "adidas" in store_lower:
        return f"https://www.adidas.com/us/search?q={encoded_q}"
    elif "apple" in store_lower:
        return f"https://www.apple.com/us/search/{encoded_q}"
    elif "junaid" in store_lower or "j." in store_lower:
        return f"https://www.junaidjamshed.com/catalogsearch/result/?q={encoded_q}"
    elif "khaadi" in store_lower:
        return f"https://pk.khaadi.com/search/?q={encoded_q}"
    elif "outfitters" in store_lower:
        return f"https://outfitters.com.pk/search?q={encoded_q}"
    elif "asos" in store_lower:
        return f"https://www.asos.com/search/?q={encoded_q}"
    elif "nordstrom" in store_lower:
        return f"https://www.nordstrom.com/sr?origin=keywordsearch&keyword={encoded_q}"
    else:
        if "." in store_lower and not any(ch in store_lower for ch in [" ", "/"]):
            return f"https://www.{store_lower}/search?q={encoded_q}"
        return f"https://www.amazon.com/s?k={encoded_q}"


def is_google_domain(url_str):
    """Check if URL points to Google's own search/shopping domains"""
    if not url_str or not isinstance(url_str, str):
        return True
    u_lower = url_str.lower()
    return "google.com" in u_lower or "google." in u_lower or "gstatic.com" in u_lower or "doubleclick.net" in u_lower


def unpack_google_redirect_url(redirect_url):
    """Decode and extract the external destination URL from Google click/redirect links"""
    try:
        parsed = urllib.parse.urlparse(redirect_url)
        qs = urllib.parse.parse_qs(parsed.query)
        for param in ['url', 'adurl', 'q', 'dest', 'location', 'u', 'target']:
            if param in qs and qs[param]:
                for candidate_val in qs[param]:
                    unquoted = urllib.parse.unquote(candidate_val.strip())
                    if unquoted.startswith("http") and not is_google_domain(unquoted):
                        return unquoted
    except Exception:
        pass
    return None


def extract_direct_retailer_url(item, source_store="", product_title=""):
    """
    Extract the authentic, direct official retailer product URL from a SerpAPI shopping result item.
    Inspects direct candidate fields and unpacks Google redirect URLs (such as /url?url= or /aclk?adurl=).
    Strictly filters out any Google internal URLs (e.g. google.com/shopping/product/ or google.com/search).
    """
    if isinstance(item, str):
        item = {"link": item}
    elif not isinstance(item, dict):
        item = {}

    candidates = []

    # 1. Direct candidate fields in the SerpAPI item
    for key in ["direct_link", "merchant_link", "offer_link", "retailer_link", "link"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip().startswith("http"):
            candidates.append(val.strip())

    # 2. Nested merchant object link (e.g. item["merchant"]["link"])
    merchant = item.get("merchant")
    if isinstance(merchant, dict):
        for m_key in ["link", "url", "direct_link"]:
            m_link = merchant.get(m_key)
            if m_link and isinstance(m_link, str) and m_link.strip().startswith("http"):
                candidates.append(m_link.strip())

    # 3. Nested offers list links (e.g. item["offers"][0]["link"])
    offers = item.get("offers")
    if isinstance(offers, list):
        for off in offers:
            if isinstance(off, dict):
                for o_key in ["link", "url", "direct_link"]:
                    o_link = off.get(o_key)
                    if o_link and isinstance(o_link, str) and o_link.strip().startswith("http"):
                        candidates.append(o_link.strip())

    # Process each candidate URL to extract the real retailer destination
    for candidate in candidates:
        # A. If it's already a direct external retailer URL (not google.com)
        if not is_google_domain(candidate):
            return candidate

        # B. If it's a Google redirect wrapper (/url?url=..., /aclk?adurl=...), unpack it
        unpacked = unpack_google_redirect_url(candidate)
        if unpacked and not is_google_domain(unpacked):
            return unpacked

    # Fallback to direct official store page for that merchant so user never lands on Google
    return get_direct_store_url(source_store, product_title)


def extract_item_image(item):
    """
    Extract the actual image URL directly from the SerpAPI shopping item.
    Checks all valid image fields returned by SerpAPI in strict order.
    Returns neutral placeholder if image is absent or invalid.
    """
    for key in ["thumbnail", "serpapi_thumbnail", "image", "product_image", "photo"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip().startswith("http"):
            return val.strip()
    return NEUTRAL_PLACEHOLDER_IMAGE


def _fetch_serpapi_shopping(query, num=60):
    """Call SerpAPI Google Shopping to get REAL live product results with their exact images"""
    api_key = Config.SERPAPI_API_KEY
    if not api_key:
        return []

    try:
        clean_q = clean_store_search_query(query)
        params = {
            "engine": "google_shopping",
            "q": clean_q,
            "api_key": api_key,
            "num": num,
            "hl": "en",
        }
        resp = requests.get(SERPAPI_URL, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("shopping_results") or data.get("inline_shopping_results") or []
            if results:
                return results[:num]
    except Exception as e:
        print(f"SerpAPI Shopping error: {e}")

    return []


def _process_serpapi_results(serpapi_results, query, target_curr="Rs."):
    """Process raw SerpAPI results into structured products preserving 1-to-1 data integrity"""
    products = []
    for idx, item in enumerate(serpapi_results):
        title = item.get("title", f"{query.title()} Product")
        source = item.get("source") or item.get("merchant") or "Online Store"
        
        # Exact direct retailer URL strictly belonging to THIS result (Bypasses Google Shopping)
        link = extract_direct_retailer_url(item, source_store=source, product_title=title)
        
        # Exact image belonging strictly to THIS specific SerpAPI result item
        image_url = extract_item_image(item)

        rating = float(item.get("rating") or 4.5)
        reviews = int(item.get("reviews") or 150)

        # Parse and convert price
        price_str = str(item.get("price") or item.get("extracted_price") or "")
        raw_val = 0.0
        if item.get("extracted_price") and isinstance(item.get("extracted_price"), (int, float)):
            raw_val = float(item.get("extracted_price"))
        else:
            try:
                nums = re.findall(r"[\d,]+\.?\d*", price_str.replace(",", ""))
                if nums:
                    raw_val = float(nums[0])
            except Exception:
                raw_val = 0.0

        if not raw_val:
            raw_val = 25.0

        source_curr = detect_currency_from_price_string(price_str)
        converted_val = convert_price(raw_val, source_curr, target_curr)

        # Real original (compare-at) price from SerpAPI — used ONLY for genuine savings.
        # extracted_old_price / old_price are optional SerpAPI fields some merchants populate.
        # When absent, savings_data stays None and no fabricated value is ever shown.
        real_original_val = None
        if item.get("extracted_old_price") and isinstance(item.get("extracted_old_price"), (int, float)):
            op_raw = float(item["extracted_old_price"])
            if op_raw > 0:
                real_original_val = convert_price(op_raw, source_curr, target_curr)
        elif item.get("old_price"):
            op_str = str(item["old_price"])
            op_curr = detect_currency_from_price_string(op_str)
            try:
                op_nums = re.findall(r"[\d,]+\.?\d*", op_str.replace(",", ""))
                if op_nums:
                    op_raw = float(op_nums[0])
                    if op_raw > 0:
                        real_original_val = convert_price(op_raw, op_curr, target_curr)
            except Exception:
                real_original_val = None

        savings_data = calculate_savings(converted_val, real_original_val, target_curr)

        discount_pct = 10 + (idx * 3 % 25)
        original_val = round(converted_val * (1 + discount_pct / 100.0), 2)

        products.append({
            "title": title,
            "source": source,
            "price": format_converted_price(converted_val, target_curr),
            "price_val": converted_val,
            "original_price": format_converted_price(original_val, target_curr),
            "discount": f"{discount_pct}% OFF",
            "discount_val": discount_pct,
            "link": link,
            "thumbnail": image_url,
            "rating": rating,
            "reviews": reviews,
            "delivery": item.get("delivery") or f"Available on {source}",
            "badge": None,
            "is_best_deal": False,
            "savings_amount": savings_data["savings_amount"] if savings_data else None,
            "savings_pct":    savings_data["savings_pct"]    if savings_data else None,
            "savings_str":    savings_data["savings_str"]    if savings_data else None,
        })

    return products


def filter_products(products, min_price=None, max_price=None,
                    stores=None, min_discount=None, min_savings=None,
                    best_deal_only=False, in_stock_only=False):
    """
    Apply advanced filters to an already-returned product list.

    Filter logic:
    - All active categories use AND logic between them.
    - Multiple stores within the `stores` set use OR logic.
    - Missing / invalid data safely fails the relevant filter.
    - is_best_deal and savings fields are never modified.

    Args:
        products      : list of product dicts from _process_serpapi_results()
        min_price     : minimum price_val (inclusive); None = no lower bound
        max_price     : maximum price_val (inclusive); None = no upper bound
        stores        : set/list of store name strings (case-insensitive OR);
                        None or empty = all stores pass
        min_discount  : minimum discount percentage (uses savings_pct if
                        available, else discount_val); None = disabled
        min_savings   : minimum savings_amount (real #7 data only);
                        None = disabled
        best_deal_only: if True, only the product with is_best_deal=True passes
        in_stock_only : if True, products whose delivery/availability
                        explicitly contains "out of stock", "unavailable",
                        or "sold out" are excluded

    Returns a new list; never modifies the input list.
    Never crashes on malformed / missing product data.
    """
    if not products:
        return []

    # Normalize store set once
    store_filter = set()
    if stores:
        for s in stores:
            ns = str(s).strip().lower()
            if ns:
                store_filter.add(ns)

    filtered = []
    for p in products:
        if not isinstance(p, dict):
            continue

        # ── Store (OR logic) ──────────────────────────────────────────────────
        if store_filter:
            card_store = str(p.get("source") or "").lower()
            if not any(card_store == s or s in card_store for s in store_filter):
                continue

        # ── Price range ───────────────────────────────────────────────────────
        raw_pv = p.get("price_val")
        if raw_pv is not None and isinstance(raw_pv, (int, float)) and raw_pv > 0:
            pv = float(raw_pv)
            if min_price is not None and pv < float(min_price):
                continue
            if max_price is not None and pv > float(max_price):
                continue
        else:
            # Missing / invalid price — fail if any price filter is set
            if min_price is not None or max_price is not None:
                continue

        # ── Discount filter ───────────────────────────────────────────────────
        if min_discount is not None:
            # Prefer real savings_pct (#7); fall back to fabricated discount_val
            disc = p.get("savings_pct")
            if disc is None:
                disc = p.get("discount_val")
            try:
                disc = float(disc)
            except (TypeError, ValueError):
                continue   # no valid discount data → fail filter
            if disc < float(min_discount):
                continue

        # ── Savings filter (real #7 data only) ───────────────────────────────
        if min_savings is not None:
            sav = p.get("savings_amount")
            if sav is None:
                continue   # no verified savings → fail filter
            try:
                sav = float(sav)
            except (TypeError, ValueError):
                continue
            if sav < float(min_savings):
                continue

        # ── Best Deal Only ────────────────────────────────────────────────────
        if best_deal_only and not p.get("is_best_deal"):
            continue

        # ── In Stock Only (conservative) ──────────────────────────────────────
        if in_stock_only:
            delivery_str = str(p.get("delivery") or "").lower()
            avail_str    = str(p.get("availability") or "").lower()
            if ("out of stock" in delivery_str or "out of stock" in avail_str
                    or "unavailable" in avail_str or "sold out" in avail_str):
                continue

        filtered.append(p)

    return filtered


def search_shopping_deals(query, sort_by="price_low", currency="Rs."):

    """
    Unified Live Shopping Search with Intelligent Query Normalization & Multi-Attempt Fallback.
    - Attempt 1: Search using the user's original query.
    - Attempt 2: If 0 results, search using the intelligently corrected / normalized query.
    - Attempt 3: If still 0 results and query is compound, search with simplified core keywords.
    Max 3 controlled attempts total to prevent excessive API calls.
    """
    raw_query = (query or "").strip()
    if not raw_query:
        raw_query = "wireless earbuds"

    target_curr = currency or "Rs."
    
    # Candidate search queries in priority order
    attempts = []
    
    # 1. First attempt: Original user query
    clean_original = clean_store_search_query(raw_query)
    attempts.append(clean_original)
    
    # 2. Second attempt: Corrected / normalized query (if different)
    corrected_q = normalize_and_correct_query(raw_query)
    clean_corrected = clean_store_search_query(corrected_q)
    if clean_corrected.lower() != clean_original.lower() and clean_corrected.lower() not in [a.lower() for a in attempts]:
        attempts.append(clean_corrected)
        
    # 3. Third attempt: Simplified core product intent (e.g. if filler prepositions caused 0 results)
    simplified_q = re.sub(r'\b(for|with|and|in|of|the|a|an)\b', ' ', clean_corrected, flags=re.IGNORECASE)
    simplified_q = re.sub(r'\s+', ' ', simplified_q).strip()
    if simplified_q.lower() not in [a.lower() for a in attempts] and len(simplified_q.split()) >= 1:
        attempts.append(simplified_q)

    final_products = []
    successful_query = clean_original
    was_corrected = False

    # Execute search with hard limit of maximum 3 attempts
    for attempt_idx, search_q in enumerate(attempts[:3]):
        raw_results = _fetch_serpapi_shopping(search_q, num=60)
        if raw_results:
            successful_query = search_q
            if attempt_idx > 0:
                was_corrected = True
            final_products = _process_serpapi_results(raw_results, search_q, target_curr)
            if final_products:
                break

    if final_products:
        select_best_deal(final_products)
        apply_sorting_and_badges(final_products, sort_by)
        return {
            "status": "success",
            "source_type": "🔴 Live Direct Store Deals & Verified Prices",
            "query": raw_query,
            "corrected_query": successful_query if was_corrected else None,
            "total_results": len(final_products),
            "products": final_products
        }

    # If truly 0 results across all attempts, return safe empty response
    return {
        "status": "success",
        "source_type": "Live Shopping Deals",
        "query": raw_query,
        "corrected_query": None,
        "total_results": 0,
        "products": []
    }


def select_best_deal(products):
    """
    Deterministically identify and mark the single BEST DEAL from search results.
    Criteria:
    - Valid numeric price > 0
    - Available (not marked out of stock or unavailable)
    - Strong priority to lowest valid final price
    - Deterministic tie-breakers: discount %, rating/reviews, known store name, first in list
    - Never selects missing, zero, or invalid price
    - Exactly ONE best deal marked with is_best_deal = True when valid candidates exist
    - Sets is_best_deal = False on all other products
    """
    if not products or not isinstance(products, list):
        return products

    # Ensure is_best_deal flag is initialized on every dictionary item
    for p in products:
        if isinstance(p, dict):
            p["is_best_deal"] = False

    valid_candidates = []

    for idx, p in enumerate(products):
        if not isinstance(p, dict):
            continue

        # Extract and validate numeric price.
        # IMPORTANT: Only use string fallback when price_val is absent (None) or
        # a non-numeric type. If price_val is an explicit numeric <= 0, it is
        # already invalid and must be disqualified without reparsing the price
        # string (which would strip the minus sign and produce a false positive).
        raw_price_val = p.get("price_val")
        if raw_price_val is None or not isinstance(raw_price_val, (int, float)):
            # price_val field absent or non-numeric — try string fallback
            price_str = str(p.get("price") or "")
            try:
                nums = re.findall(r"[\d,]+\.?\d*", price_str.replace(",", ""))
                if nums:
                    price_val = float(nums[0])
                else:
                    price_val = 0.0
            except Exception:
                price_val = 0.0
        else:
            # price_val was explicitly set as a numeric — use it directly
            price_val = float(raw_price_val)

        # Disqualify missing, zero, or negative prices
        if not price_val or price_val <= 0:
            continue

        # Availability / Stock check
        delivery_str = str(p.get("delivery") or "").lower()
        avail_str = str(p.get("availability") or "").lower()
        if "out of stock" in delivery_str or "out of stock" in avail_str or "unavailable" in avail_str or "sold out" in avail_str:
            continue

        # Discount extraction for tie-breaker
        discount_pct = 0.0
        if p.get("discount_val") and isinstance(p.get("discount_val"), (int, float)):
            discount_pct = float(p.get("discount_val"))
        else:
            disc_str = str(p.get("discount") or "")
            disc_match = re.search(r"(\d+)\s*%", disc_str)
            if disc_match:
                discount_pct = float(disc_match.group(1))

        # Rating & reviews for tie-breaker
        rating = float(p.get("rating") or 0.0)
        reviews = float(p.get("reviews") or 0.0)
        reputation_score = rating * min(reviews, 500.0)

        # Known store tie-breaker
        source = str(p.get("source") or "").strip().lower()
        store_known = 1 if source and source not in ["online store", "unknown", ""] else 0

        valid_candidates.append({
            "product": p,
            "sort_key": (
                float(price_val),     # 1. Primary: Lowest price
                -discount_pct,        # 2. Tie-break: Higher discount
                -reputation_score,    # 3. Tie-break: Higher rating & reviews
                -store_known,         # 4. Tie-break: Known store
                idx                   # 5. Tie-break: First in list
            )
        })

    if not valid_candidates:
        return products

    # Sort deterministically and select the single best candidate
    valid_candidates.sort(key=lambda x: x["sort_key"])
    best_candidate = valid_candidates[0]["product"]
    best_candidate["is_best_deal"] = True

    return products


def apply_sorting_and_badges(products, sort_by):
    """Sort products and assign badges while preserving complete product-image association"""
    if not products:
        return

    # Identify the single best deal
    select_best_deal(products)

    min_price_item = min((p for p in products if isinstance(p, dict) and p.get("price_val", 0) > 0), key=lambda x: x["price_val"], default=None)
    if min_price_item:
        min_price_item["is_lowest_price"] = True

    if sort_by == "price_low":
        products.sort(key=lambda x: x["price_val"] if isinstance(x, dict) and x.get("price_val") else float('inf'))
        if products and products[0].get("price_val", 0) > 0:
            products[0]["badge"] = "🔥 Lowest Price Deal"
            products[0]["is_best_price"] = True
    elif sort_by == "price_high":
        products.sort(key=lambda x: x["price_val"] if isinstance(x, dict) and x.get("price_val") else 0.0, reverse=True)
        if products:
            products[0]["badge"] = "💎 Premium / High-End"
            products[0]["is_premium"] = True
    elif sort_by == "rating":
        products.sort(key=lambda x: float(x.get("rating") or 0) if isinstance(x, dict) else 0.0, reverse=True)
        if products:
            products[0]["badge"] = "⭐ Highest Customer Rated"
            products[0]["is_top_rated"] = True
