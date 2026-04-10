"""
Weather Module - Open-Meteo Integration
=========================================
Fetches real-time weather data for Indian districts and injects it
into the RAG context so the LLM can give weather-aware advice.

No API key needed. Free for non-commercial use.

Usage:
    from weather import get_weather_context, detect_district

    # Get weather summary for a district
    weather = get_weather_context("Patna", "Bihar")
    print(weather)
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


# ── District coordinates (lat, lon) for our 5 states ──────────────────────
# These are district headquarters coordinates
DISTRICT_COORDS = {
    # Bihar
    "patna": (25.61, 85.14),
    "gaya": (24.80, 85.00),
    "muzaffarpur": (26.12, 85.39),
    "bhagalpur": (25.24, 86.97),
    "darbhanga": (26.17, 85.90),
    "purnea": (25.78, 87.47),
    "araria": (26.15, 87.52),
    "aurangabad": (24.75, 84.37),
    "samastipur": (25.86, 85.78),
    "begusarai": (25.42, 86.13),
    "munger": (25.38, 86.47),
    "nalanda": (25.13, 85.44),
    "vaishali": (25.69, 85.22),
    "siwan": (26.22, 84.36),
    "saran": (25.78, 84.78),
    "rohtas": (24.97, 84.01),
    "kaimur": (25.05, 83.58),
    "buxar": (25.56, 83.98),
    "bhojpur": (25.57, 84.52),
    "arwal": (25.25, 84.68),
    "kishanganj": (26.09, 87.94),
    "katihar": (25.54, 87.57),
    "madhepura": (25.92, 86.79),
    "saharsa": (25.88, 86.60),
    "supaul": (26.12, 86.60),
    "madhubani": (26.35, 86.07),
    "sitamarhi": (26.59, 85.49),
    "sheikhpura": (25.14, 85.84),
    "lakhisarai": (25.16, 86.09),
    "jamui": (24.93, 86.22),
    "banka": (24.89, 86.92),
    "nawada": (24.89, 85.54),
    "jehanabad": (25.21, 84.99),
    "gopalganj": (26.47, 84.44),
    "west champaran": (26.74, 84.74),
    "east champaran": (26.65, 84.85),
    "khagaria": (25.50, 86.47),
    "sheohar": (26.52, 85.30),

    # Odisha
    "cuttack": (20.46, 85.88),
    "puri": (19.81, 85.83),
    "bhubaneswar": (20.30, 85.82),
    "sambalpur": (21.47, 83.97),
    "bolangir": (20.70, 83.49),
    "kalahandi": (19.91, 83.17),
    "koraput": (18.81, 82.71),
    "ganjam": (19.39, 84.68),
    "sundargarh": (22.12, 84.04),
    "keonjhar": (21.63, 85.58),
    "mayurbhanj": (21.94, 86.73),
    "balasore": (21.49, 86.93),
    "bhadrak": (21.06, 86.52),
    "jajpur": (20.85, 86.34),
    "kendrapara": (20.50, 86.42),
    "jagatsinghpur": (20.26, 86.17),
    "khurdha": (20.18, 85.62),
    "nayagarh": (20.13, 85.10),
    "kandhamal": (20.47, 84.24),
    "rayagada": (19.17, 83.42),
    "malkangiri": (18.35, 81.88),
    "nabarangpur": (19.23, 82.55),
    "nuapada": (20.88, 82.55),
    "bargarh": (21.33, 83.62),
    "jharsuguda": (21.86, 84.01),
    "deogarh": (21.54, 84.73),
    "angul": (20.84, 85.10),
    "dhenkanal": (20.66, 85.60),
    "boudh": (20.84, 84.32),

    # Maharashtra
    "pune": (18.52, 73.86),
    "mumbai": (19.08, 72.88),
    "nagpur": (21.15, 79.09),
    "nashik": (20.00, 73.78),
    "aurangabad mh": (19.88, 75.32),
    "solapur": (17.68, 75.91),
    "kolhapur": (16.70, 74.24),
    "sangli": (16.85, 74.56),
    "satara": (17.69, 74.00),
    "ahmednagar": (19.09, 74.74),
    "jalgaon": (21.01, 75.57),
    "dhule": (20.90, 74.77),
    "nandurbar": (21.37, 74.24),
    "beed": (18.99, 75.76),
    "latur": (18.40, 76.57),
    "osmanabad": (18.19, 76.04),
    "nanded": (19.16, 77.30),
    "parbhani": (19.27, 76.78),
    "hingoli": (19.72, 77.15),
    "jalna": (19.84, 75.88),
    "akola": (20.71, 77.01),
    "amravati": (20.93, 77.75),
    "buldhana": (20.53, 76.18),
    "washim": (20.11, 77.13),
    "yavatmal": (20.39, 78.12),
    "wardha": (20.74, 78.60),
    "chandrapur": (19.97, 79.30),
    "gadchiroli": (20.18, 80.00),
    "gondia": (21.46, 80.20),
    "bhandara": (21.17, 79.65),
    "thane": (19.22, 72.98),
    "raigarh mh": (18.52, 73.18),
    "ratnagiri": (16.99, 73.30),
    "sindhudurg": (16.35, 73.66),

    # Rajasthan
    "udaipur": (24.58, 73.69),
    "kota": (25.18, 75.86),
    "tonk": (26.17, 75.79),
    "sikar": (27.62, 75.14),
    "nagaur": (27.20, 73.74),
    "pali": (25.77, 73.33),
    "sirohi": (24.88, 72.86),
    "rajsamand": (25.07, 73.88),
    "pratapgarh": (24.03, 74.78),
    "sawai madhopur": (26.02, 76.35),
    "sriganganagar": (29.91, 73.88),

    # Andhra Pradesh
    "anantapur": (14.68, 77.60),
    "chittoor": (13.22, 79.10),
    "east godavari": (17.00, 81.80),
    "guntur": (16.31, 80.44),
    "kadapa": (14.47, 78.82),
    "krishna": (16.57, 80.36),
    "kurnool": (15.83, 78.04),
    "nellore": (14.45, 79.99),
    "prakasam": (15.35, 79.49),
    "srikakulam": (18.30, 83.90),
    "visakhapatnam": (17.69, 83.22),
    "west godavari": (16.92, 81.34),
}

# Normal monsoon rainfall (mm) for key districts - used to assess deficit/surplus
# Source: IMD long-period averages (approximate)
NORMAL_MONSOON_RAINFALL = {
    "patna": 1100, "gaya": 1000, "muzaffarpur": 1200,
    "cuttack": 1400, "sambalpur": 1500, "kalahandi": 1300,
    "pune": 600, "nagpur": 1100, "solapur": 500,
    "udaipur": 600, "kota": 800, "sriganganagar": 200,
    "anantapur": 550, "guntur": 800, "visakhapatnam": 1000,
}


def fetch_weather(lat, lon, past_days=7, forecast_days=7):
    """Fetch weather from Open-Meteo API."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "rain_sum",
            "et0_fao_evapotranspiration",
            "wind_speed_10m_max",
        ]),
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "weather_code",
        ]),
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "Asia/Kolkata",
    }

    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AgriRAG/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠ Weather fetch failed: {e}")
        return None


