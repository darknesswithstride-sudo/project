"""Local-only vision guidance for image-to-3D workflows; never uploads images remotely."""
from __future__ import annotations
import base64, json, re
from pathlib import Path
import httpx
from .config import WORKSPACE_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL

PROFILES = {"organic", "skin_pores", "fabric", "clothing", "damaged", "hard_surface"}

def _safe_image(relative_path: str) -> Path:
    p=(WORKSPACE_DIR/relative_path).resolve()
    if p != WORKSPACE_DIR and WORKSPACE_DIR not in p.parents: raise ValueError("Image path must remain inside the OmniForge workspace.")
    if not p.is_file(): raise ValueError("Image file not found in workspace.")
    if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}: raise ValueError("Supported images: PNG, JPG, WEBP, BMP.")
    if p.stat().st_size > 20*1024*1024: raise ValueError("Image must be 20 MB or smaller.")
    return p

async def analyze_reference(relative_path: str, goal: str = "Create a production-ready 3D asset") -> dict:
    path=_safe_image(relative_path)
    image64=base64.b64encode(path.read_bytes()).decode("ascii")
    base=OLLAMA_BASE_URL.split("/v1")[0].rstrip("/")
    prompt=("Analyze this reference image for a local 3D production pipeline. Return JSON only with keys: "
            "asset_summary (string), likely_materials (array strings), visible_features (array strings), "
            "uncertainties (array strings), detail_profile (one of organic, skin_pores, fabric, clothing, damaged, hard_surface), "
            "detail_intensity (number 0..2), target_faces (integer 5000..250000), texture_size (512,1024,2048,4096), "
            "modeling_steps (array strings), topology_risks (array strings). Do not claim unseen sides are known. "
            "Avoid hallucinating hidden anatomy; mark uncertain details explicitly. Goal: "+goal[:2000])
    async with httpx.AsyncClient(timeout=180) as client:
        r=await client.post(base+"/api/chat",json={"model":OLLAMA_MODEL,"stream":False,"format":"json","messages":[{"role":"user","content":prompt,"images":[image64]}]})
        r.raise_for_status(); raw=r.json().get("message",{}).get("content","")
    try: data=json.loads(raw)
    except Exception: raise RuntimeError("Local vision model did not return valid JSON. Try an Ollama vision-capable model (for example, a locally installed LLaVA model).")
    profile=data.get("detail_profile")
    if profile not in PROFILES: data["detail_profile"]="organic"
    try: data["detail_intensity"]=max(0.0,min(2.0,float(data.get("detail_intensity",1))))
    except Exception: data["detail_intensity"]=1.0
    try: data["target_faces"]=max(5000,min(250000,int(data.get("target_faces",50000))))
    except Exception: data["target_faces"]=50000
    if data.get("texture_size") not in [512,1024,2048,4096]: data["texture_size"]=2048
    return {"ok":True,"local_only":True,"model":OLLAMA_MODEL,"image_path":relative_path,"analysis":data,"note":"Single-view analysis cannot recover hidden geometry or guarantee production topology."}
