import json
import shutil
import uuid
import httpx
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import WORKSPACE_DIR, MESHY_API_KEY, THREED_PROVIDER, TRIPOSR_DIR, AI_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL
from .models import PromptRequest, BuildRequest, BlenderRequest, RepairRequest, ModelGenerationRequest, TaskStatusRequest, RigRequest, AnimationRequest, ApplyMotionRequest, LocalModelRequest, LocalOptimizeRequest, LocalAnimationRequest, AgentRunRequest, DetailRecommendationRequest, VisionAnalyzeRequest, IsolatedBuildRequest, WorktreeCreateRequest, WorktreePathRequest
from .agent import ask_model, parse_file_response, safe_workspace_path
from .build_runner import run_profile
from .repository import inspect_repository
from .repair import repair_loop
from .coding_engine import run_coding_agent, list_local_models
from .mesh import run_blender_script

from . import asset_studio

BASE_DIR = Path(__file__).resolve().parent.parent
app=FastAPI(title="OmniForge AI Free Local Edition",version="4.7.0",docs_url="/api/docs",redoc_url=None)
app.mount("/static",StaticFiles(directory=str(BASE_DIR / "app" / "static")),name="static")

@app.get("/",response_class=HTMLResponse)
def home():
    with open(BASE_DIR / "app" / "static" / "index.html",encoding="utf-8") as f: return f.read()

@app.get("/api/status")
def status():
    from .config import MODEL_BASE_URL,MODEL_NAME,BLENDER_EXE,UNREAL_BUILD_TOOL,MAX_REPAIR_ATTEMPTS
    import shutil
    return {"app":"OmniForge AI","version":"4.7.0","workspace":str(WORKSPACE_DIR),
            "model_configured": bool(AI_PROVIDER == "ollama" and OLLAMA_BASE_URL and OLLAMA_MODEL), "remote_paid_providers_enabled": False, "free_local_only": True,
            "ai_provider": AI_PROVIDER, "3d_provider": THREED_PROVIDER, "local_triposr_configured": bool(TRIPOSR_DIR), "local_3d_tools": True,"local_video_mocap": True,"blender_configured":bool(BLENDER_EXE),
            "unreal_build_tool_configured":bool(UNREAL_BUILD_TOOL),"repair_attempt_limit":MAX_REPAIR_ATTEMPTS,"image_to_3d_configured": bool((THREED_PROVIDER == "local" and TRIPOSR_DIR) or (THREED_PROVIDER != "local" and MESHY_API_KEY)),
            "toolchains":{"git":bool(shutil.which("git")),"node":bool(shutil.which("npm")),
            "dotnet":bool(shutil.which("dotnet")),"cmake":bool(shutil.which("cmake"))},
            "profiles":["python_compile","python_tests","node_tests","dotnet_build","cmake_build","unreal_build","list_files","git_status","git_diff"]}




@app.post("/api/chat/send")
async def chat_send(message: str = Form(...), session_id: str = Form("default"), reference_image: UploadFile | None = File(None)):
    """Single chat entry point. Jobs execute in the background and are polled by the chat UI."""
    try:
        image_info=None
        if reference_image is not None:
            image_info=await asset_studio.save_image(reference_image)
        from .chat_service import start_chat_job
        return await start_chat_job(message,session_id,".",3,image_info)
    except Exception as exc:
        raise HTTPException(status_code=400,detail=str(exc))

@app.get("/api/chat/jobs/{job_id}")
def chat_job(job_id: str):
    try:
        from .chat_service import get_job
        return get_job(job_id)
    except Exception as exc: raise HTTPException(status_code=404,detail=str(exc))

@app.get("/api/chat/preview/{filename}")
def chat_preview(filename: str):
    from .visual_inspection import ROOT as VISUAL_ROOT
    if filename != Path(filename).name or not filename.lower().endswith('.png'):
        raise HTTPException(status_code=400,detail="Invalid preview filename.")
    target=(VISUAL_ROOT/filename).resolve()
    if not target.is_relative_to(VISUAL_ROOT.resolve()) or not target.is_file():
        raise HTTPException(status_code=404,detail="Preview not found.")
    return FileResponse(target,media_type='image/png',filename=target.name)

