import os
import sys


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright tidak terpasang. Install opsional: pip install playwright && playwright install chromium")
        return 2

    url = (os.getenv("ECOAIMS_FRONTEND_URL") or "http://127.0.0.1:8050").rstrip("/") + "/"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        title = page.title()
        page.wait_for_timeout(500)
        browser.close()

    if "ECO-AIMS" not in title and "ECOAIMS" not in title:
        print(f"Unexpected title: {title}")
        return 1

    print("OK: browser smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

