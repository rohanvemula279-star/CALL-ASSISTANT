#!/usr/bin/env python3
"""AGI entry point used inside the Asterisk dialplan.

Example dialplan use:
    exten => s,n,AGI(agi://127.0.0.1/ai_agi.py?op=transcribe&path=/var/lib/asterisk/ai/x.wav)

Reads AGI environment variables, optionally POSTs the recorded audio
to the FastAPI /transcribe endpoint, and returns the transcript via
the AGI `SET VARIABLE` mechanism (so the dialplan can pick it up).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def agi_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            break
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        env[k.strip()] = v.strip()
    return env


def send(command: str) -> None:
    sys.stdout.write(f"{command}\n")
    sys.stdout.flush()


def set_variable(name: str, value: str) -> None:
    escaped = value.replace("\n", " ").replace("\r", " ")
    send(f'SET VARIABLE "{name}" "{escaped}"')
    _read_status()


def get_variable(name: str) -> str:
    send(f'GET VARIABLE "{name}"')
    return _read_status() or ""


def _read_status() -> str:
    line = sys.stdin.readline().strip()
    # Lines look like: "200 result=1 ..."
    return line


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_file(url: str, path: Path) -> dict:
    boundary = "----agi-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{path.name}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    env = agi_env()
    send("ANSWER")

    # Query string: ai_agi.py?op=transcribe&path=...
    request_url = env.get("agi_request", "") or env.get("agi_arg_1", "")
    parsed = urllib.parse.urlparse(request_url)
    qs = urllib.parse.parse_qs(parsed.query)
    op = qs.get("op", ["transcribe"])[0]

    app = os.environ.get("AIAPP_URL", "http://app:8000")

    if op == "transcribe":
        path = Path(qs["path"][0])
        result = post_file(f"{app}/transcribe", path)
        set_variable("TRANSCRIPT", result.get("text", ""))
    elif op == "chat":
        text = qs.get("text", [""])[0]
        call_id = qs.get("call_id", ["agi"])[0]
        caller = env.get("agi_callerid", "")
        result = post_json(f"{app}/chat", {
            "call_id": call_id,
            "caller": caller,
            "message": text,
        })
        set_variable("REPLY_TEXT", result.get("reply", ""))
    elif op == "speak":
        text = qs.get("text", [""])[0]
        result = post_json(f"{app}/speak", {"text": text})
        set_variable("REPLY_URL", result.get("audio_path", ""))
    else:
        send("VERBOSE \"unknown op\" 1")

    send("HANGUP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
