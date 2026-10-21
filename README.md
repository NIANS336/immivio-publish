<p align="center"><img src="website/assets/icon.png" width="88" alt="Immivio icon"></p>

# Immivio

### ✨ 本分支特色：AI 实时字幕翻译（可自定义接入任意 AI 模型）

在免费开源的 VR 播放器基础上，新增一条**局域网 AI 实时字幕流水线**：头显播放 WebDAV 影片的同时，桥接服务独立读取同一文件的音轨，经 ASR 语音识别后送入大模型流式翻译，译文逐字增量实时回传头显，复用播放器原有的平面 / VR180 / VR360 字幕图层——看生肉终于不用等熟肉了。

- **自定义接入 AI 模型**：翻译端只要暴露 OpenAI 兼容接口（`/v1/chat/completions`）即可，llama.cpp、Ollama、vLLM、LM Studio 或任何云端 API 都能接，换个地址和模型名就能跑；
- **可自定义翻译人设**：内置口语化中性中文字幕默认人设，私有配置 `system_prompt` 非空即可整段替换成自己的提示词；小模型防跑偏护栏（单行截断、复读防护、引号剥离）开箱即用；
- **轻声台词也能认**：FFmpeg 响度增益 + 按连接调低的 VAD 阈值，背景音乐下的软台词不再整句丢失；
- **隐私设计**：凭据只存本机私有配置，日志不记录台词、影片路径与账号；
- 附带沉浸式字幕双眼合像校准、文件夹封面显示最后播放缩略图等改进。

部署与架构详见 [AI 字幕说明](ai-caption/README.md)。本分支为自行签名的构建版本；安装前确认不会覆盖不同签名的已有版本。

文件夹封面：WebDAV、SMB 和可识别文件路径的本地文件夹，会显示该文件夹内最后播放视频的已有缩略图，与“最近播放”使用同一张图片。子目录的视频也更新祖先目录封面；升级时会从现有最近播放记录补齐。封面引用保存在应用私有目录，最多 256 个文件夹，不额外读取或解码视频；清空历史/缓存会清除封面引用，图片缓存被淘汰时恢复文件夹图标。关闭历史记录后不新增封面记录。

沉浸式字幕双眼校准：在 VR180、VR360、鱼眼视频的“字幕”弹窗底部选择“字幕双眼校准”，用“字幕水平合像”“字幕垂直合像”分别调整两眼字幕的相对偏移（±10°，步进 0.05°）。拖动实时预览，释放后保存，下次启动沿用；“重置字幕校准”将两项归零。每眼移动总偏移的一半，字幕中心不变，影片原有 IPD/上下对齐与字幕距离、位置保持独立。AI 字幕和原有文字字幕共用此校准；普通平面字幕仍使用原有屏幕字幕层。

### Free, open-source VR video player for Meta Quest and PICO

**VR180 · VR360 · 3D · Spatial Video · Photos**

Immivio is a **free, open-source VR video and spatial media player** for standalone Android XR headsets. No player purchase or subscription is required.

Watch VR180, 360° and 3D side-by-side (SBS) videos and supported spatial photos on Meta Quest, PICO, or a compatible Android OpenXR headset. Choose a virtual cinema screen or an immersive projection, connect your NAS or media library, and keep playback controls within reach.

**Designed for high-performance playback:** libmpv uses Android hardware video decoding where supported, with shared GPU textures for rendering and adjustable display quality. Actual performance depends on headset, codec, resolution and bitrate.

