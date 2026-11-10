# Prompts: recreate and remix Hero in Motion

Copy one of these into a coding agent opened in this repository. Replace the `<...>` parts. Each prompt asks the agent to build or test what it changes and report what happened.

## 1. Build it and explain the behaviour

```text
Read AGENTS.md. Build output/hero.html from the example, copy the poster beside
it and run the unit tests. Then walk me through templates/hero.html: when the
video loads, when it pauses, what happens with reduced motion, and each fallback.
Report the actual test count.
```

## 2. Make a hero for my site

```text
Read AGENTS.md and examples/hero.json. Create examples/my-hero.json for <site:
headline, summary, CTA label, CTA target page>. Use ./my-poster.svg and
./my-video.mp4. Build output/my-hero.html, run python3 -m unittest discover -s
tests -v, and list exactly which files I must put beside it. Don't fetch,
generate or invent any media.
```

## 3. Spanish version

```text
Read AGENTS.md and examples/hero.es.json (a finished Spanish example). Create
examples/my-hero.es.json from examples/my-hero.json (or from examples/hero.json
if you have not made one) with lang "es" and every content field, including
poster_alt, translated to Spanish. If my poster has text in it, make a Spanish
copy (examples/poster-es.svg is an example) and point "poster" at it. Leave
examples/hero.es.json unchanged. Build output/my-hero-es.html and confirm the
button and status labels are Spanish in the generated HTML.
```

## 4. Remix: add a third language

```text
Read AGENTS.md and the UI dictionary in scripts/build_hero.py. Add <language,
with its code> with every key the other languages have, translated naturally.
Create examples/my-hero.<code>.json with that lang and translated content
fields. Keep every existing behaviour and rule. Run python3 scripts/film_data.py
--write, then the tests, and show me the built page's button and status labels.
```

## 5. Paste the hero into my site

```text
Read AGENTS.md and guides/variations.md. Build my hero with --fragment from
<my config>, then add it to <my page or component: path and framework>. Keep the
block's styles, ids and script as written. Tell me which media files to place
where, and how you checked that Play, Pause and the missing-video message work.
```

## 6. Recreate the kit from scratch (for learning)

```text
Without copying this repository's code, write a minimal standard-library Python
script that fills an HTML template from JSON with every value HTML-escaped, and a
small page script that only loads a video on a button press and pauses it on
visibilitychange. Add tests proving that a headline containing </script> can't
add a second <script> element and that javascript: URLs are rejected. Run your
tests and report the result. Then compare with scripts/build_hero.py and
templates/hero.html.
```

---

These prompts don't ask the agent to publish, upload, sign up for anything or send data anywhere. If you want to go further, the README's "Where to go next" section lists the author's affiliated, optional products.
