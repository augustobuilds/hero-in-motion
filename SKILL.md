---
name: hero-in-motion
description: Build an accessible homepage hero from a JSON config, as a standalone HTML page or as a block to paste into an existing page (escaped copy, a local poster, an opt-in local video with no autoplay, auto-pause, reduced-motion and missing-media fallbacks, optional captions, sound and three layouts), and check a supplied video against a size budget with an existing ffprobe. Use when adding a video you have checked (content, rights, size) to a website hero. The builder includes no product video and does not generate one; the repo's only video is the code-drawn sample in media/, rendered from film/explainer.html by the optional scripts/render_film.py (see guides/make-the-film.md).
---

# Hero in Motion

Use this skill to produce a hero section that is complete without video and plays one only on request.

1. Start from `examples/hero.json`. Every field and its rules are in [guides/quick-start.en.md](guides/quick-start.en.md#3-the-configuration-contract). For a real site, drop the example's `badge` and `details` unless the user wants them, and pick a `layout` (`split`, `stacked` or `cover`). `accent` and `accent_dark` set the button's colour, and `focus` keeps the subject in view when the picture is cropped.
2. Build: `python3 scripts/build_hero.py INPUT --output PATH`. The parent folder must exist. Add `--fragment` when the user has a site already and wants a block to paste in, and `--overwrite` only when they want to replace a file.
3. Tell the user which files must sit beside the page: the `poster` and `video` paths from the config, plus `captions` and `video_webm` if set.
4. If the user has an SVG poster and no video, `python3 scripts/render_film.py --format clip --poster FILE --output PATH` renders a 10-second clip of it (Playwright and FFmpeg; the motion attributes are in [guides/prepare-your-video.md](guides/prepare-your-video.md#no-video-yet-make-one-from-your-poster)). To show what a built page fetches, `python3 scripts/measure_page.py PAGE` (Playwright).
5. If the user has a real video, run `python3 scripts/inspect_media.py FILE --check` and pass on any `fix` it prints ([guides/prepare-your-video.md](guides/prepare-your-video.md)). Exit codes: `0` metadata found and every check passed, `1` a check failed, `2` missing, unreadable, no video stream or a still image, `3` no ffprobe installed.

Rules:

- Media paths must be simple local paths (`./…` or `/…`) with the listed extensions; `cta_href` must be a `#section`, a path on the site or an `https://` link. Don't loosen these without tests.
- Keep autoplay off, `preload="none"`, the auto-pause behaviour and every fallback. Keep the block's styles and ids scoped (`.hm`, `hm-`).
- Metadata and a passed budget are not a quality, accessibility or rights review. Never fetch, generate or invent a video for the user's hero; render the sample film with `scripts/render_film.py` only when the user asks ([guides/make-the-film.md](guides/make-the-film.md)), keeping renders in `output/`.
- For template or label changes, see [guides/variations.md](guides/variations.md). The sample film embeds the labels, template colours, the poster each example config names (`examples/poster.svg`, `examples/poster-es.svg`), example configs and the size of the example's clip in `docs/`, so after changing any of them run `python3 scripts/film_data.py --write`, then `python3 -m unittest discover -s tests -v`.
