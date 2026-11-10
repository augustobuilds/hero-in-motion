import contextlib
import copy
import io
import json
import os
from pathlib import Path
import re
import shutil
from string import Template
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from _common import load, text
import build_demo
import build_hero
import inspect_media
import measure_page

BUILD=[sys.executable,str(ROOT/"scripts/build_hero.py")]
INSPECT=[sys.executable,str(ROOT/"scripts/inspect_media.py")]

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/"examples/hero.json").read_text())

    def test_sample_is_valid(self):
        build_hero.validate(self.data)

    def test_every_example_is_valid_and_names_a_poster_that_exists(self):
        found=sorted(p.name for p in (ROOT/"examples").glob("*.json"))
        self.assertEqual(found,["hero.es.json","hero.json","radio.json","swim.json"])
        layouts=set()
        for name in found:
            data=build_hero.validate(load(ROOT/"examples"/name))
            layouts.add(data.get("layout","split"))
            self.assertTrue((ROOT/"examples"/data["poster"][2:]).is_file(),name)
            self.assertIn("details",data,name)
            self.assertIn("<!doctype html>",build_hero.build(data))
        self.assertEqual(layouts,set(build_hero.LAYOUTS))

    def test_text_rejects_blank_long_and_control_characters(self):
        for value in ("","   ","x"*1001,"a\x01b","a\x7fb","a\x85b","a\ud800b",None,3):
            with self.subTest(value=repr(value)[:20]), self.assertRaises(ValueError):
                text(value,"field")
        self.assertEqual(text("line one\nline\ttwo","field"),"line one\nline\ttwo")

    def test_parser_rejects_bad_shapes_duplicate_keys_nan_and_deep_nesting(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"input.json"
            for text_ in ('[]','{"x":1,"x":2}','{"x":NaN}','{bad','{"x":'+'['*100+']'*100+'}','{"x":'+'['*100000+']'*100000+'}'):
                path.write_text(text_)
                with self.subTest(text=text_[:20]), self.assertRaises(ValueError):
                    load(path)

    def test_validate_rejects_unknown_keys_other_languages_and_names_the_field(self):
        data=copy.deepcopy(self.data);data["autoplay"]=True
        with self.assertRaisesRegex(ValueError,"unknown keys: 'autoplay'"):build_hero.validate(data)
        data=copy.deepcopy(self.data);data["a\nb"]=1
        with self.assertRaisesRegex(ValueError,r"unknown keys: 'a\\nb'"):build_hero.validate(data)
        for lang in ("xx",["en"],{},1,None):
            data=copy.deepcopy(self.data);data["lang"]=lang
            with self.subTest(lang=lang), self.assertRaisesRegex(ValueError,"^lang must be one of: "+re.escape(", ".join(sorted(build_hero.UI)))+"$"):
                build_hero.validate(data)
        for key,value in (("video","./clip.MP4"),("poster","./my poster.svg")):
            data=copy.deepcopy(self.data);data[key]=value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,"^"+key+" must be"):
                build_hero.validate(data)

    def test_accepts_simple_local_paths(self):
        for key,value in (("cta_href","./about.html"),("cta_href","./a/b.html"),("cta_href","#details"),("video","./media/clip_01.mp4"),("poster","./media/poster-1.svg"),
                          ("poster","./photo.jpg"),("poster","./photo.jpeg"),("poster","./photo.png"),("poster","./photo.webp"),("poster","./photo.avif"),
                          ("poster","/assets/hero/poster.webp"),("video","/assets/hero/clip.mp4"),("video_webm","./clip.webm"),("captions","./clip.vtt"),
                          ("cta_href","#pricing"),("cta_href","/"),("cta_href","/pricing"),("cta_href","/docs/start/"),("cta_href","/pricing?plan=team#faq"),
                          ("cta_href","https://example.com"),("cta_href","https://example.com/a.html"),("cta_href","https://shop.example.com:8443/p/1?ref=hero#buy")):
            data=copy.deepcopy(self.data);data[key]=value
            with self.subTest(key=key,value=value):
                build_hero.validate(data)

    def test_rejects_remote_script_and_traversal_urls(self):
        for key,value in (("video","javascript:alert(1)"),("poster","https://host/image.svg"),("video","./../secret.mp4"),("video","./clip.mp4?x=1"),("cta_href","//evil.test"),("cta_href","javascript:alert(1)"),("cta_href","JavaScript:alert(1)"),("cta_href","data:text/html,x"),
                          ("cta_href","http://example.com/"),("cta_href","https://"),("cta_href","https://user@example.com/"),("cta_href","https://example.com/a b"),
                          ("cta_href","https://example.com/\"onclick=\"x"),("cta_href","/../secret"),("cta_href","./a/../b.html"),("cta_href","pricing"),
                          ("poster","./photo.gif"),("poster","./photo.JPG"),("poster","//host/photo.jpg"),("video_webm","./clip.mp4"),("captions","./clip.srt"),
                          ("captions","https://host/clip.vtt")):
            data=copy.deepcopy(self.data);data[key]=value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                build_hero.validate(data)

    def test_every_template_placeholder_has_a_value_in_both_languages(self):
        template=(ROOT/"templates/hero.html").read_text()
        names={m.group("named") or m.group("braced") for m in Template.pattern.finditer(template)}-{None}
        names|={m.group("named") or m.group("braced") for m in Template.pattern.finditer((ROOT/"templates/page.html").read_text())}-{None,"hero"}
        for name in ("hero.json","hero.es.json"):
            data=json.loads((ROOT/"examples"/name).read_text())
            for extra in ({},{"captions":"./c.vtt","video_webm":"./c.webm","sound":True,"layout":"cover","ratio":"4:3"}):
                with self.subTest(name=name,extra=bool(extra)):
                    self.assertLessEqual(names,set(build_hero.values(build_hero.validate(dict(data,**extra)))))
        minimal={k:v for k,v in self.data.items() if k in build_hero.REQUIRED}
        minimal["cta_href"]="/pricing"
        self.assertLessEqual(names,set(build_hero.values(build_hero.validate(minimal))))
        self.assertEqual(set(build_hero.UI["en"]),set(build_hero.UI["es"]))

    def test_html_escapes_strings_and_does_not_interpolate_them_into_script(self):
        from html.parser import HTMLParser
        class Tags(HTMLParser):
            def __init__(self):super().__init__();self.tags=[]
            def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))
        self.data["headline"]='<img src=x onerror="alert(1)"> & $ui_play'
        self.data["details"]='</script><script>alert(1)</script>'
        build_hero.validate(self.data)
        result=build_hero.build(self.data)
        parser=Tags();parser.feed(result)
        self.assertEqual(sum(tag=="script" for tag,attrs in parser.tags),1)
        self.assertEqual(sum(tag=="img" for tag,attrs in parser.tags),1)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; $ui_play',result)
        self.assertIn('&lt;/script&gt;',result)
        script=result[result.index("<script>"):]
        self.assertNotIn("alert",script)
        video=next(attrs for tag,attrs in parser.tags if tag=="video")
        self.assertNotIn("autoplay",video)
        self.assertNotIn("src",video)
        self.assertEqual(video["preload"],"none")
        self.assertIn("hidden",video)
        button=next(attrs for tag,attrs in parser.tags if tag=="button")
        self.assertIn("hidden",button)
        self.assertEqual(button["aria-controls"],"hm-video")
        self.assertNotIn("aria-pressed",button)

    def test_static_html_does_not_promise_a_play_button(self):
        for lang in ("en","es"):
            data=copy.deepcopy(self.data);data["lang"]=lang
            result=build_hero.build(build_hero.validate(data))
            status=re.search(r'<p class="hm-status hm-quiet" id="hm-status"[^>]*>(.*?)</p>',result).group(1)
            with self.subTest(lang=lang):
                self.assertEqual(status,build_hero.UI[lang]["idle"])
                self.assertNotIn(build_hero.UI[lang]["play"].split()[0],status)

    def test_end_of_video_has_its_own_message_in_both_languages(self):
        for lang,word in (("en","watch it again"),("es","verlo de nuevo")):
            data=copy.deepcopy(self.data);data["lang"]=lang
            result=build_hero.build(build_hero.validate(data))
            with self.subTest(lang=lang):
                self.assertIn(word,result)
                self.assertIn("paused(words.ended)",result)

    def test_page_script_keeps_its_playback_guards(self):
        template=(ROOT/"templates/hero.html").read_text()
        for line in (".observe(panel)",
                     "function autoPause() { if (starting || !video.paused) paused(); }",
                     "if (document.hidden) autoPause();",
                     "if (offscreen) autoPause();",
                     "if (startedAt && performance.now() - startedAt < 400) return;",
                     "if (token !== request) return;",
                     "if (token === request) paused(words.failed);",
                     "if (video.error) { video.removeAttribute('src'); video.load(); }",
                     "if (!video.getAttribute('src')) video.src = video.dataset.src;",
                     "else if (status.textContent === words.reduced) status.textContent = restingMessage();"):
            with self.subTest(line=line):
                self.assertIn(line,template)

    def test_text_fallback_is_the_poster_description_and_starts_hidden_from_screen_readers(self):
        self.data["poster_alt"]="A sunrise <over> hills"
        result=build_hero.build(build_hero.validate(self.data))
        self.assertIn('<p class="hm-fallback" aria-hidden="true">A sunrise &lt;over&gt; hills</p>',result)

    def test_optional_fields_add_only_what_they_name(self):
        plain={k:v for k,v in self.data.items() if k in build_hero.REQUIRED};plain["cta_href"]="/pricing"
        page=build_hero.build(build_hero.validate(plain))
        for absent in ('class="hm-badge"','id="details"','id="hm-sound"',' data-captions=',' data-webm=',"<track","--hm-focus:"):
            with self.subTest(absent=absent):self.assertNotIn(absent,page)
        self.assertIn(" muted ",page)
        self.assertIn('class="hm hm-split"',page)
        self.assertIn("--hm-ratio:1 / 1",page)
        full=dict(self.data,badge="New <b>",layout="cover",ratio="4:3",captions="./clip.vtt",video_webm="./clip.webm",sound=True)
        page=build_hero.build(build_hero.validate(full))
        for present in ('<p class="hm-badge">New &lt;b&gt;</p>','class="hm hm-cover hm-captions"',"--hm-ratio:4 / 3",'data-webm="./clip.webm"',
                        'data-captions="./clip.vtt"','<button id="hm-sound" type="button" aria-controls="hm-video" hidden>Mute sound</button>','id="details"'):
            with self.subTest(present=present):self.assertIn(present,page)
        self.assertNotIn(" muted ",page)
        self.assertNotIn("<track",page)
        self.assertEqual(build_hero.values(build_hero.validate(dict(self.data,layout="stacked")))["ratio"],"16 / 9")
        # colours and focus: strict values only, and an accent the button's label can't be read on is refused
        styled=build_hero.build(build_hero.validate(dict(self.data,accent="#0b5cad",accent_dark="#8cc8ff",focus="70% 40%")),fragment=True)
        self.assertIn(".hm { --hm-accent:#0b5cad; }\n@media (prefers-color-scheme:dark) { .hm { --hm-accent:#8cc8ff; } }\n</style>",styled)
        self.assertIn('style="--hm-ratio:1 / 1;--hm-focus:70% 40%"',styled)
        self.assertEqual(build_hero.build(build_hero.validate(self.data),fragment=True).count("--hm-accent:"),2)
        template=(ROOT/"templates/hero.html").read_text(encoding="utf-8")
        self.assertIn("--hm-card:"+build_hero.CARD["accent"]+";",template)
        self.assertIn("--hm-card:"+build_hero.CARD["accent_dark"]+";",template)
        self.assertAlmostEqual(build_hero.contrast("#000","#ffffff"),21.0)
        for key,value,message in (("accent","red","^accent must be a colour such as"),("accent","#0b6a52;x","^accent must be a colour"),("accent","#9fe","^accent #9fe is too close"),
                                  ("accent_dark","#123","^accent_dark #123 is too close"),("accent_dark",7,"^accent_dark must be a colour"),
                                  ("focus","left","^focus must be two percentages"),("focus","120% 40%","^focus must be"),("focus","50% 50%;color:red","^focus must be")):
            with self.subTest(key=key,value=value), self.assertRaisesRegex(ValueError,message):
                build_hero.validate(dict(self.data,**{key:value}))
        for key,value,message in (("layout","wide","^layout must be one of: split, stacked, cover$"),("ratio","16x9","^ratio must look like"),("ratio","0:1","^ratio must look like"),
                                  ("sound","yes","^sound must be true or false$"),("badge","","^badge must be nonempty"),("details"," ","^details must be nonempty")):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,message):
                build_hero.validate(dict(self.data,**{key:value}))
        del self.data["details"]
        with self.assertRaisesRegex(ValueError,"^cta_href points at #details"):
            build_hero.validate(self.data)

    def test_fragment_is_the_hero_block_and_the_page_wraps_exactly_it(self):
        build_hero.validate(self.data)
        fragment,page=build_hero.build(self.data,fragment=True),build_hero.build(self.data)
        for absent in ("<!doctype","<html","<head","<body","<title","<main",":root","body {"):
            with self.subTest(absent=absent):self.assertNotIn(absent,fragment)
        self.assertTrue(fragment.startswith("<style>"))
        self.assertTrue(fragment.rstrip().endswith("</script>"))
        self.assertEqual(fragment.count("<script>"),1)
        self.assertIn("(() => {\n'use strict';",fragment)
        self.assertIn(fragment,page)
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("<title>"+self.data["title"].replace("·","·")+"</title>",page)
        # every selector in the block's styles is scoped to the block, so it can't restyle the host page
        css=re.sub(r"@media[^{]*\{","",fragment[fragment.index("<style>")+7:fragment.index("</style>")])
        for selector in re.findall(r"(?:^|\})\s*([^{}]+)\{",css):
            for part in selector.split(","):
                with self.subTest(selector=part.strip()):self.assertTrue(part.strip().startswith(".hm"))
        ids=re.findall(r'\bid="([^"]+)"',fragment)
        self.assertEqual(sorted(i for i in ids if not i.startswith("hm-")),["details"])

    def test_poster_has_no_play_glyph_and_follows_dark_mode(self):
        for name in ("poster.svg","poster-es.svg"):
            svg=(ROOT/"examples"/name).read_text(encoding="utf-8")
            self.assertIn("prefers-color-scheme:dark",svg)
            self.assertNotRegex(svg,r"<path[^>]*d=\"M\d+ \d+L\d+ \d+L\d+ \d+Z\"")
        self.assertIn("Ejemplo ficticio",(ROOT/"examples/poster-es.svg").read_text(encoding="utf-8"))

