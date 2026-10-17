"""One-click, free/local-first image-to-character production workflow.

The workflow is intentionally staged and auditable. Optional downstream stages can
fail without discarding the generated mesh; reports distinguish real outputs from
stages that need manual attention.
"""
from __future__ import annotations
import asyncio, json, time, uuid
from pathlib import Path
from .config import WORKSPACE_DIR, THREED_PROVIDER
from . import asset_studio
from .local_3d_tools import inspect_model, optimize_model, auto_rig_humanoid, animate_rig
from .production_pipeline import run_pipeline

ROOT = (WORKSPACE_DIR / "omniforge_assets" / "character_jobs").resolve()
ROOT.mkdir(parents=True, exist_ok=True)
MESH_SUFFIXES = {".glb", ".gltf", ".fbx", ".obj", ".ply", ".stl", ".blend"}


def _relative_existing(value: str) -> str:
    raw = Path(value)
    path = raw.resolve() if raw.is_absolute() else (WORKSPACE_DIR / raw).resolve()
    if not path.is_relative_to(WORKSPACE_DIR.resolve()):
        raise ValueError("Generated model path escaped the OmniForge workspace.")
    if not path.is_file() or path.suffix.lower() not in MESH_SUFFIXES:
        raise ValueError("Image-to-3D backend did not produce a supported mesh file.")
    return str(path.relative_to(WORKSPACE_DIR))


def _save(job: dict, manifest: Path):
    manifest.write_text(json.dumps(job, indent=2), encoding="utf-8")


def _stage(job: dict, manifest: Path, name: str, fn, required: bool = False):
    entry = {"name": name, "status": "RUNNING", "started_at": time.time(), "required": required}
    job["stages"].append(entry); _save(job, manifest)
    try:
        result = fn()
        entry.update(status="SUCCEEDED", result=result)
        if isinstance(result, dict):
            output = result.get("output")
            if output: job["outputs"].append(output)
        return result
    except Exception as exc:
        entry.update(status="FAILED", error=str(exc))
        job["warnings"].append(f"{name}: {exc}")
        if required:
            job["status"] = "FAILED"; job["error"] = f"{name}: {exc}"
            _save(job, manifest)
            raise
        return None
    finally:
        entry["finished_at"] = time.time(); _save(job, manifest)


