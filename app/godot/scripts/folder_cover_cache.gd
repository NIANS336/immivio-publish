extends RefCounted
## Folder tiles reference the most recently played child's existing thumbnail.
## No directory scanning, remote requests, extra decoding or duplicate JPEGs.
const Thumbnails := preload("res://scripts/thumbnail_cache.gd")
const PATH := "user://settings/folder_covers.json"
const LIMIT := 256
const MAX_BYTES := 262144
static var _loaded := false
static var _records: Dictionary = {}
static var _path := PATH


static func parents(video_uri: String) -> Array[String]:
	var result: Array[String] = []
	var uri := video_uri
	if uri.begins_with("cloud://") or uri.begins_with("file://"):
		uri = uri.uri_decode()
	elif not uri.begins_with("smb://"):
		return result
	var start := uri.find("://") + 3
	var cut := uri.rfind("/")
	while cut >= start and result.size() < 64:
		var parent := uri.left(cut)
		if parent.length() > start:
			result.append(parent)
		cut = parent.rfind("/")
	return result


static func from_entry(entry: Dictionary, source: String, server: String = "") -> String:
	var id := str(entry.get("id", "")).trim_suffix("/")
	if source == "cloud" and id.begins_with("/"):
		return "cloud:/" + id  # Native IDs are already decoded paths.
	if source == "smb" and not server.is_empty() and not id.is_empty():
		return "smb://" + server + "/" + id.trim_prefix("/")
	if source == "local" and id.begins_with("file://"):
		return id.uri_decode()
	return ""


static func remember(video_uri: String) -> void:
	_load()
	var changed := false
	for folder in parents(video_uri):
		if _records.get(folder, "") == video_uri:
			continue
		_records.erase(folder)
		_records[folder] = video_uri
		changed = true
	if changed:
		_save()


## Backfill already-played videos on upgrade, newest first. Preserve newer saved covers.
static func seed(recent: Array) -> void:
	_load()
	var changed := false
	for entry in recent:
		if entry.get("kind", "video") != "video":
			continue
		var uri := str(entry.get("uri", ""))
		for folder in parents(uri):
			if not _records.has(folder):
				_records[folder] = uri
				changed = true
	if changed:
		_save()


static func texture(folder: String) -> Texture2D:
	_load()
	return Thumbnails.texture(str(_records.get(folder, "")))


static func forget(video_uri: String) -> void:
	_load()
	for folder in _records.keys():
		if _records[folder] == video_uri:
			_records.erase(folder)
	_save()


static func relocate(old_uri: String, new_uri: String) -> void:
	_load()
	var allowed := parents(new_uri)
	for folder in _records.keys():
		if _records[folder] == old_uri:
			if folder in allowed:
				_records[folder] = new_uri
			else:
				_records.erase(folder)
	_save()


static func clear() -> void:
	_load()
	_records.clear()
	_save()


static func _load() -> void:
	if _loaded:
		return
	_loaded = true
	var file := FileAccess.open(_path, FileAccess.READ)
	if not file or file.get_length() > MAX_BYTES:
		return
	var data: Variant = JSON.parse_string(file.get_as_text())
	if not data is Dictionary or data.get("version", 0) != 1:
		return
	var entries: Variant = data.get("entries", {})
	if not entries is Dictionary or entries.size() > LIMIT:
		return
	for folder in entries:
		var uri: Variant = entries[folder]
		if folder is String and uri is String and uri.length() <= 8192 and folder in parents(uri):
			_records[folder] = uri


static func _save() -> void:
	while _records.size() > LIMIT:
		_records.erase(_records.keys()[0])
	var text := JSON.stringify({"version": 1, "entries": _records})
	while text.to_utf8_buffer().size() > MAX_BYTES and not _records.is_empty():
		_records.erase(_records.keys()[0])
		text = JSON.stringify({"version": 1, "entries": _records})
	DirAccess.make_dir_recursive_absolute(_path.get_base_dir())
	var file := FileAccess.open(_path + ".tmp", FileAccess.WRITE)
	if file:
		file.store_string(text)
		file.close()
		DirAccess.rename_absolute(_path + ".tmp", _path)
