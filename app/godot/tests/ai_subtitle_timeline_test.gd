extends SceneTree


func _initialize() -> void:
	var captions := preload("res://scripts/ai_streaming_subtitles.gd").new()
	captions._epoch = 2
	captions._receive({"type": "cue", "epoch": 1, "id": 1, "start_ms": 0, "end_ms": 3000, "text": "旧字幕"})
	assert(captions._cues.is_empty(), "An old playback epoch must not add a cue")
	captions._receive({"type": "cue", "epoch": 2, "id": 1, "start_ms": 1000, "end_ms": 3000, "text": "中", "source": "日本語", "final": false})
	captions._select(500, false)
	assert(captions.text.is_empty(), "Ahead-of-play captions must wait for their timestamp")
	captions._select(1100, false)
	assert(captions.text == "中", "A partial translation must display before completion")
	captions._receive({"type": "cue", "epoch": 2, "id": 1, "start_ms": 1000, "end_ms": 3000, "text": "中文", "source": "日本語", "final": true})
	captions._select(1500, true)
	assert(captions.text == "日本語\n中文", "A completion replaces its partial cue")
	captions._select(7000, false)
	assert(captions.text.is_empty() and captions._cues.is_empty(), "Expired captions must clear")
	captions.free()
	print("AI subtitle timeline tests passed")
	quit(0)