@app.get("/api/chat/jobs")
def chat_jobs():
    from .chat_service import list_jobs
    return {"jobs":list_jobs()}

@app.get("/api/chat/history/{session_id}")
def chat_history(session_id: str):
    from .project_brain import history, recall
    return {"session_id":session_id,"messages":history(session_id,60),"memory":recall(".",18)}

@app.get("/api/chat/sessions")
def chat_sessions():
    from .project_brain import sessions
    return {"sessions":sessions()}

@app.get("/api/capabilities")
def capabilities_registry():
    from .capability_manager import registry_status
    return registry_status()

@app.post("/api/capabilities/research")
def capabilities_research(req: dict):
    from .capability_manager import research_capability
    try:
        return research_capability(str(req.get("goal", "")), bool(req.get("online", False)))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/capabilities/register-verified")
def capabilities_register_verified(req: dict):
    """Run an isolated smoke test and register metadata only if that test passes."""
    from .capability_manager import validate_candidate, promote_candidate
    try:
        manifest = req.get("manifest") or {}
        source = str(req.get("source", ""))
        test_result = validate_candidate(manifest, source)
        if test_result.get("status") != "VERIFIED":
            return {"status": "REJECTED", "test_result": test_result, "registered": False}
        promoted = promote_candidate(manifest, source, test_result)
        return {"status": "SUCCEEDED", "test_result": test_result, "registered": True, "promotion": promoted}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/unreal/installation")
def unreal_installation():
    from .unreal_game_factory import inspect_unreal_installation
    return inspect_unreal_installation()

@app.post("/api/unreal/deliver")
def unreal_delivery(req: dict):
    """Prepare asset intake, editor-driven level construction, QA evidence and Windows packaging scripts."""
    try:
        from .project_delivery import prepare_delivery, inspect_delivery_report
        if req.get("inspect_only"):
            return inspect_delivery_report(str(req.get("project_path", "")))
        return prepare_delivery(str(req.get("project_path", "")), req.get("asset_paths") or [],
                                str(req.get("level_name", "MainSurvivalLevel")),
                                str(req.get("package_platform", "Win64")))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/unreal/delivery-tools")
def unreal_delivery_tools():
    from .project_delivery import inspect_delivery_tools
    return inspect_delivery_tools()

@app.post("/api/autonomy/run")
async def run_autonomy(command: str = Form(...), project_path: str = Form("."), max_actions: int = Form(4), reference_image: UploadFile | None = File(None)):
    """Natural-language front door: plan and run only registered, bounded local tools."""
    if reference_image is not None:
        try:
            image = await asset_studio.save_image(reference_image)
            from .character_pipeline import run_character_pipeline
            result = await run_character_pipeline(image["id"], command, 50000, 2048, 3, "organic", 1.0, True, True, True, "walk", 24, True)
            return {"job_id": result.get("job_id"), "status": result.get("status"), "command": command,
                    "mode": "reference-image-character-pipeline", "reference_image": image, "result": result,
                    "local_only": True, "paid_api_calls": False}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    try:
        from .autonomous_engine import run_autonomous_task
        return await run_autonomous_task(command, project_path, max_actions)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/autonomy/jobs")
def autonomy_jobs():
    from .autonomous_engine import list_autonomous_jobs
    return {"jobs": list_autonomous_jobs()}

