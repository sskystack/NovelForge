# macOS application icon packaging

## Root cause

The previously shipped 0.1.0 and 0.2.0 applications had neither a `CFBundleIconFile`
entry in `Contents/Info.plist` nor an ICNS resource in `Contents/Resources`.
The source tree contained a PNG and a Windows ICO, but `bundle.icon` was unset.
Consequently Finder, the Dock and the DMG had no declared macOS application icon.
This is a bundle-resource defect, not a React blank-window failure.

## Maintained assets

- `apps/desktop/src-tauri/icons/mark.svg`: original blue book/pen-nib mark.
- `icon.png`: 1024-pixel master raster.
- `32x32.png`, `128x128.png`, `128x128@2x.png`: explicit Tauri PNG resources.
- `icon.icns`: macOS 16–1024-pixel representations, including small-size variants.
- `scripts/generate_macos_icon.py`: reproducible icon renderer using build-time Pillow
  and the macOS `iconutil`; no application imaging dependency is added.

The Tauri bundle configuration explicitly names these icon files. The macOS bundler
must create `CFBundleIconFile` and copy the ICNS resource into the signed app.
Do not hand-edit the built application's plist after signing.

```sh
uv run --with pillow python scripts/generate_macos_icon.py
python scripts/verify_macos_bundle.py /absolute/path/to/NovelForge.app
python scripts/verify_macos_bundle.py /absolute/path/to/NovelForge.dmg
```

The verifier checks the actual bundle declaration, ICNS header and image sizes,
the embedded API executable and nested code signatures. It mounts DMGs read-only
and always detaches them. Both the development Run entrypoint and the macOS release
workflow run the verifier, so a missing icon cannot silently pass packaging again.

## Installation and caches

An old `/Applications/NovelForge.app` remains old until the application is replaced
with the rebuilt package. Updating source files or opening a DMG does not update that
installation. Keep the bundle identifier stable and increment the version for releases.
Verify the installed bundle's icon resource before blaming the Finder/Dock cache.
Do not delete user databases, reset all LaunchServices registrations, or disable
Gatekeeper to make an application icon appear.

Ad-hoc signing validates local bundle integrity; it is separate from Developer ID
distribution signing and Apple notarization.
