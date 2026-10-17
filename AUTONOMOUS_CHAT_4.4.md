# OmniForge AI 4.4 — Autonomous Chat & Project Brain

## Product behavior
OmniForge now presents one user-facing interface: a chat. The user states the desired outcome in natural language and can optionally attach a reference image. A background supervisor plans and runs a bounded sequence of registered local tools, reports status while working, and returns the execution record and generated outputs.

## New systems
- **Persistent project brain:** SQLite stores conversation history, task goals, run outcomes, and project notes in `workspace/omniforge_brain.sqlite3`. Job manifests are persisted below `workspace/omniforge_assets/chat_jobs/`.
- **Long-running supervisor:** jobs run in the background and the UI polls status. Up to three iterations are used by default (configurable in `start_chat_job`), with a targeted self-correction attempt after reported action failures. Each individual run remains bounded by registered tools and fixed profiles.
- **Dependency setup:** `setup_dependencies` supports declared Python dependencies in `requirements.txt` or `pyproject.toml`. Installs use the current Python interpreter and fixed pip argument forms; no model-generated shell commands are executed. `npm install` is deliberately not run unattended because lifecycle scripts can execute arbitrary code.
- **Visual review:** `visual_inspect` asks installed Blender to import a supported workspace mesh and render a preview PNG. If the configured local Ollama endpoint accepts image input, OmniForge asks the configured model for a visible-evidence-only critique. Otherwise the rendered preview and mesh statistics are still reported.
- **Chat-only UI:** old dashboards are no longer the home interface. The chat supports conversation history, reference-image attachment, background status polling, and inline visual previews.

## Run it
1. On Windows, run `Setup-OmniForge.bat` to create `.venv` and install the app's own dependencies.
2. Configure `.env` for the local Ollama model and optional Blender / TripoSR paths.
3. Run `Launch-OmniForge.bat` and use the chat at the local address shown by the launcher.
4. Describe an outcome; optionally attach an image. For image-to-3D, TripoSR and model weights must already be installed and configured.

## API
- `POST /api/chat/send` — form fields `message`, optional `session_id`, optional `reference_image`; returns a background `job_id`.
- `GET /api/chat/jobs/{job_id}` — job status, iterations, actions, results, warnings, and final response.
- `GET /api/chat/jobs` — recent jobs.
- `GET /api/chat/history/{session_id}` — persistent conversation history and memory summary.
- `GET /api/chat/sessions` — saved sessions.
- `GET /api/chat/preview/{filename}` — a rendered PNG from the generated visual-review folder.

## Safety and honest boundaries
- The planner can choose only registered actions; it cannot send arbitrary shell commands.
- Paths are constrained to the configured workspace for supported project/asset tools.
- Dependency setup only processes recognized Python manifests. Python package build/install code is still third-party code; review dependency files for untrusted projects before approving installs.
- Autonomous work has bounded iterations and timeouts; it is not an infinite agent. The current implementation does not persist in-process tasks across a server restart, although chat, memory, and job manifests remain on disk.
- Visual critique depends on Blender being installed and on a local vision-capable Ollama model accepting image input. Rendered previews do not prove animation correctness, topology quality, or Unreal Engine compatibility.
- No paid API calls are required. Local model quality and available hardware determine what the agent can accomplish.
