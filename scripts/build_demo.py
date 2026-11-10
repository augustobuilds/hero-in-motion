"""Build the live demo in docs/, the folder GitHub Pages can serve, from the examples.

Each demo page is an ordinary web page (templates/demo/) with the kit's hero block placed in it, the way
--fragment is meant to be used. docs/autoplay.html is the same hero built the usual way, for comparison.
The videos in docs/ are not made here: they are the examples' clips, rendered with render_film.py.
Standard library only.

    python3 scripts/build_demo.py --check    # exit 1 if docs/ is out of date
    python3 scripts/build_demo.py --write    # refresh docs/
"""
from html import escape
import json
from pathlib import Path
from string import Template
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _common import load  # noqa: E402
import build_hero  # noqa: E402

DOCS = ROOT / "docs"
REPO = "https://github.com/augustobuilds/hero-in-motion"
SITE = "https://augustobuilds.github.io/hero-in-motion/"
CARD = "social-card.png"
CARD_ALT = "Hero in Motion: a homepage hero that waits for Play. Northern lights over a lake, with a Play button on the picture."
# page, example config, name in the menu, what the card under "Three looks" says
PAGES = (("index.html", "hero.json", "Lake cabins", "Split: words beside a square picture."),
         ("swim.html", "swim.json", "Swim school", "Stacked: a wide picture under the words, with its own colours."),
         ("radio.html", "radio.json", "Night radio", "Cover: the picture fills the hero, with the lit window kept in view."))


def amount(n):
    return "%d B" % n if n < 1000 else ("%d kB" % round(n / 1000) if n < 1_000_000 else "%.2f MB" % (n / 1_000_000))


def _template(name):
    return Template((ROOT / "templates" / "demo" / name).read_text(encoding="utf-8"))


def _size(name):
    path = DOCS / name
    if not path.is_file():
        raise ValueError("docs/" + name + " is missing: render the example's clip with scripts/render_film.py and put it there")
    return path.stat().st_size


def _with_webm(data):
    """Name the WebM copy of the example's clip when docs/ has one (it is kept only where it is the smaller file)."""
    webm = data["video"][:-4] + ".webm"
    return dict(data, video_webm=webm) if (DOCS / webm[2:]).is_file() else data


def _clips(data):
    return [data[key][2:] for key in ("video", "video_webm") if key in data]


def _nav(current):
    links = ['<a href="%s"%s>%s</a>\n' % ("./" if page == "index.html" else page, ' aria-current="page"' if page == current else "", label)
             for page, _, label, _ in PAGES]
    links.append('<a href="autoplay.html"%s>Autoplay version</a>\n' % (' aria-current="page"' if current == "autoplay.html" else ""))
    return "".join(links)


def _shell(page, title, description, main, sizes, auto=False):
    return _template("shell.html").substitute(
        title=escape(title), description=escape(description, quote=True), url=SITE + ("" if page == "index.html" else page),
        card=SITE + CARD, card_alt=escape(CARD_ALT, quote=True), body_class="demo-auto" if auto else "demo-kit",
        sizes=escape(json.dumps(sizes, separators=(",", ":")), quote=True),
        meter_label="Video fetched without asking:" if auto else "Video fetched so far:",
        stop='<button class="demo-stop" id="demo-stop" type="button" data-stop="Stop the video" data-start="Start the video">Stop the video</button>\n' if auto else "",
        nav=_nav(page), repo=REPO, main=main)


def outputs():
    """Every file this script owns in docs/, as {name: bytes}."""
    found = {".nojekyll": b""}
    configs = {}
    for page, config, _, _ in PAGES:
        data = load(ROOT / "examples" / config)
        configs[page] = build_hero.validate(_with_webm(data))
        found[data["poster"][2:]] = (ROOT / "examples" / data["poster"][2:]).read_bytes()
    looks = {}
    for page, config, label, says in PAGES:
        looks[page] = ('<li><a href="%s"%%s><img src="%s" alt="" loading="lazy" width="1600" height="900"><span><b>%s</b>%s</span></a></li>\n'
                       % ("./" if page == "index.html" else page, escape(configs[page]["poster"], quote=True), escape(label), escape(says)))
    for page, config, label, _ in PAGES:
        data = configs[page]
        hero = build_hero.build(data, fragment=True)
        sizes = {name: _size(name) for name in _clips(data)}
        mp4, small = sizes[data["video"][2:]], min(sizes.values())
        poster = len(found[data["poster"][2:]])
        block = len(hero.encode("utf-8"))
        main = _template("kit.html").substitute(
            hero=hero, before=amount(block + poster), block=amount(block), poster_size=amount(poster),
            clip=amount(small), clip_note=" as WebM (%s as MP4, for browsers that need it)" % amount(mp4) if small < mp4 else "",
            looks="".join(looks[p] % (' aria-current="page"' if p == page else "") for p, _, _, _ in PAGES),
            repo=REPO, config=config)
        title = data["title"].split(" · ")[0] + " · Hero in Motion live demo"
        description = "A homepage hero that shows its words first and fetches no video until you press Play. Press it and watch the meter."
        found[page] = _shell(page, title, description, main, sizes).encode("utf-8")
    # the same hero the usual way: the kit's own styles, a plain autoplaying <video>
    data = configs["index.html"]
    hero = build_hero.build(data, fragment=True)
    safe = build_hero.values(data)
    main = _template("autoplay.html").substitute(style=hero[:hero.index("</style>") + len("</style>")], headline=safe["headline"], summary=safe["summary"],
                                                 poster=safe["poster"], poster_alt=safe["poster_alt"],
                                                 sources="".join('<source src="%s" type="video/%s">\n' % (safe[key], kind)
                                                                 for key, kind in (("video_webm", "webm"), ("video", "mp4")) if key in data))
    sizes = {name: _size(name) for name in _clips(data)}
    found["autoplay.html"] = _shell("autoplay.html", "The autoplay version · Hero in Motion live demo",
                                    "The same hero built the usual way, with autoplay, and a meter of the video it fetches without being asked.",
                                    main, sizes, auto=True).encode("utf-8")
    return found


def videos():
    names = []
    for _, config, _, _ in PAGES:
        names += _clips(_with_webm(load(ROOT / "examples" / config)))
    return names


def stale():
    """Names of the files in docs/ that differ from a fresh build, are missing, or do not belong there."""
    found = outputs()
    wrong = [name for name, content in found.items() if not (DOCS / name).is_file() or (DOCS / name).read_bytes() != content]
    allowed = set(found) | set(videos()) | {CARD}
    wrong += [p.name for p in DOCS.iterdir() if p.name not in allowed]
    return sorted(wrong)


def main(argv):
    if argv not in (["--check"], ["--write"]):
        print(__doc__.strip(), file=sys.stderr)
        return 0 if argv in (["--help"], ["-h"]) else 2
    try:
        if argv == ["--write"]:
            for name, content in outputs().items():
                (DOCS / name).write_bytes(content)
            print("Updated docs/ (" + str(len(outputs())) + " files)")
            return 0
        wrong = stale()
    except ValueError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    if wrong:
        print("docs/ is out of date (" + ", ".join(wrong) + "): run python3 scripts/build_demo.py --write", file=sys.stderr)
        return 1
    print("docs/ matches the examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
