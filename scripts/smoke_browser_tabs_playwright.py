import os
import sys
import time
import random


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright tidak terpasang. Install opsional: pip install playwright && playwright install chromium")
        return 2

    url = (os.getenv("ECOAIMS_FRONTEND_URL") or "http://127.0.0.1:8050").rstrip("/") + "/"
    iterations = int(os.getenv("ECOAIMS_SMOKE_ITERATIONS", "1"))
    expect_neg_error = str(os.getenv("ECOAIMS_EXPECT_CONTRACT_NEGOTIATION_ERROR", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    slow_ms = int(os.getenv("ECOAIMS_SIMULATE_SLOW_NETWORK_MS", "0"))
    jitter_ms = int(os.getenv("ECOAIMS_SIMULATE_NETWORK_JITTER_MS", "0"))
    block_heavy = str(os.getenv("ECOAIMS_BLOCK_HEAVY_ASSETS", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}
    timeout_ms = int(os.getenv("ECOAIMS_SMOKE_TIMEOUT_MS", "20000"))
    profiles = [p.strip().lower() for p in str(os.getenv("ECOAIMS_NETWORK_PROFILES", "")).split(",") if p.strip()]
    interaction_rounds = int(os.getenv("ECOAIMS_SMOKE_INTERACTION_ROUNDS", "1"))
    viewports = [
        {"name": "mobile", "width": 375, "height": 667},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "desktop", "width": 1280, "height": 720},
    ]

    def _profile_cfg(name: str) -> tuple[int, int, bool, int]:
        if name == "fast":
            return 0, 0, True, timeout_ms
        if name in {"5g", "5g_nr", "nr"}:
            return max(5, slow_ms or 10), max(5, jitter_ms or 10), False, max(timeout_ms, 20000)
        if name in {"roaming", "roam"}:
            return max(120, slow_ms or 180), max(120, jitter_ms or 420), True, max(timeout_ms, 60000)
        if name in {"4g", "4g_lte", "lte"}:
            return max(30, slow_ms or 60), max(10, jitter_ms or 30), False, max(timeout_ms, 25000)
        if name in {"4g_interference", "4g_noise", "lte_interference"}:
            return max(60, slow_ms or 90), max(120, jitter_ms or 320), True, max(timeout_ms, 60000)
        if name == "wifi":
            return max(10, slow_ms or 20), max(5, jitter_ms or 15), False, max(timeout_ms, 25000)
        if name in {"wifi_high_latency", "wifi_hl"}:
            return max(200, slow_ms or 280), max(40, jitter_ms or 90), False, max(timeout_ms, 60000)
        if name in {"wifi_interference_high", "wifi_interference", "wifi_noise"}:
            return max(80, slow_ms or 120), max(120, jitter_ms or 450), True, max(timeout_ms, 60000)
        if name in {"satellite", "sat"}:
            return max(900, slow_ms or 1200), max(300, jitter_ms or 900), True, max(timeout_ms, 60000)
        if name == "edge":
            return max(300, slow_ms or 450), max(50, jitter_ms or 120), True, max(timeout_ms, 55000)
        if name == "3g":
            return max(250, slow_ms or 300), max(40, jitter_ms or 100), True, max(timeout_ms, 45000)
        if name in {"3g_high_latency", "3g_hl"}:
            return max(400, slow_ms or 520), max(120, jitter_ms or 380), True, max(timeout_ms, 60000)
        if name == "2g":
            return max(700, slow_ms or 900), max(80, jitter_ms or 220), True, max(timeout_ms, 70000)
        if name == "vpn":
            return max(350, slow_ms or 500), max(80, jitter_ms or 250), True, max(timeout_ms, 80000)
        if name == "slow":
            return max(50, slow_ms or 100), max(20, jitter_ms or 60), True, max(timeout_ms, 45000)
        if name == "very_slow":
            return max(200, slow_ms or 400), max(40, jitter_ms or 120), True, max(timeout_ms, 60000)
        if name == "timeout":
            return max(400, slow_ms or 600), max(50, jitter_ms or 150), True, min(timeout_ms, 8000)
        return slow_ms, jitter_ms, block_heavy, timeout_ms

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        run_profiles = profiles or ["custom"]
        for profile in run_profiles:
            p_slow_ms, p_jitter_ms, p_block_heavy, p_timeout_ms = _profile_cfg(profile)
            for vp in viewports:
                for _ in range(max(1, iterations)):
                    page = browser.new_page(viewport={"width": int(vp["width"]), "height": int(vp["height"])})
                    if p_slow_ms > 0 or p_jitter_ms > 0 or p_block_heavy:
                        def _route(route, request):
                            u = request.url
                            if p_block_heavy and (u.endswith(".mp3") or u.endswith(".png") or u.endswith(".jpg") or u.endswith(".jpeg") or u.endswith(".gif")):
                                route.abort()
                                return
                            if p_slow_ms > 0:
                                time.sleep(float(p_slow_ms) / 1000.0)
                            if p_jitter_ms > 0:
                                time.sleep(float(random.randint(0, int(p_jitter_ms))) / 1000.0)
                            route.continue_()
                        page.route("**/*", _route)
                    page.goto(url, wait_until="domcontentloaded", timeout=p_timeout_ms)

                    page.get_by_text("ECO-AIMS Energy Dashboard").wait_for(timeout=p_timeout_ms)

                    page.get_by_text("Monitoring", exact=True).click()
                    if expect_neg_error:
                        page.get_by_text("Contract Compatibility Check").wait_for(timeout=p_timeout_ms)
                    else:
                        page.locator("#solar-gauge").wait_for(timeout=p_timeout_ms)
                        try:
                            btn = page.locator("#comparison-update-history-btn")
                            for _round in range(max(1, interaction_rounds)):
                                if btn.count() > 0 and btn.is_enabled():
                                    btn.click()
                                    page.locator("#comparison-update-history-result").wait_for(timeout=p_timeout_ms)
                        except Exception:
                            pass
                        try:
                            page.locator("#comparison-diagnostics-details summary").click()
                            page.locator("#comparison-diagnostics-text").wait_for(timeout=p_timeout_ms)
                            try:
                                page.locator("[title='Copy diagnostics']").click()
                            except Exception:
                                pass
                            page.locator("#comparison-diagnostics-details summary").click()
                        except Exception:
                            pass

                    page.get_by_text("Optimization", exact=True).click()
                    page.locator("#opt-run-btn").wait_for(timeout=p_timeout_ms)
                    page.locator("#opt-pie-chart").wait_for(timeout=p_timeout_ms)
                    for _round in range(max(1, interaction_rounds)):
                        try:
                            page.locator("#opt-priority-dropdown").click()
                            choice = random.choice(
                                [
                                    "Prioritas Energi Terbarukan (Solar & Wind)",
                                    "Prioritas Baterai (Peak Shaving)",
                                    "Prioritas PLN / Grid (Kestabilan)",
                                ]
                            )
                            page.get_by_text(choice, exact=True).click()
                        except Exception:
                            pass
                        try:
                            battery_v = random.choice([20, 40, 60, 80, 100])
                            page.locator("#opt-battery-slider input[type='range']").evaluate(
                                f"(el) => {{ el.value = {battery_v}; el.dispatchEvent(new Event('input', {{bubbles: true}})); el.dispatchEvent(new Event('change', {{bubbles: true}})); }}"
                            )
                        except Exception:
                            pass
                        try:
                            grid_v = random.choice([50, 80, 100, 120, 150, 200])
                            page.locator("#opt-grid-slider input[type='range']").evaluate(
                                f"(el) => {{ el.value = {grid_v}; el.dispatchEvent(new Event('input', {{bubbles: true}})); el.dispatchEvent(new Event('change', {{bubbles: true}})); }}"
                            )
                        except Exception:
                            pass
                        try:
                            page.locator("#opt-run-btn").click()
                            page.locator("#opt-recommendation-text").wait_for(timeout=p_timeout_ms)
                            page.locator("#opt-bar-chart").wait_for(timeout=p_timeout_ms)
                        except Exception:
                            pass

                    page.get_by_text("Precooling / LAEOPF", exact=True).click()
                    page.locator("#precooling-floor").wait_for(timeout=p_timeout_ms)
                    page.locator("#precooling-zone").wait_for(timeout=p_timeout_ms)
                    page.locator("#precooling-run-sim-btn").wait_for(timeout=p_timeout_ms)

                    page.get_by_text("Settings", exact=True).click()
                    page.get_by_text("Precooling", exact=True).click()
                    page.locator("#precoolset-load-btn").wait_for(timeout=p_timeout_ms)
                    page.locator("#precoolset-save-btn").wait_for(timeout=p_timeout_ms)

                    page.get_by_text("Reports", exact=True).click()
                    page.locator("#reports-precooling-impact-panel").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-trend-fig").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-quality").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-export-btn").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-stream-filter").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-zone-filter").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-session-open-btn").wait_for(timeout=p_timeout_ms)
                    page.get_by_role("button", name="Open Session Detail").click()
                    page.locator("#reports-precooling-impact-session-modal").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-session-modal-body").wait_for(timeout=p_timeout_ms)
                    page.locator("#reports-precooling-impact-session-evidence-fig").wait_for(timeout=p_timeout_ms)
                    page.get_by_role("button", name="Close").click()
                    page.close()

        browser.close()

    print("OK: browser smoke tabs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
