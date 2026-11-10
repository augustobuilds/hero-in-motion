"""Build an accessible hero from a local JSON configuration: a standalone page, or with --fragment a block to paste into your own page."""
from html import escape
from pathlib import Path
import re
from string import Template
from _common import cli, obj, require, text

REQUIRED = ("lang", "title", "headline", "summary", "cta_label", "cta_href", "video", "poster", "poster_alt")
OPTIONAL = ("badge", "details", "layout", "ratio", "focus", "accent", "accent_dark", "captions", "video_webm", "sound")
KEYS = REQUIRED + OPTIONAL
LAYOUTS = {"split": "1:1", "stacked": "16:9", "cover": "16:9"}  # layout: the ratio its picture gets by default
CARD = {"accent": "#ffffff", "accent_dark": "#0f1c28"}  # what the button's label is drawn in: the template's --hm-card
POSTERS = ("svg", "jpg", "jpeg", "png", "webp", "avif")
SIMPLE_PATH = r"\.?/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\."
ANCHOR = r"#[A-Za-z][A-Za-z0-9_-]*"
SITE_PATH = r"\.?/(?:[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*/?)*(?:\?[A-Za-z0-9_=&%.+-]*)?(?:" + ANCHOR + r")?"
WEB_LINK = r"https://[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?(?:/[A-Za-z0-9_~.%+=&@:,;!*()/-]*)?(?:\?[A-Za-z0-9_~.%+=&@:,;!*()/-]*)?(?:" + ANCHOR + r")?"

UI = {
  "en": {"play": "Play video", "pause": "Pause video",
         "idle": "The video is not loaded yet.",
         "initial": "The video is not loaded yet. Press Play to load it.",
         "loading": "Loading the video. Press Pause to cancel.",
         "playing": "Playing the video.",
         "paused": "Paused. Press Play to resume when ready.",
         "ended": "The video finished. Press Play to watch it again.",
         "offscreen": "Scroll the video panel into view, then press Play.",
         "failed": "The video is missing or unavailable. The page remains usable.",
         "reduced": "Reduced motion is preferred, so nothing moves until you choose Play.",
         "mute": "Mute sound", "unmute": "Turn sound on", "captions": "Captions",
         "note": "Playback begins only when requested and pauses when hidden or offscreen. It never resumes automatically.",
         "notes": "Details"},
  "es": {"play": "Reproducir video", "pause": "Pausar video",
         "idle": "El video aún no se ha cargado.",
         "initial": "El video aún no se ha cargado. Pulsa Reproducir para cargarlo.",
         "loading": "Cargando el video. Pulsa Pausar para cancelar.",
         "playing": "Reproduciendo el video.",
         "paused": "En pausa. Pulsa Reproducir cuando quieras continuar.",
         "ended": "El video terminó. Pulsa Reproducir para verlo de nuevo.",
         "offscreen": "Desplázate hasta que se vea el panel del video y luego pulsa Reproducir.",
         "failed": "Falta el video o no está disponible. La página sigue siendo útil.",
         "reduced": "Tu sistema pide reducir el movimiento: nada se moverá hasta que pulses Reproducir.",
         "mute": "Silenciar", "unmute": "Activar el sonido", "captions": "Subtítulos",
         "note": "La reproducción empieza solo cuando la solicitas y se pausa si el panel queda oculto o fuera de pantalla. Nunca se reanuda automáticamente.",
         "notes": "Detalles"}}

def local_path(value, extensions, name):
    text(value, name, 200)
    extensions = (extensions,) if isinstance(extensions, str) else extensions
    require(re.fullmatch(SIMPLE_PATH + "(?:" + "|".join(extensions) + ")", value) is not None,
            name + " must be a simple ./local/path." + extensions[0]
            + (" (or ." + ", .".join(extensions[1:]) + ")" if extensions[1:] else "")
            + " using letters, digits, - and _ (no URLs, spaces, queries or traversal)")
    return value

def link(value, has_details):
    href = text(value, "cta_href", 200)
    ok = any(re.fullmatch(pattern, href) for pattern in (ANCHOR, SITE_PATH, WEB_LINK)) and ".." not in href and not href.startswith("//")
    require(ok, "cta_href must be a #section, a path on your site such as /pricing or ./about.html, or an https:// link")
    require(href != "#details" or has_details, "cta_href points at #details, so add a details text or change the link")
    return href

def contrast(a, b):
    """WCAG contrast ratio of two #rrggbb (or #rgb) colours."""
    def luminance(colour):
        h = colour[1:]
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)

