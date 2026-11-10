"""Inspect local video metadata with an existing ffprobe, and with --check judge it against a hero's budget; this does not decode motion."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

def inspect(path):
    file=Path(path).resolve()
    if not file.is_file():
        raise ValueError("local media file does not exist: " + str(file))
    probe=shutil.which("ffprobe")
    if probe is None:
        return {"status":"unavailable","reason":"ffprobe is not installed; nothing was downloaded"},3
    result=subprocess.run([probe,"-v","error","-select_streams","v","-show_entries",
                           "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:stream_disposition=attached_pic:format=format_name,duration,size",
                           "-of","json",str(file)],capture_output=True,text=True,timeout=30,check=False)
    if result.returncode:
        raise ValueError("ffprobe could not inspect this file: " + result.stderr.strip()[:500])
    metadata=json.loads(result.stdout)
    if not isinstance(metadata,dict) or not isinstance(metadata.get("streams"),list) or not metadata["streams"]:
        raise ValueError("no video stream found")
    format_name=str((metadata.get("format") or {}).get("format_name",""))
    if format_name=="image2" or format_name.endswith("_pipe"):
        raise ValueError("not a video file: still image ("+format_name+")")
    moving=[s for s in metadata["streams"] if isinstance(s,dict) and (s.get("disposition") or {}).get("attached_pic")!=1]
    if not moving:
        raise ValueError("not a video file: still image (attached picture only)")
    if str(moving[0].get("nb_frames",""))=="1":
        raise ValueError("not a video file: still image (single frame, "+(format_name or "unknown format")+")")
    metadata["streams"]=moving[:1]
    return {"status":"metadata inspected only","file":str(file),"metadata":metadata,
            "decode":"not performed",
            "limitation":"Reported frame rates do not prove unique frames, motion quality, accessibility or that the video is ready to publish."},0

def quick_start(path):
    """True when an MP4's index (moov) comes before its picture data (mdat), so playback can begin before the whole file has arrived."""
    seen=[]
    with Path(path).open("rb") as stream:
        while len(seen)<64:
            head=stream.read(8)
            if len(head)<8:
                break
            size,kind=int.from_bytes(head[:4],"big"),head[4:]
            if size==1:
                size=int.from_bytes(stream.read(8),"big")-8
            if kind in (b"moov",b"mdat"):
                seen.append(kind)
            if size<8:
                break
            stream.seek(size-8,1)
    return seen[:1]==[b"moov"] if seen else None

def budget(metadata,size,sound,quick,max_seconds=20.0,max_kb_per_second=300.0,max_height=1080):
    """Judge a clip against a hero's budget. Pure: it takes what inspect() and the file system report."""
    stream=metadata["streams"][0]
    def number(value):
        try:
            return float(value)
        except (TypeError,ValueError):
            return None
    seconds=number((metadata.get("format") or {}).get("duration")) or number(stream.get("duration"))
    height=number(stream.get("height"))
    rate=size/1000/seconds if seconds else None
    def line(name,ok,found,limit,fix):
        return {"check":name,"result":"unknown" if ok is None else "pass" if ok else "fail","found":found,"limit":limit,**({"fix":fix} if ok is False else {})}
    checks=[
        line("length",None if seconds is None else seconds<=max_seconds,None if seconds is None else "%.1f s"%seconds,"%g s or less"%max_seconds,
             "Trim it: a hero clip is a glance, not a film. ffmpeg -i IN.mp4 -t %g -c copy OUT.mp4"%max_seconds),
        line("weight",None if rate is None else rate<=max_kb_per_second,None if rate is None else "%.0f kB per second (%.2f MB in all)"%(rate,size/1e6),"%g kB per second or less"%max_kb_per_second,
             "Compress it: ffmpeg -i IN.mp4 -an -vf scale=-2:720 -c:v libx264 -crf 26 -preset slow -movflags +faststart OUT.mp4"),
        line("height",None if height is None else height<=max_height,None if height is None else "%d px"%height,"%d px or less"%max_height,
             "Scale it down: ffmpeg -i IN.mp4 -vf scale=-2:%d -c:v libx264 -crf 24 -movflags +faststart OUT.mp4"%max_height),
        line("quick start",quick,{True:"index first",False:"index last",None:"not an MP4 this check can read"}[quick],"index before the picture data",
             "Move the index to the front, without re-encoding: ffmpeg -i IN.mp4 -c copy -movflags +faststart OUT.mp4"),
    ]
    checks.append({"check":"sound","result":"note","found":"has a sound track" if sound else "silent",
                   "advice":"The page plays muted unless the config sets \"sound\": true. If the sound carries meaning, also set \"captions\" to a .vtt file." if sound
                            else "Nothing to do: the page plays it muted."})
    return checks

def sound_tracks(file,probe):
    result=subprocess.run([probe,"-v","error","-select_streams","a","-show_entries","stream=codec_name","-of","json",str(file)],capture_output=True,text=True,timeout=30,check=False)
    try:
        return bool(json.loads(result.stdout).get("streams")) if result.returncode==0 else False
    except ValueError:
        return False

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",metavar="FILE",help="existing local media file")
    parser.add_argument("--check",action="store_true",help="also judge the file against a hero's budget (length, weight, height, quick start); exit 1 if a check fails")
    parser.add_argument("--max-seconds",type=float,default=20.0,help="longest clip --check accepts (default: 20)")
    parser.add_argument("--max-kb-per-second",type=float,default=300.0,help="heaviest clip --check accepts, in kB per second of video (default: 300)")
    parser.add_argument("--max-height",type=int,default=1080,help="tallest picture --check accepts, in pixels (default: 1080)")
    args=parser.parse_args()
    try:
        report,code=inspect(args.input)
        if args.check and code==0:
            file=Path(report["file"])
            report["budget"]=budget(report["metadata"],file.stat().st_size,sound_tracks(file,shutil.which("ffprobe")),quick_start(file),
                                    args.max_seconds,args.max_kb_per_second,args.max_height)
            report["budget_note"]="A pass means the file fits these numbers. It says nothing about how the video looks, what it shows or whether you may use it."
            code=1 if any(c["result"]=="fail" for c in report["budget"]) else 0
        print(json.dumps(report,indent=2,ensure_ascii=False))
        return code
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print("error: "+str(exc),file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
