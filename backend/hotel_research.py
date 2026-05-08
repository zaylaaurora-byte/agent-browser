#!/usr/bin/env python3
"""
Hotel Research Tool — autonomous multi-city hotel price extraction.
Extracts structured pricing data from Booking.com for any number of cities.

Usage:
    python3 hotel_research.py                    # All 6 cities
    python3 hotel_research.py Paris Barcelona    # Specific cities
    python3 hotel_research.py --checkin 2026-07-01 --checkout 2026-07-05 --adults 2

Output: ~/.agent-browser/hotel-research/{city}_results.json
"""
import asyncio
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

OUT_DIR = Path.home() / ".agent-browser" / "hotel-research"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CITIES = [
    {"city": "Paris",      "country": "France",       "checkin": "2026-06-10", "checkout": "2026-06-13"},
    {"city": "Barcelona",  "country": "Spain",        "checkin": "2026-06-15", "checkout": "2026-06-18"},
    {"city": "Rome",       "country": "Italy",        "checkin": "2026-07-01", "checkout": "2026-07-05"},
    {"city": "Amsterdam",  "country": "Netherlands",  "checkin": "2026-06-20", "checkout": "2026-06-23"},
    {"city": "Lisbon",     "country": "Portugal",     "checkin": "2026-07-10", "checkout": "2026-07-14"},
    {"city": "Berlin",     "country": "Germany",      "checkin": "2026-08-01", "checkout": "2026-08-04"},
]

STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-web-security",
]


def parse_args():
    requested_cities = []
    checkin, checkout, adults = None, None, 2
    children = 0
    child_ages = []

    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if arg.startswith("--checkin="): checkin = arg.split("=", 1)[1]
            elif arg.startswith("--checkout="): checkout = arg.split("=", 1)[1]
            elif arg.startswith("--adults="): adults = int(arg.split("=", 1)[1])
            elif arg.startswith("--children="): children = int(arg.split("=", 1)[1])
            elif arg.startswith("--child-ages="):
                raw = arg.split("=", 1)[1].strip()
                child_ages = [int(x.strip()) for x in raw.split(",") if x.strip()]
        else:
            requested_cities.append(arg)

    # Build city list: defaults from CITIES; allow arbitrary user-provided cities (no silent drop)
    if not requested_cities:
        cities = [dict(c) for c in CITIES]
    else:
        known_by_name = {c["city"].lower(): c for c in CITIES}
        default_checkin = checkin or CITIES[0]["checkin"]
        default_checkout = checkout or CITIES[0]["checkout"]
        cities = []
        for city_name in requested_cities:
            known = known_by_name.get(city_name.lower())
            if known:
                cities.append(dict(known))
            else:
                cities.append({
                    "city": city_name,
                    "country": "Unknown",
                    "checkin": default_checkin,
                    "checkout": default_checkout,
                })

    if checkin:
        [c.update({"checkin": checkin}) for c in cities]
    if checkout:
        [c.update({"checkout": checkout}) for c in cities]
    [c.update({"adults": adults, "children": children}) for c in cities]

    if child_ages and len(child_ages) >= children:
        [c.update({"child_ages": child_ages[:children]}) for c in cities]
    elif children > 0:
        default_ages = [12, 10, 8, 6, 4, 2]
        [c.update({"child_ages": default_ages[:children]}) for c in cities]

    return cities


async def setup_browser(pw):
    browser = await pw.chromium.launch(
        headless=True,
        args=STEALTH_ARGS,
    )
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-GB",
        extra_http_headers={
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    # Accept OneTrust cookies silently
    await ctx.add_init_script("""
        window.addEventListener('load', () => {
            setTimeout(() => {
                try {
                    const btn = document.querySelector('#onetrust-accept-btn-handler');
                    if (btn) btn.click();
                    // Fallback: any button with 'Accept' text
                    document.querySelectorAll('button').forEach(b => {
                        const t = b.textContent || '';
                        if (t.includes('Accept') || t.includes('agree') || t.includes('AGREE')) {
                            b.click();
                        }
                    });
                } catch(e) {}
            }, 600);
        });
    """)

    page = await ctx.new_page()

    # Block overlay dialogs
    page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))

    return browser, ctx, page


