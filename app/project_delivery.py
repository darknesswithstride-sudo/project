"""Unreal project delivery pipeline: asset intake, level authoring, QA evidence and packaging.

Creates reviewable local scripts/manifests. Engine-dependent stages are only marked complete
when their actual process ran and returned success; generated scripts are never counted as tests.
"""
from __future__ import annotations
import json, os, shutil, time, zipfile
from pathlib import Path
from typing import Any
from .config import WORKSPACE_DIR, BLENDER_EXE, UNREAL_BUILD_TOOL

ROOT = (WORKSPACE_DIR / "OmniForgeGames").resolve()
ASSET_EXTENSIONS = {".fbx":"StaticMesh", ".obj":"StaticMesh", ".glb":"StaticMesh", ".gltf":"StaticMesh", ".png":"Texture", ".jpg":"Texture", ".jpeg":"Texture", ".tga":"Texture", ".wav":"Sound", ".ogg":"Sound", ".mp3":"Sound", ".uasset":"UnrealAsset"}

def _inside(path: Path, root: Path) -> bool:
    try: return path.resolve().is_relative_to(root.resolve())
    except Exception: return False

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")

def inspect_delivery_tools() -> dict:
    ue_root = os.getenv("UE_ROOT", "") or os.getenv("UNREAL_ENGINE_ROOT", "")
    ue_editor = None
    if ue_root:
        for candidate in (Path(ue_root)/"Engine/Binaries/Win64/UnrealEditor-Cmd.exe", Path(ue_root)/"Engine/Binaries/Win64/UnrealEditor.exe", Path(ue_root)/"Engine/Binaries/Linux/UnrealEditor-Cmd"):
            if candidate.exists(): ue_editor = str(candidate); break
    blender = BLENDER_EXE or shutil.which("blender")
    return {"unreal_build_tool_configured":bool(UNREAL_BUILD_TOOL),"unreal_root_configured":bool(ue_root),"unreal_editor_detected":bool(ue_editor),"unreal_editor_path":ue_editor,"blender_detected":bool(blender),"blender_path":blender,"notes":"Tool detection is not proof that the project builds or runs."}

