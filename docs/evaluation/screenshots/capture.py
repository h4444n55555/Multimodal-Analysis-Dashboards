"""Before/after screenshots of the Study Hub areas changed for the Lab 7 report.

    python docs/evaluation/screenshots/capture.py before 01 02 03
    python docs/evaluation/screenshots/capture.py after  01 02 03

Needs the website running on http://localhost:3000. Uses the installed Edge
through Playwright, dark theme, 1440x900. Writes <id>-<name>-<phase>.png next to
this script. A shot whose area no longer exists is skipped with a note.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
OUT = Path(__file__).resolve().parent

# id -> list of (name, path, how). how is a CSS selector to capture, or a
# callable(page) returning a clip dict.


def union_clip(page, top_sel, bottom_sel, pad=24):
    a = page.locator(top_sel).first.bounding_box()
    b = page.locator(bottom_sel).last.bounding_box()
    if not a or not b:
        return None
    # span both boxes, whichever comes first on the page
    x0, y0 = min(a["x"], b["x"]) - pad, min(a["y"], b["y"]) - pad
    x1 = max(a["x"] + a["width"], b["x"] + b["width"]) + pad
    y1 = max(a["y"] + a["height"], b["y"] + b["height"]) + pad
    return {"x": max(0, x0), "y": max(0, y0), "width": x1 - max(0, x0), "height": y1 - max(0, y0)}


def dashboard_bottom(page):
    # from the request-access card to whatever follows it at the page bottom
    top = "main section:has-text('Want to use this data?')"
    for bottom in ("main a:has-text('See the')", "main [data-details-link]", top):
        if page.locator(bottom).count():
            clip = union_clip(page, top, bottom, pad=32)
            if clip:
                clip["height"] += 40
            return clip
    return None


def page_top(page):
    # the modality header down to the "About this data" panel
    return union_clip(page, "main > div > div:first-child", "section[aria-labelledby='about-data']", pad=24)


SHOTS = {
    "01": [("home-sample-cards", "/", "#sensors")],
    "02": [
        ("thermal-top", "/thermal", page_top),
        ("ecg-top", "/ecg", page_top),
        ("rppg-top", "/rppg", page_top),
    ],
    "03": [("ecg-dashboard", "/ecg", "main")],
    "04": [("rppg-dashboard", "/rppg", "main")],
    "05": [("dashboard-bottom", "/ecg", dashboard_bottom)],
    "06": [("built-with-the-data", "/", "#apps")],
    # 08 adds a details link above the access card (shot 05 shows both) and
    # the reading card it opens
    "08": [
        ("thermal-details-card", "/thermal", {"click": "[data-details-link]", "shot": "[role='dialog']"}),
        ("ecg-details-card", "/ecg", {"click": "[data-details-link]", "shot": "[role='dialog']"}),
        ("rppg-details-card", "/rppg", {"click": "[data-details-link]", "shot": "[role='dialog']"}),
    ],
    "09": [("thermal-video", "/thermal", "div.viz:has(h3:has-text('Thermal video'))")],
    # the real viewport after scrolling, with the sticky nav left as it is
    "10": [("data-agreement-scrolled", "/data-agreement", {"scroll": 900})],
    "11": [("research-pipeline", "/", "#status")],
    "12": [("footer", "/", "footer")],
    # r2-14: pipeline text sizing (before = state after r2-12)
    "14": [("pipeline-text", "/", "#status")],
    # EMG goes from "soon" to a live page
    "13": [
        ("modality-pills", "/ecg", "nav[aria-label='Modalities']"),
        ("emg-modalities-row", "/", "#sensors"),
        ("emg-dashboard", "/emg", "main"),
        ("emg-details-card", "/emg", {"click": "[data-details-link]", "shot": "[role='dialog']"}),
    ],
}


def settle(page, keep_header=False):
    """Dark theme, then scroll the whole page so scroll-in animations finish."""
    page.evaluate("document.documentElement.classList.add('dark')")
    # hide the dev-mode badge, and (unless asked not to) keep the sticky nav
    # from covering the sections being captured
    css = "nextjs-portal{display:none!important}"
    if not keep_header:
        css += " header{position:relative!important}"
    page.add_style_tag(content=css)
    height = page.evaluate("document.body.scrollHeight")
    for y in range(0, height + 900, 450):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(120)
    page.wait_for_timeout(1200)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def main():
    phase, ids = sys.argv[1], sys.argv[2:] or list(SHOTS)
    assert phase in ("before", "after"), "phase must be before or after"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        for sid in ids:
            for name, path, how in SHOTS[sid]:
                page.goto(BASE + path, wait_until="load")
                page.wait_for_timeout(2500)
                scroll_shot = isinstance(how, dict) and "scroll" in how
                settle(page, keep_header=scroll_shot)
                out = OUT / f"{sid}-{name}-{phase}.png"
                if scroll_shot:
                    page.evaluate(f"window.scrollTo(0, {how['scroll']})")
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(out))
                    print("saved", out.name)
                    continue
                if isinstance(how, dict):
                    if page.locator(how["click"]).count() == 0:
                        print(f"skip {out.name}: {how['click']} not found")
                        continue
                    # a taller window so the whole reading card fits
                    page.set_viewport_size({"width": 1440, "height": 1400})
                    page.locator(how["click"]).first.click()
                    page.wait_for_timeout(800)
                    page.locator(how["shot"]).first.screenshot(path=str(out))
                    page.set_viewport_size({"width": 1440, "height": 900})
                    print("saved", out.name)
                    continue
                if callable(how):
                    clip = how(page)
                    if not clip:
                        print(f"skip {out.name}: area not found")
                        continue
                    page.screenshot(path=str(out), clip=clip, full_page=True)
                else:
                    loc = page.locator(how)
                    if loc.count() == 0:
                        print(f"skip {out.name}: {how} not found")
                        continue
                    if loc.count() > 1:
                        # several siblings: capture the box around all of them
                        boxes = [loc.nth(i).bounding_box() for i in range(loc.count())]
                        boxes = [b for b in boxes if b]
                        x0 = min(b["x"] for b in boxes) - 16
                        y0 = min(b["y"] for b in boxes) - 16
                        x1 = max(b["x"] + b["width"] for b in boxes) + 16
                        y1 = max(b["y"] + b["height"] for b in boxes) + 16
                        page.screenshot(path=str(out), full_page=True,
                                        clip={"x": max(0, x0), "y": max(0, y0), "width": x1 - max(0, x0), "height": y1 - max(0, y0)})
                    else:
                        loc.screenshot(path=str(out))
                print("saved", out.name)
        browser.close()


if __name__ == "__main__":
    main()
