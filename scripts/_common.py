"""Small local input/output helpers; standard library only, no network access."""
import argparse
import errno
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unicodedata

def require(ok, message):
    if not ok:
        raise ValueError(message)

def obj(value, name):
    require(isinstance(value, dict), name + " must be an object")
    return value

def text(value, name, limit=1000):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
            name + " must be nonempty text (maximum " + str(limit) + " characters)")
    require(all(c in "\n\t" or unicodedata.category(c) not in ("Cc", "Cs") for c in value),
            name + " contains control characters")
    return value

def load(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1048577)
    require(len(raw) <= 1048576, "input exceeds the 1 MiB limit")
    def reject(value):
        raise ValueError("JSON contains non-finite number: " + value)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + repr(key))
            result[key] = value
        return result
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=reject, object_pairs_hook=pairs)
    except RecursionError:
        raise ValueError("JSON is nested too deeply") from None
    stack = [(data, 1)]
    while stack:
        value, depth = stack.pop()
        require(depth <= 64, "JSON is nested too deeply")
        children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
        stack.extend((child, depth + 1) for child in children)
    return obj(data, "input")

def write(path, value, overwrite=False):
    data = value.encode("utf-8")
    if not overwrite:
        with Path(path).open("xb") as stream:
            stream.write(data)
        return
    target = Path(os.path.realpath(path))
    if not target.parent.is_dir():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(path))
    if target.exists():
        info = target.stat()
        require(stat.S_ISREG(info.st_mode), "output must be a regular file: " + str(path))
        require(os.access(str(target), os.W_OK), "output is read-only: " + str(path))
        mode = stat.S_IMODE(info.st_mode)
    else:
        mask = os.umask(0)
        os.umask(mask)
        mode = 0o666 & ~mask
    try:
        handle, temp = tempfile.mkstemp(prefix="." + target.name + ".", dir=str(target.parent))
    except PermissionError:
        raise PermissionError(errno.EACCES, "output folder is not writable", str(target.parent)) from None
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.chmod(temp, mode)
        os.replace(temp, str(target))
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise

def cli(validate, build, description, flags=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", metavar="INPUT", help="local JSON input")
    parser.add_argument("--output", required=True, help="output path; parent directory must exist")
    parser.add_argument("--overwrite", action="store_true", help="explicitly replace an existing output")
    for name, help_text in (flags or {}).items():
        parser.add_argument("--" + name, action="store_true", help=help_text)
    args = parser.parse_args()
    try:
        data = load(args.input)
        validate(data)
        require(Path(args.input).resolve() != Path(args.output).resolve(), "output must not replace input")
        write(args.output, build(data, **{name: True for name in (flags or {}) if getattr(args, name)}), args.overwrite)
        print("Wrote " + args.output)
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