async def extract_prices(page) -> list:
    """Extract hotel cards with prices from current search results page."""
    hotels = []

    # Strategy 1: data-testid property-card-container (updated selector)
    cards = await page.query_selector_all('[data-testid="property-card-container"]')

    if cards:
        for card in cards[:10]:  # Top 10 results
            try:
                name_el = await card.query_selector('[data-testid="title"]')
                price_el = await card.query_selector('[data-testid="price-and-discounted-price"]')
                # Review score: data-testid=review-score contains "Scored 9.1 9.1 Superb 1,159 reviews"
                rating_el = await card.query_selector('[data-testid="review-score"]')
                link_el = await card.query_selector('a[href*="/hotel/"]')

                name = await name_el.inner_text() if name_el else ""
                price_text = await price_el.inner_text() if price_el else ""
                rating_text = await rating_el.inner_text() if rating_el else ""
                href = await link_el.get_attribute('href') if link_el else ""

                # Parse price — extract numeric value (handles £1,055 and €327)
                price_val = None
                price_match = re.search(r'[\$£€]\s*([\d,]+)', price_text.replace(',', ''))
                if price_match:
                    price_val = int(price_match.group(1))

                # Parse review score from rating_text like "Scored 9.1 9.1 Superb 1,159 reviews"
                score = None
                review_count = None
                review_label = ""
                score_match = re.search(r'Scored\s+([\d.]+)', rating_text)
                count_match = re.search(r'([\d,]+)\s+reviews?', rating_text)
                # Extract review label (e.g. "Superb", "Fabulous", "Very Good")
                label_words = re.findall(r'\b([A-Z][a-z]+)\b', rating_text)
                review_label = " ".join(label_words[:2]) if label_words else ""
                if score_match:
                    try: score = float(score_match.group(1))
                    except: pass
                if count_match:
                    try: review_count = int(count_match.group(1).replace(',', ''))
                    except: pass

                if name:
                    hotels.append({
                        "name": name.strip(),
                        "price_text": price_text.strip(),
                        "price_value": price_val,
                        "currency": "GBP" if '£' in price_text else "EUR",
                        "review_text": rating_text.strip(),  # e.g. "Scored 9.1 Superb 1,159 reviews"
                        "review_score": score,
                        "review_count": review_count,
                        "review_label": review_label,  # e.g. "Superb"
                        "booking_url": href if href.startswith('http') else f"https://www.booking.com{href}" if href else "",
                    })
            except Exception:
                continue

    # Strategy 2: fallback — search for price elements by class pattern
    if not hotels:
        price_els = await page.query_selector_all('.bui-price-display__value, [class*="price"], .prco-valign-middle-helper')
        for el in price_els[:10]:
            try:
                text = await el.inner_text()
                price_match = re.search(r'([\d,]+)', text.replace(',', ''))
                if price_match:
                    # Try to get the parent card context
                    parent = await el.query_selector_xpath(
                        './ancestor::[@data-testid="property-card" or contains(@class, "property-card")]'
                    )
                    name_el = await el.query_selector('[data-testid="title"]') if parent else None
                    name = await name_el.inner_text() if name_el else f"Hotel #{len(hotels)+1}"
                    hotels.append({
                        "name": name.strip(),
                        "price_text": text.strip(),
                        "price_value": int(price_match.group(1)),
                        "currency": "GBP" if '£' in text else "EUR",
                        "score": None,
                        "rating_text": "",
                        "location": "",
                        "booking_url": "",
                    })
            except Exception:
                continue

    return hotels


