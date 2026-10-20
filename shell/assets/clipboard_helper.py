#!/usr/bin/env python3
"""Clipboard helper for Hyprstack shell (cliphist integration)."""

import sys
import os
import subprocess
import json
import argparse
import base64
from pathlib import Path


def get_clip_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    clip_dir = Path(base) / "hyprstack-clip"
    clip_dir.mkdir(parents=True, exist_ok=True)
    return clip_dir


def extract_raw_bytes(args, raw_arg="raw", b64_arg="b64") -> bytes:
    b64_val = getattr(args, b64_arg, None)
    if b64_val:
        try:
            return base64.b64decode(b64_val)
        except Exception:
            pass

    raw_val = getattr(args, raw_arg, None)
    if raw_val:
        return raw_val.encode("utf-8")

    if not sys.stdin.isatty():
        return sys.stdin.buffer.read()

    return b""


def cmd_list(args):
    clip_dir = get_clip_dir()
    try:
        proc = subprocess.run(["cliphist", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        out = proc.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(json.dumps({"error": str(e), "entries": []}))
        return

    lines = [l for l in out.splitlines() if l.strip()]
    entries = []
    
    # Process up to 100 entries for responsiveness
    for idx, line in enumerate(lines[:100]):
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        cid, body = parts
        is_binary = body.startswith("[[ binary data")
        image_path = ""

        if is_binary:
            thumb = clip_dir / f"{cid}.png"
            if not thumb.exists() and idx < 50:
                try:
                    dec = subprocess.Popen(["cliphist", "decode"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                    stdout, _ = dec.communicate(input=line.encode("utf-8") + b"\n", timeout=2)
                    if stdout:
                        thumb.write_bytes(stdout)
                except Exception:
                    pass
            if thumb.exists():
                image_path = str(thumb)

        entries.append({
            "id": cid,
            "text": body,
            "raw": line,
            "isBinary": is_binary,
            "imagePath": image_path
        })

    print(json.dumps(entries, ensure_ascii=False))


def cmd_decode(args):
    raw_data = extract_raw_bytes(args)
    if not raw_data:
        sys.exit(0)

    if not raw_data.endswith(b"\n"):
        raw_data += b"\n"

    try:
        proc = subprocess.Popen(["cliphist", "decode"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _ = proc.communicate(input=raw_data, timeout=5)
        sys.stdout.buffer.write(stdout)
    except Exception as e:
        sys.stderr.write(f"Decode error: {e}\n")
        sys.exit(1)


def cmd_edit(args):
    try:
        old_raw = extract_raw_bytes(args, raw_arg="raw", b64_arg="b64_raw")
        
        b64_text = getattr(args, "b64_text", None)
        if b64_text:
            new_text = base64.b64decode(b64_text).decode("utf-8")
        elif args.text is not None:
            new_text = args.text
        else:
            raw_input = sys.stdin.read()
            payload = json.loads(raw_input)
            old_raw = payload.get("raw", "").encode("utf-8")
            new_text = payload.get("text", "")

        # 1. Copy new text to clipboard via wl-copy
        cp = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        cp.communicate(input=new_text.encode("utf-8"), timeout=5)

        # 2. Delete old entry from cliphist
        if old_raw:
            if not old_raw.endswith(b"\n"):
                old_raw += b"\n"
            dp = subprocess.Popen(["cliphist", "delete"], stdin=subprocess.PIPE)
            dp.communicate(input=old_raw, timeout=5)

        print(json.dumps({"status": "ok"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def cmd_copy(args):
    raw_data = extract_raw_bytes(args)
    if not raw_data:
        print(json.dumps({"error": "No raw data"}))
        return

    if not raw_data.endswith(b"\n"):
        raw_data += b"\n"

    try:
        dec = subprocess.Popen(["cliphist", "decode"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        decoded, _ = dec.communicate(input=raw_data, timeout=5)
        if decoded:
            cp = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            cp.communicate(input=decoded, timeout=5)
        print(json.dumps({"status": "ok"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def cmd_delete(args):
    raw_data = extract_raw_bytes(args)
    if not raw_data:
        print(json.dumps({"error": "No raw data"}))
        return

    if not raw_data.endswith(b"\n"):
        raw_data += b"\n"

    try:
        dp = subprocess.Popen(["cliphist", "delete"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = dp.communicate(input=raw_data, timeout=5)
        
        # Clean thumbnail if it exists
        try:
            line_str = raw_data.decode("utf-8", errors="ignore").strip()
            cid = line_str.split("\t", 1)[0]
            thumb = get_clip_dir() / f"{cid}.png"
            if thumb.exists():
                thumb.unlink()
        except Exception:
            pass

        print(json.dumps({"status": "ok"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def cmd_wipe(args):
    try:
        subprocess.run(["cliphist", "wipe"], timeout=5)
        clip_dir = get_clip_dir()
        for f in clip_dir.glob("*.png"):
            try:
                f.unlink()
            except Exception:
                pass
        print(json.dumps({"status": "ok"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Hyprstack clipboard helper")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list")

    p_decode = subparsers.add_parser("decode")
    p_decode.add_argument("--b64", type=str, default="", help="Base64 encoded raw line")
    p_decode.add_argument("--raw", type=str, default="", help="Raw clipboard line")

    p_edit = subparsers.add_parser("edit")
    p_edit.add_argument("--b64-raw", type=str, default="", help="Base64 encoded old raw line")
    p_edit.add_argument("--b64-text", type=str, default="", help="Base64 encoded new text")
    p_edit.add_argument("--raw", type=str, default="", help="Old raw clipboard line")
    p_edit.add_argument("--text", type=str, default=None, help="New text content")

    p_copy = subparsers.add_parser("copy")
    p_copy.add_argument("--b64", type=str, default="", help="Base64 encoded raw line")
    p_copy.add_argument("--raw", type=str, default="", help="Raw clipboard line")

    p_del = subparsers.add_parser("delete")
    p_del.add_argument("--b64", type=str, default="", help="Base64 encoded raw line")
    p_del.add_argument("--raw", type=str, default="", help="Raw clipboard line")

    subparsers.add_parser("wipe")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "decode":
        cmd_decode(args)
    elif args.command == "edit":
        cmd_edit(args)
    elif args.command == "copy":
        cmd_copy(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "wipe":
        cmd_wipe(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
