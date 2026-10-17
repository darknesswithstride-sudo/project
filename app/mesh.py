import subprocess
from .config import BLENDER_EXE
from .agent import safe_workspace_path

def run_blender_script(relative_script):
    if not BLENDER_EXE: raise RuntimeError("Blender executable not configured. Set BLENDER_EXE in .env.")
    script=safe_workspace_path(relative_script)
    if not script.is_file() or script.suffix.lower()!=".py": raise ValueError("Choose a Python script inside the workspace.")
    result=subprocess.run([BLENDER_EXE,"--background","--python",str(script)],cwd=str(script.parent),
                          capture_output=True,text=True,timeout=900,shell=False)
    output=(result.stdout or "")+(result.stderr or "")
    return {"ok":result.returncode==0,"exit_code":result.returncode,"output":output[-30000:]}