def interpret_weather_code(code):
    """Convert WMO weather code to description."""
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, f"Weather code {code}")


def analyze_rainfall(daily_data, district_key):
    """Analyze rainfall pattern relative to normal."""
    dates = daily_data.get("time", [])
    rain = daily_data.get("rain_sum", []) or daily_data.get("precipitation_sum", [])

    if not rain:
        return ""

    # Split into past and forecast
    today = datetime.now().strftime("%Y-%m-%d")
    past_rain = []
    future_rain = []
    for d, r in zip(dates, rain):
        if r is None:
            r = 0.0
        if d <= today:
            past_rain.append(r)
        else:
            future_rain.append(r)

    past_total = sum(past_rain)
    future_total = sum(future_rain)

    analysis = f"Last 7 days rainfall: {past_total:.1f}mm. "
    analysis += f"Next 7 days forecast: {future_total:.1f}mm. "

    # Compare to normal if available
    normal = NORMAL_MONSOON_RAINFALL.get(district_key)
    if normal:
        # Rough weekly normal during monsoon (June-Sep = ~17 weeks)
        weekly_normal = normal / 17
        if past_total < weekly_normal * 0.3:
            analysis += f"⚠ SEVERE DEFICIT — well below weekly normal of ~{weekly_normal:.0f}mm. Drought conditions likely."
        elif past_total < weekly_normal * 0.6:
            analysis += f"⚠ DEFICIT — below weekly normal of ~{weekly_normal:.0f}mm."
        elif past_total > weekly_normal * 1.5:
            analysis += f"⚠ EXCESS — above weekly normal of ~{weekly_normal:.0f}mm. Waterlogging risk."
        else:
            analysis += f"Rainfall near normal (~{weekly_normal:.0f}mm/week)."

    return analysis


