# OmniForge AI 4.3 — Autonomous Command Engine

OmniForge now exposes a natural-language command front door at **Autonomous Command** in the web UI and `POST /api/autonomy/run`.

## How it works

1. Describe the outcome you want, not a list of UI clicks.
2. OmniForge asks the configured local Ollama model to choose a short sequence of registered tools. If the model is unavailable or produces invalid JSON, a deterministic local router handles common tasks.
3. The executor runs up to four actions sequentially and records a JSON manifest under `workspace/omniforge_assets/autonomous_runs/`.
4. Results include per-action status, errors, output paths, and timestamps. Previous jobs can be listed at `GET /api/autonomy/jobs`.

## Available action registry

- `diagnostics`: local dependency / setup checks
- `repository`: repository inventory and analysis
- `build`: fixed compile/test/build profiles only
- `repair`: bounded repair loop with a fixed verifier
- `coding`: repository-aware local coding agent with bounded patches and verification
- `graphics_pack`: reproducible procedural environment starter pack
- `graphics_validate`: graphics toolchain readiness
- `production_build`: LOD/export/validation package for an existing workspace mesh
- `studio_pipeline`: inspect, optionally optimize, and package an existing workspace mesh
- `3d_validate`: local 3D pipeline readiness
- `vision_status`: local vision model configuration status

The planner cannot issue shell commands. Tool names and build profiles are allowlisted. Project and model paths are constrained to the configured workspace. The graphics starter pack is generated without automatically launching a potentially long Blender render.

## Image-to-character mode

Attach a PNG/JPG/WEBP reference image to the same command form. OmniForge runs the existing local character pipeline: image-to-3D generation, inspection, optional optimization, production packaging, best-effort humanoid rigging, and starter animation. TripoSR model weights, Python dependencies, and compatible hardware must already be installed. The pipeline returns its stage report even if optional later stages fail.

## API

`POST /api/autonomy/run` as multipart form fields:
- `command` (required)
- `project_path` (default `.`; workspace-relative)
- `max_actions` (1–4)
- `reference_image` (optional image; selecting it invokes the character pipeline)

`GET /api/autonomy/jobs` lists recent saved job summaries.

## Safety and operational boundaries

This is autonomous orchestration over registered tools, not unrestricted computer control. It does not run arbitrary shell commands, delete files, make paid API calls, or silently use cloud services. Coding and repair actions can modify files within the selected workspace, so use Git or a disposable project copy for important work. The engine stops after failed coding/build/repair steps rather than blindly continuing.

## Local-only constraint

OmniForge remains free/local-first. Planning uses Ollama when reachable; without it, a rule-based fallback still handles common tasks. Quality depends on the installed local model and the availability of Blender, TripoSR, and other optional backends. External model generation, Blender renders, rigging, animation, and Unreal builds must be tested on the target PC.