Immivio 是面向 Meta Quest 与 PICO 的免费开源 VR 视频播放器，支持 VR180、360° 全景、3D 左右立体视频与空间照片，提供硬件解码、GPU 渲染，以及 SMB、WebDAV、DLNA 网络媒体库访问。[查看中文官网](https://northboundwisdom.github.io/immivio/zh/)。

[Website](https://northboundwisdom.github.io/immivio/) · [Releases](https://github.com/NorthBoundWisdom/immivio/releases) · [Development builds](https://github.com/NorthBoundWisdom/immivio/actions/workflows/android-release.yml) · [User guide](https://northboundwisdom.github.io/immivio/guide/) · [中文官网与使用指南](https://northboundwisdom.github.io/immivio/zh/)

Immivio continues development of [zerochocobo/Thru3D-Media-Player](https://github.com/zerochocobo/Thru3D-Media-Player). **Version 0.6.0 is the last shared baseline. From that point, this project follows its own development and release path, independently maintained by NorthBoundWisdom.** The original source history, attribution and GPL-3.0 license are preserved.

## Your media, all around you

![The playback interface displaying the supplied VR180 stereo video](website/assets/screenshots/playback.png)

*Actual Android emulator capture using `blandscape-60mbps.mp4`, recorded before the Immivio rename. The 2D diagnostic view demonstrates the interface, not headset stereoscopy, passthrough or frame rate. The original video is not bundled. Current playback controls use toolbar popups; these captures predate that layout.*

| Playback settings | Display preferences |
| --- | --- |
| ![Playback settings](website/assets/screenshots/settings.png) | ![Display preferences](website/assets/screenshots/display.png) |

- **Watch flat or immersive media.** Flat screens, VR180, VR360 and fisheye projections; side-by-side and top-bottom stereo layouts, including half-width/half-height formats.
- **Free and open source.** Download, use and build the player under GPL-3.0; third-party services follow their own terms and may have their own fees.
- **Bring your own library.** Local files, SMB, WebDAV, DLNA, supported media servers and cloud sources. Available operations depend on the source and your account permissions.
- **Get comfortable.** Move the picture and panels, adjust supported screen size/distance/curvature, and use reclining mode or head-follow when you want them.
- **Keep control.** Compact playback popups with slider resets, subtitles, playback speed, per-video audio/subtitle timing, automatic queue advance and optional shuffle.
- **Return to familiar settings.** Remembered per-video track choices and stereo alignment, system-controlled volume, and full filename hover tips.
- **Explore photos.** Single images, side previews, 1–3-row photo walls and memory fragments. HEIF photo decoding depends on the Android device and source format.

Immivio has **one playback edition**. It displays existing stereo/spatial content; it does not generate 3D from 2D. The earlier live AI depth, person-matting, model preparation and inference features have been removed.

## Download and install

Use [Releases](https://github.com/NorthBoundWisdom/immivio/releases) for published APKs. Current development packages are under a successful [Android workflow run](https://github.com/NorthBoundWisdom/immivio/actions/workflows/android-release.yml) → **Artifacts**; GitHub sign-in is required for those artifacts. Releases from before the rename retain their historical names and behavior.

Choose an APK matching your headset:

| Device | Artifact name |
| --- | --- |
| Meta Quest | `Immivio-QUEST-<version>-<debug-or-release>-<date>.apk` |
| PICO | `Immivio-PICO-<version>-<debug-or-release>-<date>.apk` |
| Compatible Android OpenXR runtime | `Immivio-OpenXR-<version>-<debug-or-release>-<date>.apk` — experimental |

1. Enable developer mode on your headset, connect it to your computer, and approve USB debugging.
2. Install the matching APK with your preferred sideloading tool. Source ZIP/TAR archives are not installable apps.
3. Launch **Immivio** from the headset's sideloaded-app library.
4. Open a local file or add a network source, granting only the access you want to use.
5. Match the projection and stereo layout to the file. For VR180 SBS fisheye content, choose **Fisheye + SBS**.

Quest 2 and PICO Neo3 are compatibility targets. Actual performance depends on headset, codec, bitrate and resolution. The generic OpenXR build needs a compatible Android runtime.

## Everyday controls

| Action | How |
| --- | --- |
| Show or hide playback controls | Left Menu button, or tap the picture with the trigger |
| Select a control | Controller ray + trigger; supported hand pointing/pinching also works |
| Move the picture or library window | Hold grip; use the same hand's thumbstick for distance where supported |
| Seek | Drag the timeline or use horizontal thumbstick shortcuts while lists/sliders are inactive |
| Change volume | Use the headset’s system volume controls |
| Scroll a library or settings list | Use the thumbstick while the list is open |
| Return to the library | Choose **Close video** |
| Watch while reclined | **Settings → General → Reclining mode**; Follow is a separate setting |

The interface supports English, Simplified Chinese, Traditional Chinese and Japanese. Text subtitles offer five color palettes. Color grading offers Original, Warm, Cool and Custom presets, with individual slider resets and a reset for the current popup page. Subtitle, timing, eye-alignment and photo sliders also reset independently. See the [user guide](https://northboundwisdom.github.io/immivio/guide/) for sources, layouts, timing and queues.

## Useful answers

**What happened to AI / No AI editions?** Immivio is a single media player with no model-based conversion or person matting. Existing stereo video and native spatial formats are separate from those removed features.

**Will Immivio update my existing app?** The ordinary player's application ID and signing identity are retained to preserve its data. Android still requires matching signing keys; builds from other distributors or ephemeral CI keys may not update one another. Check the package notes before replacing an installation.

**Which subtitle and spatial formats are supported?** Text subtitle tracks and ordinary packed SBS/TB video are supported. Bitmap subtitles are not offered; MV-HEVC dual-view video and Dolby Vision colour correctness require separate device/media validation. See [playback libraries and formats](docs/BUILD.md#playback-libraries-and-formats).

**Will every 8K video play smoothly?** Codec, bitrate, projection and hardware all matter. An emulator screenshot is not a headset benchmark.

**Where do I report a problem?** Use [this repository's Issues](https://github.com/NorthBoundWisdom/immivio/issues). Include headset, build version, media format and reproduction steps. Share a sample only if you may distribute it; keep credentials and private media out of public reports.

## Project and development

- Store listing name: **Immivio – VR & Spatial Media Player**
- [Changelog](CHANGELOG.md) · [Release notes / 更新说明](https://northboundwisdom.github.io/immivio/updates/)
- [Build from source](docs/BUILD.md) · [Architecture](docs/ARCHITECTURE.md) · [Refactor plan](docs/REFACTOR_PLAN.md) · [Testing](docs/TESTING.md) · [Refactor acceptance](docs/ACCEPTANCE.md) · [Contributing](CONTRIBUTING.md)
- Project source is [GPL-3.0-only](LICENSE). Third-party components retain their licenses, including the embedded OpenList component's AGPL-3.0 obligations. See [licensing details](docs/LICENSING.md).

[**Ravo Studio**](https://northboundwisdom.github.io/Ravo/) — organize, review and develop photographs.

[**SonaFolio**](https://northboundwisdom.github.io/sonafolio/) — turn podcasts and media into transcripts and a local knowledge library.
