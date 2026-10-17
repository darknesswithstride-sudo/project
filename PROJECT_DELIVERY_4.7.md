# OmniForge 4.7 — Project Delivery Pipeline

OmniForge now prepares delivery artifacts after creating an Unreal project rather than stopping at the initial project structure.

## New delivery stages
1. **Asset intake:** accepts supported FBX, OBJ, GLB/GLTF, image, audio, and Unreal asset files. Supported source files are copied into `Content/OmniForgeImported` and listed in `Delivery/asset_manifest.json`. Staging is not the same as a successful Unreal import.
2. **Editor-side import and level creation:** `Delivery/UnrealEditor-ImportAssets-And-BuildLevel.py` is intended to run inside Unreal Editor Python. It imports staged source files, creates an editable level, lays down a ground plane, cover/barricade blockout, salvage landmarks and route markers, and writes `Delivery/editor_pipeline_result.json`.
3. **QA plan:** `Delivery/qa_test_plan.json` separates build, editor import, visual review, gameplay checks and packaged smoke test. Items remain `NOT_RUN` until actually executed.
4. **Packaging:** `Delivery/Build-Test-Package-Windows.bat` runs the Unreal build and BuildCookRun stages; a manifest is emitted only when package files exist. File presence does not prove the game launches; the manifest explicitly leaves `verified_launch` false.
5. **Report:** `Delivery/delivery_report.json` and `GET /api/unreal/deliver` inspect the pipeline state. `GET /api/unreal/delivery-tools` reports local tool detection.

## Use
- Ask OmniForge to build an Unreal game; the delivery files are prepared automatically after generation.
- Or call `POST /api/unreal/deliver` with JSON like `{"project_path":"OmniForgeGames/MyGame","asset_paths":["D:/Assets/tree.fbx"],"level_name":"MainSurvivalLevel","package_platform":"Win64"}`.
- Run the editor Python script in an Unreal Editor environment with Python Editor Script Plugin enabled. Review the generated level and assets before treating the import stage as passed.
- On Windows, set `UE_ROOT` to the Unreal Engine installation and run `Delivery/Build-Test-Package-Windows.bat`.

## Verification boundary
Python source compiles and automated OmniForge tests validate the preparation workflow. This environment has not run Unreal Editor, imported actual assets into Unreal, visually inspected rendered gameplay, completed functional playtests, or produced a Windows package. Those remain engine-dependent steps, tracked as such rather than falsely reported as complete.
