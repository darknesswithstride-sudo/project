"""Free/local-first 3D asset studio. TripoSR runs locally; cloud API is not required."""
import base64, mimetypes, re, json, subprocess, uuid, shutil, asyncio
from pathlib import Path
from urllib.parse import urlparse
import httpx
from fastapi import UploadFile
from .config import WORKSPACE_DIR, MESHY_API_KEY, MESHY_BASE_URL, THREED_PROVIDER, TRIPOSR_DIR, TRIPOSR_PYTHON

ASSET_DIR = WORKSPACE_DIR / "omniforge_assets"
INPUT_DIR = ASSET_DIR / "inputs"
OUTPUT_DIR = ASSET_DIR / "outputs"
TASK_DIR = ASSET_DIR / "tasks"
for _p in (INPUT_DIR, OUTPUT_DIR, TASK_DIR): _p.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_MODEL_BYTES = 400 * 1024 * 1024


def _require_key():
    if not MESHY_API_KEY:
        raise RuntimeError("Meshy API is not configured. Add MESHY_API_KEY to .env; API access/credits may be required.")


def _headers():
    _require_key()
    return {"Authorization": f"Bearer {MESHY_API_KEY}", "Content-Type": "application/json"}


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")[:100] or "asset"

async def save_image(upload: UploadFile):
    suffix = Path(upload.filename or "image.png").suffix.lower()
    if suffix not in ALLOWED_IMAGE:
        raise ValueError(f"Unsupported image type {suffix or '(none)'}. Use PNG, JPG, JPEG, or WEBP.")
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be non-empty and no larger than 20 MB.")
    # Verify basic image signature instead of trusting only the filename.
    signatures = {".png": data.startswith(b"\x89PNG\r\n\x1a\n"), ".jpg": data.startswith(b"\xff\xd8\xff"), ".jpeg": data.startswith(b"\xff\xd8\xff"), ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP"}
    if not signatures.get(suffix, False): raise ValueError("Image contents do not match the file extension.")
    import uuid
    asset_id = uuid.uuid4().hex
    path = INPUT_DIR / f"{asset_id}{suffix}"
    path.write_bytes(data)
    return {"id": asset_id, "filename": _safe_name(upload.filename or path.name), "path": str(path.relative_to(WORKSPACE_DIR)), "bytes": len(data), "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream"}


def _input_path(asset_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", asset_id): raise ValueError("Invalid image asset ID.")
    matches = list(INPUT_DIR.glob(asset_id + ".*"))
    if not matches or not matches[0].is_file(): raise ValueError(f"Uploaded image not found: {asset_id}")
    return matches[0]


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

async def _post(endpoint: str, payload: dict):
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(f"{MESHY_BASE_URL}{endpoint}", headers=_headers(), json=payload)
        if r.is_error: raise RuntimeError(f"Meshy API {r.status_code}: {r.text[:1500]}")
        return r.json()

async def _get(endpoint: str):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(f"{MESHY_BASE_URL}{endpoint}", headers=_headers())
        if r.is_error: raise RuntimeError(f"Meshy API {r.status_code}: {r.text[:1500]}")
        return r.json()

async def create_model(image_ids: list[str], prompt: str = "", model_type: str = "single"):
    if THREED_PROVIDER == "local":
        if model_type == "multi":
            raise RuntimeError("Free local mode currently supports single-image TripoSR reconstruction. Multi-view fusion is not wired into this build.")
        if not TRIPOSR_DIR:
            raise RuntimeError("Free local image-to-3D is selected, but TRIPOSR_DIR is not set. Install the open-source TripoSR repo, then set TRIPOSR_DIR in .env. No paid API is used.")
        if not 1 <= len(image_ids) <= 1:
            raise ValueError("Local TripoSR mode accepts one image per generation.")
        src = _input_path(image_ids[0])
        repo = Path(TRIPOSR_DIR).expanduser().resolve()
        runner = repo / "run.py"
        if not runner.is_file():
            raise RuntimeError(f"TRIPOSR_DIR does not contain run.py: {repo}")
        task_id = uuid.uuid4().hex
        task_output = OUTPUT_DIR / f"triposr_{task_id}"
        task_output.mkdir(parents=True, exist_ok=True)
        cmd = [TRIPOSR_PYTHON or "python", str(runner), str(src), "--output-dir", str(task_output)]
        try:
            completed = await asyncio.to_thread(subprocess.run, cmd, cwd=str(repo), capture_output=True, text=True, timeout=1800, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Local TripoSR generation timed out after 30 minutes. Try a smaller image or check GPU setup.") from exc
        if completed.returncode != 0:
            raise RuntimeError("Local TripoSR failed. Check that its dependencies/model weights are installed. Output: " + (completed.stderr or completed.stdout)[-2500:])
        generated = [p for p in task_output.rglob("*") if p.is_file() and p.suffix.lower() in {".obj", ".glb", ".ply", ".mtl", ".png"}]
        if not generated:
            raise RuntimeError("TripoSR finished but no supported mesh output was found. Check the installed TripoSR version and its output format.")
        for p in generated:
            if p.parent != OUTPUT_DIR:
                dest = OUTPUT_DIR / f"{task_id}_{_safe_name(p.name)}"
                shutil.copy2(p, dest)
        record = {"task_id": task_id, "task_type": "image-to-3d", "status": "SUCCEEDED", "progress": 100,
                  "provider": "local TripoSR", "message": "Generated locally; no paid API used.",
                  "files": [str((OUTPUT_DIR / f"{task_id}_{_safe_name(p.name)}").relative_to(WORKSPACE_DIR)) for p in generated]}
        (TASK_DIR / f"{task_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record
    if not 1 <= len(image_ids) <= 4: raise ValueError("Upload 1 to 4 images.")
    paths = [_input_path(x) for x in image_ids]
    if model_type == "multi" and len(paths) < 2: raise ValueError("Multi-view mode needs at least two images.")
    if model_type not in {"single", "multi"}: raise ValueError("Model type must be single or multi.")
    if model_type == "multi":
        payload = {"image_urls": [_data_uri(p) for p in paths], "ai_model": "latest", "should_texture": True, "enable_pbr": True, "target_formats": ["glb", "fbx", "obj"]}
        if prompt.strip(): payload["texture_prompt"] = prompt.strip()[:1000]
        endpoint = "/openapi/v1/multi-image-to-3d"
    else:
        payload = {"image_url": _data_uri(paths[0]), "ai_model": "latest", "should_texture": True, "enable_pbr": True, "target_formats": ["glb", "fbx", "obj"]}
        if prompt.strip(): payload["texture_prompt"] = prompt.strip()[:1000]
        endpoint = "/openapi/v1/image-to-3d"
    result = await _post(endpoint, payload)
    task_id = result.get("result") or result.get("id")
    if not task_id: raise RuntimeError(f"Meshy did not return a task ID: {result}")
    return {"task_id": task_id, "task_type": "multi-image-to-3d" if model_type == "multi" else "image-to-3d", "status": "PENDING", "message": "Generation started. Poll task status; generation may take several minutes."}

async def task_status(task_type: str, task_id: str):
    if THREED_PROVIDER == "local":
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", task_id): raise ValueError("Invalid task ID.")
        task_file = TASK_DIR / f"{task_id}.json"
        if task_file.is_file(): return json.loads(task_file.read_text(encoding="utf-8"))
        raise ValueError("Local task not found. Local generation runs synchronously and keeps its task record in workspace/omniforge_assets/tasks.")
    endpoint = _task_endpoint(task_type)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", task_id): raise ValueError("Invalid task ID.")
    return await _get(f"{endpoint}/{task_id}")

async def rig_model(model_path_rel: str, height_meters: float = 1.7):
    if THREED_PROVIDER == "local":
        raise RuntimeError("Paid auto-rigging is disabled. For a zero-cost workflow, open the model in Blender and use its built-in Rigify tools for supported humanoids; automatic arbitrary-mesh rigging is not included in this free local build.")
    if not 0.1 <= height_meters <= 10: raise ValueError("Height must be between 0.1 and 10 meters.")
    path = (WORKSPACE_DIR / model_path_rel).resolve()
    if not path.is_relative_to(WORKSPACE_DIR) or not path.is_file() or path.suffix.lower() != ".glb":
        raise ValueError("Choose a GLB file inside the workspace.")
    if path.stat().st_size > 100 * 1024 * 1024: raise ValueError("Rigging data URI limit is 100 MB; use a smaller GLB.")
    payload = {"model_url": _data_uri(path), "height_meters": height_meters, "generate_basic_animations": True}
    result = await _post("/openapi/v1/rigging", payload)
    task_id = result.get("result") or result.get("id")
    if not task_id: raise RuntimeError(f"Meshy did not return a rigging task ID: {result}")
    return {"task_id": task_id, "task_type": "rigging", "status": "PENDING", "message": "Auto-rigging started. Best results are expected for clear, textured humanoid characters."}

async def create_animation(rig_task_id: str, action_ids: list[int] | None = None, motion_prompt: str = ""):
    if THREED_PROVIDER == "local":
        raise RuntimeError("Paid motion-generation APIs are disabled. Use Blender's free animation tools or locally installed motion-capture/animation assets. Text-to-motion generation is not bundled in this build.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", rig_task_id): raise ValueError("Invalid rigging task ID.")
    if motion_prompt.strip():
        payload = {"mode": "prime", "prompt": motion_prompt.strip()[:400], "duration": 3}
        motion = await _post("/openapi/v1/text-to-motion", payload)
        motion_id = motion.get("result") or motion.get("id")
        if not motion_id: raise RuntimeError(f"Meshy did not return a motion task ID: {motion}")
        return {"task_id": motion_id, "task_type": "text-to-motion", "status": "PENDING", "message": "Motion clip generation started. After it succeeds, apply its task ID to the rig using the animation endpoint."}
    ids = action_ids or [0]
    if not 1 <= len(ids) <= 10 or any(not isinstance(i, int) or i < 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Provide 1–10 unique non-negative animation library action IDs.")
    payload = {"rig_task_id": rig_task_id}
    if len(ids) == 1: payload["action_id"] = ids[0]
    else: payload["action_ids"] = ids
    result = await _post("/openapi/v1/animations", payload)
    task_id = result.get("result") or result.get("id")
    if not task_id: raise RuntimeError(f"Meshy did not return an animation task ID: {result}")
    return {"task_id": task_id, "task_type": "animations", "status": "PENDING"}

async def apply_motion(rig_task_id: str, motion_task_id: str):
    if THREED_PROVIDER == "local":
        raise RuntimeError("Cloud motion retargeting is disabled in free mode. Retarget animation locally in Blender after preparing a compatible rig and motion clip.")
    result = await _post("/openapi/v1/animations", {"rig_task_id": rig_task_id, "motion_task_id": motion_task_id})
    task_id = result.get("result") or result.get("id")
    if not task_id: raise RuntimeError(f"Meshy did not return an animation task ID: {result}")
    return {"task_id": task_id, "task_type": "animations", "status": "PENDING"}

def _task_endpoint(task_type: str):
    routes = {"image-to-3d": "/openapi/v1/image-to-3d", "multi-image-to-3d": "/openapi/v1/multi-image-to-3d", "rigging": "/openapi/v1/rigging", "animations": "/openapi/v1/animations", "text-to-motion": "/openapi/v1/text-to-motion"}
    if task_type not in routes: raise ValueError("Unsupported task type.")
    return routes[task_type]

async def download_result(task_type: str, task_id: str, fmt: str = "glb"):
    task = await task_status(task_type, task_id)
    if THREED_PROVIDER == "local":
        files = []
        for rel in task.get("files", []):
            p = (WORKSPACE_DIR / rel).resolve()
            if p.is_file() and p.suffix.lower().lstrip(".") == fmt.lower():
                files.append({"name": p.name, "path": rel, "url": "/api/3d/files/" + p.name, "bytes": p.stat().st_size})
        return {"status": task.get("status", "SUCCEEDED"), "progress": 100, "task": task, "downloaded": files,
                "message": "No matching file for requested format." if not files else "Local files are ready."}
    status = task.get("status", "UNKNOWN")
    if status != "SUCCEEDED": return {"status": status, "progress": task.get("progress", 0), "task": task, "downloaded": []}
    urls = []
    if task_type in {"image-to-3d", "multi-image-to-3d"}:
        model_urls = task.get("model_urls") or {}
        if fmt not in model_urls: raise ValueError(f"Format {fmt} is not available. Available: {', '.join(model_urls.keys()) or 'none'}")
        urls.append((fmt, model_urls[fmt]))
    elif task_type == "rigging":
        result = task.get("result") or {}
        key = "rigged_character_fbx_url" if fmt == "fbx" else "rigged_character_glb_url"
        if result.get(key): urls.append((fmt, result[key]))
        if fmt == "all":
            for k,v in result.items():
                if k.endswith("_url") and v: urls.append((k.replace("rigged_character_", ""),v))
            for k,v in (result.get("basic_animations") or {}).items():
                if v: urls.append((k,v))
    elif task_type == "animations":
        result = task.get("result") or {}
        key = "animation_fbx_url" if fmt == "fbx" else "animation_glb_url"
        if result.get(key): urls.append((fmt, result[key]))
    elif task_type == "text-to-motion":
        result = task.get("result") or {}
        motion_url = result.get("motion_url")
        motion_format = result.get("motion_format", "fbx")
        if motion_url and (fmt == "all" or fmt == motion_format): urls.append(("motion_" + motion_format, motion_url))
    if not urls: return {"status": status, "progress": 100, "task": task, "downloaded": [], "message": "Task succeeded, but no matching downloadable asset URL was present in the response."}
    downloaded=[]
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        for label,url in urls:
            if not isinstance(url,str) or urlparse(url).scheme != "https": continue
            r=await client.get(url)
            if r.is_error: raise RuntimeError(f"Asset download failed ({r.status_code}) for {label}.")
            if len(r.content)>MAX_MODEL_BYTES: raise ValueError("Downloaded asset exceeds the 400 MB safety limit.")
            suffix = "." + ("glb" if "glb" in label else "fbx" if "fbx" in label else "obj" if "obj" in label else "bvh" if "bvh" in label else "bin")
            name = _safe_name(f"{task_type}_{task_id}_{label}") + suffix
            target=OUTPUT_DIR/name
            target.write_bytes(r.content)
            downloaded.append({"name":name,"path":str(target.relative_to(WORKSPACE_DIR)),"url":"/api/3d/files/" + name,"bytes":len(r.content)})
    return {"status": status, "progress": 100, "task": task, "downloaded": downloaded}

def list_assets():
    items=[]
    for folder in (INPUT_DIR,OUTPUT_DIR):
        for p in folder.iterdir():
            if p.is_file(): items.append({"name":p.name,"path":str(p.relative_to(WORKSPACE_DIR)),"bytes":p.stat().st_size,"kind":"input" if folder==INPUT_DIR else "output"})
    return sorted(items,key=lambda x:x["name"])
