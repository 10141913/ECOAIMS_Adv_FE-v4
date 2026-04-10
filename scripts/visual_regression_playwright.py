import hashlib
import os
import sys


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_pillow():
    try:
        from PIL import Image, ImageChops  # type: ignore
        return Image, ImageChops
    except Exception:
        return None, None


def _pixel_diff_ratio(a_path: str, b_path: str) -> float | None:
    Image, ImageChops = _try_pillow()
    if Image is None or ImageChops is None:
        return None
    a = Image.open(a_path).convert("RGBA")
    b = Image.open(b_path).convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    if bbox is None:
        return 0.0
    pixels = a.size[0] * a.size[1]
    diff_pixels = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    if pixels <= 0:
        return 0.0
    return float(diff_pixels) / float(pixels)


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright tidak terpasang. Install opsional: pip install playwright && playwright install chromium")
        return 2

    url = (os.getenv("ECOAIMS_FRONTEND_URL") or "http://127.0.0.1:8050").rstrip("/") + "/"
    baseline_dir = os.path.abspath(os.getenv("ECOAIMS_VISUAL_BASELINE_DIR") or "output/visual_baseline")
    out_dir = os.path.abspath(os.getenv("ECOAIMS_VISUAL_OUT_DIR") or "output/visual_current")
    update_baseline = str(os.getenv("ECOAIMS_VISUAL_UPDATE_BASELINE", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    threshold = float(os.getenv("ECOAIMS_VISUAL_DIFF_THRESHOLD", "0.0002"))
    timeout_ms = int(os.getenv("ECOAIMS_VISUAL_TIMEOUT_MS", "30000"))
    expect_neg_error = str(os.getenv("ECOAIMS_VISUAL_EXPECT_CONTRACT_NEGOTIATION_ERROR", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}
    open_tech_details = str(os.getenv("ECOAIMS_VISUAL_OPEN_TECH_DETAILS", "false")).strip().lower() in {"1", "true", "yes", "y", "on"}

    viewports = [
        {"name": "mobile", "width": 375, "height": 667},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "desktop", "width": 1280, "height": 720},
    ]

    os.makedirs(out_dir, exist_ok=True)
    if update_baseline:
        os.makedirs(baseline_dir, exist_ok=True)

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in viewports:
            page = browser.new_page(viewport={"width": int(vp["width"]), "height": int(vp["height"])})
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.get_by_text("ECO-AIMS Energy Dashboard").wait_for(timeout=timeout_ms)

            shots = []
            page.get_by_text("Home", exact=True).click()
            shots.append(("home", page))

            page.get_by_text("Monitoring", exact=True).click()
            if expect_neg_error:
                page.get_by_text("Contract Compatibility Check").wait_for(timeout=timeout_ms)
                if open_tech_details:
                    try:
                        page.get_by_text("Technical Details", exact=True).click()
                    except Exception:
                        pass
                try:
                    title1 = page.locator("#use-simulation-data").get_attribute("title") or ""
                    title2 = page.locator("#check-backend-status").get_attribute("title") or ""
                    if not title1.strip() or not title2.strip():
                        failures.append((f"{vp['name']}_monitoring", "missing_tooltip_title"))
                except Exception:
                    pass
            else:
                page.locator("#solar-gauge").wait_for(timeout=timeout_ms)
                page.locator("#renewable-comparison-content").wait_for(timeout=timeout_ms)
                try:
                    btn = page.locator("#comparison-update-history-btn")
                    if btn.count() > 0 and btn.is_enabled():
                        btn.click()
                        page.locator("#comparison-update-history-result").wait_for(timeout=timeout_ms)
                        shots.append(("monitoring_after_interaction", page))
                except Exception:
                    pass
                try:
                    page.locator("#comparison-diagnostics-details summary").click()
                    shots.append(("monitoring_diagnostics_open", page))
                    page.locator("#comparison-diagnostics-details summary").click()
                except Exception:
                    pass
            shots.append(("monitoring", page))

            page.get_by_text("Forecasting", exact=True).click()
            page.locator("#forecast-consumption-graph").wait_for(timeout=timeout_ms)
            shots.append(("forecasting", page))

            page.get_by_text("Optimization", exact=True).click()
            page.locator("#opt-run-btn").wait_for(timeout=timeout_ms)
            page.locator("#opt-pie-chart").wait_for(timeout=timeout_ms)
            shots.append(("optimization", page))
            try:
                page.locator("#opt-priority-dropdown").click()
                shots.append(("optimization_dropdown_open", page))
                page.get_by_text("Prioritas PLN / Grid (Kestabilan)", exact=True).click()
                page.locator("#opt-run-btn").click()
                page.locator("#opt-recommendation-text").wait_for(timeout=timeout_ms)
                shots.append(("optimization_after_interaction", page))
            except Exception:
                pass

            page.get_by_text("Precooling / LAEOPF", exact=True).click()
            page.locator("#precooling-floor").wait_for(timeout=timeout_ms)
            page.locator("#precooling-zone").wait_for(timeout=timeout_ms)
            page.locator("#precooling-run-sim-btn").wait_for(timeout=timeout_ms)
            shots.append(("precooling", page))

            page.get_by_text("BMS", exact=True).click()
            page.locator("#bms-soc-gauge").wait_for(timeout=timeout_ms)
            page.locator("#bms-live-graph").wait_for(timeout=timeout_ms)
            shots.append(("bms", page))

            page.get_by_text("Reports", exact=True).click()
            page.locator("#reports-precooling-impact-panel").wait_for(timeout=timeout_ms)
            page.locator("#reports-precooling-impact-session-open-btn").wait_for(timeout=timeout_ms)
            shots.append(("reports", page))

            page.get_by_role("button", name="Open Session Detail").click()
            page.locator("#reports-precooling-impact-session-modal").wait_for(timeout=timeout_ms)
            shots.append(("reports_session_modal", page))
            if open_tech_details:
                try:
                    page.get_by_text("Technical Details").click()
                except Exception:
                    pass
            page.get_by_role("button", name="Close").click()

            page.get_by_text("Settings", exact=True).click()
            page.get_by_text("Precooling", exact=True).click()
            page.locator("#precoolset-load-btn").wait_for(timeout=timeout_ms)
            shots.append(("settings_precooling", page))

            page.get_by_text("Help/FAQ", exact=True).click()
            page.get_by_text("FAQ").wait_for(timeout=timeout_ms)
            shots.append(("help", page))

            page.get_by_text("About", exact=True).click()
            page.get_by_text("Tentang ECO-AIMS Dashboard").wait_for(timeout=timeout_ms)
            shots.append(("about", page))

            for name, pg in shots:
                fn = f"{vp['name']}_{name}.png"
                out_path = os.path.join(out_dir, fn)
                pg.screenshot(path=out_path, full_page=True)

                if update_baseline:
                    base_path = os.path.join(baseline_dir, fn)
                    with open(out_path, "rb") as fsrc, open(base_path, "wb") as fdst:
                        fdst.write(fsrc.read())
                else:
                    base_path = os.path.join(baseline_dir, fn)
                    if os.path.exists(base_path):
                        ratio = _pixel_diff_ratio(base_path, out_path)
                        if ratio is None:
                            if _sha256_file(base_path) != _sha256_file(out_path):
                                failures.append((fn, "hash_mismatch"))
                        else:
                            if ratio > threshold:
                                failures.append((fn, f"diff_ratio={ratio:.6f} threshold={threshold:.6f}"))
                    else:
                        failures.append((fn, "missing_baseline"))
            page.close()
        browser.close()

    if failures:
        for fn, why in failures:
            print(f"VISUAL_REGRESSION_FAIL file={fn} reason={why}")
        if any(why == "missing_baseline" for _fn, why in failures):
            print(f"Baselines belum ada. Jalankan: ECOAIMS_VISUAL_UPDATE_BASELINE=true python {os.path.basename(__file__)}")
        Image, _ = _try_pillow()
        if Image is None:
            print("Pillow tidak terpasang; fallback perbandingan memakai hash (lebih sensitif).")
        return 1

    print("OK: visual regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