class CliTests(unittest.TestCase):
    def test_cli_writes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"output.html"
            cmd=BUILD+[str(ROOT/"examples/hero.json"),"--output",str(path)]
            first=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            before=path.read_bytes()
            again=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(again.returncode,2)
            self.assertEqual(path.read_bytes(),before)
            self.assertNotIn("Traceback",again.stderr)
            path.write_text("old")
            replacement=subprocess.run(cmd+["--overwrite"],capture_output=True,text=True)
            self.assertEqual(replacement.returncode,0,replacement.stderr)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()),["output.html"])
            block=Path(temp)/"block.html"
            fragment=subprocess.run(BUILD+[str(ROOT/"examples/hero.json"),"--output",str(block),"--fragment"],capture_output=True,text=True)
            self.assertEqual(fragment.returncode,0,fragment.stderr)
            self.assertTrue(block.read_text(encoding="utf-8").startswith("<style>"))
            self.assertIn(block.read_text(encoding="utf-8"),path.read_text(encoding="utf-8"))

    def test_bad_input_cli_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            for name,body in (("empty.json",'{}'),("deep.json",'{"x":'+'['*100000+']'*100000+'}')):
                path=Path(temp)/name;path.write_text(body)
                result=subprocess.run(BUILD+[str(path),"--output",str(Path(temp)/"out.html")],capture_output=True,text=True)
                with self.subTest(name=name):
                    self.assertEqual(result.returncode,2)
                    self.assertIn("error:",result.stderr)
                    self.assertNotIn("Traceback",result.stderr)
                    self.assertFalse((Path(temp)/"out.html").exists())

    def test_cli_never_replaces_its_input(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"hero.json";source.write_bytes((ROOT/"examples/hero.json").read_bytes())
            link=Path(temp)/"link.json";os.symlink(source,link)
            before=source.read_bytes()
            for output in (source,link):
                result=subprocess.run(BUILD+[str(source),"--output",str(output),"--overwrite"],capture_output=True,text=True)
                with self.subTest(output=output.name):
                    self.assertEqual(result.returncode,2)
                    self.assertIn("must not replace input",result.stderr)
                    self.assertEqual(source.read_bytes(),before)

    def test_failed_write_keeps_the_existing_page(self):
        import _common
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"page.html";path.write_text("good")
            with self.assertRaises(UnicodeError):_common.write(path,"bad \ud800",overwrite=True)
            fresh=Path(temp)/"new.html"
            with self.assertRaises(UnicodeError):_common.write(fresh,"bad \ud800")
            self.assertFalse(fresh.exists())
            with patch.object(_common.os,"replace",side_effect=OSError("disk full")), self.assertRaises(OSError):
                _common.write(path,"new",overwrite=True)
            self.assertEqual(path.read_text(),"good")
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()),["page.html"])
            _common.write(path,"new",overwrite=True)
            self.assertEqual(path.read_text(),"new")

    @unittest.skipIf(os.name!="posix","POSIX permissions and symlinks")
    def test_overwrite_keeps_mode_follows_symlinks_and_refuses_unsafe_targets(self):
        import _common
        with tempfile.TemporaryDirectory() as temp:
            real=Path(temp)/"real.html";real.write_text("old");os.chmod(real,0o640)
            link=Path(temp)/"link.html";os.symlink(real,link)
            _common.write(link,"new",overwrite=True)
            self.assertTrue(link.is_symlink())
            self.assertEqual(real.read_text(),"new")
            self.assertEqual(real.stat().st_mode&0o777,0o640)
            with self.assertRaisesRegex(ValueError,"regular file"):_common.write(Path(temp),"x",overwrite=True)
            os.chmod(real,0o440)
            if not os.access(real,os.W_OK):
                with self.assertRaisesRegex(ValueError,"read-only"):_common.write(real,"x",overwrite=True)
                self.assertEqual(real.read_text(),"new")
            with self.assertRaises(FileNotFoundError) as caught:_common.write(Path(temp)/"no"/"page.html","x",overwrite=True)
            self.assertIn("page.html",str(caught.exception))

    def test_help_describes_each_tool(self):
        for cmd,phrase in ((BUILD,"--fragment"),(INSPECT,"ffprobe")):
            result=subprocess.run(cmd+["--help"],capture_output=True,text=True)
            with self.subTest(phrase=phrase):
                self.assertEqual(result.returncode,0)
                self.assertIn(phrase,result.stdout)

