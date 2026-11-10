"""Checks that the sample film stays in step with the kit. Standard library only; nothing is rendered."""
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_hero  # noqa: E402
import film_data  # noqa: E402
import score_film  # noqa: E402


class FilmTests(unittest.TestCase):
    def test_spanish_example_is_valid(self):
        data = json.loads((ROOT / "examples/hero.es.json").read_text(encoding="utf-8"))
        build_hero.validate(data)
        self.assertEqual(data["lang"], "es")

    def test_film_matches_the_kit(self):
        data = film_data.kit_data()
        self.assertEqual(data["lang"]["en"]["ui"]["play"], build_hero.UI["en"]["play"])
        self.assertEqual(data["lang"]["es"]["ui"]["play"], build_hero.UI["es"]["play"])
        self.assertEqual(film_data._embedded(), data, "run: python3 scripts/film_data.py --write")

    def test_example_posters_carry_the_layers_the_motion_needs(self):
        # The film animates the six layers. Its hooks (the shoreline, the lit window, the cabin's outline) are
        # optional and skipped when absent, so they are checked only when present, matched as the film matches.
        svg = "{http://www.w3.org/2000/svg}"
        cls = lambda el: (el.get("class") or "").split()

        def num(el, key, what):
            try:
                return float(el.get(key))
            except (TypeError, ValueError):
                self.fail(what + ": " + key + " is missing or not a number")

        for name in ("poster.svg", "poster-es.svg"):
            root = ET.fromstring((ROOT / "examples" / name).read_text(encoding="utf-8"))
            ids = [el.get("id") for el in root.iter() if el.get("id")]
            self.assertEqual(len(ids), len(set(ids)), name + ": duplicate ids")
            layers = [g.get("id") for g in root.iter(svg + "g") if "layer" in cls(g)]
            self.assertEqual(layers, ["sky", "aurora", "lake", "mirror", "front", "label"], name)
            for clip in (c for c in root.iter(svg + "clipPath") if c.get("id") == "water-clip"):
                rect = next(clip.iter(svg + "rect"), None)
                self.assertIsNotNone(rect, name + ": #water-clip has no rect")
                num(rect, "y", name + " #water-clip rect")
            win = next((el for el in root.iter() if "win" in cls(el)), None)
            if win is not None:
                for key in ("x", "y", "width", "height"):
                    num(win, key, name + " .win")
            cabin = next((el for el in root.iter() if "cabin" in cls(el)), None)
            if cabin is not None:
                self.assertEqual(cabin.tag, svg + "path", name + ": class=\"cabin\" must be a path")
                self.assertTrue(cabin.get("d"), name + ": the cabin path has no d")

    def test_film_page_never_plays_by_itself_and_stays_offline(self):
        html = (ROOT / "film/explainer.html").read_text(encoding="utf-8")
        # the film quotes the tag it argues against, as words drawn on the canvas; the page itself has no video
        self.assertNotIn("<video", re.sub(r"<script\b.*?</script>", "", html, flags=re.S))
        self.assertNotRegex(html, r"createElement\(\s*['\"](video|audio|iframe)|\.play\(\)|innerHTML")
        self.assertIn("playing = false", html)
        self.assertNotRegex(html, r"(src|href)=\"https?:|fetch\(|XMLHttpRequest")

    def test_poster_clip_page_stays_offline_and_the_extra_posters_say_how_they_move(self):
        html = (ROOT / "film/poster-clip.html").read_text(encoding="utf-8")
        self.assertNotIn("<video", html)
        self.assertIn("let playing = false", html)
        self.assertNotRegex(html, r"(src|href)=\"https?:|fetch\(|XMLHttpRequest|<link|import\(")
        svg = "{http://www.w3.org/2000/svg}"
        tags = {"data-move": (2, 2), "data-sway": (2, 3), "data-zoom": (1, 1), "data-turn": (1, 2), "data-pulse": (1, 2), "data-camera": (1, 1)}
        for name in ("poster-swim.svg", "poster-radio.svg"):
            root = ET.fromstring((ROOT / "examples" / name).read_text(encoding="utf-8"))
            self.assertRegex(root.get("viewBox") or "", r"^0 0 \d+ \d+$", name)
            ids = [el.get("id") for el in root.iter() if el.get("id")]
            self.assertEqual(len(ids), len(set(ids)), name + ": duplicate ids")
            # a picture only: nothing that runs, loads from elsewhere or depends on the fonts of the machine that draws it
            for el in root.iter():
                self.assertNotIn(el.tag, {svg + t for t in ("script", "foreignObject", "image", "text", "style", "a")}, name)
                for key, value in el.attrib.items():
                    self.assertFalse(key.lower().startswith("on"), name + ": " + key)
                    if key.endswith("href"):
                        self.assertTrue(value.startswith("#"), name + ": " + value)
                    if key in tags:
                        numbers = value.split()
                        self.assertTrue(tags[key][0] <= len(numbers) <= tags[key][1], name + ": " + key + "=" + value)
                        [float(n) for n in numbers]
            moving = [el for el in root.iter() if any(k in el.attrib for k in tags if k != "data-camera")]
            self.assertGreaterEqual(len(moving), 5, name + " should mark the parts that move")

    def test_soundtrack_is_the_same_every_time_and_as_long_as_the_film(self):
        import tempfile
        import wave
        cues = [{"t": 0, "k": "hit"}, {"t": 0.3, "k": "whoosh", "until": 0.6}, {"t": 0.6, "k": "press"},
                {"t": 0.9, "k": "tick"}, {"t": 1.0, "k": "mute", "until": 1.3}, {"t": 1.4, "k": "end"}]
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp, "a.wav"), Path(tmp, "b.wav")
            score_film.score(cues, 2.0, a)
            score_film.score(cues, 2.0, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with wave.open(str(a)) as w:
                self.assertEqual((w.getnchannels(), w.getframerate(), w.getnframes()), (2, 48000, 96000))


if __name__ == "__main__":
    unittest.main()
