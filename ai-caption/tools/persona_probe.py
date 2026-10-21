"""Print what the configured translation persona actually produces.

Run on the Windows bridge host, no server restart needed:

    .venv\\Scripts\\python.exe tools\\persona_probe.py out.json "台词一" "台词二"

With no lines it uses a built-in sample set. Writes UTF-8 JSON so the results
can be read back without console codepage damage.
"""
import asyncio
import json
import sys
from pathlib import Path

import aiohttp

from immivio_caption.config import Config
from immivio_caption.translation import (DEFAULT_SYSTEM_PROMPT, clean_translation,
                                         translate)

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ["ちょっと待って、今行くね", "これ、見て見て、すごいでしょう",
           "ほんと？うれしい、ありがとう", "気をつけて帰ってね",
           "今日はいい天気ですね"]


async def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("persona-probe.json")
    lines = sys.argv[2:] or SAMPLES
    config = Config.load(ROOT / "config.private.json")
    rows = []
    async with aiohttp.ClientSession() as http:
        for line in lines:
            raw = "".join([part async for part in translate(http, config, line)])
            rows.append({"source": line, "translation": clean_translation(raw),
                         "raw": raw})
            print("...", line, flush=True)
    out.write_text(json.dumps({"temperature": config.translation_temperature,
                               "persona": (config.system_prompt or DEFAULT_SYSTEM_PROMPT)[:60] + "…",
                               "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out, flush=True)


asyncio.run(main())
