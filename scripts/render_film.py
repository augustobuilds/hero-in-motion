"""Render film/explainer.html to an MP4, frame by frame.

Optional tool. It needs two things the page builder does not: the Playwright package for Python with
a Chromium browser, and ffmpeg. Install them yourself if you want to render:

    python3 -m venv .venv && . .venv/bin/activate
    python3 -m pip install playwright && python3 -m playwright install chromium
    # ffmpeg: https://ffmpeg.org/download.html (or your package manager)

    python3 scripts/render_film.py --format square --lang en --output output/hero-in-motion-demo.mp4
    python3 scripts/render_film.py --format tall --output output/hero-in-motion-9x16.mp4
    python3 scripts/render_film.py --format wide --still 12.5 --output output/still.png
    python3 scripts/render_film.py --format clip --output output/lantern-lake.mp4
    python3 scripts/render_film.py --format clip --poster examples/poster-swim.svg --output output/swim.mp4

--format clip renders the example's own video: the poster's northern lights brought to life, 10 seconds at
1080x1080, starting and ending on the poster's picture. Put it beside the page built from
examples/hero.json and that page plays it.

--format clip --poster YOUR.svg makes the same kind of clip from any SVG poster (film/poster-clip.html): the
picture moves the way its data-move, data-sway, data-zoom, data-turn and data-pulse attributes say, under a
slow push-in, and ends where it started. It is 1080 pixels high and as wide as the poster's shape asks.

Every frame is drawn by the page for an exact time (frame / 30 s), screenshotted and piped to ffmpeg, so
the same inputs always give the same picture. The film is one 16-second cut in three shapes: square
(1080x1080), tall (1080x1920, for phones) and wide (1920x1080). Each carries a soundtrack made with code
(scripts/score_film.py, from the film's own cues; --silent leaves it out); a clip is silent. Exit codes: 0 done, 2 bad input or
failed render, 3 Playwright or ffmpeg missing, or Chromium won't start. To use a Chrome or Chromium you
already have, pass --chromium PATH or set HERO_CHROMIUM.
"""
import argparse
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import film_data  # noqa: E402
import score_film  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Render the explainer film to MP4 (or one still to PNG).")
    parser.add_argument("--format", choices=("square", "tall", "wide", "clip"), default="square",
                        help="square = 1080x1080 (default), tall = 1080x1920, wide = 1920x1080, clip = the example's own 10 s video, 1080x1080")
    parser.add_argument("--lang", choices=("en", "es"), default="en")
    parser.add_argument("--output", required=True, help="output .mp4 (or .png with --still); parent folder must exist")
    parser.add_argument("--poster", help="with --format clip: make the clip from this SVG poster instead of the example's (see film/poster-clip.html)")
    parser.add_argument("--still", type=float, help="render only the frame at this time in seconds, as PNG")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing output")
    parser.add_argument("--silent", action="store_true", help="leave out the film's soundtrack (a clip never has one)")
    parser.add_argument("--crf", type=int, default=18, help="x264 quality, lower is better (default 18)")
    parser.add_argument("--chromium", default=os.environ.get("HERO_CHROMIUM"), help="path to a Chromium/Chrome binary, if Playwright's own is not installed (default: $HERO_CHROMIUM)")
    args = parser.parse_args()
    if args.still is not None and not math.isfinite(args.still):
        parser.error("--still must be a finite number of seconds")

    poster = None
    if args.poster is not None:
        if args.format != "clip":
            parser.error("--poster goes with --format clip")
        try:
            poster = Path(args.poster).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print("error: could not read the poster " + args.poster + ": " + str(exc), file=sys.stderr)
            return 2

    out = Path(args.output)
    if out.exists() and not args.overwrite:
        print("error: " + str(out) + " exists; choose a new --output or add --overwrite", file=sys.stderr)
        return 2
    if not out.parent.is_dir():
        print("error: folder " + str(out.parent) + " does not exist", file=sys.stderr)
        return 2
    if film_data.main(["--check"]) != 0:
        return 2
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        print("error: Playwright is not installed (python3 -m pip install playwright && python3 -m playwright install chromium)", file=sys.stderr)
        return 3
    ffmpeg = shutil.which("ffmpeg")
    if args.still is None and not ffmpeg:
        print("error: ffmpeg is not installed", file=sys.stderr)
        return 3

    url = (ROOT / "film" / "explainer.html").as_uri() + "?render=1&format=" + args.format + "&lang=" + args.lang
    if poster is not None:
        url = (ROOT / "film" / "poster-clip.html").as_uri() + "?render=1"
    tmp = tempfile.TemporaryDirectory()
    with tmp, sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(executable_path=args.chromium) if args.chromium else pw.chromium.launch()
        except PlaywrightError as exc:
            print("error: could not start Chromium (run python3 -m playwright install chromium, pass --chromium PATH, or fix or unset HERO_CHROMIUM): "
                  + str(exc).splitlines()[0], file=sys.stderr)
            return 3
        enc = None
        try:
            size = {"width": 1920 if args.format == "wide" or poster is not None else 1080, "height": 1920 if args.format == "tall" else 1080}
            page = browser.new_page(viewport=size, device_scale_factor=1, offline=poster is not None)
            page.goto(url)
            page.evaluate("film.ready")
            if poster is not None:
                try:
                    page.evaluate("svg => film.load(svg)", poster)
                except PlaywrightError as exc:
                    print("error: could not use the poster " + args.poster + ": " + str(exc).splitlines()[0].replace("Error: ", ""), file=sys.stderr)
                    return 2
            info = page.evaluate("({w: film.width, h: film.height, fps: film.fps, frames: film.frames, layered: film.layered, cues: film.cues, dur: film.duration})")
            if poster is not None and not info["layered"]:
                print("warning: the poster marks no moving parts (data-move, data-sway, data-zoom, data-turn, data-pulse), "
                      "so the clip is only a slow push-in", file=sys.stderr)
            elif args.format == "clip" and not info["layered"]:
                print("warning: the poster has no layers (groups with class=\"layer\" and the ids sky, aurora, lake, mirror, "
                      "front, label), so the clip shows it still, with its own text", file=sys.stderr)
            canvas = page.locator("#film")
            if args.still is not None:
                page.evaluate("t => film.frame(Math.round(t * film.fps))", args.still)
                out.write_bytes(canvas.screenshot(type="png"))
                print("Wrote " + str(out))
                return 0
            # the film's soundtrack, written from the film's own cues (scripts/score_film.py)
            sound = []
            if info["cues"] and not args.silent:
                wav = Path(tmp.name) / "score.wav"
                score_film.score(info["cues"], info["dur"], wav)
                sound = ["-i", str(wav)]
            cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y" if args.overwrite else "-n",
                   "-f", "image2pipe", "-framerate", str(info["fps"]), "-c:v", "png", "-i", "-", *sound,
                   *(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"] if sound else ["-an"]), "-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-crf", str(args.crf),
                   "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                   "-movflags", "+faststart", str(out)]
            enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            for i in range(info["frames"]):
                page.evaluate("i => film.frame(i)", i)
                enc.stdin.write(canvas.screenshot(type="png"))
                if i % (info["fps"] * 5) == 0:
                    print("frame " + str(i) + " / " + str(info["frames"]), file=sys.stderr)
            enc.stdin.close()
            if enc.wait() != 0:
                print("error: ffmpeg failed", file=sys.stderr)
                return 2
        except (OSError, PlaywrightError) as exc:
            if enc is not None and enc.poll() is None:
                enc.kill()
                enc.wait()
            print("error: render failed: " + str(exc).splitlines()[0], file=sys.stderr)
            return 2
        finally:
            browser.close()
    print("Wrote " + str(out) + " (" + str(info["frames"]) + " frames, " + str(info["w"]) + "x" + str(info["h"]) + ", "
          + str(info["fps"]) + " fps, " + ("with sound" if sound else "silent") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
