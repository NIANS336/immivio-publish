extends RefCounted
## Provision once through the existing native account API, then erase plaintext.
const CONFIG := "user://ai_subtitles.private.json"
const BOOTSTRAP := "user://ai_bootstrap.private.json"
var config: Dictionary = {}
var status := ""
var _platform: Object
var _request := 0
var _name := ""


func _init(platform: Object) -> void:
	_platform = platform
	config = _read(CONFIG)
	var data := _read(BOOTSTRAP)
	if data.is_empty():
		return
	for key in ["server", "token", "enabled", "bilingual"]:
		if data.has(key):
			config[key] = data[key]
	var dav: Dictionary = data.get("webdav", {})
	if dav.is_empty() or _platform == null:
		_save()
		return
	_name = str(dav.get("name", "PikPak AI"))
	# A previous successful import is identified by the stored UUID, never by name alone.
	var account_id := str(config.get("mount_id", ""))
	_request = int(_platform.account_open("cloud", "webdav", account_id, "{}"))
	if _request <= 0:
		status = "WebDAV 配置失败"
		return
	for key in ["name", "base", "username", "password"]:
		_platform.account_input(_request, key, "replace", str(dav.get(key, "")))
	_platform.account_action(_request, "save_webdav", "{}")
	status = "正在连接 WebDAV"


func poll() -> void:
	if _request <= 0:
		return
	var data: Variant = JSON.parse_string(_platform.account_snapshot(_request))
	if not data is Dictionary or data.get("busy", false):
		return
	if data.get("state", "") == "done":
		var accounts: Variant = JSON.parse_string(_platform.account_list("cloud"))
		if accounts is Array:
			for account in accounts:
				if account.get("provider", "") == "webdav" and account.get("name", "") == _name:
					config["mount_id"] = str(account.id)
		_save()
		_request = 0
		status = ""
	elif not str(data.get("error", "")).is_empty():
		status = "WebDAV 连接失败，请检查账户"
		_request = 0


func _save() -> void:
	var file := FileAccess.open(CONFIG, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(config))
		file.close()
		DirAccess.remove_absolute(ProjectSettings.globalize_path(BOOTSTRAP))


func set_enabled(value: bool) -> void:
	config["enabled"] = value
	var file := FileAccess.open(CONFIG, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(config))


static func _read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return data if data is Dictionary else {}