@app.post("/api/studio/pipeline")
def run_integrated_studio_pipeline(req: dict):
    """Run a reviewable local pipeline: inspect, optionally optimize, then package for production."""
    try:
        from .studio_pipeline import run_studio_pipeline
        return run_studio_pipeline(
            model_path=str(req.get("model_path", "")),
            inspect=bool(req.get("inspect", True)), optimize=bool(req.get("optimize", False)),
            production=bool(req.get("production", True)), target_faces=int(req.get("target_faces", 12000)),
            lod_count=int(req.get("lod_count", 3)), texture_size=int(req.get("texture_size", 2048)),
            detail_profile=str(req.get("detail_profile", "organic")), detail_intensity=float(req.get("detail_intensity", 1.0)),
            optimize_faces=int(req.get("optimize_faces", 50000)), export_format=str(req.get("export_format", "glb")),
            run_blender=bool(req.get("run_blender", True)))
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/studio/character-pipeline")
async def studio_character_pipeline(file: UploadFile = File(...), prompt: str = Form(""),
        target_faces: int = Form(50000), texture_size: int = Form(2048), lod_count: int = Form(3),
        detail_profile: str = Form("organic"), detail_intensity: float = Form(1.0),
        optimize: bool = Form(True), rig: bool = Form(True), animate: bool = Form(True),
        action: str = Form("walk"), fps: int = Form(24), package: bool = Form(True)):
    """Run local reference image -> mesh -> inspect/optimize/package -> humanoid rig -> starter animation."""
    try:
        image = await asset_studio.save_image(file)
        from .character_pipeline import run_character_pipeline
        result = await run_character_pipeline(image["id"], prompt, target_faces, texture_size, lod_count,
            detail_profile, detail_intensity, optimize, rig, animate, action, fps, package)
        result["reference_image"] = image
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/studio/character-jobs")
def studio_character_jobs():
    from .character_pipeline import list_character_jobs
    return {"jobs": list_character_jobs()}

