#!/usr/bin/env python3
"""
Family holiday qualifier for extracted Booking.com options.
Scores each option against: budget, beach, all-inclusive, water-park, bonus activities.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

IN_PATH = Path.home() / ".agent-browser" / "hotel-research" / "_combined_results.json"
OUT_PATH = Path.home() / ".agent-browser" / "hotel-research" / "family_qualified_options.json"

BUDGET_TOTAL_GBP = 4000

BEACH_KWS = ["beachfront", "beach front", "private beach", "near the beach", "beach"]
ALL_INC_KWS = ["all inclusive", "all-inclusive", "full board", "inclusive package"]
WATERPARK_KWS = ["water park", "waterpark", "aquapark", "aqua park", "slides", "waterslide"]
BONUS_KWS = ["kids club", "spa", "kids pool", "evening entertainment", "snorkeling", "family rooms"]


def _kw_hit(text: str, kws: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in kws)


def _extract_total_nights(city_item: dict) -> int:
    c_in = city_item.get("checkin", "")
    c_out = city_item.get("checkout", "")
    try:
        from datetime import datetime
        d1 = datetime.fromisoformat(c_in)
        d2 = datetime.fromisoformat(c_out)
        return max((d2 - d1).days, 1)
    except Exception:
        return 3


async def main():
    data = json.loads(IN_PATH.read_text())
    city_items = data.get("results", [])

    candidates = []
    for city in city_items:
        nights = _extract_total_nights(city)
        for h in city.get("hotels", []):
            pv = h.get("price_value")
            if not pv:
                continue
            total_est = pv  # Booking price in results is usually total stay price.
            if total_est > BUDGET_TOTAL_GBP:
                continue
            candidates.append({
                "city": city.get("city"),
                "checkin": city.get("checkin"),
                "checkout": city.get("checkout"),
                "nights": nights,
                "name": h.get("name"),
                "price_value": pv,
                "price_text": h.get("price_text"),
                "review_score": h.get("review_score"),
                "url": h.get("booking_url", ""),
            })

    # Cheapest first; limit pages visited for speed
    candidates.sort(key=lambda x: x["price_value"])
    candidates = candidates[:30]

    qualified = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(locale="en-GB", viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        for c in candidates:
            url = c["url"]
            if not url:
                continue
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2500)
                text = await page.evaluate("document.body ? document.body.innerText : ''")
                text = re.sub(r"\s+", " ", text)[:200000]

                beach = _kw_hit(text, BEACH_KWS)
                all_inc = _kw_hit(text, ALL_INC_KWS)
                water = _kw_hit(text, WATERPARK_KWS)
                bonus_count = sum(1 for k in BONUS_KWS if k in text.lower())

                score = (3 if beach else 0) + (4 if all_inc else 0) + (5 if water else 0) + min(bonus_count, 3)

                c.update({
                    "beach": beach,
                    "all_inclusive": all_inc,
                    "water_park": water,
                    "bonus_hits": bonus_count,
                    "fit_score": score,
                })

                # keep broad set; strict-filtered list is derived below
                qualified.append(c)
            except Exception as e:
                c.update({"error": str(e)[:240]})

        await browser.close()

    strict = [x for x in qualified if x["beach"] and x["all_inclusive"] and x["water_park"]]
    fallback = sorted(qualified, key=lambda x: (-x["fit_score"], x["price_value"]))

    payload = {
        "budget_total_gbp": BUDGET_TOTAL_GBP,
        "strict_matches": strict,
        "ranked_matches": fallback,
        "candidate_count": len(candidates),
        "qualified_count": len(qualified),
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Saved: {OUT_PATH}")
    print(f"Strict matches: {len(strict)}")
    print(f"Ranked matches: {len(fallback)}")
    for i, x in enumerate(fallback[:15], 1):
        print(f"{i}. £{x['price_value']} | {x['city']} | {x['name']} | score={x['fit_score']} | beach={x['beach']} allinc={x['all_inclusive']} water={x['water_park']}")


if __name__ == "__main__":
    asyncio.run(main())
