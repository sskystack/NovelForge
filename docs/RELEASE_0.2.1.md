# NovelForge 0.2.1 — redesigned macOS workspace and application icon

The UI redesign is authored in Figma and implemented in the shared React frontend.
The maintained runtime remains the macOS Tauri application and bundled local API.

## Design source

- [Figma file](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS)
- [Writing workspace](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=6-129)
- [Knowledge](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=7-2)
- [Agent and approval](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=7-70)
- [Settings](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-2)
- [Project setup](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-74)
- [Tokens and states](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-136)

The previous warm-paper/olive palette is replaced with graphite navigation, a cool
neutral workspace, a white manuscript surface and blue actions. Product labels are
localized into Simplified Chinese. Layout and visual states follow the design file;
model keys and user manuscripts were not uploaded to Figma.

## Application icon correction

Previous packages omitted both `CFBundleIconFile` and a bundled ICNS resource. The
source PNG/ICO alone did not supply an icon to macOS. 0.2.1 explicitly configures
macOS PNG/ICNS assets and supplies an original book/pen-nib icon at 16–1024 pixels.
See `MACOS_ICON_PACKAGING.md` for the cause and reproducible build commands.

`scripts/verify_macos_bundle.py` now checks the packaged icon declaration, ICNS
representations, embedded service and nested signatures. Both the development Run
entrypoint and macOS release workflow apply this gate to the actual built bundle.

## Verification record

| Check | Observed result |
| --- | --- |
| API tests / Ruff | 118 passed / passed |
| Frontend tests / lint / typecheck / build | 48 passed / passed |
| Frozen 0.2.1 sidecar | 16 checks passed; real SDK discovery/call and durable approval |
| macOS release build | 0.2.1 Apple Silicon DMG built |
| DMG and installed bundle | Declared ICNS, small/1024px representations, embedded sidecar and deep strict signatures passed |
| Installed native app | Chinese login, existing synthetic manuscript, Cmd-S/new version, knowledge search/source detail, completed model/tool/model run, settings and MCP tabs passed |
| Finder / DMG | Actual icons visibly present; screenshots saved |
| Installation | Previous 0.1.0 app backed up, `/Applications/NovelForge.app` updated to 0.2.1 |
| Cleanup | Test app, sidecar and frontend/API test servers stopped; DMG detached |

Native testing used a copy of the isolated 0.2.0 fixture. No real manuscript database
was used or changed. The Dock has no capturable application window in the available
UI tool, so its appearance was not separately screenshot-verified. Finder and the
DMG were verified visually in addition to checking the installed icon declaration.
Detailed final results are recorded in the delivered verification JSON and
`UI_DESIGN.md`.

Ad-hoc signing remains separate from Developer ID signing and Apple notarization.
Agent/RAG/MCP behavior, local data ownership and explicit author approval are retained.
