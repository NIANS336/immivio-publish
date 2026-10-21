extends Node
## Bounded live cue buffer. No audio decoding or model inference on the headset.
const Bootstrap := preload("res://scripts/ai_subtitle_bootstrap.gd")
var enabled := false
var status := "AI 字幕已关闭"
var text := ""
var _host: WeakRef
var _bootstrap: RefCounted
var _socket: WebSocketPeer
var _cues: Dictionary = {}
var _epoch := 0
var _active_key := ""
var _connected := false
var _retry_at := 0
var _clock_at := 0
var _last_status := ""


func setup(owner: Node) -> void:
	_host = weakref(owner)
	_bootstrap = Bootstrap.new(owner.platform)
	enabled = bool(_bootstrap.config.get("enabled", false))


func set_enabled(value: bool) -> void:
	enabled = value
	_bootstrap.set_enabled(value)
	_disconnect()
	status = "正在连接 AI 字幕" if enabled else "AI 字幕已关闭"


func _process(_delta: float) -> void:
	if _host == null:
		return
	_bootstrap.poll()
	var host: Node = _host.get_ref()
	if not is_instance_valid(host):
		return
	var config: Dictionary = _bootstrap.config
	var prefix := "cloud://" + str(config.get("mount_id", "")) + "/"
	var supported: bool = not str(config.get("mount_id", "")).is_empty() and host.local_uri.begins_with(prefix)
	if not enabled or not supported or not host.media.accepts(host.media.session_id):
		if _socket != null:
			_disconnect()
		text = ""
		if enabled:
			status = _bootstrap.status if not _bootstrap.status.is_empty() else "请选择配置的 WebDAV 影片"
		return
	var now := Time.get_ticks_msec()
	if _socket == null:
		if now < _retry_at:
			return
		var endpoint := str(config.get("server", ""))
		if not endpoint.begins_with("ws://") and not endpoint.begins_with("wss://"):
			status = "请配置 AI 字幕服务器"
			return
		_socket = WebSocketPeer.new()
		_socket.handshake_headers = PackedStringArray(["Authorization: Bearer " + str(config.get("token", ""))])
		if _socket.connect_to_url(endpoint) != OK:
			_retry()
			return
		status = "正在连接 AI 字幕"
	_socket.poll()
	if _socket.get_ready_state() == WebSocketPeer.STATE_CLOSED:
		_retry()
		return
	if _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	while _socket.get_available_packet_count() > 0:
		var packet: Variant = JSON.parse_string(_socket.get_packet().get_string_from_utf8())
		if packet is Dictionary:
			_receive(packet)
	if not _connected:
		return
	var position_ms: int = host.control.display_position_ms()
	var audio := _audio_index(host)
	# Include the seek sequence even if a small seek lands close to the old clock.
	var key := "%s|%s|%s|%s" % [host.local_uri, host.media.session_id, host.control.sequence, audio]
	if key != _active_key:
		_active_key = key
		_epoch += 1
		_cues.clear()
		text = ""
		var path: String = "/" + host.local_uri.trim_prefix(prefix).uri_decode()
		_send({"type": "start", "epoch": _epoch, "path": path, "position_ms": position_ms, "audio_index": audio})
		_clock_at = now
	elif now >= _clock_at:
		_clock_at = now + 250
		_send({"type": "clock", "epoch": _epoch, "position_ms": position_ms})
	_select(position_ms - host.subtitle_delay_ms, bool(config.get("bilingual", false)))
	if status != _last_status:
		_last_status = status
		host.changed.emit()


func _receive(packet: Dictionary) -> void:
	if packet.get("type", "") == "ready":
		_connected = true
		return
	if int(packet.get("epoch", -1)) != _epoch:
		return
	match packet.get("type", ""):
		"cue":
			var id := int(packet.get("id", 0))
			if id <= 0 or str(packet.get("text", "")).length() > 4096:
				return
			if _cues.size() >= 64 and not _cues.has(id):
				_cues.erase(_cues.keys()[0])
			_cues[id] = packet
			status = "AI 中文字幕 · 流式翻译中" if not packet.get("final", false) else "AI 中文字幕 · 已同步"
		"status", "error":
			status = str(packet.get("message", "AI 字幕连接中断"))


func _select(position_ms: int, bilingual: bool) -> void:
	text = ""
	var selected := -1
	for id in _cues.keys():
		var cue: Dictionary = _cues[id]
		var start := int(cue.get("start_ms", 0))
		var end := int(cue.get("end_ms", start))
		if end + 2000 < position_ms:
			_cues.erase(id)
			continue
		if start <= position_ms and position_ms <= end + 600 and start >= selected:
			selected = start
			text = str(cue.get("text", "")).strip_edges()
			if bilingual and not text.is_empty():
				text = str(cue.get("source", "")) + "\n" + text


func _audio_index(host: Node) -> int:
	var tracks: Array = host.media.playback.get("details", {}).get("audio_tracks", [])
	var selected := str(host.media.playback.get("details", {}).get("audio_track_id", ""))
	var index := 0
	for track in tracks:
		if track.get("external", false):
			continue
		if str(track.get("id", "")) == selected:
			return index
		index += 1
	return 0


func _send(packet: Dictionary) -> void:
	if _socket != null:
		_socket.send_text(JSON.stringify(packet))


func _disconnect() -> void:
	if _socket != null:
		_socket.close()
	_socket = null
	_connected = false
	_active_key = ""
	_cues.clear()
	text = ""


func _retry() -> void:
	_disconnect()
	_retry_at = Time.get_ticks_msec() + 3000
	status = "AI 服务器未连接，正在重试"


func _exit_tree() -> void:
	_disconnect()
