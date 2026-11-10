# Reference: files and troubleshooting

[Back to README](../README.md)

## What the files are

| Path | What it is |
| --- | --- |
| `examples/hero.json` | The example input: language, page title, badge, headline, summary, button label and link, video and poster paths, poster description, and a details paragraph. |
| `examples/poster.svg` | The example's poster: northern lights over a lake with a lit cabin, a source-authored SVG labelled as a fictional example. It is also the first and last frame of the example's video (without its tag), and the film animates its layers. |
| `examples/hero.es.json`, `examples/poster-es.svg` | The same example in Spanish: every content field translated, and the poster's title, description and label. |
| `examples/swim.json`, `examples/radio.json` | Two more made-up brands: the stacked layout with its own colours, and the cover layout with a `focus` point. Their posters, `examples/poster-swim.svg` and `examples/poster-radio.svg`, mark the parts that move in their clips. |
| `templates/hero.html` | The hero block: its styles, semantic HTML and the playback script. This is what `--fragment` writes. |
| `templates/page.html` | The thin page around the block: doctype, title, language and base font. |
| `scripts/build_hero.py` | Validates the JSON, escapes every value and writes the page or the block. |
| `scripts/inspect_media.py` | Runs an existing `ffprobe` on a local file and prints its stream metadata as JSON. With `--check` it also judges the file against a hero's budget. |
| `scripts/measure_page.py` | Optional: serves a built page to this computer only, opens it in a headless Chromium and counts the bytes sent before and after Play (needs Playwright). Exit codes `0`, `2` and `3`. |
| `scripts/build_demo.py`, `templates/demo/` | Builds the live demo in `docs/` from the examples: ordinary pages with the hero block placed in them, a meter of the video fetched, and an autoplay version for comparison. `--check` fails when `docs/` is stale. |
| `docs/` | The live demo, ready for GitHub Pages: the built pages, the posters and the three examples' clips. |
| `scripts/_common.py` | Shared helpers: safe JSON loading, safe writing and the CLI wrapper. |
| `tests/test_tools.py` | Unit tests: escaping, accepted and rejected paths and links, optional fields, colours and focus, the fragment, safe overwrites, every example, the demo in `docs/`, the measuring server, and the inspector's budget and its honesty about what it checks. |
| `tests/test_browser.py` | Optional browser tests of the real page (Play, double-click, pause, end, scroll away, reduced motion, missing video, no JavaScript, captions and sound, the block inside another page). They are skipped unless the Playwright package for Python, a Chromium it can start (its own, or `HERO_CHROMIUM`) and ffmpeg are available. |
| `tests/test_film.py` | Checks that the film's `kit-data` block matches the kit (`python3 scripts/film_data.py --write` refreshes it), that the Spanish example validates, that the example posters carry the six layers the film animates, and that the film page has no `<video>`, starts paused and makes no network requests. |
| `film/explainer.html` | The sample film: a canvas animation drawn from a time value, watchable in a browser. |
| `film/poster-clip.html` | Sets any SVG poster in motion for 10 seconds, ending where it started; the poster marks what moves. `render_film.py --format clip --poster` renders it. |
| `scripts/film_data.py` | Reads the film's words, colours and posters out of the kit and keeps the copy in `film/explainer.html` in sync. |
| `scripts/render_film.py`, `scripts/score_film.py` | Optional: render the film to MP4 or a PNG still, or the example's own video with `--format clip` (needs Playwright with Chromium, and FFmpeg). The second writes the film's soundtrack. |
| `media/hero-in-motion-demo.mp4` | The rendered 16-second sample (the square cut) and its poster frame (`media/hero-in-motion-demo-poster.png`). |
| `assets/hero-anatomy-diagram.svg` | A diagram of the page, source-authored SVG. |
| `assets/social-card.html` | The source of `docs/social-card.png`, the picture a shared link shows: a 1280 x 640 page over the example's poster. |
| `validation.json` | What was actually run on this version and the results. |
| `provenance.json` | Where each file came from. |
| `AGENTS.md`, `SKILL.md`, `llms.txt` | Notes, a skill definition and a docs index for coding agents and LLM tools. |

## Troubleshooting

| You see | What to do |
| --- | --- |
| `error: [Errno 17] File exists: '…'` | Choose a new `--output` name or add `--overwrite`. |
| `error: [Errno 2] No such file or directory: '…'` | Check the path it names. If it's your input JSON, fix the path; if it's your `--output`, create its folder first (`mkdir -p output`). |
| `error: video must be a simple ./local/path.mp4 ...` (or `poster`, `captions`, `video_webm`) | Use a path such as `./clip.mp4` or `/assets/clip.mp4`. URLs, spaces, extra dots, `..`, query strings and other extensions are rejected on purpose. |
| `error: cta_href must be a #section, a path on your site ... or an https:// link` | Use `#pricing`, `/pricing`, `./about.html` or `https://example.com/page`. `http://`, `javascript:` and `//host` links are rejected. |
| `error: cta_href points at #details, so add a details text or change the link` | The details section only exists when the config has `details`. Add it, or link somewhere else. |
| `error: output must be a regular file` or `output is read-only` | `--overwrite` only replaces a normal, writable file. Pick another `--output`. |
| `error: unknown keys: ...` | Remove or fix the misspelled field. The accepted fields are listed in [the guide](quick-start.en.md#3-the-configuration-contract). |
| The poster doesn't appear | Copy the poster next to the HTML file: `cp -f examples/poster.svg output/poster.svg`. |
| "The video is missing or unavailable" | Expected until a real video sits at the `video` path beside the page. For the example, copy `docs/lantern-lake.mp4` beside it (see the README's quick start). |
| `inspect_media.py` exits `1` | `--check` found a file over budget. The report names the failed check and the FFmpeg command that fixes it. |
| `inspect_media.py` exits `2` | The file doesn't exist, `ffprobe` couldn't read a video stream from it, or it is a still image. |
| `inspect_media.py` exits `3` | `ffprobe` isn't installed. Install FFmpeg yourself if you need it; the kit won't download it. |
| `measure_page.py` or `render_film.py` exits `3` | Playwright or Chromium is missing (and, for the renderer, FFmpeg). Set them up as in [make-the-film.md](make-the-film.md), or pass `--chromium PATH`. |
| `error: accent ... is too close to the button's ... label` | Pick a darker `accent` (or a lighter `accent_dark`): the label is white in light mode and near-black in dark mode. |
| A test says `docs/` is out of date | Run `python3 scripts/build_demo.py --write` after changing an example, a template or a clip in `docs/`. |