@app.get("/api/studio/character-jobs/{job_id}")
def studio_character_job(job_id: str):
    try:
        from .character_pipeline import get_character_job
        return get_character_job(job_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/studio/jobs")
def studio_jobs():
    from .studio_pipeline import list_jobs
    return {"jobs": list_jobs()}

@app.get("/api/studio/jobs/{job_id}")
def studio_job(job_id: str):
    try:
        from .studio_pipeline import get_job
        return get_job(job_id)
    except Exception as e: raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/studio/catalog")
def studio_catalog():
    """Unified local asset catalog and readiness snapshot for the 3D Studio."""
    try:
        assets = asset_studio.list_assets()
    except Exception:
        assets = []
    from .advanced_3d import inventory
    from .production_pipeline import pipeline_status
    return {"studio_version": "4.7.0", "local_only": True, "assets": assets,
            "asset_count": len(assets), "backends": inventory(),
            "production": pipeline_status(),
            "workflow": ["reference", "reconstruction", "refinement", "rigging", "animation", "export"],
            "note": "Stages require compatible local tools/models. This endpoint reports availability; it does not imply every backend is installed."}

@app.get("/api/diagnostics")
async def diagnostics():
    """Check local dependencies without making paid API calls."""
    from .config import BLENDER_EXE, TRIPOSR_DIR, TRIPOSR_PYTHON, OLLAMA_BASE_URL, OLLAMA_MODEL, UNREAL_BUILD_TOOL
    from .autodetect import detect_tools, version_of
    detected = detect_tools()
    checks = {}
    checks["workspace"] = {"ok": WORKSPACE_DIR.exists(), "path": str(WORKSPACE_DIR)}
    checks["ollama"] = {"ok": False, "model": OLLAMA_MODEL, "url": OLLAMA_BASE_URL}
    try:
        base = OLLAMA_BASE_URL.split("/v1")[0].rstrip("/")
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(base + "/api/tags")
            checks["ollama"]["ok"] = r.is_success
            if r.is_success:
                payload = r.json()
                names = [m.get("name", "") for m in payload.get("models", [])]
                checks["ollama"]["installed_models"] = names
                checks["ollama"]["configured_model_installed"] = any(n == OLLAMA_MODEL or n.startswith(OLLAMA_MODEL + ":") for n in names)
    except Exception as exc:
        checks["ollama"]["message"] = "Ollama not reachable. Install/start Ollama and pull the configured model."
    blender_value = BLENDER_EXE or detected.get("blender_exe")
    blender_path = Path(blender_value).expanduser() if blender_value else None
    checks["blender"] = {"ok": bool(blender_path and blender_path.is_file()), "path": str(blender_path) if blender_path else "Not detected", "version": version_of(str(blender_path)) if blender_path else None}
    triposr_value = TRIPOSR_DIR or detected.get("triposr_dir")
    triposr_repo = Path(triposr_value).expanduser() if triposr_value else None
    checks["triposr"] = {"ok": bool(triposr_repo and (triposr_repo / "run.py").is_file()), "path": str(triposr_repo) if triposr_repo else "Not configured", "python": TRIPOSR_PYTHON}
    checks["ollama_executable"] = {"ok": bool(detected.get("ollama_exe")), "path": detected.get("ollama_exe")}
    checks["unreal_build_tool"] = {"ok": bool(UNREAL_BUILD_TOOL or detected.get("unreal_build_tool")), "path": UNREAL_BUILD_TOOL or detected.get("unreal_build_tool")}
    try:
        import torch
        checks["gpu"] = {"ok": bool(torch.cuda.is_available()), "torch_installed": True, "cuda_available": bool(torch.cuda.is_available()), "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    except Exception: checks["gpu"] = {"ok": False, "torch_installed": False, "note": "Run /api/3d/local/validate for full local GPU diagnostics."}
    checks["git"] = {"ok": bool(shutil.which("git")), "path": shutil.which("git")}
    checks["python"] = {"ok": True, "version": __import__("sys").version.split()[0]}
    return {"free_local_only": True, "paid_api_calls": False, "checks": checks,
            "next_steps": [k for k, v in checks.items() if not v.get("ok")],
            "note": "Diagnostics do not install dependencies or download model weights."}

@app.post("/api/plan")
async def plan(req:PromptRequest):
    try:
        return {"plan":await ask_model("Create a detailed development plan with architecture, milestones, file tree, dependencies, build/test strategy, risks and acceptance criteria.\nProject: "+req.project_name+"\nRequest: "+req.prompt)}
    except Exception as e: raise HTTPException(status_code=503,detail=str(e))

@app.post("/api/generate")
async def generate(req:PromptRequest):
    try:
        answer=await ask_model("Generate starter implementation files. Return ONLY JSON with summary and files [{path,content}]. Keep scope small and runnable. No destructive commands or arbitrary shell execution.\nProject: "+req.project_name+"\nRequest: "+req.prompt)
        data=parse_file_response(answer); written=[]
        for item in data["files"]:
            path=safe_workspace_path(item["path"]); path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists(): raise ValueError(f"Refusing to overwrite existing file without explicit review: {item['path']}")
            path.write_text(item["content"],encoding="utf-8"); written.append(item["path"])
        return {"summary":data.get("summary",""),"written_files":written,"review_required":True}
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/agent/capabilities")
def agent_capabilities():
    return {"engine":"OmniForge Agentic Coding Engine", "engine_version":"1.0", "free_local_only":True, "paid_api_calls":False, "features":["repository-aware planning", "relevance-ranked source context", "bounded multi-step implementation", "fixed-profile build/test verification", "automatic rollback on failed verification", "persistent JSON run reports", "local Ollama model inventory", "local multimodal reference analysis", "optional advanced 3D backend inventory", "disposable-copy verification", "Git worktrees and review diffs", "repeatable local model smoke benchmark"], "safety":{"arbitrary_shell_from_model":False,"protected_secret_paths":True,"max_steps":3,"max_patch_files":20,"verification_required_for_success":True}}

@app.get("/api/agent/models")
async def agent_models():
    return await list_local_models()

@app.post("/api/agent/run")
async def agent_run(req:AgentRunRequest):
    try:
        return await run_coding_agent(req.relative_path, req.task, req.profile, req.max_steps, req.apply_changes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/repository")
def repository(req:BuildRequest):
    try: return inspect_repository(req.relative_path)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/build")
def build(req:BuildRequest):
    try: return run_profile(req.profile,req.relative_path)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/repair")
async def repair(req:RepairRequest):
    try: return await repair_loop(req.relative_path,req.profile,req.goal,req.attempts)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/blender")
def blender(req:BlenderRequest):
    try: return run_blender_script(req.script_path)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/files")
def list_files():
    return {"files":[str(p.relative_to(WORKSPACE_DIR)) for p in WORKSPACE_DIR.rglob("*") if p.is_file()][:2000]}


@app.post("/api/3d/upload")
async def upload_3d_images(files: list[UploadFile] = File(...)):
    if not 1 <= len(files) <= 4: raise HTTPException(status_code=400, detail="Upload between 1 and 4 reference images.")
    saved=[]
    try:
        for file in files: saved.append(await asset_studio.save_image(file))
        return {"images":saved,"message":"Reference images saved to the local workspace."}
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/3d/generate")
async def generate_3d(req: ModelGenerationRequest):
    try: return await asset_studio.create_model(req.image_ids,req.prompt,req.model_type)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/3d/tasks/{task_type}/{task_id}")
async def get_3d_task(task_type: str, task_id: str):
    try: return await asset_studio.task_status(task_type,task_id)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/3d/download")
async def download_3d(req: TaskStatusRequest, fmt: str = "glb"):
    try: return await asset_studio.download_result(req.task_type,req.task_id,fmt)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/3d/rig")
async def rig_3d(req: RigRequest):
    try: return await asset_studio.rig_model(req.model_path,req.height_meters)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/3d/animate")
async def animate_3d(req: AnimationRequest):
    try: return await asset_studio.create_animation(req.rig_task_id,req.action_ids,req.motion_prompt)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.post("/api/3d/apply-motion")
async def apply_motion(req: ApplyMotionRequest):
    try: return await asset_studio.apply_motion(req.rig_task_id,req.motion_task_id)
    except Exception as e: raise HTTPException(status_code=400,detail=str(e))

@app.get("/api/3d/assets")
def list_3d_assets():
    return {"assets":asset_studio.list_assets()}


@app.get("/api/3d/files/{filename}")
def get_3d_file(filename: str):
    from pathlib import Path
    from .asset_studio import OUTPUT_DIR
    if filename != Path(filename).name: raise HTTPException(status_code=400, detail="Invalid filename.")
    target=(OUTPUT_DIR/filename).resolve()
    if not target.is_relative_to(OUTPUT_DIR.resolve()) or not target.is_file(): raise HTTPException(status_code=404,detail="Asset not found.")
    return FileResponse(target, filename=target.name)

@app.post("/api/3d/local/inspect")
def inspect_local_model(req: LocalModelRequest):
    try:
        from .local_3d_tools import inspect_model
        return inspect_model(req.model_path)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/3d/local/optimize")
def optimize_local_model(req: LocalOptimizeRequest):
    try:
        from .local_3d_tools import optimize_model
        return optimize_model(req.model_path, req.target_faces, req.export_format)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/3d/local/animate")
def animate_local_model(req: LocalAnimationRequest):
    try:
        from .local_3d_tools import animate_rig
        return animate_rig(req.model_path, req.action, req.fps)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/3d/local/rig")
def auto_rig_local_model(req: LocalOptimizeRequest):
    try:
        from .local_3d_tools import auto_rig_humanoid
        return auto_rig_humanoid(req.model_path, req.export_format)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/3d/mocap/upload")
async def upload_motion_capture_video(file: UploadFile = File(...)):
    from .mocap import CAPTURE_DIR, ALLOWED_VIDEO, MAX_VIDEO_BYTES
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO:
        raise HTTPException(status_code=400, detail="Supported video types: MP4, MOV, AVI, MKV, WEBM.")
    data = await file.read(MAX_VIDEO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded video is empty.")
    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video exceeds the 250 MB upload limit.")
    safe_stem = "".join(c for c in Path(file.filename or "video").stem if c.isalnum() or c in "-_ ").strip().replace(" ", "_")[:60] or "video"
    target = CAPTURE_DIR / f"{safe_stem}_{uuid.uuid4().hex[:8]}{suffix}"
    target.write_bytes(data)
    return {"ok": True, "video_path": str(target.relative_to(WORKSPACE_DIR)), "bytes": len(data), "message": "Video saved locally. Run pose extraction next."}

@app.post("/api/3d/mocap/process")
def process_motion_capture_video(req: LocalModelRequest):
    try:
        from .mocap import CAPTURE_DIR, process_video
        video = (WORKSPACE_DIR / req.model_path).resolve()
        if not video.is_relative_to(CAPTURE_DIR.resolve()):
            raise ValueError("Select a video uploaded through the Motion Capture panel.")
        return process_video(str(video))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/3d/local/validate")
def validate_local_3d_pipeline():
    try:
        from .local_3d_tools import validate_local_pipeline
        return validate_local_pipeline()
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/graphics/validate")
def validate_graphics_pipeline():
    from .graphics_lab import validate_graphics_pipeline as validate
    return validate()

@app.get("/api/graphics/presets")
def graphics_presets():
    from .graphics_lab import PRESETS
    return {"presets": PRESETS, "free_local_only": True}

@app.post("/api/graphics/create-pack")
def create_graphics_pack(req: dict):
    try:
        from .graphics_lab import create_pack
        preset = str(req.get("preset", "post_apocalyptic"))
        project_name = str(req.get("project_name", "OmniForge Graphics Starter"))[:100]
        seed = int(req.get("seed", 42))
        if seed < 0 or seed > 2_147_483_647: raise ValueError("Seed must be between 0 and 2147483647.")
        return create_pack(preset, project_name, seed, bool(req.get("run_blender", False)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/3d/local/smoke-test")
def smoke_test_local_blender(export_format: str = "glb"):
    try:
        from .local_3d_tools import smoke_test_blender
        return smoke_test_blender(export_format)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/vision/status")
def vision_status():
    from .config import OLLAMA_MODEL
    return {"local_only": True, "configured_model": OLLAMA_MODEL, "note": "Image understanding requires a locally installed Ollama vision-capable model; no image is uploaded to a remote service."}

@app.post("/api/vision/analyze-reference")
async def analyze_vision_reference(req: VisionAnalyzeRequest):
    try:
        from .vision_director import analyze_reference
        return await analyze_reference(req.image_path, req.goal)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/3d/backends")
def advanced_3d_backends():
    from .advanced_3d import inventory
    return inventory()

@app.post("/api/build/isolated")
def isolated_build(req: IsolatedBuildRequest):
    try:
        from .sandbox_runner import run_isolated
        return run_isolated(req.profile, req.relative_path, req.keep_copy)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/worktrees/create")
def create_agent_worktree(req: WorktreeCreateRequest):
    try:
        from .worktrees import create_worktree
        return create_worktree(req.relative_path, req.branch_name)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/worktrees/diff")
def get_agent_worktree_diff(req: WorktreePathRequest):
    try:
        from .worktrees import worktree_diff
        return worktree_diff(req.relative_path)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/worktrees/remove")
def remove_agent_worktree(req: WorktreePathRequest):
    try:
        from .worktrees import remove_worktree
        return remove_worktree(req.relative_path, req.force)
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/agent/benchmark")
async def benchmark_local_model():
    try:
        from .benchmark_suite import run_benchmark
        return await run_benchmark()
    except Exception as e: raise HTTPException(status_code=503, detail=str(e))

@app.get("/api/production/status")
def production_pipeline_status():
    from .production_pipeline import pipeline_status
    return pipeline_status()

@app.post("/api/production/recommend-detail")
async def recommend_production_detail(req:DetailRecommendationRequest):
    try:
        from .detail_director import recommend_detail
        return await recommend_detail(req.description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/production/build")
def build_production_asset(req: dict):
    """Build local LOD/export/validation package for an existing workspace asset."""
    try:
        from .production_pipeline import run_pipeline
        relative_path = str(req.get("model_path", ""))
        if not relative_path: raise ValueError("model_path is required and must point to a file inside the workspace.")
        return run_pipeline(relative_path, req.get("target_faces", 12000), req.get("lod_count", 3), req.get("texture_size", 2048), req.get("run_blender", True), req.get("detail_profile", "organic"), req.get("detail_intensity", 1.0))
    except Exception as e: raise HTTPException(status_code=400, detail=str(e))
