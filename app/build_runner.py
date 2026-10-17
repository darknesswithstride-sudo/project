import subprocess, sys, time, shutil, os, importlib.util
from pathlib import Path
from .config import WORKSPACE_DIR, LOG_DIR, UNREAL_BUILD_TOOL
from .agent import safe_workspace_path
from .repository import git_command

def _run(cmd, cwd, timeout=600):
    started=time.time()
    result=subprocess.run(cmd,cwd=str(cwd),capture_output=True,text=True,timeout=timeout,shell=False)
    output=(result.stdout or "")+(result.stderr or "")
    log=LOG_DIR/f"build_{int(started)}.log"
    log.write_text(output,encoding="utf-8",errors="replace")
    return {"ok":result.returncode==0,"exit_code":result.returncode,"duration_seconds":round(time.time()-started,2),
            "command_profile":" ".join(str(x) for x in cmd[:4]),"output":output[-30000:],"log_file":log.name}

def run_profile(profile, relative_path="."):
    target=safe_workspace_path(relative_path)
    if not target.exists(): raise ValueError("Target path does not exist in workspace.")
    if profile=="list_files":
        return {"ok":True,"exit_code":0,"output":"\n".join(str(p.relative_to(WORKSPACE_DIR)) for p in target.rglob("*") if p.is_file())[:30000]}
    if profile=="git_status": return git_command(relative_path,["status","--short"])
    if profile=="git_diff": return git_command(relative_path,["diff","--"])
    if profile=="python_compile": return _run([sys.executable,"-m","compileall","-q",str(target)],WORKSPACE_DIR)
    if profile=="python_tests":
        if importlib.util.find_spec("pytest"):
            return _run([sys.executable,"-m","pytest","-q"],target,timeout=900)
        return _run([sys.executable,"-m","unittest","discover","-s",str(target)],WORKSPACE_DIR,timeout=900)
    if profile=="node_tests":
        if not shutil.which("npm"): raise ValueError("Node.js/npm not installed.")
        if not (target/"package.json").is_file(): raise ValueError("No package.json in target.")
        return _run(["npm","test","--","--runInBand"],target,timeout=900)
    if profile=="dotnet_build":
        if not shutil.which("dotnet"): raise ValueError(".NET SDK not installed.")
        projects=list(target.glob("*.sln"))+list(target.glob("*.csproj"))
        if not projects: raise ValueError("No .sln or .csproj in target root.")
        return _run(["dotnet","build",str(projects[0]),"--nologo"],target,timeout=1200)
    if profile=="cmake_build":
        if not shutil.which("cmake"): raise ValueError("CMake not installed.")
        if not (target/"CMakeLists.txt").exists(): raise ValueError("CMakeLists.txt not found.")
        build_dir=target/"build"
        build_dir.mkdir(exist_ok=True)
        configure=_run(["cmake","-S",str(target),"-B",str(build_dir)],target,timeout=1200)
        if not configure["ok"]: return configure
        return _run(["cmake","--build",str(build_dir),"--config","Release"],target,timeout=1800)
    if profile=="unreal_build":
        if not UNREAL_BUILD_TOOL: raise ValueError("Set UNREAL_BUILD_TOOL in .env to UnrealBuildTool or a build wrapper.")
        uprojects=list(target.glob("*.uproject"))
        if not uprojects: raise ValueError("No .uproject file in target root.")
        # The project must already define a valid target; do not guess its target name.
        target_name=uprojects[0].stem
        unreal_cmd=[UNREAL_BUILD_TOOL,target_name,"Development","Win64",f"-Project={uprojects[0]}","-WaitMutex"]
        # Windows batch files must be launched through cmd.exe; .exe tools run directly.
        if sys.platform == "win32" and str(UNREAL_BUILD_TOOL).lower().endswith(".bat"):
            unreal_cmd=[os.environ.get("COMSPEC","cmd.exe"),"/d","/s","/c",subprocess.list2cmdline(unreal_cmd)]
        return _run(unreal_cmd,target,timeout=2400)
    raise ValueError("Unsupported build profile.")
