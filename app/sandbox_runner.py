"""Best-effort isolated verification by copying a project into a disposable workspace directory."""
from __future__ import annotations
import shutil, uuid, time
from pathlib import Path
from .config import WORKSPACE_DIR
from .agent import safe_workspace_path
from .build_runner import run_profile

IGNORE=shutil.ignore_patterns('.git','.venv','venv','node_modules','__pycache__','.pytest_cache','Binaries','Intermediate','Saved','.env','credentials.json','secrets.json')
ALLOWED={'python_compile','python_tests','node_tests','dotnet_build','cmake_build','unreal_build'}
def run_isolated(profile: str, relative_path: str='.', keep_copy: bool=False) -> dict:
    if profile not in ALLOWED: raise ValueError('Only fixed build/test profiles are allowed in isolated verification.')
    source=safe_workspace_path(relative_path)
    if not source.is_dir(): raise ValueError('Project path must be an existing directory inside workspace.')
    if source == WORKSPACE_DIR: raise ValueError('Select a project subdirectory, not the entire workspace root.')
    sandbox_root=(WORKSPACE_DIR/'.omniforge_sandboxes').resolve(); sandbox_root.mkdir(parents=True,exist_ok=True)
    dest=sandbox_root/(uuid.uuid4().hex[:12])
    started=time.time()
    shutil.copytree(source,dest,ignore=IGNORE,symlinks=False)
    relative=dest.relative_to(WORKSPACE_DIR).as_posix()
    try:
        result=run_profile(profile,relative)
        return {"ok":bool(result.get('ok')),"profile":profile,"isolated_copy":relative,"duration_seconds":round(time.time()-started,2),"verification":result,"copy_retained":keep_copy,"security_note":"Disposable copy protects original project files, but this is not an OS/container security boundary. Tests/build scripts can still execute code on the host."}
    finally:
        if not keep_copy: shutil.rmtree(dest,ignore_errors=True)
