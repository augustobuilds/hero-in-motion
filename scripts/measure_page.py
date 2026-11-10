"""Measure what a page makes a browser fetch before anyone presses Play, and after.

Optional tool. Like render_film.py it needs the Playwright package for Python and a Chromium
(pass --chromium PATH or set HERO_CHROMIUM to use one you already have). No ffmpeg.

    python3 scripts/measure_page.py output/hero.html
    python3 scripts/measure_page.py docs/autoplay.html --seconds 8 --json

It serves the page's folder to this computer only (127.0.0.1), opens the page in a headless Chromium,
waits, and adds up the bytes the server sent for each file. If the page has the kit's Play button it then
presses it, waits for the video to play, and adds up again. The numbers are what was sent over a local
connection with nothing cached: a real visit adds the network's own overhead, and a browser on a slow
connection may fetch a video in smaller steps.

Exit codes: 0 done, 2 bad input or the page did not open, 3 Playwright is missing or Chromium won't start.
"""
import argparse
import functools
import http.server
import json
import os
from pathlib import Path
import re
import sys
import threading
from urllib.parse import unquote, urlsplit

VIDEO = (".mp4", ".webm", ".m4v", ".mov", ".ogv")


class Counting(http.server.SimpleHTTPRequestHandler):
    """A static file server that answers byte ranges, as real hosts do, and counts what it sends."""

    sent, lock = {}, threading.Lock()

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        asked = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        partial = bool(asked and (asked.group(1) or asked.group(2)))
        if partial:
            if asked.group(1):
                start = int(asked.group(1))
                end = min(int(asked.group(2)), size - 1) if asked.group(2) else size - 1
            else:
                start = max(0, size - int(asked.group(2)))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if partial:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        name = unquote(urlsplit(self.path).path).lstrip("/")
        left = end - start + 1
        with path.open("rb") as handle:
            handle.seek(start)
            try:
                while left > 0:
                    chunk = handle.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
                    with self.lock:
                        self.sent[name] = self.sent.get(name, 0) + len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser stopped reading: what was sent so far still counts


def summary(sent):
    video = sum(n for name, n in sent.items() if name.lower().endswith(VIDEO))
    return {"files": dict(sorted(sent.items())), "video_bytes": video, "total_bytes": sum(sent.values())}


def measure(page_path, seconds=5.0, chromium=None):
    """Return {"before": ..., "after": ... or None, "pressed_play": bool} for one built page."""
    from playwright.sync_api import sync_playwright
    page_path = Path(page_path).resolve()
    sent = {}
    handler = type("Handler", (Counting,), {"sent": sent, "lock": threading.Lock()})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(page_path.parent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chromium) if chromium else pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto("http://127.0.0.1:%d/%s" % (server.server_address[1], page_path.name))
                page.wait_for_timeout(seconds * 1000)
                with handler.lock:
                    before = summary(dict(sent))
                after, pressed = None, page.locator("#hm-toggle").count() == 1 and page.is_visible("#hm-toggle")
                if pressed:
                    page.click("#hm-toggle")
                    try:
                        page.wait_for_function("(() => { const v = document.querySelector('#hm-video'); return v && !v.paused && v.currentTime > 0; })()", timeout=15000)
                    except Exception:
                        pass  # a missing video stays unplayed; the numbers say so
                    page.wait_for_timeout(seconds * 1000)
                    with handler.lock:
                        after = summary(dict(sent))
                return {"page": page_path.name, "seconds": seconds, "before": before, "pressed_play": pressed, "after": after}
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


def amount(n):
    return "%d B" % n if n < 1000 else ("%.1f kB" % (n / 1000) if n < 1_000_000 else "%.2f MB" % (n / 1_000_000))


def report(found):
    lines = ["%s, %g s after opening, before anyone presses Play:" % (found["page"], found["seconds"])]
    width = max([len(name) for name in found["before"]["files"]] + [len(name) for name in (found["after"] or {"files": {}})["files"]] + [5])
    for name, n in found["before"]["files"].items():
        lines.append("  %-*s  %10s" % (width, name, amount(n)))
    lines.append("  %-*s  %10s" % (width, "total", amount(found["before"]["total_bytes"])))
    lines.append("  %-*s  %10s" % (width, "video", amount(found["before"]["video_bytes"])))
    if found["after"]:
        lines.append("After Play, %g s later:" % found["seconds"])
        for name, n in found["after"]["files"].items():
            more = n - found["before"]["files"].get(name, 0)
            if more:
                lines.append("  %-*s  %10s" % (width, name, "+" + amount(more)))
        lines.append("  %-*s  %10s" % (width, "video", amount(found["after"]["video_bytes"])))
    elif not found["pressed_play"]:
        lines.append("No Play button from this kit on the page, so nothing was pressed.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure what a page fetches before anyone presses Play, and after.")
    parser.add_argument("page", help="a built .html file; its folder is served to this computer only")
    parser.add_argument("--seconds", type=float, default=5.0, help="how long to wait before each count (default 5)")
    parser.add_argument("--json", action="store_true", help="print the numbers as JSON")
    parser.add_argument("--chromium", default=os.environ.get("HERO_CHROMIUM"), help="path to a Chromium/Chrome binary (default: $HERO_CHROMIUM)")
    args = parser.parse_args(argv)
    page = Path(args.page)
    if not page.is_file() or page.suffix.lower() not in (".html", ".htm"):
        print("error: " + args.page + " is not an .html file", file=sys.stderr)
        return 2
    if not 0 < args.seconds <= 120:
        print("error: --seconds must be more than 0 and at most 120", file=sys.stderr)
        return 2
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print("error: Playwright is not installed (python3 -m pip install playwright && python3 -m playwright install chromium)", file=sys.stderr)
        return 3
    from playwright.sync_api import Error as PlaywrightError
    try:
        found = measure(page, args.seconds, args.chromium)
    except PlaywrightError as exc:
        first = str(exc).splitlines()[0]
        if "Executable doesn't exist" in first or "launch" in first.lower():
            print("error: could not start Chromium (run python3 -m playwright install chromium, pass --chromium PATH, or fix or unset HERO_CHROMIUM): " + first, file=sys.stderr)
            return 3
        print("error: the page did not open: " + first, file=sys.stderr)
        return 2
    print(json.dumps(found, indent=2) if args.json else report(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
