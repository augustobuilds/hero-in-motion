# Prepare your video

[Back to README](../README.md)

The hero only downloads the video when someone presses Play, but a visitor who presses Play is waiting. A short, light file that can start before it has fully arrived makes the press feel instant. This page takes a clip you already have and gets it ready. You need FFmpeg, which the kit never installs for you.

## 1. Check what you have

```sh
python3 scripts/inspect_media.py my-clip.mp4 --check
```

The report lists five lines under `budget`:

| Check | Passes when | Why |
| --- | --- | --- |
| `length` | 20 seconds or less | A hero clip is a glance. Long clips are rarely watched to the end. |
| `weight` | 300 kB per second or less | That is about 3 MB for a 10-second clip, which starts quickly on a phone connection. |
| `height` | 1080 px or less | A hero panel is rarely shown taller than this. |
| `quick start` | The MP4's index comes before its picture data | Otherwise the browser must fetch the whole file before the first frame. |
| `sound` | Always a note, never a failure | Tells you whether the file has a sound track, and what to set if it matters. |

The command exits `0` when every check passes and `1` when one fails. Each failed line carries a `fix` with the FFmpeg command for it. Change a limit with `--max-seconds`, `--max-kb-per-second` or `--max-height` if your site needs a different budget.

A pass means the file fits those numbers. It doesn't mean the video looks good, and it says nothing about what the video shows or whether you may use it.

## 2. Make the web copy

One command covers the usual case: no sound, 720 px tall, H.264, index at the front.

```sh
ffmpeg -i my-clip.mov -an -vf scale=-2:720 -c:v libx264 -crf 26 -preset slow -pix_fmt yuv420p -movflags +faststart hero.mp4
```

- Raise `-crf` (towards 30) for a smaller file, lower it (towards 22) for a cleaner picture.
- Drop `-an` to keep the sound, and then set `"sound": true` in the config. If the sound carries meaning, write captions too (step 4).
- Add `-t 10` to keep only the first 10 seconds.

Optionally make a WebM copy as well. Browsers that can play it will fetch it in place of the MP4, and it is often smaller:

```sh
ffmpeg -i my-clip.mov -an -vf scale=-2:720 -c:v libvpx-vp9 -crf 34 -b:v 0 hero.webm
```

## 3. Take the poster from the video

The switch from poster to video is seamless when the poster is the video's first frame.

```sh
ffmpeg -i hero.mp4 -frames:v 1 -q:v 3 hero.jpg
```

Start and end the clip on the same picture if you can, so the return to the poster at the end is seamless too.

## 4. Captions, if the video has speech

Write a WebVTT file. It is plain text:

```text
WEBVTT

00:00.000 --> 00:03.500
We roast every Monday morning.

00:03.500 --> 00:07.000
Your order leaves the same afternoon.
```

## 5. Point the config at the files

```json
{
  "video": "./hero.mp4",
  "video_webm": "./hero.webm",
  "poster": "./hero.jpg",
  "captions": "./hero.vtt",
  "sound": true
}
```

Leave out the lines you don't use. Put the files beside the built page, run the check from step 1 on `hero.mp4`, and open the page: keyboard only, with reduced motion on, on a phone, and with the video file renamed so you see the missing-video message.

## No video yet? Make one from your poster

If your poster is an SVG, the kit can set it in motion for 10 seconds:

```sh
python3 scripts/render_film.py --format clip --poster my-poster.svg --output output/my-clip.mp4
```

The clip starts and ends on the poster itself, so the visitor can't see the switch from picture to video or back. It is 30 frames a second and 1080 pixels high, as wide as the poster's `viewBox` asks (up to 1920). Rendering needs Playwright and FFmpeg, set up as in [Make the hero clip with code](make-the-film.md#render-it).

The poster says how it moves. Add these attributes to the parts that should move, usually to a `<g>`:

| Attribute | What the part does |
| --- | --- |
| `data-move="dx dy"` | Drifts that far, in the poster's own units, and comes back. |
| `data-sway="dx dy times"` | Rocks to and fro that far, `times` times (2 if you leave it out). |
| `data-zoom="0.05"` | Grows by that share of its size and comes back. |
| `data-turn="degrees times"` | Rocks around its own centre. |
| `data-pulse="0.5 times"` | Dims by that share and comes back: a lamp, a star, a ripple. |

On the `<svg>` itself, `data-camera="0.04"` sets the slow push-in on the whole picture (`0` turns it off). A poster with no attributes still gets the push-in. Every motion is back at rest by the last frame, which is why a part that travels one way, such as a car crossing the picture, doesn't suit this: choose things that bob, breathe, blink or drift.

`examples/poster-swim.svg` and `examples/poster-radio.svg` are worked examples: water light that drifts, a float that bobs, stars that twinkle, a lamp that blinks every two seconds. Open `film/poster-clip.html` in a browser to try your poster before you render: choose the file and drag the slider.

Scripts, event handlers, embedded pages and outside links in the SVG are removed before it is drawn, and the render runs with the network off. Text in the poster is drawn with the fonts of the computer that renders it, so outline your lettering or keep words out of the picture. Run `--check` from step 1 on the result: busy pictures at full width can come out heavy, and the check prints the command that fixes it.
