"""
Mandi Price Module - Agmarknet Integration
=============================================
Fetches daily commodity prices from Indian mandis via data.gov.in API.
Compares market prices with MSP and injects into RAG context.

No registration needed — uses the public sample API key (10 records/call).
For production, register at data.gov.in for a full key.

Usage:
    from mandi_prices import get_price_context, fetch_mandi_prices

    # Get formatted price context for RAG
    context = get_price_context("onion", "Maharashtra")
    print(context)

    # Or fetch raw data
    prices = fetch_mandi_prices(commodity="Wheat", state="Bihar")
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime


# ── Configuration ──────────────────────────────────────────────────────────
# Public sample key from data.gov.in (returns max 10 records)
# For full access, register at https://data.gov.in and get your own key
DATA_GOV_API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
DATA_GOV_URL = "https://api.data.gov.in/resource/" + RESOURCE_ID


# ── MSP (Minimum Support Prices) 2025-26 ──────────────────────────────────
# Source: Commission for Agricultural Costs and Prices (CACP)
MSP_2025_26 = {
    "paddy": {"common": 2300, "grade_a": 2320, "unit": "quintal"},
    "rice": {"common": 2300, "grade_a": 2320, "unit": "quintal"},
    "wheat": {"common": 2425, "unit": "quintal"},
    "jowar": {"hybrid": 3371, "maldandi": 3421, "unit": "quintal"},
    "bajra": {"common": 2625, "unit": "quintal"},
    "maize": {"common": 2225, "unit": "quintal"},
    "ragi": {"common": 4290, "unit": "quintal"},
    "arhar": {"common": 7550, "unit": "quintal"},
    "moong": {"common": 8682, "unit": "quintal"},
    "urad": {"common": 7400, "unit": "quintal"},
    "groundnut": {"common": 6377, "unit": "quintal"},
    "soyabean": {"yellow": 4892, "unit": "quintal"},
    "sunflower": {"common": 7280, "unit": "quintal"},
    "sugarcane": {"common": 340, "unit": "quintal"},
    "cotton": {"medium": 7121, "long": 7521, "unit": "quintal"},
    "mustard": {"common": 5950, "unit": "quintal"},
    "gram": {"common": 5650, "unit": "quintal"},
    "masoor": {"common": 6700, "unit": "quintal"},
    "onion": {"common": None, "unit": "quintal"},  # No MSP for onion
    "potato": {"common": None, "unit": "quintal"},  # No MSP for potato
    "tomato": {"common": None, "unit": "quintal"},  # No MSP for tomato
}

# Commodity name normalization
COMMODITY_ALIASES = {
    "rice": "Rice", "paddy": "Rice", "chawal": "Rice", "dhan": "Rice",
    "wheat": "Wheat", "gehu": "Wheat", "gehun": "Wheat",
    "onion": "Onion", "pyaz": "Onion", "pyaaz": "Onion", "kanda": "Onion",
    "potato": "Potato", "aloo": "Potato", "batata": "Potato",
    "tomato": "Tomato", "tamatar": "Tomato",
    "soyabean": "Soyabean", "soybean": "Soyabean", "soya": "Soyabean",
    "groundnut": "Groundnut", "moongphali": "Groundnut", "mungfali": "Groundnut",
    "cotton": "Cotton", "kapas": "Cotton",
    "maize": "Maize", "makka": "Maize",
    "jowar": "Jowar", "sorghum": "Jowar",
    "bajra": "Bajra", "pearl millet": "Bajra",
    "arhar": "Arhar (Tur/Red Gram)", "tur": "Arhar (Tur/Red Gram)",
    "toor": "Arhar (Tur/Red Gram)", "pigeon pea": "Arhar (Tur/Red Gram)",
    "moong": "Green Gram (Moong)(Whole)", "mung": "Green Gram (Moong)(Whole)",
    "green gram": "Green Gram (Moong)(Whole)",
    "urad": "Black Gram (Urd Beans)(Whole)", "black gram": "Black Gram (Urd Beans)(Whole)",
    "mustard": "Mustard", "sarson": "Mustard",
    "gram": "Bengal Gram(Gram)(Whole)", "chana": "Bengal Gram(Gram)(Whole)",
    "masoor": "Masoor Dal", "lentil": "Masoor Dal",
    "sugarcane": "Sugarcane", "ganna": "Sugarcane",
    "ragi": "Ragi (Finger Millet)", "finger millet": "Ragi (Finger Millet)",
    "sunflower": "Sunflower", "surajmukhi": "Sunflower",
}

# State name normalization
STATE_ALIASES = {
    "bihar": "Bihar", "odisha": "Odisha", "orissa": "Odisha",
    "maharashtra": "Maharashtra", "rajasthan": "Rajasthan",
    "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "punjab": "Punjab", "haryana": "Haryana",
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
    "karnataka": "Karnataka", "tamil nadu": "Tamil Nadu",
    "gujarat": "Gujarat", "telangana": "Telangana",
    "west bengal": "West Bengal", "kerala": "Kerala",
}


def normalize_commodity(name):
    """Normalize commodity name for API query."""
    return COMMODITY_ALIASES.get(name.lower().strip(), name.title())


def normalize_state(name):
    """Normalize state name for API query."""
    return STATE_ALIASES.get(name.lower().strip(), name.title())


def get_msp(commodity):
    """Get MSP for a commodity if available."""
    key = commodity.lower().strip()
    # Try direct match first
    if key in MSP_2025_26:
        return MSP_2025_26[key]
    # Try aliases
    for alias, canonical in COMMODITY_ALIASES.items():
        if alias == key or canonical.lower() == key:
            # Find in MSP dict
            for msp_key in MSP_2025_26:
                if msp_key in alias or alias in msp_key:
                    return MSP_2025_26[msp_key]
    return None


def fetch_mandi_prices(commodity=None, state=None, market=None, limit=10):
    """
    Fetch current mandi prices from data.gov.in API.

    Args:
        commodity: Crop name (e.g., "Wheat", "Onion")
        state: State name (e.g., "Bihar", "Maharashtra")
        market: Specific market/mandi name
        limit: Max records to fetch (sample key caps at 10)

    Returns:
        List of price records or empty list on failure
    """
    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": limit,
    }

    # Add filters
    filters = []
    if commodity:
        normalized = normalize_commodity(commodity)
        filters.append(f"commodity={urllib.parse.quote(normalized)}")
    if state:
        normalized = normalize_state(state)
        filters.append(f"state={urllib.parse.quote(normalized)}")
    if market:
        filters.append(f"market={urllib.parse.quote(market)}")

    if filters:
        params["filters[" + "]&filters[".join(f.split("=")[0] + "]=" + f.split("=")[1] for f in filters)] = ""

    # Build URL manually for cleaner filter handling
    url = f"{DATA_GOV_URL}?api-key={DATA_GOV_API_KEY}&format=json&limit={limit}"
    if commodity:
        url += f"&filters[commodity]={urllib.parse.quote(normalize_commodity(commodity))}"
    if state:
        url += f"&filters[state]={urllib.parse.quote(normalize_state(state))}"
    if market:
        url += f"&filters[market]={urllib.parse.quote(market)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgriRAG/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        records = data.get("records", [])
        return records

    except Exception as e:
        print(f"  Warning: Mandi price fetch failed: {e}")
        return []


def format_price_table(records):
    """Format price records into a readable string."""
    if not records:
        return "No price data available."

    lines = []
    for r in records:
        state = r.get("state", "?")
        market = r.get("market", "?")
        commodity = r.get("commodity", "?")
        variety = r.get("variety", "")
        min_price = r.get("min_price", "?")
        max_price = r.get("max_price", "?")
        modal_price = r.get("modal_price", "?")
        date = r.get("arrival_date", "?")

        line = (f"  {market} ({state}): Rs.{modal_price}/qtl "
                f"(min {min_price}, max {max_price})")
        if variety:
            line += f" [{variety}]"
        lines.append(line)

    return "\n".join(lines)


def get_price_context(commodity, state=None):
    """
    Get formatted price context for injection into RAG prompt.
    Includes market prices + MSP comparison.

    Returns:
        str: Price context string, or empty string on failure
    """
    records = fetch_mandi_prices(commodity=commodity, state=state)

    if not records:
        return ""

    # Parse prices
    prices = []
    for r in records:
        try:
            modal = float(r.get("modal_price", 0))
            if modal > 0:
                prices.append(modal)
        except (ValueError, TypeError):
            pass

    if not prices:
        return ""

    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    # Get MSP comparison
    msp_info = get_msp(commodity)
    msp_comparison = ""
    if msp_info:
        msp_value = msp_info.get("common") or msp_info.get("medium")
        if msp_value:
            diff = avg_price - msp_value
            pct = (diff / msp_value) * 100
            if diff > 0:
                msp_comparison = (
                    f"MSP: Rs.{msp_value}/qtl. "
                    f"Market price is Rs.{diff:.0f} ABOVE MSP (+{pct:.0f}%)."
                )
            else:
                msp_comparison = (
                    f"MSP: Rs.{msp_value}/qtl. "
                    f"WARNING: Market price is Rs.{abs(diff):.0f} BELOW MSP ({pct:.0f}%). "
                    f"Consider government procurement or storage."
                )
        else:
            msp_comparison = f"No MSP exists for {commodity}. Price is market-driven."

    # Format context
    state_label = state or "India"
    normalized_commodity = normalize_commodity(commodity)

    lines = [
        f"=== MANDI PRICE DATA for {normalized_commodity} in {state_label} ===",
        f"Average modal price: Rs.{avg_price:.0f}/quintal",
        f"Price range: Rs.{min_price:.0f} — Rs.{max_price:.0f}/quintal",
        f"Data from {len(records)} mandi(s)",
    ]

    if msp_comparison:
        lines.append(f"MSP comparison: {msp_comparison}")

    lines.append("Market-wise breakdown:")
    lines.append(format_price_table(records[:5]))  # Top 5 mandis
    lines.append("=" * 50)

    return "\n".join(lines)


def detect_commodity(query):
    """Try to detect a commodity name from a user query."""
    query_lower = query.lower()

    # Check each alias
    best_match = None
    best_len = 0
    for alias in COMMODITY_ALIASES:
        if alias in query_lower and len(alias) > best_len:
            best_match = alias
            best_len = len(alias)

    return best_match


# ── CLI testing ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2:
        commodity = sys.argv[1]
        state = sys.argv[2] if len(sys.argv) >= 3 else None

        print(f"Fetching prices for {commodity}" +
              (f" in {state}" if state else "") + "...\n")

        # Raw data
        records = fetch_mandi_prices(commodity=commodity, state=state)
        if records:
            print(f"Found {len(records)} records:\n")
            print(format_price_table(records))

            # MSP comparison
            msp = get_msp(commodity)
            if msp:
                msp_val = msp.get("common") or msp.get("medium")
                if msp_val:
                    print(f"\nMSP (2025-26): Rs.{msp_val}/quintal")

            # Full context
            print(f"\n{'='*50}")
            print("RAG Context Output:\n")
            print(get_price_context(commodity, state))
        else:
            print("No data found. Try different commodity/state names.")
            print("Examples: python mandi_prices.py Wheat Bihar")
            print("          python mandi_prices.py Onion Maharashtra")
    else:
        print("Mandi Price Module — Test Mode\n")
        print("Usage: python mandi_prices.py <commodity> [state]")
        print("\nRunning demo queries...\n")

        for commodity, state in [("Wheat", "Bihar"), ("Onion", "Maharashtra"), ("Rice", None)]:
            print(f"--- {commodity} in {state or 'All India'} ---")
            ctx = get_price_context(commodity, state)
            if ctx:
                print(ctx)
            else:
                print("  No data available")
            print()