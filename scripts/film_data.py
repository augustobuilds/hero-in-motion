"""Collect the facts the explainer film shows, straight from the kit itself.

The film (film/explainer.html) draws an illustration of the page build_hero.py writes. So that its
words and colours stay in step with the kit, they come from here: the labels are read back out
of real pages built from examples/hero.json and examples/hero.es.json, the colours from the
template's CSS, each language's poster from the path its example config names, and the size of the example's
own clip in docs/ (the number the film opens on).
Standard library only.

    python3 scripts/film_data.py            # print the data as JSON
    python3 scripts/film_data.py --check    # exit 1 if film/explainer.html embeds stale data
    python3 scripts/film_data.py --write    # refresh the copy embedded in film/explainer.html
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _common import load  # noqa: E402
import build_hero  # noqa: E402

FILM = ROOT / "film" / "explainer.html"
BLOCK = re.compile(r'(<script id="kit-data" type="application/json">)(.*?)(</script>)', re.S)


class _Page(HTMLParser):
    """Pull the visible strings and the data-* labels out of one built page."""

    def __init__(self):
        super().__init__()
        self.found, self._want = {}, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id") == "hm-messages":
            self.found.update({k[5:]: v for k, v in a.items() if k.startswith("data-")})
        elif a.get("id") == "hm-toggle":
            self._want = "play"
        elif a.get("class") == "hm-badge":
            self._want = "badge"
        elif a.get("id") == "hm-status":
            self._want = "idle"
        elif a.get("id") == "hm-caption":
            self._want = "note"
        elif a.get("id") == "hm-notes":
            self._want = "notes"
        elif tag == "h1":
            self._want = "headline"
        elif a.get("class") == "hm-cta":
            self._want = "cta"
        elif tag == "img" and a.get("id") == "hm-poster":
            self.found["poster_alt"] = a.get("alt", "")

    def handle_data(self, data):
        if self._want and data.strip():
            self.found.setdefault(self._want, data.strip())
            self._want = None


def _page(config):
    parser = _Page()
    parser.feed(build_hero.build(build_hero.validate(load(config))))
    return parser.found


def _colours():
    css = (ROOT / "templates" / "hero.html").read_text(encoding="utf-8")
    light = re.search(r"\.hm\s*\{[^}]*\}", css).group(0)
    dark = re.search(r"prefers-color-scheme:\s*dark\)\s*\{\s*\.hm\s*\{[^}]*\}", css).group(0)
    pick = lambda block: dict(re.findall(r"--hm-(bg|ink|card|accent):\s*(#[0-9a-fA-F]{3,8})", block))  # noqa: E731
    return {"light": pick(light), "dark": pick(dark)}


def kit_data():
    pages, posters = {}, {}
    for lang, name in (("en", "hero.json"), ("es", "hero.es.json")):
        config = ROOT / "examples" / name
        found = _page(config)
        data = load(config)
        pages[lang] = {
            "ui": {k: found[k] for k in ("play", "pause", "idle", "initial", "loading", "playing", "paused", "ended", "offscreen", "failed", "reduced", "badge", "note", "notes")},
            "page": {"headline": found["headline"], "summary": data["summary"], "cta": found["cta"], "details": data["details"],
                     "video": data["video"], "poster": data["poster"]},
        }
        # the config's poster path is relative to the built page; the example posters sit in examples/
        posters[lang] = (ROOT / "examples" / data["poster"][2:]).read_text(encoding="utf-8")
    # the opening of the film counts up to what an autoplaying hero fetches unasked: the example's own clip in docs/
    video = load(ROOT / "examples" / "hero.json")["video"][2:-4]
    clip = {kind: (ROOT / "docs" / (video + "." + kind)).stat().st_size for kind in ("mp4", "webm")}
    return {"colours": _colours(), "lang": pages, "clip": clip, "posters": posters}


def _embedded():
    m = BLOCK.search(FILM.read_text(encoding="utf-8"))
    return json.loads(m.group(2)) if m else None


def main(argv):
    unknown = [a for a in argv if a not in ("--write", "--check")]
    if unknown:
        print(__doc__.strip(), file=sys.stderr)
        return 0 if unknown in (["--help"], ["-h"]) else 2
    data = kit_data()
    if "--write" in argv:
        html = FILM.read_text(encoding="utf-8")
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        FILM.write_text(BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), html), encoding="utf-8")
        print("Updated " + str(FILM.relative_to(ROOT)))
        return 0
    if "--check" in argv:
        if _embedded() != data:
            print("film/explainer.html is out of date: run python3 scripts/film_data.py --write", file=sys.stderr)
            return 1
        print("film/explainer.html matches the kit")
        return 0
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