class DemoTests(unittest.TestCase):
    def test_demo_in_docs_is_a_fresh_build_of_the_examples(self):
        self.assertEqual(build_demo.stale(),[],"run: python3 scripts/build_demo.py --write")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(build_demo.main(["--check"]),0)
            self.assertEqual(build_demo.main(["--bogus"]),2)
        for page,config,_,_ in build_demo.PAGES:
            html=(ROOT/"docs"/page).read_text(encoding="utf-8")
            data=build_demo._with_webm(load(ROOT/"examples"/config))
            with self.subTest(page=page):
                # the demo page holds the kit's own block, untouched, and its meter knows the clips' real sizes
                self.assertIn(build_hero.build(build_hero.validate(data),fragment=True),html)
                self.assertNotRegex(html,r"<video[^>]*\sautoplay|<script[^>]*\ssrc=|<link[^>]*stylesheet|@import")
                for name in build_demo._clips(data):
                    self.assertIn("&quot;%s&quot;:%d"%(name,(ROOT/"docs"/name).stat().st_size),html)
                self.assertEqual(html.count("<h1"),1)
        auto=(ROOT/"docs/autoplay.html").read_text(encoding="utf-8")
        self.assertRegex(auto,r"<video autoplay muted loop playsinline ")
        self.assertIn('id="demo-stop"',auto)
        self.assertNotIn('id="hm-toggle"',auto)

    def test_demo_check_names_what_is_stale_and_what_does_not_belong(self):
        with tempfile.TemporaryDirectory() as temp:
            copy=Path(temp)/"docs";shutil.copytree(ROOT/"docs",copy)
            (copy/"index.html").write_text("old",encoding="utf-8");(copy/"stray.txt").write_text("x",encoding="utf-8");(copy/"poster.svg").unlink()
            with patch.object(build_demo,"DOCS",copy), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(build_demo.stale(),["index.html","poster.svg","stray.txt"])
                self.assertEqual(build_demo.main(["--check"]),1)
                (copy/"stray.txt").unlink()
                self.assertEqual(build_demo.main(["--write"]),0)
                self.assertEqual(build_demo.stale(),[])
                (copy/"swim.mp4").unlink()
                self.assertEqual(build_demo.main(["--check"]),2)

