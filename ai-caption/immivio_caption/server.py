"""LAN WebSocket endpoint and a loopback-only authenticated range relay."""
import asyncio
import hmac
import ipaddress
import logging
import secrets

import aiohttp
from aiohttp import web

from .config import media_path, position
from .pipeline import Pipeline, cancel


async def lifespan(app):
    timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_read=60)
    app["http"] = aiohttp.ClientSession(timeout=timeout, trust_env=False)
    yield
    for socket in list(app["sockets"]):
        await socket.close(code=1001, message=b"server shutdown")
    await app["http"].close()


async def health(request):
    return web.json_response({"service": "immivio-ai-caption", "protocol": 1,
                              "clients": len(request.app["sockets"]),
                              "asr": "continuous_pcm_short_segments",
                              "translation": "SSE_incremental"})


async def status(request):
    if not hmac.compare_digest(request.headers.get("Authorization", ""),
                               "Bearer " + request.app["config"].token):
        raise web.HTTPUnauthorized()
    return web.json_response({"pipelines": [
        {**p.stats, "epoch": p.epoch, "position_ms": p.position_ms,
         "decoded_ms": p.decoded_ms, "start_ms": p.start_ms}
        for p in request.app["pipelines"].values()]})


async def relay(request):
    if not ipaddress.ip_address(request.remote).is_loopback:
        raise web.HTTPForbidden()
    app = request.app
    if not hmac.compare_digest(request.match_info["nonce"], app["nonce"]):
        raise web.HTTPForbidden()
    config = app["config"]
    try:
        path = media_path("/" + request.match_info["path"])
    except ValueError:
        raise web.HTTPBadRequest() from None
    headers = {"Accept-Encoding": "identity"}
    for key in ("Range", "If-Range"):
        if key in request.headers:
            headers[key] = request.headers[key]
    auth = aiohttp.BasicAuth(config.webdav_user, config.webdav_password)
    try:
        async with app["http"].request(request.method, config.media_url(path),
                                        headers=headers, auth=auth,
                                        allow_redirects=True, max_redirects=5) as upstream:
            if upstream.status not in (200, 206, 416):
                raise web.HTTPBadGateway(text="Remote media unavailable")
            response_headers = {k: v for k, v in upstream.headers.items()
                                if k.lower() in ("content-type", "content-length", "content-range",
                                                 "accept-ranges", "last-modified", "etag")}
            response = web.StreamResponse(status=upstream.status, headers=response_headers)
            await response.prepare(request)
            if request.method != "HEAD":
                async for chunk in upstream.content.iter_chunked(65536):
                    await response.write(chunk)
            return response
    except (aiohttp.ClientError, asyncio.TimeoutError):
        raise web.HTTPBadGateway(text="Remote media unavailable") from None
    except (ConnectionResetError, BrokenPipeError):
        return response


async def subtitles(request):
    config = request.app["config"]
    supplied = request.headers.get("Authorization", "")
    if not hmac.compare_digest(supplied, "Bearer " + config.token):
        raise web.HTTPUnauthorized()
    request.app["sockets"].difference_update(s for s in list(request.app["sockets"]) if s.closed)
    if len(request.app["sockets"]) >= 2:
        raise web.HTTPServiceUnavailable()
    socket = web.WebSocketResponse(heartbeat=20, max_msg_size=16384)
    await socket.prepare(request)
    request.app["sockets"].add(socket)
    pipeline, task, current_epoch = None, None, 0
    send_lock = asyncio.Lock()

    async def send(item):
        if item.get("epoch") != current_epoch or socket.closed:
            return
        async with send_lock:
            await socket.send_json(item)

    try:
        await socket.send_json({"type": "ready", "protocol": 1})
        async for message in socket:
            if message.type != aiohttp.WSMsgType.TEXT:
                break
            try:
                item = message.json()
                if not isinstance(item, dict):
                    raise ValueError()
                kind = item.get("type")
                if kind == "start":
                    epoch = item.get("epoch")
                    if isinstance(epoch, bool) or not isinstance(epoch, int) or not current_epoch < epoch <= 2147483647:
                        raise ValueError()
                    path = media_path(item.get("path"))
                    start = position(item.get("position_ms"))
                    audio = item.get("audio_index", 0)
                    if isinstance(audio, bool) or not isinstance(audio, int) or not 0 <= audio < 64:
                        raise ValueError()
                    current_epoch = epoch  # Invalidate before awaiting cancellation.
                    await cancel(task)
                    pipeline = Pipeline(request.app["http"], config, send, request.app["nonce"],
                                        epoch, path, start, audio)
                    request.app["pipelines"][socket] = pipeline
                    task = asyncio.create_task(pipeline.run())
                elif kind == "clock" and pipeline and item.get("epoch") == current_epoch:
                    pipeline.position_ms = position(item.get("position_ms"))
                elif kind == "stop":
                    current_epoch += 1
                    await cancel(task)
                    pipeline, task = None, None
                    request.app["pipelines"].pop(socket, None)
                else:
                    raise ValueError()
            except (ValueError, TypeError, KeyError):
                await socket.send_json({"type": "error", "epoch": current_epoch,
                                        "message": "无效的字幕请求"})
    finally:
        request.app["sockets"].discard(socket)
        request.app["pipelines"].pop(socket, None)
        await cancel(task)
    return socket


def create_app(config):
    app = web.Application(client_max_size=16384)
    app["config"], app["nonce"], app["sockets"] = config, secrets.token_urlsafe(32), set()
    app["pipelines"] = {}
    app.cleanup_ctx.append(lifespan)
    app.router.add_get("/health", health)
    app.router.add_get("/status", status)
    app.router.add_get("/subtitles", subtitles)
    app.router.add_get("/media/{nonce}/{path:.*}", relay)
    return app


def run(config):
    # Access URLs can contain signed tokens. Keep request logging disabled.
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("aiohttp.server").disabled = True
    web.run_app(create_app(config), host=config.bind, port=config.port, access_log=None)