async def run_character_pipeline(image_id: str, prompt: str = "", target_faces: int = 50000,
                                 texture_size: int = 2048, lod_count: int = 3,
                                 detail_profile: str = "organic", detail_intensity: float = 1.0,
                                 optimize: bool = True, rig: bool = True,
                                 animate: bool = True, action: str = "walk", fps: int = 24,
                                 package: bool = True):
    if THREED_PROVIDER != "local":
        raise ValueError("This all-in-one workflow is free/local-only. Set THREED_PROVIDER=local; paid cloud providers are not used.")
    if not isinstance(image_id, str) or len(image_id) != 32 or any(c not in "0123456789abcdef" for c in image_id.lower()):
        raise ValueError("Invalid reference image ID.")
    if not 1000 <= int(target_faces) <= 2_000_000: raise ValueError("target_faces must be between 1,000 and 2,000,000.")
    if int(texture_size) not in {512, 1024, 2048, 4096}: raise ValueError("texture_size must be 512, 1024, 2048, or 4096.")
    if not 1 <= int(lod_count) <= 4: raise ValueError("lod_count must be between 1 and 4.")
    if detail_profile not in {"organic", "skin_pores", "fabric", "clothing", "damaged", "hard_surface"}: raise ValueError("Unsupported detail profile.")
    if not 0 <= float(detail_intensity) <= 2: raise ValueError("detail_intensity must be between 0 and 2.")
    if action not in {"idle", "walk", "run", "attack", "death"}: raise ValueError("Unsupported animation action.")
    if not 12 <= int(fps) <= 60: raise ValueError("fps must be between 12 and 60.")

    job_id = uuid.uuid4().hex
    manifest = ROOT / f"{job_id}.json"
    job = {"job_id": job_id, "status": "RUNNING", "created_at": time.time(),
           "local_only": True, "reference_image_id": image_id,
           "prompt": prompt[:1000], "stages": [], "outputs": [], "warnings": [],
           "settings": {"target_faces": int(target_faces), "texture_size": int(texture_size),
             "lod_count": int(lod_count), "detail_profile": detail_profile,
             "detail_intensity": float(detail_intensity), "optimize": bool(optimize),
             "rig": bool(rig), "animate": bool(animate), "action": action, "fps": int(fps), "package": bool(package)}}
    _save(job, manifest)
    try:
        generated = await _stage_async_generation(job, manifest, image_id, prompt)
        candidates = generated.get("files", [])
        priority = {".glb": 0, ".gltf": 1, ".fbx": 2, ".blend": 3, ".obj": 4, ".ply": 5, ".stl": 6}
        model = next(iter(sorted((p for p in candidates if Path(p).suffix.lower() in priority), key=lambda p: priority[Path(p).suffix.lower()])), None)
        if not model: raise RuntimeError("Generation finished but no supported mesh output was found.")
        current = _relative_existing(model)
        job["generated_model_path"] = current

        await asyncio.to_thread(_stage, job, manifest, "inspect_generated_mesh", lambda: inspect_model(current))
        if optimize:
            result = await asyncio.to_thread(_stage, job, manifest, "optimize_mesh", lambda: optimize_model(current, int(target_faces), "glb"))
            if result and result.get("output"):
                try: current = _relative_existing(result["output"]); job["optimized_model_path"] = current
                except Exception as exc: job["warnings"].append(f"Optimized output was not usable: {exc}")

        if package:
            result = await asyncio.to_thread(_stage, job, manifest, "production_package", lambda: run_pipeline(current, int(target_faces), int(lod_count), int(texture_size), True, detail_profile, float(detail_intensity)))
            if result:
                job["production_result"] = result
                for key in ("manifest", "output_dir", "package"):
                    if result.get(key): job["outputs"].append(result[key])

        if rig:
            result = await asyncio.to_thread(_stage, job, manifest, "humanoid_auto_rig", lambda: auto_rig_humanoid(current, "fbx"))
            if result and result.get("output"):
                try: current_rig = _relative_existing(result["output"]); job["rigged_model_path"] = current_rig
                except Exception as exc: current_rig = None; job["warnings"].append(f"Rigged output was not usable: {exc}")
            else: current_rig = None
            if animate and current_rig:
                anim = await asyncio.to_thread(_stage, job, manifest, "procedural_animation", lambda: animate_rig(current_rig, action, int(fps)))
                if anim and anim.get("output"): job["animated_model_path"] = anim["output"]
            elif animate:
                job["stages"].append({"name":"procedural_animation", "status":"SKIPPED", "reason":"Rigging did not produce a usable humanoid FBX."})
        elif animate:
            job["stages"].append({"name":"procedural_animation", "status":"SKIPPED", "reason":"Rigging was disabled."})

        job["final_model_path"] = job.get("animated_model_path") or job.get("rigged_model_path") or current
        # Best-effort visual QA: render the actual final artifact when Blender is available.
        try:
            from .visual_inspection import inspect_visual
            visual = await asyncio.to_thread(inspect_visual, job["final_model_path"])
            job["visual_review"] = visual
            if visual.get("preview_path"):
                job["outputs"].append(visual["preview_path"])
            if visual.get("status") == "SUCCEEDED":
                job["stages"].append({"name":"visual_review", "status":"SUCCEEDED", "result":visual})
            else:
                job["stages"].append({"name":"visual_review", "status":"SKIPPED", "reason":visual.get("reason") or visual.get("error") or "Visual review could not be completed with the configured local tools."})
                job["warnings"].append("Visual review was unavailable or failed; inspect the final model manually.")
        except Exception as visual_exc:
            job["stages"].append({"name":"visual_review", "status":"SKIPPED", "reason":str(visual_exc)[:500]})
            job["warnings"].append("Visual review could not run; inspect the final model manually.")
        failures = [s for s in job["stages"] if s.get("status") == "FAILED"]
        job["status"] = "COMPLETED_WITH_WARNINGS" if failures else "SUCCEEDED"
        job["message"] = "Pipeline finished. Inspect the manifest and outputs; heuristic humanoid rigging and starter motion require visual review before production use."
    except Exception as exc:
        if job["status"] != "FAILED": job["status"] = "FAILED"; job["error"] = str(exc)
    finally:
        job["finished_at"] = time.time(); _save(job, manifest)
    return job


async def _stage_async_generation(job: dict, manifest: Path, image_id: str, prompt: str):
    entry = {"name":"image_to_3d_generation", "status":"RUNNING", "started_at":time.time(), "required":True}
    job["stages"].append(entry); _save(job, manifest)
    try:
        result = await asset_studio.create_model([image_id], prompt, "single")
        if result.get("status") != "SUCCEEDED":
            raise RuntimeError("The configured local backend did not finish synchronously; use the existing task-status workflow.")
        entry.update(status="SUCCEEDED", result=result)
        return result
    except Exception as exc:
        entry.update(status="FAILED", error=str(exc)); job["status"]="FAILED"; job["error"]=f"image_to_3d_generation: {exc}"; _save(job,manifest); raise
    finally:
        entry["finished_at"] = time.time(); _save(job,manifest)


def get_character_job(job_id: str):
    if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id.lower()):
        raise ValueError("Invalid character job ID.")
    path = (ROOT / f"{job_id}.json").resolve()
    if not path.is_relative_to(ROOT) or not path.is_file(): raise ValueError("Character job not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def list_character_jobs(limit: int = 20):
    items=[]
    for path in sorted(ROOT.glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True)[:max(1,min(int(limit),100))]:
        try:
            job=json.loads(path.read_text(encoding="utf-8"))
            items.append({k:job.get(k) for k in ("job_id","status","created_at","final_model_path","error","warnings")})
        except Exception: pass
    return items
