"""Detect optional local 3D generators and provide transparent setup guidance."""
import os, shutil, sys
from pathlib import Path
from .config import WORKSPACE_DIR, TRIPOSR_DIR, TRIPOSR_PYTHON

def _probe(name, envvar, expected, repo_url, notes):
    raw=os.getenv(envvar,"").strip(); path=Path(raw).expanduser() if raw else None
    ok=bool(path and path.exists() and any((path/x).exists() for x in expected))
    return {"name":name,"configured":bool(raw),"ready":ok,"path":str(path) if path else None,"env_var":envvar,"repository":repo_url,"notes":notes}

def inventory():
    tools=[{"name":"TripoSR","configured":bool(TRIPOSR_DIR),"ready":bool(TRIPOSR_DIR and (Path(TRIPOSR_DIR)/"run.py").is_file()),"path":TRIPOSR_DIR or None,"python":TRIPOSR_PYTHON,"repository":"https://github.com/VAST-AI-Research/TripoSR","notes":"Existing single-image reconstruction backend; infer unseen surfaces."},
      _probe("Microsoft TRELLIS","TRELLIS_DIR",["app.py","trellis"],"https://github.com/microsoft/TRELLIS","High-quality image/text-to-3D. Official repo states Linux-tested and NVIDIA GPU with at least 16 GB VRAM; Windows is not fully tested."),
      _probe("Tencent Hunyuan3D","HUNYUAN3D_DIR",["hy3dgen","infer","README.md"],"https://github.com/Tencent-Hunyuan/Hunyuan3D-2","Advanced image-to-3D candidate. Check upstream model/code license, CUDA/PyTorch compatibility, and VRAM requirements before installing.")]
    return {"free_local_only":True,"tools":tools,"recommendation":"Use the backend whose dependencies, license, GPU memory, and export format fit your PC. This detector does not download multi-gigabyte model weights.","workspace":str(WORKSPACE_DIR)}
