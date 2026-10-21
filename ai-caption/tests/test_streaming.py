import asyncio
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import aiohttp
from aiohttp.test_utils import AioHTTPTestCase

from immivio_caption.config import Config, media_path, position
from immivio_caption.server import create_app
from immivio_caption.translation import sse_events


CONFIG = Config(token="a" * 40, webdav_base="https://dav.example.com",
                webdav_user="test", webdav_password="private", ffmpeg="unused")


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
