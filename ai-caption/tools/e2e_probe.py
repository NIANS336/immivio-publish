"""Smoke probe for the subtitle bridge: play a real WebDAV file, count final cues.

Run it on the Windows bridge host. It registers as a subtitle client, sends
`clock` messages like the headset does, and prints every final cue, so a
loudness/threshold change can be compared on the same audio track.

    .venv\\Scripts\\python.exe tools\\e2e_probe.py [seconds] [config] [media path]

Only one subtitle client fits at a time: stop the headset's AI subtitles first.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.private.json"
DEFAULT_MEDIA = "/PikPak Tutorial.mp4"


async def main():
    window = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
    config_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CONFIG
    media = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MEDIA
    settings = json.loads(config_path.read_text(encoding="utf-8-sig"))
    token, port = settings["token"], settings.get("port", 8773)
    url = f"http://127.0.0.1:{port}/subtitles"
    finals, partials = 0, 0
    async with aiohttp.ClientSession() as http:
        async with http.ws_connect(url, headers={"Authorization": "Bearer " + token},
                                   heartbeat=20, max_msg_size=65536) as ws:
            print("ready", await ws.receive_json(), flush=True)
            await ws.send_json({"type": "start", "epoch": 1, "path": media, "position_ms": 0})
            began = time.monotonic()

            async def clock():
                while True:
                    elapsed = time.monotonic() - began
                    if elapsed >= window:
                        return
                    await ws.send_json({"type": "clock", "epoch": 1,
                                        "position_ms": round(elapsed * 1000)})
                    await asyncio.sleep(0.25)

            ticker = asyncio.ensure_future(clock())
            try:
                while time.monotonic() - began < window:
                    try:
                        item = await asyncio.wait_for(ws.receive_json(), 20)
                    except asyncio.TimeoutError:
                        continue
                    except Exception as exc:
                        print("recv stop", type(exc).__name__, flush=True)
                        break
                    kind = item.get("type")
                    if kind == "cue" and item.get("final"):
                        finals += 1
                        print("cue", item.get("start_ms"), item.get("end_ms"),
                              repr(item.get("source", ""))[:36], "->", item.get("text"), flush=True)
                    elif kind == "cue":
                        partials += 1
                    elif kind == "status":
                        print("status", item.get("message"), flush=True)
                    elif kind == "error":
                        print("ERROR", item, flush=True)
                        break
            finally:
                ticker.cancel()
    print(json.dumps({"seconds": round(time.monotonic() - began, 1), "final_cues": finals,
                      "partial_updates": partials, "vad_note": "check GET /status"},
                     ensure_ascii=False), flush=True)


asyncio.run(main())
