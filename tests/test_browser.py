"""Optional browser checks of the generated page.

Skipped unless the Playwright package for Python, a Chromium it can start and ffmpeg are available. Set
HERO_CHROMIUM to a Chromium or Chrome binary if Playwright's own browser isn't installed.
"""
import functools
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import build_hero
from _common import load

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright=None

EN=build_hero.UI["en"]

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass

@unittest.skipUnless(sync_playwright and shutil.which("ffmpeg"),"needs the playwright package and ffmpeg")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        site=Path(cls.temp.name)
        data=load(ROOT/"examples/hero.json")
        (site/"hero.html").write_text(build_hero.build(build_hero.validate(data)),encoding="utf-8")
        shutil.copy(ROOT/"examples/poster.svg",site/"poster.svg")
        # a WebM copy for the video_webm field, when this ffmpeg can encode one (VP9, else VP8); otherwise that part is left out
        cls.webm=any(subprocess.run(["ffmpeg","-loglevel","error","-y","-f","lavfi","-i","testsrc=size=320x320:rate=30:duration=2","-c:v",codec,"-b:v","200k",
                                     str(site/"clip.webm")],timeout=120).returncode==0 for codec in ("libvpx-vp9","libvpx"))
        full=build_hero.validate(dict(data,layout="cover",captions="./clip.vtt",sound=True,**({"video_webm":"./clip.webm"} if cls.webm else {})))
        (site/"full.html").write_text(build_hero.build(full),encoding="utf-8")
        (site/"clip.vtt").write_text("WEBVTT\n\n00:00.000 --> 00:02.000\nNorthern lights over the lake.\n",encoding="utf-8")
        (site/"host.html").write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Host</title><style>p{color:rgb(1,2,3)}button{border-radius:0}</style></head>'
                                      '<body><p id="status">Host status</p>'+build_hero.build(data,fragment=True)+'<button id="toggle" hidden>Host</button></body></html>',encoding="utf-8")
        subprocess.run(["ffmpeg","-loglevel","error","-y","-f","lavfi","-i","testsrc=size=320x320:rate=30:duration=2",
                        "-pix_fmt","yuv420p","-movflags","+faststart",str(site/"lantern-lake.mp4")],check=True,timeout=120)
        cls.server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(Quiet,directory=str(site)))
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base="http://127.0.0.1:%d/"%cls.server.server_address[1]
        cls.url=cls.base+"hero.html"
        cls.pw=sync_playwright().start()
        try:
            cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get("HERO_CHROMIUM") or None)
        except Exception as exc:
            cls.pw.stop()
            cls.server.shutdown()
            cls.server.server_close()
            cls.temp.cleanup()
            raise unittest.SkipTest("Chromium could not start (python3 -m playwright install chromium, or set HERO_CHROMIUM): "+str(exc).splitlines()[0])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def open(self,video=True,path="hero.html",**options):
        context=self.browser.new_context(**dict({"viewport":{"width":1280,"height":800}},**options))
        self.addCleanup(context.close)
        page=context.new_page()
        requests=[]
        page.on("request",lambda r:requests.append(r.url.rsplit("/",1)[1]) if r.url.endswith((".mp4",".webm",".vtt")) else None)
        self.errors=[]
        page.on("pageerror",lambda e:self.errors.append(str(e)))
        if not video:
            page.route("**/*.mp4",lambda route:route.fulfill(status=404,body=""))
        page.goto(self.base+path)
        page.wait_for_function("document.querySelector('#hm-toggle').hidden === false")
        return page,requests

    def state(self,page):
        return page.evaluate("({label:document.querySelector('#hm-toggle').textContent,status:document.querySelector('#hm-status').textContent,"
                             "paused:document.querySelector('#hm-video').paused,t:document.querySelector('#hm-video').currentTime})")

    def wait_status(self,page,text):
        page.wait_for_function("t => document.querySelector('#hm-status').textContent === t",arg=text,timeout=10000)

    def test_square_film_draws_every_shot_and_its_cues_fit(self):
        page=self.browser.new_page(viewport={"width":1080,"height":1080})
        self.addCleanup(page.close)
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto((ROOT/"film/explainer.html").as_uri()+"?render=1&format=square")
        page.evaluate("film.ready")
        info=page.evaluate("({dur:film.duration,cues:film.cues,shots:KSHOTS.map(s=>s[0])})")
        for t in info["shots"]+[info["dur"]]:
            page.evaluate("t=>film.frame(Math.round(t*film.fps))",min(t+0.2,info["dur"]))
        self.assertEqual(errors,[])
        times=[c["t"] for c in info["cues"]]
        self.assertEqual(times,sorted(times))
        self.assertTrue(all(0<=c["t"]<info["dur"] and c["k"] in {"hit","press","whoosh","tick","mute","end"} for c in info["cues"]))
        self.assertTrue(all(c["until"]>c["t"] for c in info["cues"] if c["k"] in ("whoosh","mute")))

    def test_nothing_loads_before_play_and_a_double_click_keeps_playing(self):
        page,requests=self.open()
        page.wait_for_timeout(300)
        self.assertEqual(requests,[])
        self.assertEqual(self.state(page)["status"],EN["initial"])
        page.click("#hm-toggle");page.wait_for_timeout(150);page.click("#hm-toggle")
        self.wait_status(page,EN["playing"])
        page.wait_for_timeout(400)
        state=self.state(page)
        self.assertFalse(state["paused"])
        self.assertEqual(state["label"],EN["pause"])

    def test_status_shows_on_the_picture_only_when_it_has_news(self):
        page,_=self.open()
        quiet=lambda:page.evaluate("document.querySelector('#hm-status').classList.contains('hm-quiet')")
        box=lambda sel:page.evaluate("s=>{const b=document.querySelector(s).getBoundingClientRect();return [b.left,b.top,b.right,b.bottom]}",sel)
        self.assertTrue(quiet())
        self.assertLessEqual(page.evaluate("document.querySelector('#hm-status').getBoundingClientRect().width"),1)
        self.assertEqual(page.get_attribute("#hm-toggle","data-state"),"play")
        panel,button=box(".hm-panel"),box("#hm-toggle")
        self.assertTrue(panel[0]<=button[0] and panel[1]<=button[1] and button[2]<=panel[2] and button[3]<=panel[3],"the Play button sits on the picture")
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        self.assertTrue(quiet())
        self.assertEqual(page.get_attribute("#hm-toggle","data-state"),"pause")
        page.wait_for_timeout(450);page.click("#hm-toggle")
        self.assertEqual(self.state(page)["status"],EN["paused"])
        page.wait_for_function("!document.querySelector('#hm-status').classList.contains('hm-quiet')")
        self.assertTrue(page.is_visible("#hm-status"))
        status=box("#hm-status")
        self.assertTrue(panel[0]<=status[0] and status[2]<=panel[2] and status[3]<=panel[3])
        self.assertEqual(self.errors,[])

    def test_captions_webm_and_sound_load_only_on_play(self):
        page,requests=self.open(path="full.html")
        page.wait_for_timeout(300)
        self.assertEqual(requests,[])
        self.assertEqual(page.evaluate("document.querySelectorAll('track').length"),0)
        self.assertFalse(page.evaluate("document.querySelector('#hm-video').muted"))
        self.assertTrue(page.is_visible("#hm-sound"))
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        page.wait_for_function("document.querySelector('#hm-video').textTracks[0].cues && document.querySelector('#hm-video').textTracks[0].cues.length === 1")
        self.assertEqual(sorted(set(requests)),["clip.vtt","clip.webm" if self.webm else "lantern-lake.mp4"])
        track=page.evaluate("(t=>({kind:t.kind,lang:t.srclang,label:t.label,mode:t.track.mode}))(document.querySelector('track'))")
        self.assertEqual(track,{"kind":"captions","lang":"en","label":EN["captions"],"mode":"showing"})
        page.click("#hm-sound")
        self.assertTrue(page.evaluate("document.querySelector('#hm-video').muted"))
        self.assertEqual(page.text_content("#hm-sound"),EN["unmute"])
        page.click("#hm-sound")
        self.assertEqual(page.text_content("#hm-sound"),EN["mute"])
        page.wait_for_timeout(450);page.click("#hm-toggle");page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        self.assertEqual(page.evaluate("document.querySelectorAll('track').length"),1)
        self.assertEqual(self.errors,[])

    def test_fragment_works_inside_another_page_and_leaves_it_alone(self):
        page,requests=self.open(path="host.html")
        self.assertEqual(page.text_content("#status"),"Host status")
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#status')).color"),"rgb(1, 2, 3)")
        self.assertFalse(page.is_visible("#toggle"))
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        self.assertEqual(requests,["lantern-lake.mp4"])
        self.assertEqual(page.text_content("#status"),"Host status")
        self.assertEqual(self.errors,[])

    def test_pause_end_and_replay(self):
        page,_=self.open()
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        page.wait_for_timeout(500);page.click("#hm-toggle")
        self.assertEqual(self.state(page)["status"],EN["paused"])
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        self.wait_status(page,EN["ended"])
        self.assertEqual(self.state(page)["label"],EN["play"])
        self.assertTrue(page.is_visible("#hm-poster"))
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])

    def test_outside_pause_syncs_the_button(self):
        page,_=self.open()
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        page.evaluate("document.querySelector('#hm-video').pause()")
        self.wait_status(page,EN["paused"])
        self.assertEqual(self.state(page)["label"],EN["play"])

    def test_missing_video_keeps_poster_and_message(self):
        page,_=self.open(video=False)
        page.click("#hm-toggle");self.wait_status(page,EN["failed"])
        self.assertTrue(page.is_visible("#hm-poster"))
        self.assertFalse(page.is_visible("#hm-video"))
        page.evaluate("window.scrollTo(0,document.body.scrollHeight)");page.wait_for_timeout(300)
        page.evaluate("window.scrollTo(0,0)");page.wait_for_timeout(300)
        self.assertEqual(self.state(page)["status"],EN["failed"])

    def test_scrolling_the_panel_away_pauses_and_never_resumes(self):
        page,_=self.open(viewport={"width":1280,"height":400})
        page.add_style_tag(content="body{min-height:3000px}")  # room to scroll the picture right off the screen
        page.evaluate("window.scrollTo(0,0)")
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        top=page.evaluate("document.querySelector('.hm-panel').getBoundingClientRect().bottom+window.scrollY")
        page.evaluate("y => window.scrollTo(0,y)",top-60)
        self.wait_status(page,EN["paused"])
        page.evaluate("window.scrollTo(0,0)");page.wait_for_timeout(500)
        self.assertTrue(self.state(page)["paused"])

    def test_idle_scroll_and_hidden_tab_leave_the_status_alone(self):
        page,_=self.open(viewport={"width":1280,"height":400})
        page.evaluate("window.scrollTo(0,document.body.scrollHeight)");page.wait_for_timeout(300)
        page.evaluate("window.scrollTo(0,0)");page.wait_for_timeout(300)
        page.evaluate("Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
        self.assertEqual(self.state(page)["status"],EN["initial"])

    def test_reduced_motion_starts_still_and_restores_the_right_message(self):
        page,_=self.open(reduced_motion="reduce")
        self.assertEqual(self.state(page)["status"],EN["reduced"])
        page.click("#hm-toggle");self.wait_status(page,EN["playing"])
        page.wait_for_timeout(500);page.click("#hm-toggle")
        page.emulate_media(reduced_motion="no-preference");page.wait_for_timeout(100)
        page.emulate_media(reduced_motion="reduce");page.wait_for_timeout(100)
        self.assertEqual(self.state(page)["status"],EN["reduced"])
        page.emulate_media(reduced_motion="no-preference");page.wait_for_timeout(100)
        self.assertEqual(self.state(page)["status"],EN["paused"])

    def test_without_javascript_the_page_reads_cleanly(self):
        page_context=self.browser.new_context(java_script_enabled=False)
        self.addCleanup(page_context.close)
        page=page_context.new_page();page.goto(self.url)
        self.assertFalse(page.is_visible("#hm-toggle"))
        self.assertEqual(page.text_content("#hm-status"),EN["idle"])

    def test_measure_page_counts_no_video_before_play_and_the_clip_after(self):
        import json
        result=subprocess.run([sys.executable,str(ROOT/"scripts/measure_page.py"),str(Path(self.temp.name)/"hero.html"),"--seconds","1","--json"],
                              capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        found=json.loads(result.stdout)
        self.assertEqual(sorted(found["before"]["files"]),["hero.html","poster.svg"])
        self.assertEqual(found["before"]["video_bytes"],0)
        self.assertTrue(found["pressed_play"])
        self.assertEqual(found["after"]["video_bytes"],(Path(self.temp.name)/"lantern-lake.mp4").stat().st_size)

    def test_poster_clip_moves_what_the_poster_marks_and_ends_on_the_poster(self):
        context=self.browser.new_context(viewport={"width":1920,"height":1080},offline=True)
        self.addCleanup(context.close)
        page=context.new_page();page.goto((ROOT/"film/poster-clip.html").as_uri()+"?render=1")
        svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" onload="window.ran=1"><script>window.ran=2</script>'
             '<a href="https://example.com/"><rect id="a" data-move="200 0" x="100" y="100" width="100" height="100"/></a>'
             '<rect id="b" data-turn="20 1" data-pulse="0.6 3" opacity="0.5" transform="translate(5 5)" x="900" y="300" width="200" height="200"/></svg>')
        self.assertEqual(page.evaluate("svg => film.load(svg)",svg),{"w":1920,"h":1080,"moving":2})
        look="i => { film.frame(i); const a=document.querySelector('#a'),b=document.querySelector('#b'); return [a.getAttribute('transform'),b.getAttribute('transform'),b.getAttribute('opacity'),document.querySelector('#film svg').style.transform]; }"
        start,middle,end=(page.evaluate(look,i) for i in (0,75,300))
        self.assertEqual(start,[None,"translate(5 5) rotate(0 1000 400)","0.5","scale(1)"])
        self.assertEqual(end,start)
        self.assertEqual(middle[0],"translate(100 0)")
        self.assertEqual(middle[1],"translate(5 5) rotate(20 1000 400)")
        self.assertEqual(middle[2],"0.35")
        self.assertEqual(middle[3],"scale(1.02)")
        self.assertEqual(page.evaluate("[window.ran||0,document.querySelectorAll('#film script,#film [onload],#film [href]').length]"),[0,0])
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#help')).display"),"none")
        for bad,message in (("<p>no</p>","not an SVG picture"),('<svg xmlns="http://www.w3.org/2000/svg"/>',"needs a viewBox"),
                            ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><g data-move="far"/></svg>','data-move="far" is not 2 number'),):
            with self.subTest(bad=bad), self.assertRaisesRegex(Exception,message):
                page.evaluate("svg => film.load(svg)",bad)

if __name__ == "__main__":
    unittest.main()