def prepare_delivery(project_path: str, asset_paths: list[str] | None = None, level_name: str = "MainSurvivalLevel", package_platform: str = "Win64") -> dict:
    """Prepare an Unreal project's content intake, editor level-builder, QA plan and packaging scripts."""
    raw = Path(project_path)
    project = (raw if raw.is_absolute() else (WORKSPACE_DIR/raw)).resolve()
    if not _inside(project, ROOT) or not project.is_dir():
        raise ValueError(f"Project must be an existing directory inside {ROOT}")
    up = list(project.glob("*.uproject"))
    if not up: raise ValueError("No .uproject found in project directory")
    project_name = up[0].stem
    safe_level = "".join(c for c in level_name if c.isalnum() or c == "_")[:48] or "MainSurvivalLevel"
    content = project / "Content"
    inbox = content / "OmniForgeImported"
    inbox.mkdir(parents=True, exist_ok=True)
    assets=[]; warnings=[]
    for item in asset_paths or []:
        src=Path(item).expanduser().resolve()
        if not src.is_file(): warnings.append(f"Asset not found: {item}"); continue
        ext=src.suffix.lower()
        if ext not in ASSET_EXTENSIONS: warnings.append(f"Unsupported asset type skipped: {src.name}"); continue
        # Stage external source assets under a predictable, reviewable folder; Unreal imports them on editor script run.
        dst=inbox/src.name
        if src != dst.resolve(): shutil.copy2(src,dst)
        assets.append({"source":str(src),"staged_path":str(dst),"relative_path":dst.relative_to(project).as_posix(),"type":ASSET_EXTENSIONS[ext],"extension":ext,"bytes":dst.stat().st_size,"imported_into_unreal":False})
    asset_manifest={"project":project_name,"created_at":time.time(),"assets":assets,"warnings":warnings,"status":"STAGED" if assets else "NO_EXTERNAL_ASSETS_STAGED"}
    _write(project/"Delivery"/"asset_manifest.json",json.dumps(asset_manifest,indent=2))
    # Runs inside Unreal Editor Python; import staged source assets and construct a blockout level with robust fallback primitives.
    editor_script = r'''import unreal, json, os, math
PROJECT = unreal.Paths.project_dir()
ROOT = os.path.join(PROJECT, "Content", "OmniForgeImported")
DEST = "/Game/OmniForgeImported"
LEVEL_NAME = "__LEVEL__"
LOG = os.path.join(PROJECT, "Delivery", "editor_pipeline_result.json")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
result={"imports":[],"level_created":False,"spawned_actors":0,"errors":[],"engine_ran":True}
try:
    tasks=[]
    for base, dirs, files in os.walk(ROOT):
        for fn in files:
            ext=os.path.splitext(fn)[1].lower()
            if ext not in (".fbx", ".obj", ".glb", ".gltf", ".png", ".jpg", ".jpeg", ".tga", ".wav", ".ogg", ".mp3"): continue
            task=unreal.AssetImportTask(); task.filename=os.path.join(base,fn); task.destination_path=DEST
            task.automated=True; task.save=True; task.replace_existing=True; task.replace_existing_settings=False
            tasks.append(task)
    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        for t in tasks: result["imports"].append({"source":t.filename,"imported":list(t.imported_object_paths)})
    level_path="/Game/OmniForgeLevels/"+LEVEL_NAME
    unreal.EditorAssetLibrary.make_directory("/Game/OmniForgeLevels")
    unreal.EditorLevelLibrary.new_level(level_path)
    # Large ground plane and survival route markers, all editable actors in a real UE level.
    cube=unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube:
        def spawn_cube(label, loc, scale, color=None):
            actor=unreal.EditorLevelLibrary.spawn_actor_from_object(cube, unreal.Vector(*loc), unreal.Rotator(0,0,0))
            if actor:
                actor.set_actor_label(label); actor.set_actor_scale3d(unreal.Vector(*scale)); result["spawned_actors"]+=1
                if color:
                    try:
                        mat=unreal.MaterialInstanceDynamic.create(unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"), actor)
                        mat.set_vector_parameter_value("Color",unreal.LinearColor(*color)); actor.set_material(0,mat)
                    except Exception: pass
                return actor
        spawn_cube("OF_Level_Ground",(0,0,-80),(80,80,1))
        # Grid of cover, salvage points and navigation landmarks. Labels support later AI/editor review.
        for i in range(6):
            x=(i-2.5)*850
            spawn_cube("OF_Cover_Barricade_%02d"%i,(x,750,60),(2.4,.25,1.2))
            spawn_cube("OF_Salvage_Landmark_%02d"%i,(x,-550,90),(.6,.6,1.8))
        for i in range(4):
            spawn_cube("OF_Route_Marker_%02d"%i,(-900+i*600,0,20),(.18, .18, .18))
    unreal.EditorLevelLibrary.save_current_level()
    result["level_created"]=True; result["level_path"]=level_path
except Exception as e:
    result["errors"].append(str(e))
with open(LOG,"w",encoding="utf-8") as f: json.dump(result,f,indent=2)
print("OMNIFORGE_DELIVERY_RESULT="+json.dumps(result))
'''.replace("__LEVEL__",safe_level)
    _write(project/"Delivery"/"UnrealEditor-ImportAssets-And-BuildLevel.py",editor_script)
    test_plan={"project":project_name,"created_at":time.time(),"tests":[
        {"id":"compile_editor_target","kind":"engine_build","pass_condition":"Unreal build tool exits 0 for Editor Development target","status":"NOT_RUN"},
        {"id":"editor_import_and_level","kind":"editor_python","pass_condition":"editor_pipeline_result.json has level_created=true and errors=[]","status":"NOT_RUN"},
        {"id":"level_visual_review","kind":"visual","pass_condition":"Capture editor/gameplay screenshots; check missing assets, scale, collisions, lighting and player start","status":"NOT_RUN"},
        {"id":"player_controls","kind":"functional","pass_condition":"WASD/mouse, attack, harvest, build, sprint, save/load work in PIE","status":"NOT_RUN"},
        {"id":"gameplay_loop","kind":"functional","pass_condition":"Zombie pursuit/damage, night waves and survival loop behave as specified","status":"NOT_RUN"},
        {"id":"packaged_smoke_test","kind":"package","pass_condition":"Windows package launches and a short smoke test completes","status":"NOT_RUN"}],"status":"PLAN_GENERATED"}
    _write(project/"Delivery"/"qa_test_plan.json",json.dumps(test_plan,indent=2))
    # Package script verifies compiled build and writes a manifest after the user/engine actually packages.
    build_bat=f'''@echo off\nsetlocal\nif "%UE_ROOT%"=="" (echo Set UE_ROOT to Unreal Engine installation folder & exit /b 2)\nset UPROJECT=%~dp0..\\{project_name}.uproject\n"%UE_ROOT%\\Engine\\Build\\BatchFiles\\Build.bat" {project_name}Editor Win64 Development "%UPROJECT%" -WaitMutex -FromMsBuild\nif errorlevel 1 exit /b %errorlevel%\n"%UE_ROOT%\\Engine\\Build\\BatchFiles\\RunUAT.bat" BuildCookRun -project="%UPROJECT%" -noP4 -platform={package_platform} -clientconfig=Development -build -cook -stage -pak -archive -archivedirectory="%~dp0..\\Build\\{package_platform}"\nif errorlevel 1 exit /b %errorlevel%\npython "%~dp0Write-Package-Manifest.py"\nexit /b %errorlevel%\n'''
    _write(project/"Delivery"/"Build-Test-Package-Windows.bat",build_bat)
    manifest_py='''from pathlib import Path\nimport json,time,sys\nr=Path(__file__).resolve().parents[1]; build=r/"Build"/"Win64"\nfiles=[str(p.relative_to(r)) for p in build.rglob("*") if p.is_file()] if build.exists() else []\nstatus="PACKAGED" if files else "BUILD_OUTPUT_MISSING"\nreport={"project":r.name,"created_at":time.time(),"package_status":status,"file_count":len(files),"files":files[:500],"verified_launch":False,"note":"File presence is not proof of successful launch; mark verified_launch only after running the packaged game."}\n(r/"Delivery"/"package_manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")\nprint(json.dumps(report,indent=2));sys.exit(0 if files else 2)\n'''
    _write(project/"Delivery"/"Write-Package-Manifest.py",manifest_py)
    report={"status":"PREPARED","project_name":project_name,"project_path":str(project),"asset_count_staged":len(assets),"assets":assets,"warnings":warnings,"generated_files":["Delivery/asset_manifest.json","Delivery/UnrealEditor-ImportAssets-And-BuildLevel.py","Delivery/qa_test_plan.json","Delivery/Build-Test-Package-Windows.bat","Delivery/Write-Package-Manifest.py"],"toolchain":inspect_delivery_tools(),"engine_import_executed":False,"visual_review_completed":False,"functional_tests_passed":False,"package_built":False,"next_steps":["Run the Unreal Editor Python script from the project's editor Python console or commandlet.","Inspect the generated level and imported assets in the Unreal Editor; capture screenshots for visual review.","Run the QA checklist and fix each failure before packaging.","Run Delivery/Build-Test-Package-Windows.bat on Windows with UE_ROOT set."]}
    _write(project/"Delivery"/"delivery_report.json",json.dumps(report,indent=2))
    return report

def inspect_delivery_report(project_path: str) -> dict:
    raw=Path(project_path); project=(raw if raw.is_absolute() else WORKSPACE_DIR/raw).resolve()
    if not _inside(project,ROOT): raise ValueError("Project must be inside OmniForgeGames workspace")
    f=project/"Delivery"/"delivery_report.json"
    if not f.is_file(): return {"status":"NOT_PREPARED","project_path":str(project)}
    report=json.loads(f.read_text(encoding="utf-8"))
    for key, filename in (("editor_result","editor_pipeline_result.json"),("package_result","package_manifest.json")):
        p=project/"Delivery"/filename
        if p.exists(): report[key]=json.loads(p.read_text(encoding="utf-8"))
    return report
