#!/usr/bin/env python3
"""Recompile changed Godot scripts, retain the matching v0.9.3 native runtime.

This resource-only build does not rebuild or alter upstream DEX/ELF libraries.
Requires Godot 4.7.2, apktool 2.12.1, JDK and Android build-tools 36.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import struct
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ["ai_streaming_subtitles", "ai_subtitle_bootstrap", "mpv_video_display",
           "playback_coordinator", "xr_presentation_coordinator", "player_menu",
           "folder_cover_cache", "recent_files", "library_menu",
           "subtitle_stereo_alignment", "main", "player_settings_controller", "playback_popups"]
ASSETS = ["shaders/projected_subtitles.gdshaderinc"]
BASE_SHA256 = "b08471877ffe6307ffdf4d8954d4875db1bd1451fddeadccbdc0b4fab1af9b04"


def run(args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def read_index(data):
    if struct.unpack_from("<6I", data) != (0x43504447, 4, 4, 7, 2, 6):
        raise ValueError("Expected an unencrypted Godot 4.7.2 sparse PCK v4")
    offset = struct.unpack_from("<Q", data, 32)[0]
    count = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    entries = {}
    for _ in range(count):
        length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        path = data[offset:offset + length].rstrip(b"\0").decode("utf-8")
        offset += length
        entries[path] = data[offset:offset + 36]
        offset += 36
    if offset != len(data):
        raise ValueError("Unexpected sparse PCK directory trailer")
    return bytearray(data[:struct.unpack_from("<Q", data, 32)[0]]), entries


def overlay_scripts(base, resources):
    pack = base / "assets/assets.sparsepck"
    header, entries = read_index(pack.read_bytes())
    with ZipFile(resources) as exported:
        names = ["scripts/" + script + suffix for script in SCRIPTS for suffix in (".gdc", ".gd.remap")]
        for name in names + ASSETS:
            payload = exported.read(name)
            (base / "assets" / name).write_bytes(payload)
            # Existing remaps may not appear in the upstream sparse directory;
            # add both new scripts and their remaps explicitly.
            entries[name] = struct.pack("<QQ", 0, len(payload)) + hashlib.md5(payload).digest() + struct.pack("<I", 0)
    directory = bytearray(struct.pack("<I", len(entries)))
    for name, metadata in sorted(entries.items()):
        encoded = name.encode("utf-8")
        encoded += b"\0" * (-len(encoded) % 4)
        directory += struct.pack("<I", len(encoded)) + encoded + metadata
    pack.write_bytes(header + directory)


def verify_native(original, modified):
    with ZipFile(original) as old, ZipFile(modified) as new:
        unchanged = [x for x in old.namelist() if x.startswith("lib/") or x.endswith(".dex")]
        for name in unchanged:
            if hashlib.sha256(old.read(name)).digest() != hashlib.sha256(new.read(name)).digest():
                raise ValueError("Native runtime unexpectedly changed: " + name)
        if not unchanged:
            raise ValueError("No native runtime found")
    print(f"Verified {len(unchanged)} unchanged DEX/native library entries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("base-apk", "godot", "apktool", "java-home", "build-tools", "keystore", "out", "work-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    for name, value in vars(args).items():
        setattr(args, name, value.resolve())
    if hashlib.sha256(args.base_apk.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError("Expected the verified upstream v0.9.3 Quest release APK")
    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    java = args.java_home / "bin/java"
    resources = work / "ai-resources.zip"
    run([args.godot, "--headless", "--path", ROOT / "app/godot", "--export-pack", "Quest 3", resources])
    unpacked = work / "apk"
    run([java, "-jar", args.apktool, "d", "-s", "-f", args.base_apk, "-o", unpacked])
    overlay_scripts(unpacked, resources)
    manifest = unpacked / "AndroidManifest.xml"
    # Preserve namespace prefixes required by Horizon OS and apktool.
    text = manifest.read_text()
    text = text.replace("<application ", '<application android:debuggable="true" ', 1)
    manifest.write_text(text)
    for strings in (unpacked / "res").glob("values*/strings.xml"):
        text = re.sub(r'(<string\b[^>]*\bname="godot_project_name_string"[^>]*>)[^<]*(</string>)',
                      r'\g<1>Immivio AI\g<2>', strings.read_text())
        strings.write_text(text)
    yaml = unpacked / "apktool.yml"
    yaml.write_text(yaml.read_text().replace("versionName: 0.9.3", "versionName: 0.9.3-ai.3"))
    unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
    run([java, "-jar", args.apktool, "b", unpacked, "-o", unsigned])
    run([args.build_tools / "zipalign", "-f", "-P", "16", "4", unsigned, aligned])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "JAVA_HOME": str(args.java_home),
           "PATH": str(args.java_home / "bin") + os.pathsep + os.environ.get("PATH", "")}
    signer = args.build_tools / "apksigner"
    run([signer, "sign", "--ks", args.keystore, "--ks-key-alias", "immivio-ai",
         "--ks-pass", "env:IMMIVIO_KEYSTORE_PASSWORD", "--key-pass", "env:IMMIVIO_KEYSTORE_PASSWORD",
         "--out", args.out, aligned], env=env)
    run([signer, "verify", "--verbose", args.out], env=env)
    verify_native(args.base_apk, args.out)
    print("APK SHA256:", hashlib.sha256(args.out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
