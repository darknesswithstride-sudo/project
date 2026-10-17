"""Best-effort discovery of free local tools on Windows, macOS and Linux."""
import os, shutil, subprocess
from pathlib import Path

def _valid_file(value):
    if not value: return None
    p=Path(value).expanduser()
    return str(p.resolve()) if p.is_file() else None

def _from_path(names):
    for n in names:
        found=shutil.which(n)
        if found: return _valid_file(found)
    return None

def detect_tools():
    home=Path.home(); env=os.environ
    blender_candidates=[]
    if env.get('BLENDER_EXE'): blender_candidates.append(env['BLENDER_EXE'])
    roots=[Path('C:/Program Files/Blender Foundation'),Path('C:/Program Files (x86)/Blender Foundation'),home/'Applications',Path('/Applications/Blender.app/Contents/MacOS'),Path('/usr/bin'),Path('/usr/local/bin'),Path('/opt/homebrew/bin')]
    for base in roots:
        try:
            if not base.is_dir(): continue
            if base.name in ('bin','MacOS'):
                blender_candidates.extend([base/'blender',base/'Blender',base/'blender.exe'])
            else:
                for pattern in ('Blender*/blender.exe','Blender*/blender','Blender*/Contents/MacOS/Blender'):
                    blender_candidates.extend(sorted(base.glob(pattern),reverse=True))
        except OSError: pass
    blender=next((v for p in blender_candidates if (v:=_valid_file(p))),None) or _from_path(['blender','blender.exe'])
    ollama=_from_path(['ollama','ollama.exe']) or next((v for p in [Path(env.get('LOCALAPPDATA','C:/Users/Default/AppData/Local'))/'Programs/Ollama/ollama.exe',Path('/usr/local/bin/ollama'),Path('/opt/homebrew/bin/ollama')] if (v:=_valid_file(p))),None)
    unreal_candidates=[]
    if env.get('UNREAL_BUILD_TOOL'): unreal_candidates.append(env['UNREAL_BUILD_TOOL'])
    for var in ['ProgramFiles','ProgramFiles(x86)']:
        base=Path(env.get(var,'C:/Program Files'))/'Epic Games'
        try:
            for ver in sorted(base.glob('UE_*'),reverse=True):
                unreal_candidates.extend([ver/'Engine/Build/BatchFiles/Build.bat',ver/'Engine/Binaries/Win64/UnrealBuildTool.exe',ver/'Engine/Binaries/Linux/UnrealBuildTool'])
        except OSError: pass
    unreal=next((v for p in unreal_candidates if (v:=_valid_file(p))),None) or _from_path(['UnrealBuildTool','UnrealBuildTool.exe'])
    tr_candidates=[]
    if env.get('TRIPOSR_DIR'): tr_candidates.append(Path(env['TRIPOSR_DIR'])/'run.py')
    tr_candidates.extend([home/'TripoSR/run.py',home/'src/TripoSR/run.py',home/'Projects/TripoSR/run.py',Path.cwd()/'TripoSR/run.py'])
    tr_file=next((v for p in tr_candidates if (v:=_valid_file(p))),None)
    return {'blender_exe':blender,'ollama_exe':ollama,'unreal_build_tool':unreal,'triposr_dir':str(Path(tr_file).parent) if tr_file else None}

def version_of(exe,args=('--version',),timeout=8):
    if not exe: return {'installed':False,'version':None,'error':'Not detected'}
    try:
        p=subprocess.run([exe,*args],capture_output=True,text=True,timeout=timeout,shell=False)
        out=(p.stdout+'\n'+p.stderr).strip().splitlines()
        return {'installed':True,'version':out[0][:250] if out else 'Version command returned no text','returncode':p.returncode}
    except Exception as e: return {'installed':True,'version':None,'error':str(e)}
