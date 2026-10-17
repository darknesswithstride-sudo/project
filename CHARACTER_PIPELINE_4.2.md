# OmniForge AI 4.2 — One-Click Character Pipeline

## Workflow
1. Choose a PNG/JPG/WEBP reference image and click **Run full character pipeline**.
2. OmniForge stores the image in the local workspace and calls the configured local TripoSR runner.
3. It inspects the generated mesh, optionally exports an optimized copy, and optionally builds a production package with Blender.
4. If enabled, it attempts a heuristic humanoid rig and creates a procedural starter animation on that rig.
5. Every stage and its result/error is persisted under `workspace/omniforge_assets/character_jobs/<job_id>.json`. Successful earlier outputs are retained if a later optional stage fails.

## API
- `POST /api/studio/character-pipeline` — multipart form: `file` (required), `prompt`, `target_faces`, `texture_size`, `lod_count`, `detail_profile`, `detail_intensity`, `optimize`, `rig`, `animate`, `action`, `fps`, `package`.
- `GET /api/studio/character-jobs` — recent job summaries.
- `GET /api/studio/character-jobs/{job_id}` — full saved manifest.

## Local prerequisites
- Python dependencies from `requirements.txt`.
- A working local TripoSR checkout with model weights and its Python environment configured using `TRIPOSR_DIR` and `TRIPOSR_PYTHON`.
- Blender is needed for optimize, production package, rigging, and animation. Disable optional stages in the UI if a local dependency is not ready.
- No paid API is called by this workflow.

## Important limitations
- Single-image reconstruction estimates unseen surfaces and is not a true scan or exact 360-degree reconstruction. The current local TripoSR runner is image-conditioned, not text-prompt-conditioned; the brief is saved in the job manifest but does not steer TripoSR geometry.
- TripoSR must already be installed with weights; this release does not bundle multi-gigabyte neural weights.
- Procedural surface detail and the production pipeline add bounded procedural relief/material detail; they are not semantic sculpting by an expert character artist.
- Humanoid auto-rigging uses approximate skeleton placement and Blender automatic weights. It is best-effort for upright human-like proportions; it is not a universal creature/face rig.
- Walk/run/idle/attack/death clips are procedural starter motion, not mocap-quality animation. Review deformation, scale, UVs, materials, and animation in Blender before shipping.
- Blender rendering/baking and Unreal import/build are not verified by the automated test suite unless explicitly run on the target machine.