class MeasureTests(unittest.TestCase):
    def test_server_answers_byte_ranges_and_counts_what_it_sends(self):
        import functools,http.server,threading,urllib.error,urllib.request
        with tempfile.TemporaryDirectory() as temp:
            Path(temp,"clip.mp4").write_bytes(bytes(range(200)));Path(temp,"page.html").write_text("<p>hi</p>",encoding="utf-8")
            sent={}
            handler=type("Handler",(measure_page.Counting,),{"sent":sent,"lock":threading.Lock()})
            server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(handler,directory=temp))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
            base="http://127.0.0.1:%d/"%server.server_address[1]
            def get(name,span=None):
                request=urllib.request.Request(base+name,headers={"Range":span} if span else {})
                with urllib.request.urlopen(request,timeout=10) as answer:
                    return answer.status,answer.headers.get("Content-Range"),answer.read()
            self.assertEqual(get("page.html"),(200,None,b"<p>hi</p>"))
            self.assertEqual(get("clip.mp4","bytes=0-9"),(206,"bytes 0-9/200",bytes(range(10))))
            self.assertEqual(get("clip.mp4","bytes=190-"),(206,"bytes 190-199/200",bytes(range(190,200))))
            self.assertEqual(get("clip.mp4","bytes=-5"),(206,"bytes 195-199/200",bytes(range(195,200))))
            for name,span,code in (("clip.mp4","bytes=500-",416),("missing.mp4",None,404),("../"+Path(temp).name+"/page.html",None,404)):
                try:
                    status=get(name,span)[0]
                except urllib.error.HTTPError as exc:
                    status=exc.code
                with self.subTest(name=name):self.assertEqual(status,code)
            self.assertEqual(sent["clip.mp4"],25)
            found=measure_page.summary(sent)
            self.assertEqual((found["video_bytes"],found["total_bytes"]),(25,25+len(b"<p>hi</p>")))

    def test_cli_rejects_bad_input_and_the_report_reads_plainly(self):
        measure=[sys.executable,str(ROOT/"scripts/measure_page.py")]
        for args in (["nothing.html"],[str(ROOT/"README.md")],[str(ROOT/"docs/index.html"),"--seconds","0"]):
            result=subprocess.run(measure+args,capture_output=True,text=True,timeout=60)
            with self.subTest(args=args):
                self.assertEqual(result.returncode,2)
                self.assertRegex(result.stderr,"^error: ")
        found={"page":"hero.html","seconds":5.0,"pressed_play":True,
               "before":{"files":{"hero.html":13000,"poster.svg":40780},"video_bytes":0,"total_bytes":53780},
               "after":{"files":{"hero.html":13000,"poster.svg":40780,"clip.mp4":683284},"video_bytes":683284,"total_bytes":737064}}
        text_report=measure_page.report(found)
        self.assertIn("before anyone presses Play",text_report)
        self.assertRegex(text_report,r"video\s+0 B")
        self.assertRegex(text_report,r"clip\.mp4\s+\+683\.3 kB")
        self.assertEqual([measure_page.amount(n) for n in (0,999,1000,53780,1234567)],["0 B","999 B","1.0 kB","53.8 kB","1.23 MB"])
        self.assertIn("nothing was pressed",measure_page.report(dict(found,pressed_play=False,after=None)))

