# Customizing Hero in Motion

[Back to README](../README.md)

## Words, links and language (no script edits)

- Edit `headline`, `summary`, `cta_label`, `cta_href`, `poster_alt` and the optional `badge` and `details` in your JSON.
- For a Spanish page, set `lang` to `es` and translate every content field, including `poster_alt`. The button and status labels switch automatically. If your poster contains text, make a Spanish version of it too, as `examples/poster-es.svg` does for the Spanish example.

## Layout

Set `layout` in your JSON:

| `layout` | What it looks like | Good for |
| --- | --- | --- |
| `split` | Text on the left, picture on the right (stacked on a phone). The default. | A product shot or an illustration. |
| `stacked` | Text above a wide picture. | A screen recording or a demo. |
| `cover` | The picture fills the hero and the text sits over it on a dark gradient. | A photograph or a scene. |

`ratio` sets the picture's shape for `split` and `stacked`, for example `"ratio": "4:3"`. The picture is cropped to fill its frame, so keep the subject away from the edges. In every layout the Play button sits on the picture, at the bottom right, and the status message appears beside it only when there is something to say. With `captions` set, the button moves to the top so it doesn't cover them.

## Replacing the media

1. Put your poster and video beside the built page and set `poster` and `video` to their paths.
2. Run `python3 scripts/inspect_media.py <file> --check` and fix what it flags. [Prepare your video](prepare-your-video.md) has the commands.
3. Make sure you have the rights to everything shown.
4. If the video has sound that matters, set `"sound": true` and give it `captions`.

## Pasting the hero into your own site

`--fragment` writes the hero without a page around it:

```sh
python3 scripts/build_hero.py my-hero.json --output output/hero-block.html --fragment
```

The file holds one `<style>`, the markup and one `<script>`, in that order. Every style rule is scoped under `.hm`, and every id starts with `hm-` except `details`. The block sets its own colours and inherits your page's font.

- **Plain HTML or a static site generator.** Paste the file where the hero goes, or include it (`{% include %}`, a partial, a shortcode).
- **Astro.** Save it as `src/components/hero-block.html` and render it with `<Fragment set:html={block} />`, where `block` is the file imported with `?raw`. The script runs once when the page loads.
- **WordPress.** Paste it into a Custom HTML block. If your theme strips `<script>`, put the script part in the theme's footer scripts.
- **React or Next.js.** React doesn't run `<script>` tags set through `dangerouslySetInnerHTML`. Keep the style and markup as the component's output, and move the body of the script into a `useEffect` that runs once after mount. The script finds its elements by id, so it works unchanged.

The block expects to appear once on a page, because it finds its elements by id.

## Changes that need script or template edits

- **Colours.** The button's colour needs no edit: set `accent` and `accent_dark` in the config. The other three, the background, the text and the card, are custom properties at the top of `templates/hero.html` (`--hm-bg`, `--hm-ink`, `--hm-card`), with a second set for dark mode. If you change `--hm-card`, change `CARD` in `scripts/build_hero.py` to match, because the builder checks your accent against it. In a fragment you can also override them from your own stylesheet: `.hm { --hm-accent: #c2410c; }`.
- **More languages.** Add an entry to the `UI` dictionary in `scripts/build_hero.py` with every key the other languages have; `validate()` accepts any language in it. The tests check that both built-in languages have the same keys.
- **Other link or media types.** `cta_href` and the media paths are deliberately strict. If you loosen them, keep rejecting `javascript:` and traversal, and add tests for whatever you allow.

The sample film in `film/` shows the kit's own labels, the template colours, the poster each example config names (`examples/poster.svg`, `examples/poster-es.svg`), the example configs and the size of the example's clip in `docs/`. After you change any of these, run `python3 scripts/film_data.py --write` before the tests; otherwise `tests/test_film.py` fails. The MP4 in `media/` then no longer matches until you re-render it ([make-the-film.md](make-the-film.md)). If you don't keep the film, delete `film/` and `tests/test_film.py` instead.

Run `python3 -m unittest discover -s tests -v` after any of these.

## Before shipping

Test the real page with a keyboard only, with reduced motion on, with the video and poster missing, on a narrow phone screen, with the tab hidden, and while scrolling. The builder writes a file; deploying it is up to you.

## Keep it portable

The builder and inspector use only the Python standard library and import nothing from outside this folder; only the optional film renderer and browser tests need Playwright and FFmpeg. Keep it that way, and you can copy the folder anywhere and it will still run.