def get_weather_context(district, state=None):
    """
    Get a formatted weather context string for a district.
    This string is injected into the RAG prompt alongside document context.

    Returns:
        str: Weather summary, or empty string if district not found/API fails
    """
    # Normalize district name for lookup
    district_key = district.lower().strip()

    # Try direct match, then partial match
    coords = DISTRICT_COORDS.get(district_key)
    if not coords:
        # Try partial matching
        for key, val in DISTRICT_COORDS.items():
            if district_key in key or key in district_key:
                coords = val
                district_key = key
                break

    if not coords:
        return ""

    lat, lon = coords
    data = fetch_weather(lat, lon)
    if not data:
        return ""

    # Build weather context
    current = data.get("current", {})
    daily = data.get("daily", {})

    # Current conditions
    temp = current.get("temperature_2m", "N/A")
    humidity = current.get("relative_humidity_2m", "N/A")
    wind = current.get("wind_speed_10m", "N/A")
    weather_code = current.get("weather_code", 0)
    weather_desc = interpret_weather_code(weather_code)

    # Temperature range from forecast
    max_temps = [t for t in (daily.get("temperature_2m_max") or []) if t is not None]
    min_temps = [t for t in (daily.get("temperature_2m_min") or []) if t is not None]

    # ET0 (evapotranspiration) - useful for irrigation advice
    et0_values = [e for e in (daily.get("et0_fao_evapotranspiration") or []) if e is not None]
    avg_et0 = sum(et0_values) / len(et0_values) if et0_values else None

    # Rainfall analysis
    rainfall_analysis = analyze_rainfall(daily, district_key)

    # Format the context
    lines = [
        f"=== REAL-TIME WEATHER for {district.title()}, {state or 'India'} ===",
        f"Current: {weather_desc}, {temp}°C, Humidity {humidity}%, Wind {wind} km/h",
    ]

    if max_temps and min_temps:
        lines.append(f"7-day temperature range: {min(min_temps):.0f}°C to {max(max_temps):.0f}°C")

    if rainfall_analysis:
        lines.append(f"Rainfall: {rainfall_analysis}")

    if avg_et0:
        lines.append(f"Avg daily evapotranspiration (ET0): {avg_et0:.1f}mm — {'High water demand' if avg_et0 > 5 else 'Moderate water demand' if avg_et0 > 3 else 'Low water demand'}")

    # Determine current season
    month = datetime.now().month
    if month in (6, 7, 8, 9):
        season = "Kharif (monsoon) season"
    elif month in (10, 11, 12, 1, 2):
        season = "Rabi (winter) season"
    else:
        season = "Zaid (summer) season"
    lines.append(f"Current agricultural season: {season}")

    lines.append("=" * 50)

    return "\n".join(lines)


def detect_district(query):
    """
    Try to detect district and state from a user query.
    Returns (district, state) or (None, None).
    """
    query_lower = query.lower()

    # Check each district name against the query
    best_match = None
    best_len = 0

    for district_key in DISTRICT_COORDS:
        # Check if district name appears in query
        if district_key in query_lower and len(district_key) > best_len:
            best_match = district_key
            best_len = len(district_key)

    if not best_match:
        return None, None

    # Determine state from district
    state_map = {}
    for d in ["patna", "gaya", "muzaffarpur", "bhagalpur", "darbhanga", "purnea",
              "araria", "aurangabad", "samastipur", "begusarai", "munger", "nalanda",
              "vaishali", "siwan", "saran", "rohtas", "kaimur", "buxar", "bhojpur",
              "arwal", "kishanganj", "katihar", "madhepura", "saharsa", "supaul",
              "madhubani", "sitamarhi", "sheikhpura", "lakhisarai", "jamui", "banka",
              "nawada", "jehanabad", "gopalganj", "west champaran", "east champaran",
              "khagaria", "sheohar"]:
        state_map[d] = "Bihar"
    for d in ["cuttack", "puri", "bhubaneswar", "sambalpur", "bolangir", "kalahandi",
              "koraput", "ganjam", "sundargarh", "keonjhar", "mayurbhanj", "balasore",
              "bhadrak", "jajpur", "kendrapara", "jagatsinghpur", "khurdha", "nayagarh",
              "kandhamal", "rayagada", "malkangiri", "nabarangpur", "nuapada", "bargarh",
              "jharsuguda", "deogarh", "angul", "dhenkanal", "boudh"]:
        state_map[d] = "Odisha"
    for d in ["pune", "mumbai", "nagpur", "nashik", "solapur", "kolhapur", "sangli",
              "satara", "ahmednagar", "jalgaon", "dhule", "nandurbar", "beed", "latur",
              "osmanabad", "nanded", "parbhani", "hingoli", "jalna", "akola", "amravati",
              "buldhana", "washim", "yavatmal", "wardha", "chandrapur", "gadchiroli",
              "gondia", "bhandara", "thane", "ratnagiri", "sindhudurg"]:
        state_map[d] = "Maharashtra"
    for d in ["udaipur", "kota", "tonk", "sikar", "nagaur", "pali", "sirohi",
              "rajsamand", "pratapgarh", "sawai madhopur", "sriganganagar"]:
        state_map[d] = "Rajasthan"
    for d in ["anantapur", "chittoor", "east godavari", "guntur", "kadapa", "krishna",
              "kurnool", "nellore", "prakasam", "srikakulam", "visakhapatnam", "west godavari"]:
        state_map[d] = "Andhra Pradesh"

    state = state_map.get(best_match, None)
    return best_match, state


# ── CLI testing ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        district = " ".join(sys.argv[1:])
        detected, state = detect_district(district)
        if detected:
            print(get_weather_context(detected, state))
        else:
            # Try direct lookup
            print(get_weather_context(district))
    else:
        # Demo
        print("Testing weather module...\n")
        for test in ["Patna", "Pune", "Kalahandi", "Udaipur"]:
            ctx = get_weather_context(test)
            if ctx:
                print(ctx)
                print()
            else:
                print(f"No data for: {test}\n")