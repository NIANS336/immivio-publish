"""One bounded, cancellable audio/ASR/translation pipeline per playback epoch."""
import asyncio
import contextlib
import logging
import os
import subprocess
import time
from urllib.parse import quote

import aiohttp

from .translation import clean_translation, translate


def decoder_args(config, url, audio_index, start_ms):
    """FFmpeg command for one playback epoch: 16 kHz mono PCM, loudness lifted.

    The loudness filter is what makes quiet dialogue survive VAD. Resample runs
    first because a trailing filter may otherwise change the sample rate the ASR
    was told to expect (loudnorm silently rescales to 192 kHz).
    """
    filters = ["aresample=16000"]
    if config.dialogue_filter:
        filters.append(config.dialogue_filter)
    return [config.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rw_timeout", "20000000", "-protocol_whitelist", "http,tcp",
            "-ss", str(start_ms / 1000), "-i", url, "-map", f"0:a:{audio_index}",
            "-vn", "-sn", "-dn", "-af", ",".join(filters),
            "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"]


class Pipeline:
    def __init__(self, http, config, send, nonce, epoch, path, start_ms, audio_index=0):
        self.http, self.config, self.send = http, config, send
        self.epoch, self.path = epoch, path
        self.start_ms = max(0, start_ms - 160)
        self.position_ms = start_ms
        self.audio_index = audio_index
        self.nonce = nonce
        self.queue = asyncio.Queue(maxsize=3)
        self.process = None
        self.decoded_ms = self.start_ms
        self.previous = ""
        self.stats = {"phase": "starting", "recognized": 0, "translated": 0,
                      "partial_updates": 0, "last_start_ms": 0, "last_end_ms": 0}

    async def emit(self, message):
        await self.send({**message, "epoch": self.epoch})

    async def run(self):
        try:
            self.stats["phase"] = "reading_audio"
            await self.emit({"type": "status", "message": "正在读取音轨"})
            async with self.http.ws_connect(self.config.asr_url, heartbeat=20,
                                            max_msg_size=65536) as asr:
                ready = await asr.receive_json(timeout=10)
                if ready.get("type") != "ready":
                    raise RuntimeError("ASR is not ready")
                # Per-connection VAD only; the shared ASR keeps its own defaults.
                # threshold 0.5 drops lines whose speech probability sinks under the
                # music bed, so soft dialogue never reaches the recogniser.
                await asr.send_json({"type": "configure", "silence_ms": 220,
                                     "min_speech_ms": 1000,
                                     "max_speech_s": self.config.segment_seconds,
                                     "threshold": self.config.vad_threshold})
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(self.feed(asr))
                    tasks.create_task(self.receive(asr))
                    tasks.create_task(self.translations())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.stats["phase"] = "error"
            logging.warning("Subtitle pipeline stopped (%s)", type(exc).__name__)
            # Do not log upstream URLs, credentials, signed links, or dialogue.
            await self.emit({"type": "error", "message": "AI 字幕连接中断，请关闭后重开 AI 字幕"})
        finally:
            await self.close_process()

    async def close_process(self):
        if self.process:
            if self.process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    self.process.kill()
            # wait() can deadlock with a full stdout pipe, even after kill().
            # communicate() drains the pipe so cancellation can release the slot.
            await asyncio.wait_for(self.process.communicate(), timeout=5)

    async def feed(self, asr):
        url = f"http://127.0.0.1:{self.config.port}/media/{self.nonce}" + quote(self.path, safe="/")
        args = decoder_args(self.config, url, self.audio_index, self.start_ms)
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, **options)
        sent = 0
        while True:
            while (self.start_ms + sent / 32 > self.position_ms + self.config.ahead_ms
                   or self.queue.qsize() >= 2):
                await asyncio.sleep(0.05)
            data = await self.process.stdout.read(1024)
            if not data:
                break
            await asr.send_bytes(data)
            sent += len(data)
            self.decoded_ms = self.start_ms + sent // 32
            self.stats["phase"] = "streaming"
            # At most 4x real time; prevents overrunning the ASR's four-segment queue.
            await asyncio.sleep(len(data) / 32000 / 4)
        code = await self.process.wait()
        if code:
            raise RuntimeError("remote audio decode failed")
        await asr.send_json({"type": "flush"})

    async def receive(self, asr):
        async for message in asr:
            if message.type != aiohttp.WSMsgType.TEXT:
                raise RuntimeError("ASR disconnected")
            item = message.json()
            kind = item.get("type")
            if kind == "transcript" and item.get("text", "").strip():
                self.stats["recognized"] += 1
                await self.queue.put(item)
            elif kind == "error":
                raise RuntimeError("ASR returned an error")
            elif kind == "flushed":
                await self.queue.put(None)
                return
        raise RuntimeError("ASR disconnected")

    async def translations(self):
        while True:
            item = await self.queue.get()
            if item is None:
                await self.emit({"type": "status", "message": "字幕处理完成"})
                return
            start = self.start_ms + int(item["start_ms"])
            end = self.start_ms + int(item["end_ms"])
            if end < self.position_ms - 1500:
                continue
            cue = {"type": "cue", "id": int(item["utterance_id"]),
                   "start_ms": start, "end_ms": max(start + 1000, end),
                   "source": item["text"][:2000], "text": "", "final": False}
            began = time.monotonic()
            first_ms = None
            async for token in translate(self.http, self.config, cue["source"], self.previous):
                self.stats["partial_updates"] += 1
                cue["text"] += token
                if first_ms is None:
                    first_ms = round((time.monotonic() - began) * 1000)
                await self.emit(cue)
            cue["text"] = clean_translation(cue["text"])
            cue.update(final=True, first_token_ms=first_ms,
                       translation_ms=round((time.monotonic() - began) * 1000),
                       asr_ms=item.get("asr_ms"))
            await self.emit(cue)
            self.stats.update(translated=self.stats["translated"] + 1,
                              last_start_ms=start, last_end_ms=cue["end_ms"],
                              translated_chars=len(cue["text"]), first_token_ms=first_ms)
            self.previous = cue["source"]


async def cancel(task):
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
