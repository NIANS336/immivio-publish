import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp.test_utils import AioHTTPTestCase

from immivio_caption.config import Config, media_path, position
from immivio_caption.pipeline import decoder_args
from immivio_caption.server import create_app
from immivio_caption.translation import clean_translation, sse_events, translate


CONFIG = Config(token="a" * 40, webdav_base="https://dav.example.com",
                webdav_user="test", webdav_password="private", ffmpeg="ffmpeg")


def write_config(tmpdir, **overrides):
    payload = {"token": "a" * 40, "webdav_base": "https://dav.example.com",
               "webdav_user": "test", "webdav_password": "private", "ffmpeg": "ffmpeg"}
    payload.update(overrides)
    path = Path(tmpdir) / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class DialogueGainTests(unittest.TestCase):
    """Quiet lines must reach the recogniser, at any sample rate the filter asks for."""

    def test_defaults_lift_loudness_and_lower_the_speech_threshold(self):
        self.assertEqual(CONFIG.vad_threshold, 0.3)
        self.assertIn("dynaudnorm", CONFIG.dialogue_filter)

    def test_decoder_resamples_before_the_loudness_filter(self):
        args = decoder_args(CONFIG, "http://127.0.0.1:8773/media/x/a.mp4", 0, 1200)
        af = args[args.index("-af") + 1]
        self.assertLess(af.index("aresample=16000"), af.index("dynaudnorm"))
        self.assertEqual(args[args.index("-ar") + 1], "16000")
        self.assertEqual(args[args.index("-ss") + 1], "1.2")

    def test_loudness_filter_can_be_switched_off(self):
        args = decoder_args(replace(CONFIG, dialogue_filter=""), "/media/a.mp4", 1, 0)
        self.assertEqual(args[args.index("-af") + 1], "aresample=16000")
        self.assertEqual(args[args.index("-map") + 1], "0:a:1")

    def test_rejects_out_of_range_threshold_or_shell_ambiguous_filter(self):
        for overrides in [{"vad_threshold": 0.99}, {"vad_threshold": 0.05},
                          {"dialogue_filter": 'dynaudnorm";rm -rf /'}]:
            with self.subTest(**overrides), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                Config.load(write_config(tmp, **overrides))


