"""Validate the actual macOS app icon, embedded service and nested signatures.

Accept an .app path or a .dmg; a disk image is mounted read-only and always detached.
No application is launched, no user database is read, and no trust setting is changed.
"""

import argparse
import json
import plistlib
import struct
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def application(path: Path):
    if path.suffix == ".app":
        yield path
        return
    if path.suffix != ".dmg":
        raise ValueError("Expected a macOS .app bundle or .dmg")
    result = subprocess.check_output(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(path)]
    )
    mounts = [
        Path(item["mount-point"])
        for item in plistlib.loads(result)["system-entities"]
        if "mount-point" in item
    ]
    try:
        bundles = [bundle for mount in mounts for bundle in mount.glob("*.app")]
        if len(bundles) != 1:
            raise ValueError("Disk image must contain exactly one top-level application")
        yield bundles[0]
    finally:
        for mount in reversed(mounts):
            subprocess.run(["hdiutil", "detach", str(mount)], check=True, capture_output=True)


def icon_representations(path: Path) -> list[str]:
    data = path.read_bytes()
    if data[:4] != b"icns" or struct.unpack(">I", data[4:8])[0] != len(data):
        raise ValueError("Invalid ICNS header or file length")
    offset, representations = 8, []
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("Truncated ICNS representation")
        kind, length = struct.unpack(">4sI", data[offset : offset + 8])
        if length <= 8 or offset + length > len(data):
            raise ValueError("Empty or truncated ICNS image data")
        representations.append(kind.decode("ascii"))
        offset += length
    # Recent iconutil versions encode small legacy ARGB images as ic04/ic05.
    if not {"icp4", "is32", "ic04"}.intersection(representations) or "ic10" not in representations:
        raise ValueError("Icon must contain both a small Finder representation and a 1024px image")
    return representations


def verify(app: Path) -> dict:
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    name = info.get("CFBundleIconFile")
    if not name or Path(name).name != name:
        raise ValueError("Info.plist has no valid CFBundleIconFile")
    icon = app / "Contents/Resources" / name
    if not icon.suffix:
        icon = icon.with_suffix(".icns")
    representations = icon_representations(icon)
    executable = app / "Contents/MacOS" / info["CFBundleExecutable"]
    sidecar = executable.parent / "novelforge-api"
    if not executable.is_file() or not sidecar.is_file():
        raise ValueError("Application executable or embedded API is missing")
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    return {
        "status": "passed",
        "version": info["CFBundleShortVersionString"],
        "bundle_identifier": info["CFBundleIdentifier"],
        "icon_file": icon.name,
        "icon_representations": representations,
        "embedded_sidecar": True,
        "nested_signature_verified": True,
        "notarization_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    path = args.path
    if path.is_dir() and path.suffix != ".app":
        images = list(path.glob("*.dmg"))
        if len(images) != 1:
            parser.error("Expected exactly one DMG in the supplied directory")
        path = images[0]
    with application(path.resolve()) as app:
        result = verify(app)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