class InspectTests(unittest.TestCase):
    def test_cli_exit_codes_for_missing_file_and_missing_ffprobe(self):
        with tempfile.TemporaryDirectory() as temp:
            missing=subprocess.run(INSPECT+[str(Path(temp)/"none.mp4")],capture_output=True,text=True)
            self.assertEqual(missing.returncode,2)
            self.assertIn("error:",missing.stderr)
            self.assertNotIn("Traceback",missing.stderr)
            fixture=Path(temp)/"clip.mp4";fixture.write_bytes(b"not a film")
            env=dict(os.environ,PATH=temp)
            absent=subprocess.run(INSPECT+[str(fixture)],capture_output=True,text=True,env=env)
            self.assertEqual(absent.returncode,3)
            self.assertEqual(json.loads(absent.stdout)["status"],"unavailable")

    def test_ffprobe_absence_missing_media_and_metadata_honesty(self):
        with tempfile.TemporaryDirectory() as temp:
            missing=Path(temp)/"missing.mp4"
            with self.assertRaises(ValueError):inspect_media.inspect(missing)
            fixture=Path(temp)/"-fixture.mp4";fixture.write_bytes(b"not a film: mocked process only")
            with patch.object(inspect_media.shutil,"which",return_value=None):
                report,code=inspect_media.inspect(fixture)
                self.assertEqual(code,3)
                self.assertEqual(report["status"],"unavailable")
            fake=subprocess.CompletedProcess([],0,json.dumps({"streams":[{"width":300,"disposition":{"attached_pic":1}},{"width":1080,"height":1080,"avg_frame_rate":"60/1","nb_frames":"240","disposition":{"attached_pic":0}}],"format":{"format_name":"mov,mp4,m4a,3gp,3g2,mj2"}}),"")
            with patch.object(inspect_media.shutil,"which",return_value="/mock/ffprobe"),patch.object(inspect_media.subprocess,"run",return_value=fake) as run:
                report,code=inspect_media.inspect(fixture)
                self.assertEqual(code,0)
                self.assertEqual(report["decode"],"not performed")
                self.assertIn("unique frames",report["limitation"])
                self.assertEqual(report["metadata"]["streams"][0]["width"],1080)
                args=run.call_args.args[0]
                self.assertEqual(args[-1],str(fixture.resolve()))
                self.assertEqual(args[args.index("-select_streams")+1],"v")
                entries=args[args.index("-show_entries")+1]
                for entry in ("stream_disposition=attached_pic","format_name","nb_frames"):
                    self.assertIn(entry,entries)
                self.assertNotIn("shell",run.call_args.kwargs)

    def test_unreadable_streamless_and_still_image_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=Path(temp)/"clip.mp4";fixture.write_bytes(b"mocked")
            cases=(subprocess.CompletedProcess([],1,"","Invalid data"),
                   subprocess.CompletedProcess([],0,json.dumps({"streams":[]}),""),
                   subprocess.CompletedProcess([],0,json.dumps({"streams":[{"width":1080}],"format":{"format_name":"svg_pipe"}}),""),
                   subprocess.CompletedProcess([],0,json.dumps({"streams":[{"width":1080}],"format":{"format_name":"image2"}}),""),
                   subprocess.CompletedProcess([],0,json.dumps({"streams":[{"width":1080,"disposition":{"attached_pic":1}}],"format":{"format_name":"mp3"}}),""),
                   subprocess.CompletedProcess([],0,json.dumps({"streams":[{"width":64,"nb_frames":"1"}],"format":{"format_name":"gif"}}),""))
            for fake in cases:
                with self.subTest(stdout=fake.stdout[:60]),patch.object(inspect_media.shutil,"which",return_value="/mock/ffprobe"),patch.object(inspect_media.subprocess,"run",return_value=fake):
                    with self.assertRaises(ValueError):inspect_media.inspect(fixture)

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"),"needs ffmpeg and ffprobe")
    def test_real_ffprobe_on_tiny_fixtures(self):
        with tempfile.TemporaryDirectory() as temp:
            def make(name,*args):
                subprocess.run(["ffmpeg","-loglevel","error","-y",*args,str(Path(temp)/name)],check=True,timeout=60)
                return Path(temp)/name
            clip=make("clip.mp4","-f","lavfi","-i","testsrc=size=64x64:rate=10:duration=1","-pix_fmt","yuv420p")
            png=make("still.png","-f","lavfi","-i","testsrc=size=64x64","-frames:v","1")
            gif=make("still.gif","-f","lavfi","-i","testsrc=size=64x64","-frames:v","1")
            cover=make("cover.mp4","-i",str(clip),"-i",str(png),"-map","0","-map","1","-c","copy","-disposition:v:1","attached_pic")
            for path,code in ((clip,0),(cover,0),(png,2),(gif,2),(ROOT/"examples/poster.svg",2)):
                result=subprocess.run(INSPECT+[str(path)],capture_output=True,text=True)
                with self.subTest(file=path.name):
                    self.assertEqual(result.returncode,code,result.stderr)
                    self.assertNotIn("Traceback",result.stderr)

    def test_budget_judges_length_weight_height_and_quick_start(self):
        meta=lambda seconds,height:{"streams":[{"height":height,"width":height}],"format":{"duration":str(seconds)}}
        result=lambda checks:{c["check"]:c["result"] for c in checks}
        good=inspect_media.budget(meta(10,720),2_000_000,False,True)
        self.assertEqual(result(good),{"length":"pass","weight":"pass","height":"pass","quick start":"pass","sound":"note"})
        self.assertTrue(all("fix" not in c for c in good))
        bad=inspect_media.budget(meta(45,2160),40_000_000,True,False)
        self.assertEqual(result(bad),{"length":"fail","weight":"fail","height":"fail","quick start":"fail","sound":"note"})
        self.assertTrue(all("ffmpeg -i IN.mp4" in c["fix"] for c in bad[:4]))
        self.assertIn("captions",bad[4]["advice"])
        self.assertEqual(result(inspect_media.budget(meta(45,2160),40_000_000,False,True,max_seconds=60,max_kb_per_second=1000,max_height=2160)),
                         {"length":"pass","weight":"pass","height":"pass","quick start":"pass","sound":"note"})
        unknown=inspect_media.budget({"streams":[{}],"format":{}},1000,False,None)
        self.assertEqual(result(unknown),{"length":"unknown","weight":"unknown","height":"unknown","quick start":"unknown","sound":"note"})
        with tempfile.TemporaryDirectory() as temp:
            atom=lambda kind,body=b"":(len(body)+8).to_bytes(4,"big")+kind+body
            for name,parts,expected in (("front.mp4",(atom(b"ftyp",b"isom"),atom(b"moov",b"x"*20),atom(b"mdat",b"y"*40)),True),
                                        ("back.mp4",(atom(b"ftyp",b"isom"),atom(b"free"),atom(b"mdat",b"y"*40),atom(b"moov",b"x"*20)),False),
                                        ("other.webm",(b"\x1aE\xdf\xa3"+b"z"*40,),None),("empty.mp4",(),None)):
                path=Path(temp)/name;path.write_bytes(b"".join(parts))
                with self.subTest(name=name):self.assertIs(inspect_media.quick_start(path),expected)

    @unittest.skipUnless(shutil.which("ffprobe") and shutil.which("ffmpeg"),"needs ffmpeg and ffprobe")
    def test_check_exit_codes_on_real_clips(self):
        with tempfile.TemporaryDirectory() as temp:
            def make(name,*args):
                subprocess.run(["ffmpeg","-loglevel","error","-y","-f","lavfi","-i","testsrc=size=64x64:rate=10:duration=1",*args,str(Path(temp)/name)],check=True,timeout=60)
                return str(Path(temp)/name)
            fast=make("fast.mp4","-pix_fmt","yuv420p","-movflags","+faststart")
            slow=make("slow.mp4","-pix_fmt","yuv420p")
            loud=make("loud.mp4","-f","lavfi","-i","sine=frequency=440:duration=1","-pix_fmt","yuv420p","-shortest","-movflags","+faststart")
            for path,flags,code,failed in ((fast,[],0,[]),(slow,[],1,["quick start"]),(fast,["--max-seconds","0.5"],1,["length"]),(loud,[],0,[])):
                done=subprocess.run(INSPECT+[path,"--check"]+flags,capture_output=True,text=True)
                with self.subTest(file=Path(path).name,flags=flags):
                    self.assertEqual(done.returncode,code,done.stderr+done.stdout)
                    report=json.loads(done.stdout)
                    self.assertEqual([c["check"] for c in report["budget"] if c["result"]=="fail"],failed)
                    self.assertEqual(report["budget"][-1]["found"],"has a sound track" if path==loud else "silent")
            plain=subprocess.run(INSPECT+[fast],capture_output=True,text=True)
            self.assertNotIn("budget",json.loads(plain.stdout))

    def test_timeout_exits_2(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=Path(temp)/"clip.mp4";fixture.write_bytes(b"mocked")
            with patch.object(inspect_media.shutil,"which",return_value="/mock/ffprobe"),\
                 patch.object(inspect_media.subprocess,"run",side_effect=subprocess.TimeoutExpired("ffprobe",30)),\
                 patch.object(sys,"argv",["inspect_media.py",str(fixture)]),patch("sys.stderr"):
                self.assertEqual(inspect_media.main(),2)

if __name__ == "__main__":
    unittest.main()
