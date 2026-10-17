# OmniForge AI 4.1 — Integrated Studio Pipeline

This release adds a real orchestration endpoint for existing local tools rather than presenting a stage diagram alone.

## Integrated flow
1. Validate that the input model exists within the OmniForge workspace and uses a supported format.
2. Optionally inspect the model through Blender (mesh/face/vertex/material/armature report).
3. Optionally optimize a separate output copy to a chosen face budget and GLB/FBX format.
4. Run the existing production pipeline for LODs, detail, texture baking, and package/manifest creation.
5. Persist each stage's status and result to `workspace/omniforge_assets/studio_jobs/<job_id>.json`.

API:
- `POST /api/studio/pipeline`
- `GET /api/studio/jobs`
- `GET /api/studio/jobs/{job_id}`

The request uses `model_path`, `inspect`, `optimize`, `production`, `target_faces`, `optimize_faces`, `lod_count`, `texture_size`, `detail_profile`, `detail_intensity`, `export_format`, and `run_blender`.

## Limits
This is orchestration around installed local tools, not a new neural 3D model. Blender must be configured for inspection, optimization, and production. The current automatic rigging is heuristic and intended for roughly upright humanoid meshes; animation operates on an existing compatible armature. The workflow does not claim to infer unseen image surfaces perfectly or guarantee AAA quality. Unreal project import/build still needs to be validated on the target machine.