async def research_city(page, dest: dict) -> dict:
    """Research hotels for one city — navigate, extract, return structured data."""
    city = dest["city"]
    checkin = dest["checkin"]
    checkout = dest["checkout"]
    adults = dest.get("adults", 2)
    children = dest.get("children", 0)
    child_ages = dest.get("child_ages", [])

    print(f"\n{'─'*60}")
    print(f"  🔍 {city} | {checkin} → {checkout} | {adults} adults, {children} children")
    print(f"{'─'*60}")

    city_slug = city.replace(" ", "+")
    age_query = "".join([f"&age={a}" for a in child_ages]) if children > 0 else ""
    search_url = (
        f"https://www.booking.com/searchresults.en-gb.html"
        f"?ss={city_slug}&checkin={checkin}&checkout={checkout}"
        f"&group_adults={adults}&group_children={children}{age_query}"
    )

    result = {
        "city": city,
        "country": dest["country"],
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "children": children,
        "child_ages": child_ages,
        "search_url": search_url,
        "status": "pending",
        "hotels": [],
        "error": "",
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # Navigate to search results
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)  # Wait for JS rendering

        title = await page.title()
        url = page.url
        print(f"  Page title: {title[:70]}")
        print(f"  URL: {url[:80]}")

        # Check for antibot/challenge
        title_lower = title.lower()
        if any(x in title_lower for x in ["access denied", "forbidden", "captcha", "challenge", "cloudflare", "blocked"]):
            print(f"  ⚠️  Blocked by antibot — trying alternate URL...")
            # Try the generic search URL
            alt_url = f"https://www.booking.com/searchresults.html?ss={city_slug}"
            await page.goto(alt_url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(3)
            title = await page.title()

        # Capture visual evidence screenshot for this city
        screenshot_file = OUT_DIR / f"{city.lower().replace(' ', '_')}_search.png"
        await page.screenshot(path=str(screenshot_file), full_page=True)
        result["screenshot"] = str(screenshot_file)

        # Extract hotel prices
        hotels = await extract_prices(page)

        if hotels:
            result["hotels"] = hotels
            result["status"] = "success"
            total = sum(h.get("price_value") or 0 for h in hotels)
            print(f"  ✅ {len(hotels)} hotels extracted")
            for h in hotels[:5]:
                price_str = h.get('price_text', 'N/A')
                score_str = f"⭐{h['review_score']}" if h.get('review_score') else ""
                print(f"     {h['name'][:45]:<45} {price_str:<18} {score_str}")
            if len(hotels) > 5:
                print(f"     ... and {len(hotels)-5} more")
        else:
            result["status"] = "no_results"
            print(f"  ⚠️  No hotel cards found — page may be blocked or empty")

            # Debug: get page text snippet
            try:
                body_text = await page.inner_text('body')
                snippet = body_text[:300].replace('\n', ' ')
                print(f"  Page snippet: {snippet}")
            except:
                pass

    except asyncio.TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Navigation timeout for {search_url}"
        print(f"  ❌ Timeout loading {city}")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ❌ Error: {e}")

    return result


async def main():
    cities = parse_args()
    print(f"\n{'='*60}")
    print(f"  HOTEL RESEARCH — {len(cities)} cities")
    print(f"  Output: {OUT_DIR}")
    print(f"{'='*60}")

    async with async_playwright() as pw:
        browser, ctx, page = await setup_browser(pw)

        all_results = []
        for dest in cities:
            result = await research_city(page, dest)
            all_results.append(result)

            # Save individual city result
            city_id = dest["city"].lower()
            out_file = OUT_DIR / f"{city_id}_results.json"
            out_file.write_text(json.dumps(result, indent=2))
            print(f"  📄 Saved: {out_file.name}")

            # Brief pause between cities to avoid rate limiting
            if dest != cities[-1]:
                await asyncio.sleep(2)

        await browser.close()

    # Save combined results
    combined = {
        "research_date": datetime.now().isoformat(),
        "total_cities": len(all_results),
        "results": all_results,
    }
    combined_file = OUT_DIR / "_combined_results.json"
    combined_file.write_text(json.dumps(combined, indent=2))

    # Print summary
    print(f"\n{'='*60}")
    print(f"  RESEARCH COMPLETE")
    print(f"{'='*60}")
    for r in all_results:
        status_icon = "✅" if r["status"] == "success" else ("⚠️" if r["status"] == "no_results" else "❌")
        hotel_count = len(r.get("hotels", []))
        avg_price = 0
        prices = [h.get('price_value') for h in r.get('hotels', []) if h.get('price_value')]
        if prices:
            avg_price = sum(prices) // len(prices)
        print(f"  {status_icon} {r['city']:<12} {hotel_count} hotels  avg £{avg_price}/night")

    print(f"\n  All results: {OUT_DIR}/")
    print(f"  Combined:   {combined_file.name}")

    return combined


if __name__ == "__main__":
    asyncio.run(main())