def validate(data):
    obj(data, "hero")
    extra = sorted(set(data) - set(KEYS))
    require(not extra, "unknown keys: " + ", ".join(map(repr, extra)))
    lang = data.get("lang")
    require(isinstance(lang, str) and lang in UI, "lang must be one of: " + ", ".join(sorted(UI)))
    for key in ("title", "headline", "summary", "cta_label", "poster_alt"):
        text(data.get(key), key, 1000)
    for key, limit in (("badge", 200), ("details", 1000)):
        if key in data:
            text(data[key], key, limit)
    local_path(data.get("video"), "mp4", "video")
    local_path(data.get("poster"), POSTERS, "poster")
    if "video_webm" in data:
        local_path(data["video_webm"], "webm", "video_webm")
    if "captions" in data:
        local_path(data["captions"], "vtt", "captions")
    link(data.get("cta_href"), "details" in data)
    require(data.get("layout", "split") in LAYOUTS, "layout must be one of: " + ", ".join(LAYOUTS))
    ratio = data.get("ratio", "1:1")
    require(isinstance(ratio, str) and re.fullmatch(r"[1-9][0-9]?:[1-9][0-9]?", ratio) is not None,
            "ratio must look like 16:9, 4:3 or 1:1")
    require(isinstance(data.get("sound", False), bool), "sound must be true or false")
    if "focus" in data:
        require(isinstance(data["focus"], str) and re.fullmatch(r"(?:100|[0-9]{1,2})% (?:100|[0-9]{1,2})%", data["focus"]) is not None,
                "focus must be two percentages such as 70% 40% (across, then down): the part of the picture to keep in view when it is cropped")
    for key, where in (("accent", "light"), ("accent_dark", "dark")):
        if key in data:
            require(isinstance(data[key], str) and re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", data[key]) is not None,
                    key + " must be a colour such as #0b6a52")
            require(contrast(data[key], CARD[key]) >= 4.5,
                    "%s %s is too close to the button's %s label (%s) to read: it needs a contrast of 4.5 to 1, and has %.1f"
                    % (key, data[key], where, CARD[key], contrast(data[key], CARD[key])))
    return data

def values(data):
    """Everything the templates may use: every string escaped, plus the optional blocks as ready HTML."""
    ui = UI[data["lang"]]
    safe = {key: escape(str(value), quote=True) for key, value in data.items()}
    safe.update(("ui_" + key, escape(value, quote=True)) for key, value in ui.items())
    layout = data.get("layout", "split")
    safe["layout"] = layout
    safe["ratio"] = data.get("ratio", LAYOUTS[layout]).replace(":", " / ")
    safe["focus_style"] = ";--hm-focus:" + data["focus"] if "focus" in data else ""
    safe["accent_css"] = ((".hm { --hm-accent:%s; }\n" % data["accent"] if "accent" in data else "")
                          + ("@media (prefers-color-scheme:dark) { .hm { --hm-accent:%s; } }\n" % data["accent_dark"] if "accent_dark" in data else ""))
    safe["badge_html"] = '<p class="hm-badge">' + safe["badge"] + "</p>\n" if "badge" in data else ""
    safe["details_html"] = ('<section class="hm-details" id="details" aria-labelledby="hm-notes"><h2 id="hm-notes">'
                            + safe["ui_notes"] + "</h2><p>" + safe["details"] + "</p></section>\n") if "details" in data else ""
    safe["muted"] = "" if data.get("sound") else " muted"
    safe["sound_html"] = ('<button id="hm-sound" type="button" aria-controls="hm-video" hidden>' + safe["ui_mute"] + "</button>\n"
                          if data.get("sound") else "")
    safe["captions_class"] = " hm-captions" if "captions" in data else ""
    safe["video_data"] = "".join(' data-%s="%s"' % (name, safe[key])
                                 for name, key in (("webm", "video_webm"), ("captions", "captions")) if key in data)
    return safe

def build(data, fragment=False):
    folder = Path(__file__).resolve().parent.parent / "templates"
    found = values(data)
    try:
        hero = Template((folder / "hero.html").read_text(encoding="utf-8")).substitute(found)
        if fragment:
            return hero
        return Template((folder / "page.html").read_text(encoding="utf-8")).substitute(found, hero=hero)
    except KeyError as exc:
        raise ValueError("template placeholder $" + exc.args[0] + " has no value") from None

if __name__ == "__main__":
    raise SystemExit(cli(validate, build, __doc__,
                         flags={"fragment": "write only the hero block (its styles, markup and script), to paste into an existing page"}))
