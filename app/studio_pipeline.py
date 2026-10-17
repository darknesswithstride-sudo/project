"""Integrated local asset pipeline orchestration. Runs only explicitly requested local stages."""
from __future__ import annotations
import json, uuid, time
from pathlib import Path
from .config import WORKSPACE_DIR
from .production_pipeline import run_pipeline
from .local_3d_tools import inspect_model, optimize_model
from .asset_studio import OUTPUT_DIR

JOBS = (WORKSPACE_DIR / "omniforge_assets" / "studio_jobs").resolve()
JOBS.mkdir(parents=True, exist_ok=True)
ALLOWED = {".glb", ".gltf", ".fbx", ".obj", ".ply", ".stl", ".blend"}

def _input(value):
    p = Path(value)
    p = p.resolve() if p.is_absolute() else (WORKSPACE_DIR / p).resolve()
    if not p.is_relative_to(WORKSPACE_DIR.resolve()):
        raise ValueError("Model path must stay inside the OmniForge workspace.")
    if not p.is_file() or p.suffix.lower() not in ALLOWED:
        raise ValueError("Choose an existing supported model file inside the workspace.")
    return p

def run_studio_pipeline(model_path: str, inspect: bool = True, optimize: bool = False,
                        production: bool = True, target_faces: int = 12000,
                        lod_count: int = 3, texture_size: int = 2048,
                        detail_profile: str = "organic", detail_intensity: float = 1.0,
                        optimize_faces: int = 50000, export_format: str = "glb",
                        run_blender: bool = True):
    source = _input(model_path)
    job_id = uuid.uuid4().hex
    job = {"job_id": job_id, "status": "RUNNING", "created_at": time.time(),
           "input": str(source.relative_to(WORKSPACE_DIR)), "local_only": True,
           "stages": [], "outputs": [], "warnings": []}
    manifest = JOBS / f"{job_id}.json"
    def save(): manifest.write_text(json.dumps(job, indent=2), encoding="utf-8")
    def stage(name, fn):
        entry = {"name": name, "status": "RUNNING", "started_at": time.time()}
        job["stages"].append(entry); save()
        try:
            result = fn(); entry.update(status="SUCCEEDED", result=result)
            for key in ("output", "report_file"):
                if isinstance(result, dict) and result.get(key): job["outputs"].append(result[key])
            return result
        except Exception as exc:
            entry.update(status="FAILED", error=str(exc)); job["status"] = "FAILED"; job["error"] = f"{name}: {exc}"; save(); raise
        finally:
            entry["finished_at"] = time.time(); save()
    try:
        current = str(source.relative_to(WORKSPACE_DIR))
        if inspect:
            stage("inspect", lambda: inspect_model(current))
        if optimize:
            result = stage("optimize", lambda: optimize_model(current, optimize_faces, export_format))
            current = result["output"]
        if production:
            result = stage("production_package", lambda: run_pipeline(current, target_faces, lod_count, texture_size,
                    run_blender, detail_profile, detail_intensity))
            job["production_result"] = result
            if isinstance(result, dict):
                for key in ("manifest", "output_dir", "package"):
                    if result.get(key): job["outputs"].append(result[key])
        job["status"] = "SUCCEEDED"
        job["final_model_path"] = current
        job["message"] = "Requested stages completed. Rigging and animation are separate stages and require a compatible rig/toolchain."
    except Exception:
        if job["status"] != "FAILED": job["status"] = "FAILED"
    finally:
        job["finished_at"] = time.time(); save()
    return job

def get_job(job_id: str):
    if not isinstance(job_id, str) or not (8 <= len(job_id) <= 64) or not all(c in "0123456789abcdef" for c in job_id.lower()):
        raise ValueError("Invalid studio job ID.")
    p = (JOBS / f"{job_id}.json").resolve()
    if not p.is_relative_to(JOBS) or not p.is_file(): raise ValueError("Studio job not found.")
    return json.loads(p.read_text(encoding="utf-8"))

def list_jobs(limit: int = 20):
    files = sorted(JOBS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max(1,min(limit,100))]
    out=[]
    for p in files:
        try:
            j=json.loads(p.read_text(encoding="utf-8")); out.append({k:j.get(k) for k in ("job_id","status","created_at","input","final_model_path","error")})
        except Exception: continue
    return out
