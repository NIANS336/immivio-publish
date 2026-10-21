extends SceneTree
const Alignment := preload("res://scripts/subtitle_stereo_alignment.gd")
const Menu := preload("res://scripts/player_menu.gd")

class VideoSettings:
	extends Node
	var subtitle_eye_horizontal := 0.0
	var subtitle_eye_vertical := 0.0
	var stereo_horizontal := -2.1
	var stereo_vertical := -1.9
	var subtitle_distance := 5.0


func _initialize() -> void:
	var video := VideoSettings.new()
	Alignment.apply(video, Alignment.HORIZONTAL, 2.13)
	Alignment.apply(video, Alignment.VERTICAL, -1.27)
	assert(is_equal_approx(video.subtitle_eye_horizontal, 2.15))
	assert(is_equal_approx(video.subtitle_eye_vertical, -1.25))
	assert(video.stereo_horizontal == -2.1 and video.stereo_vertical == -1.9)
	assert(video.subtitle_distance == 5.0, "Subtitle eye correction must not change depth")
	var settings := ConfigFile.new()
	Alignment.save(video, settings)
	Alignment.reset(video)
	assert(video.subtitle_eye_horizontal == 0 and video.subtitle_eye_vertical == 0)
	Alignment.restore(video, settings)
	assert(is_equal_approx(video.subtitle_eye_horizontal, 2.15))
	assert(is_equal_approx(video.subtitle_eye_vertical, -1.25))
	assert(Alignment.value(INF) == 0 and Alignment.value(NAN) == 0)
	assert(Alignment.value(100) == 10 and Alignment.value(-100) == -10)
	var material := ShaderMaterial.new()
	material.shader = load("res://shaders/video_pair.gdshader")
	var offset := Alignment.radians(2.0, -1.0)
	material.set_shader_parameter("subtitle_eye_offset", offset)
	assert(material.get_shader_parameter("subtitle_eye_offset") == offset)
	var menu := Menu.new()
	var committed: Array = []
	menu.adjustment_requested.connect(func(key, value): committed.append([key, value]))
	menu._on_choice_changed(Alignment.HORIZONTAL, 1.5)
	menu._on_choice_changed(Alignment.VERTICAL, -0.5)
	assert(committed == [[Alignment.HORIZONTAL, 1.5], [Alignment.VERTICAL, -0.5]])
	assert(Menu.POPUP_TARGETS[Menu.SUBTITLE_ALIGNMENT] == "subtitle_alignment")
	menu.free()
	video.free()
	print("Subtitle stereo alignment tests passed")
	quit(0)
