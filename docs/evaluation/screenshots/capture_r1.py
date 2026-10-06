"""Before/after screenshots for the round 1 changes (01, 02, 03, 04, 07).

    python docs/evaluation/screenshots/capture_r1.py before
    python docs/evaluation/screenshots/capture_r1.py after

Same setup as capture.py (Edge, dark, 1440x900). Writes r1-<id>-<name>-<phase>.png.
The access form is filled with placeholder values to reach its later steps; it
is never submitted.
"""

import sys

from playwright.sync_api import sync_playwright

from capture import BASE, OUT, settle

FILL_FORM = """() => {
  const d = document.querySelector('[role=dialog]');
  const set = (el, v) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const fs = [...d.querySelectorAll('fieldset')].find(f => !f.hidden);
  for (const el of fs.querySelectorAll('input, select, textarea')) {
    if (el.type === 'checkbox') { if (!el.checked && !el.name) el.click(); continue; }
    if (el.tagName === 'SELECT') {
      const opt = [...el.options].find(o => !o.disabled && o.value && /Faculty|Approved|12/.test(o.value)) || [...el.options].find(o => !o.disabled && o.value);
      if (opt) set(el, opt.value);
      continue;
    }
    if (el.readOnly) continue;
    if (el.type === 'email') set(el, 'jane.doe@university.ac.in');
    else if (el.type === 'url') set(el, 'https://example.ac.in/jane');
    else if (el.tagName === 'TEXTAREA') set(el, 'Placeholder text for the screenshot: a research question about multimodal stress signals and the methods used to study it.');
    else if (el.name === 'name' || el.name === 'signature') set(el, 'Jane Doe');
    else set(el, 'Example');
  }
}"""


def open_menu(page):
    page.locator("header nav button:has-text('Data'), header nav button:has-text('Modalities')").first.click()
    page.wait_for_timeout(500)


def open_form(page, step):
    page.locator("button:has-text('Request access')").first.click()
    page.wait_for_timeout(600)
    for _ in range(step):
        page.evaluate(FILL_FORM)
        page.wait_for_timeout(200)
        page.locator("[role=dialog] button[type=submit]").click()
        page.wait_for_timeout(500)


def widget(title):
    return f"div.viz:has(h3:has-text('{title}'))"


# id, name, path, setup(page) or None, what to capture: selector | "viewport" | ("clip", x, y, w, h)
SHOTS = [
    ("01", "ecg-page", "/ecg", None, "main"),
    ("02", "hero", "/", None, "#hero"),
    ("02", "nav-data-menu", "/", open_menu, ("clip", 280, 0, 620, 470)),
    ("02", "modalities-list", "/", None, "#sensors"),
    ("02", "footer", "/", None, "footer"),
    ("03", "access-form-step1", "/ecg", lambda p: open_form(p, 0), "[role='dialog']"),
    ("03", "access-form-agreement-step", "/ecg", lambda p: open_form(p, 2), "[role='dialog']"),
    ("03", "data-agreement-page", "/data-agreement", None, ("clip", 0, 0, 1440, 900)),
    ("04", "pipeline-diagram", "/", None, "#status"),
    ("04", "chart-labels", "/ecg", None, widget("Heart rate over time")),
    ("07", "built-with-the-data", "/", None, "#apps"),
]


def main():
    phase = sys.argv[1]
    assert phase in ("before", "after")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        for sid, name, path, setup, what in SHOTS:
            out = OUT / f"r1-{sid}-{name}-{phase}.png"
            page.goto(BASE + path, wait_until="load")
            page.wait_for_timeout(2500)
            # menus and dialogs sit under the nav: keep the nav where it really is
            settle(page, keep_header=setup is not None or isinstance(what, tuple))
            try:
                if setup:
                    setup(page)
                if isinstance(what, tuple):
                    _, x, y, w, h = what
                    page.screenshot(path=str(out), clip={"x": x, "y": y, "width": w, "height": h})
                else:
                    loc = page.locator(what).first
                    loc.scroll_into_view_if_needed()
                    page.wait_for_timeout(400)
                    loc.screenshot(path=str(out))
                print("saved", out.name)
            except Exception as e:  # report and carry on with the other shots
                print(f"FAILED {out.name}: {str(e).splitlines()[0]}")
        browser.close()


if __name__ == "__main__":
    main()
