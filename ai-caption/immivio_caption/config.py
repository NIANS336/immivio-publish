"""Private runtime configuration; never embed WebDAV credentials in an APK."""
import json
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit


def media_path(value):
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 4096:
        raise ValueError("invalid media path")
    if any(c in value for c in ("\\", "\x00", "\r", "\n")):
        raise ValueError("invalid media path")
    if any(p in (".", "..") for p in value.split("/")) or value.startswith("//"):
        raise ValueError("invalid media path")
    return value


def position(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid position")
    if not math.isfinite(value) or not 0 <= value <= 7 * 86400_000:
        raise ValueError("invalid position")
    return round(value)


@dataclass(frozen=True)
class Config:
    token: str
    webdav_base: str
    webdav_user: str
    webdav_password: str
    ffmpeg: str
    bind: str = "0.0.0.0"
    port: int = 8773
    asr_url: str = "http://127.0.0.1:8765/ws/asr"
    translation_url: str = "http://127.0.0.1:8081/v1/chat/completions"
    model: str = "Ternary-Bonsai-2-9B-Q2_0.gguf"
    ahead_ms: int = 12000
    segment_seconds: float = 3.0
    # Soft dialogue sinks under the music bed, so Silero scores it below its 0.5
    # default and the line dies before recognition. Lift quiet passages towards
    # the local average and lower the speech threshold of this connection only.
    dialogue_filter: str = "dynaudnorm=f=200:g=15"
    vad_threshold: float = 0.3
    # llama.cpp has no server-side system prompt, so the translator persona is set
    # per request here. Empty means the built-in default persona.
    system_prompt: str = ""
    # Sent on every request, so it overrides the llama.cpp server's --temp default.
    # 0.7 measured least stiff for this persona; drop towards 0.1 for literal output.
    translation_temperature: float = 0.7

    @classmethod
    def load(cls, path):
        config = cls(**json.loads(Path(path).read_text(encoding="utf-8-sig")))
        base = urlsplit(config.webdav_base)
        if base.scheme != "https" or not base.hostname or base.username or base.password:
            raise ValueError("WebDAV requires an HTTPS origin without URL credentials")
        if base.query or base.fragment or len(config.token) < 32:
            raise ValueError("invalid private configuration")
        if not 4000 <= config.ahead_ms <= 30000 or not 1 <= config.segment_seconds <= 5:
            raise ValueError("invalid streaming limits")
        if not 0.1 <= config.vad_threshold <= 0.95:
            raise ValueError("invalid vad_threshold")
        if any(c in config.dialogue_filter for c in ('"', "'", "`", "$", ";", "\n", "\r")):
            raise ValueError("invalid dialogue_filter")
        if len(config.system_prompt) > 2000:
            raise ValueError("system_prompt is too long for the translation context")
        if not 0 <= config.translation_temperature <= 1.5:
            raise ValueError("invalid translation_temperature")
        return config

    def media_url(self, path):
        return self.webdav_base.rstrip("/") + quote(media_path(path), safe="/")
