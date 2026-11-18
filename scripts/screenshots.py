#!/usr/bin/env python3
"""Rebuild the README images from scripts/preview.html (demo data) and the brand icons.

Usage:  pip install playwright && playwright install chromium
        python scripts/screenshots.py
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parents[1]
IMAGES = {"en": "card.png", "it": "card-it.png"}
BRAND = ROOT / "custom_components" / "daily_goals" / "brand"


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def _icons() -> None:
    """Render the brand icons from scripts/icon.svg (needs rsvg-convert)."""
    if not shutil.which("rsvg-convert"):
        print("rsvg-convert not found: brand icons not rebuilt")
        return
    for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
        subprocess.run(
            [
                "rsvg-convert",
                "-w",
                str(size),
                "-h",
                str(size),
                str(ROOT / "scripts" / "icon.svg"),
                "-o",
                str(BRAND / name),
            ],
            check=True,
        )
        print("written", name)


def main() -> None:
    _icons()
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/scripts/preview.html"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL"))
        for lang, name in IMAGES.items():
            page = browser.new_page(viewport={"width": 976, "height": 600}, device_scale_factor=2)
            page.goto(f"{url}?lang={lang}")
            page.wait_for_selector("body[data-ready]")
            page.wait_for_timeout(1500)  # history and frame
            page.locator("body").screenshot(path=str(ROOT / "images" / name), animations="disabled")
            print("written", name)
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