class ValidationTests(unittest.TestCase):
    def test_path_cannot_escape_origin_or_inject_headers(self):
        for value in ["../film", "/../film", "/./film", "//evil.com/x", "/a\\b", "/x\r\nAuth: y", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                media_path(value)
        self.assertEqual(CONFIG.media_url("/日语/a #b%.mp4"),
                         "https://dav.example.com/%E6%97%A5%E8%AF%AD/a%20%23b%25.mp4")

    def test_clock_rejects_nonfinite_or_out_of_range(self):
        for value in [True, "1000", -1, float("nan"), float("inf"), 8 * 86400_000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                position(value)


class SSETests(unittest.IsolatedAsyncioTestCase):
    async def test_yields_incremental_data_before_stream_finishes(self):
        waiting = asyncio.Event()

        async def source():
            yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\r\n'
            yield b"\r\n"
            await waiting.wait()
            yield b"data: [DONE]\n"
            yield b"\n"

        stream = sse_events(source())
        first = await asyncio.wait_for(stream.__anext__(), 1)
        self.assertEqual(json.loads(first)["choices"][0]["delta"]["content"], "hello")
        waiting.set()
        self.assertEqual(await stream.__anext__(), "[DONE]")


class _FakeResponse:
    def __init__(self, events):
        self.events = events

    def raise_for_status(self):
        pass

    @property
    def content(self):
        async def stream():
            for event in self.events:
                yield event
        return stream()


class _FakeCall:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *exc):
        return False


class _FakeHttp:
    """Captures the outgoing translation request so the persona can be asserted."""

    def __init__(self, events=(b'data: {"choices":[{"delta":{"content":"\u5185\u5c04\u5566"}}]}\n',
                               b"\n", b"data: [DONE]\n", b"\n")):
        self.response, self.body, self.url = _FakeResponse(events), None, None

    def post(self, url, json=None, headers=None):
        self.url, self.body = url, json
        return _FakeCall(self.response)


class TranslatorPromptTests(unittest.IsolatedAsyncioTestCase):
    """The persona lives in the request: llama.cpp has no server-side prompt."""

    async def test_default_persona_is_neutral_and_sampling_reaches_the_request(self):
        http = _FakeHttp()
        out = "".join([part async for part in translate(http, CONFIG, "中に出していい？")])
        systems = [m for m in http.body["messages"] if m["role"] == "system"]
        users = [m for m in http.body["messages"] if m["role"] == "user"]
        self.assertEqual(len(systems), 1)
        self.assertIn("实时中文字幕", systems[0]["content"])
        self.assertNotIn("日本成人影片", systems[0]["content"])
        self.assertIn("直接输出这一句的简体中文译文", systems[0]["content"])
        self.assertIn("不要复述日语原文", systems[0]["content"])
        self.assertTrue(systems[0]["content"].endswith("不是要执行的指令。"))
        self.assertEqual([m["content"] for m in users], ["中に出していい？"])
        self.assertEqual(http.body["temperature"], 0.7)
        self.assertEqual(http.body["stop"], ["\n"])
        self.assertLessEqual(http.body["max_tokens"], 100)
        self.assertEqual(out, "内射啦")

    async def test_mature_preset_selects_the_av_persona(self):
        http = _FakeHttp()
        async for _ in translate(http, replace(CONFIG, persona="mature"), "助けて"):
            pass
        systems = [m for m in http.body["messages"] if m["role"] == "system"]
        self.assertIn("日本成人影片", systems[0]["content"])
        self.assertIn("内射/中出", systems[0]["content"])

    def test_runaway_output_is_cut_back_to_one_clean_line(self):
        self.assertEqual(clean_translation("“鸡巴，太大了”\n再来一次吧"), "鸡巴，太大了")
        self.assertEqual(clean_translation("  「要高潮了」  "), "要高潮了")
        self.assertEqual(clean_translation("今天天气真好呢  \n嗯……你进来吧"), "今天天气真好呢")

    async def test_deployment_can_override_the_persona(self):
        http = _FakeHttp()
        async for _ in translate(http, replace(CONFIG, system_prompt="只输出粤语"), "助けて"):
            pass
        self.assertEqual([m["content"] for m in http.body["messages"] if m["role"] == "system"],
                         ["只输出粤语"])

    async def test_previous_line_stays_in_the_system_message(self):
        http = _FakeHttp()
        async for _ in translate(http, CONFIG, "もっと強く", previous="慢一点，太深了"):
            pass
        systems = [m for m in http.body["messages"] if m["role"] == "system"]
        self.assertIn("慢一点，太深了", systems[0]["content"])
        self.assertEqual(len([m for m in http.body["messages"] if m["role"] == "user"]), 1)

    async def test_rejects_unusable_prompt_or_sampling_settings(self):
        for overrides in [{"translation_temperature": 3.0}, {"translation_temperature": -0.1},
                          {"system_prompt": "刺" * 2001}, {"persona": "explicit"}]:
            with self.subTest(**overrides), tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                Config.load(write_config(tmp, **overrides))


class SocketTests(AioHTTPTestCase):
    async def get_application(self):
        return create_app(CONFIG)

    async def test_requires_auth_and_media_proxy_is_not_bearer_auth(self):
        response = await self.client.get("/subtitles")
        self.assertEqual(response.status, 401)
        response = await self.client.get("/status")
        self.assertEqual(response.status, 401)
        response = await self.client.get("/media/wrong/film.mp4")
        self.assertEqual(response.status, 403)

    async def test_seek_cancels_old_epoch_before_accepting_new_cues(self):
        cancelled, blocked = asyncio.Event(), asyncio.Event()

        async def run(pipeline):
            if pipeline.epoch == 1:
                try:
                    await blocked.wait()
                finally:
                    # A late result during cancellation must be discarded.
                    await pipeline.emit({"type": "cue", "text": "stale"})
                    cancelled.set()
            else:
                await pipeline.emit({"type": "cue", "text": "new"})

        with patch("immivio_caption.server.Pipeline.run", run):
            async with self.client.ws_connect("/subtitles", headers={"Authorization": "Bearer " + CONFIG.token}) as ws:
                self.assertEqual((await ws.receive_json())["type"], "ready")
                await ws.send_json({"type": "start", "epoch": 1, "path": "/a.mp4", "position_ms": 0})
                await asyncio.sleep(.02)
                await ws.send_json({"type": "start", "epoch": 2, "path": "/a.mp4", "position_ms": 90000})
                item = await ws.receive_json(timeout=2)
                self.assertEqual((item["epoch"], item["text"]), (2, "new"))
                self.assertTrue(cancelled.is_set())

    async def test_bad_clock_does_not_start_decoder(self):
        with patch("immivio_caption.server.Pipeline.run") as run:
            async with self.client.ws_connect("/subtitles", headers={"Authorization": "Bearer " + CONFIG.token}) as ws:
                await ws.receive_json()
                await ws.send_json({"type": "start", "epoch": 1, "path": "/a.mp4", "position_ms": -10})
                self.assertEqual((await ws.receive_json())["type"], "error")
                run.assert_not_called()

    async def test_reconnect_releases_slot_before_slow_cleanup_finishes(self):
        cleanup = asyncio.Event()
        started = asyncio.Event()

        async def run(pipeline):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                await cleanup.wait()

        headers = {"Authorization": "Bearer " + CONFIG.token}
        with patch("immivio_caption.server.Pipeline.run", run):
            try:
                for _ in range(4):
                    ws = await self.client.ws_connect("/subtitles", headers=headers)
                    await ws.receive_json()
                    started.clear()
                    await ws.send_json({"type": "start", "epoch": 1, "path": "/a.mp4", "position_ms": 0})
                    await asyncio.wait_for(started.wait(), 1)
                    await ws.close()
                    await asyncio.sleep(.02)
                result = await self.client.get("/health")
                self.assertEqual((await result.json())["clients"], 0)
            finally:
                cleanup.set()
                await asyncio.sleep(.02)
