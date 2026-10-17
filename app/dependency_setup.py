"""Safe, explicit dependency setup for common project manifests; no model-authored commands."""
from __future__ import annotations
import subprocess, sys, time
from pathlib import Path
from .config import WORKSPACE_DIR
from .agent import safe_workspace_path

def setup_dependencies(relative_path: str='.') -> dict:
    root=safe_workspace_path(relative_path)
    if not root.exists() or not root.is_dir(): raise ValueError('Project folder does not exist inside the workspace.')
    results=[]
    req=root/'requirements.txt'
    pyproject=root/'pyproject.toml'
    if req.is_file():
        cmd=[sys.executable,'-m','pip','install','-r',str(req)]
        try:
            p=subprocess.run(cmd,cwd=str(root),capture_output=True,text=True,timeout=900,shell=False)
            results.append({'manager':'pip','manifest':str(req.relative_to(WORKSPACE_DIR)),'exit_code':p.returncode,'stdout':p.stdout[-6000:],'stderr':p.stderr[-6000:]})
        except subprocess.TimeoutExpired: results.append({'manager':'pip','manifest':str(req.relative_to(WORKSPACE_DIR)),'exit_code':124,'error':'Dependency install exceeded 15 minutes.'})
    elif pyproject.is_file():
        cmd=[sys.executable,'-m','pip','install','-e',str(root)]
        try:
            p=subprocess.run(cmd,cwd=str(root),capture_output=True,text=True,timeout=900,shell=False)
            results.append({'manager':'pip','manifest':str(pyproject.relative_to(WORKSPACE_DIR)),'exit_code':p.returncode,'stdout':p.stdout[-6000:],'stderr':p.stderr[-6000:]})
        except subprocess.TimeoutExpired: results.append({'manager':'pip','manifest':str(pyproject.relative_to(WORKSPACE_DIR)),'exit_code':124,'error':'Dependency install exceeded 15 minutes.'})
    package=root/'package.json'
    if package.is_file():
        results.append({'manager':'npm','manifest':str(package.relative_to(WORKSPACE_DIR)),'status':'NOT_RUN','reason':'npm install can execute arbitrary package lifecycle scripts; OmniForge will not run those scripts unattended. Ask to review the package manifest or approve a controlled install.'})
    if not results: return {'status':'NO_MANIFEST','project':str(root),'message':'No requirements.txt or pyproject.toml found. No package was installed.','local_only':True}
    ok=all(r.get('exit_code',0)==0 for r in results if r.get('exit_code') is not None)
    return {'status':'SUCCEEDED' if ok else 'COMPLETED_WITH_WARNINGS','project':str(root),'results':results,'local_only':True,'paid_api_calls':False}
