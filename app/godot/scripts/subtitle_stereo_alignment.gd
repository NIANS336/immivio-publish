extends RefCounted
## Total angular separation between subtitle eyes; independent of video alignment.
const LIMIT := 10.0
const STEP := 0.05
const HORIZONTAL := "subtitle_eye_horizontal"
const VERTICAL := "subtitle_eye_vertical"


static func value(degrees: float) -> float:
	return clampf(snappedf(degrees, STEP), -LIMIT, LIMIT) if is_finite(degrees) else 0.0


static func radians(horizontal: float, vertical: float) -> Vector2:
	return Vector2(deg_to_rad(value(horizontal)), deg_to_rad(value(vertical)))


static func restore(video: Node, settings: ConfigFile) -> void:
	video.subtitle_eye_horizontal = value(float(settings.get_value("subtitles", "eye_horizontal_degrees", 0.0)))
	video.subtitle_eye_vertical = value(float(settings.get_value("subtitles", "eye_vertical_degrees", 0.0)))


static func save(video: Node, settings: ConfigFile) -> void:
	settings.set_value("subtitles", "eye_horizontal_degrees", video.subtitle_eye_horizontal)
	settings.set_value("subtitles", "eye_vertical_degrees", video.subtitle_eye_vertical)


static func apply(video: Node, key: String, degrees: float) -> void:
	if key == HORIZONTAL:
		video.subtitle_eye_horizontal = value(degrees)
	elif key == VERTICAL:
		video.subtitle_eye_vertical = value(degrees)


static func reset(video: Node) -> void:
	video.subtitle_eye_horizontal = 0.0
	video.subtitle_eye_vertical = 0.0
