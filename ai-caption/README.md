# Immivio LAN AI subtitles

此分支基于保留 WebDAV 的 Immivio v0.9.3。Quest 播放远程影片；Windows 独立读取同一 WebDAV 文件的音轨，16 kHz 单声道 PCM 连续送入现有 ASR，短句送入 llama.cpp 的流式翻译接口。译文的每个增量通过 WebSocket 返回，复用播放器原有的平面/VR180/VR360 字幕图层。

## 流式与时间同步

- ASR 是连续音频输入、VAD 短句输出，**不是逐字 ASR 假设**。本服务的连接使用 220 ms 静音、最多 3 秒分句，既有 ASR 的全局设置不变。现有 ASR 的最短语音限制是 1 秒，更短的独立感叹词可能漏掉。
- llama.cpp 使用 `stream: true`，每个 SSE 文本增量立即回传，不等待整句生成。字幕按照片中起止时间显示，尚未播到的结果会暂存。
- Windows 最多提前读取 12 秒音轨；不会保存整部影片。远程服务器是否支持 Range、容器布局和网络速度会影响开播、跳转后的等待及实际流量。
- 暂停时停止推进预读窗口；切片、切音轨、拖动进度和重连均取消旧任务并增加 epoch，旧结果不能进入新画面。不会暂停电影等翻译，也不保证开播/跳转零延迟。
- 连接断开时先释放连接名额，再回收音轨任务；回收 FFmpeg 同时排空输出管道，避免已断开的旧连接占满名额、使头显反复收到 503。
- 当前仅对私有配置指定的 WebDAV 挂载启用。字幕菜单的“AI 中文字幕”可随时关闭，关闭后恢复原字幕显示。

## Windows 运行

使用独立 Python 3.11+ 虚拟环境，安装 `requirements.txt` 和可用的 FFmpeg（部署使用 `imageio-ffmpeg==0.6.0` 的独立二进制）。复制 `config.example.json` 为 `config.private.json`，填入自己的地址和凭据。不要提交该私有文件。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt imageio-ffmpeg==0.6.0
.venv\Scripts\python.exe -m immivio_caption --config config.private.json
```

默认仅新增 8773 端口；8765 ASR 和 8081 翻译服务需已运行。本服务不启停、修改或重新加载它们。防火墙只向所需局域网地址开放 8773。`GET /health` 检查桥接进程；它不代表上游模型可用，实际验收要播放带人声的影片。

部署后的无窗口入口是 `control.ps1 -Action Start|Stop|Status`，只控制 `Immivio-AI-Captions` 手动计划任务，无开机/登录触发器。日志在 `logs/service.log`，不记录账户、影片路径或台词。Windows 登录后若未启动该桥接，可运行 Start。

FFmpeg 只访问本服务的回环 Range 代理；WebDAV 密码不进入 FFmpeg 参数或 APK。代理只接受回环连接和随机令牌；向 WebDAV 源提供 Basic 认证，跨域重定向由 aiohttp 去除认证。

`GET /status` 使用与字幕连接相同的 Bearer 鉴权，报告当前播放/预读时间、识别段数、完成翻译段数和增量次数。它不包含台词、影片路径或账号；用来区分连接失败、等待音频、译文已到但尚未到显示时间。

## Quest 私有配置

`user://ai_subtitles.private.json` 保存播放器的服务器地址、随机令牌、挂载 ID 与开关。示例：

```json
{"server":"ws://192.168.1.10:8773/subtitles","token":"same-private-token-as-server","mount_id":"webdav-account-uuid","enabled":true}
```

调试安装支持通过 ADB `run-as` 写入应用私有目录。一次性 `user://ai_bootstrap.private.json` 可包含 `webdav: {name, base, username, password}`，播放器通过既有账户 API 保存到原生加密账户库，随后删除一次性文件。不要将这些文件放入 `res://` 或 APK。服务端私有配置和签名密钥均不提交。

## 验证

```sh
python -m unittest discover -s tests -v
```

回归涵盖路径/时间校验、SSE 增量边界、鉴权、旧会话取消与上游错误。真机还需确认选中的音轨与声音一致、跳转后不串句，以及 VR 投影下的位置、中文字体和网络延迟。该分支新增的脚本与服务源代码沿用仓库许可证。

## 本地 APK 构建

新增代码只有 GDScript 和独立 Windows 服务，原生播放器未改。`tools/build_ai_apk.py` 使用匹配的 Godot 4.7.2 编译修改过的字幕和媒体库脚本，以 v0.9.3 Quest APK 为原生基底，更新 sparse PCK 索引，使用 apktool 2.12.1 重新打包并以私有密钥签名。脚本逐项验证原 APK 的所有 DEX 和 ELF 内容未变；无需重新构建 OpenList、FFmpeg 或 libmpv。

参数：`--base-apk --godot --apktool --java-home --build-tools --keystore --out --work-dir`。这些参数都是本机路径，签名密码由环境变量 `IMMIVIO_KEYSTORE_PASSWORD` 提供。APK 名称为 Immivio AI，版本为 0.9.3-ai.3，保留应用 ID `com.wapok.thru3d`，启用调试仅用于 ADB 私有配置。保留签名密钥才能以后覆盖更新。不同发行方签名不能互相覆盖。构建同时更新字幕 shader include 及其 sparse PCK 索引，确保新的双眼偏移进入 APK。

所有 Android 语言资源中的应用名均为 Immivio AI（包括 zh-CN）。侧载应用从 Quest 应用库的“未知来源”打开。SMB 播放沿用原播放器的账户库；当前头显已添加 Windows 共享入口，具体共享目录在该入口下选择。AI 音轨读取目前针对所配置的 WebDAV，SMB 的 AI 音轨读取尚未接入。

字幕时间线回归可使用匹配 Godot 执行：`--headless --xr-mode off --path app/godot --script res://tests/ai_subtitle_timeline_test.gd`。桌面无头运行必须关闭 XR，避免 OpenXR 等待头显。

文件夹封面回归：设置环境变量 `IMMIVIO_TEST_DIR` 为工作区临时目录，再运行同样的无头命令，将脚本改为 `res://tests/folder_cover_test.gd`。覆盖升级补齐、最近子视频选择、跨账户隔离、编码文件夹名称、与最近播放共用同一纹理、重启保存，以及清除历史。
