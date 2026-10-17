"""Local-first natural-language task router for OmniForge.

The planner can select only registered, bounded tools. It cannot submit shell commands.
Every run is persisted as an audit manifest, and individual tool results are retained.
"""
from __future__ import annotations
import asyncio, json, re, time, uuid
from pathlib import Path
from .config import WORKSPACE_DIR, LOG_DIR
from .agent import ask_model

ROOT = (WORKSPACE_DIR / "omniforge_assets" / "autonomous_runs").resolve()
ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_ACTIONS = {"diagnostics", "repository", "build", "repair", "coding", "graphics_pack", "graphics_validate", "production_build", "studio_pipeline", "3d_validate", "vision_status", "setup_dependencies", "visual_inspect", "unreal_game", "unreal_deliver", "capability_research", "capability_registry", "capability_develop"}
BUILD_PROFILES = {"python_compile", "python_tests", "node_tests", "dotnet_build", "cmake_build", "unreal_build"}

SYSTEM = """You are OmniForge's local autonomous project manager. Convert the user's request into a short sequence of actions using ONLY this allowlist: diagnostics, repository, build, repair, coding, graphics_pack, graphics_validate, production_build, studio_pipeline, 3d_validate, vision_status, setup_dependencies, visual_inspect, unreal_game, unreal_deliver, capability_research, capability_registry, capability_develop. Return ONLY JSON: {\"summary\":string,\"actions\":[{\"tool\":string,\"reason\":string,\"args\":object}]}. At most 6 actions. Available args: repository/coding/build/repair use relative_path; coding uses task, profile, max_steps (1-3); build uses profile; repair uses profile, goal, attempts (1-3); graphics_pack uses preset (post_apocalyptic/dark_forest/industrial/desert), project_name, seed, run_blender=false; production_build uses model_path,target_faces,lod_count,texture_size,run_blender,detail_profile,detail_intensity; studio_pipeline uses model_path,inspect,optimize,production,target_faces,lod_count,texture_size,detail_profile,detail_intensity,optimize_faces,export_format,run_blender; setup_dependencies uses relative_path; visual_inspect uses model_path; unreal_game uses project_name, game_brief, ue_version; unreal_deliver uses project_path, asset_paths, level_name, package_platform; capability_research uses goal, online; capability_develop uses goal, online; other tools take no args. Use workspace-relative paths only. Never invent a model path. For vague coding/build requests use coding or build. For game/environment art requests use graphics_pack and then optionally coding to build supporting project files. For existing mesh optimization/export use studio_pipeline or production_build. For requests to inspect/fix a repository, use repository/build/repair/coding as needed. Do not propose arbitrary shell, destructive file deletion, external paid services, cloud APIs, credentials, or actions outside the allowlist. Do not claim a tool succeeded before execution."""


def _fallback_plan(command: str, project_path: str) -> dict:
    s = command.lower()
    actions = []
    base = {"relative_path": project_path or "."}
    if any(w in s for w in ("unreal", "full game", "complete game", "survival game", "zombie game", "game project")) and any(w in s for w in ("make", "build", "create", "generate", "develop", "implement", "complete", "full game", "unreal")) and not any(w in s for w in ("integration", "capability", "teach yourself", "can't perform", "cannot perform")):
        pname = "AshfallSurvival"
        m = re.search(r"(?:called|named|title(?:d)?|name\s*[:=])\s+[\"']?([A-Za-z][A-Za-z0-9 _-]{2,48})", command, re.I)
        if m: pname = re.sub(r"[^A-Za-z0-9_]", "", m.group(1).replace(" ", ""))[:48] or pname
        actions.append({"tool":"unreal_game","reason":"Generate a self-contained Unreal Engine C++ survival-game project scaffold with gameplay systems and build instructions.","args":{"project_name":pname,"game_brief":command[:1800],"ue_version":"5.4"}})
    if any(w in s for w in ("implement missing integration", "develop a capability", "build an integration", "add a capability", "teach yourself to", "can't perform", "cannot perform", "missing integration")):
        actions.append({"tool":"capability_develop","reason":"Research the missing capability, create a candidate adapter in an isolated workspace, test it, and register it only after verification.","args":{"goal":command[:1000],"online":any(w in s for w in ("online", "github", "internet", "web"))}})
    if any(w in s for w in ("research a capability", "research how to add", "missing capability", "find an integration", "research suitable", "capability research")) and not actions:
        actions.append({"tool":"capability_research","reason":"Research candidate implementations and prepare a safe integration plan.","args":{"goal":command[:1000],"online":any(w in s for w in ("online", "github", "internet", "web"))}})
    if any(w in s for w in ("list capabilities", "capability registry", "what tools can you use", "show your capabilities")):
        actions.append({"tool":"capability_registry","reason":"Report currently registered built-in and verified capabilities.","args":{}})
    if any(a["tool"] in {"unreal_game", "unreal_deliver", "capability_research", "capability_registry", "capability_develop"} for a in actions):
        return {"summary":"Run the requested Unreal project or capability workflow.","actions":actions[:6],"planner":"fallback"}
    if any(w in s for w in ("diagnos", "dependencies", "what is installed", "check setup", "toolchain")) and not actions:
        actions.append({"tool":"diagnostics","reason":"Check local dependencies and configured backends.","args":{}})
    if any(w in s for w in ("environment", "biome", "landscape", "level art", "scene", "graphics pack", "world art")):
        preset = "dark_forest" if "forest" in s else "industrial" if any(w in s for w in ("industrial", "factory")) else "desert" if "desert" in s else "post_apocalyptic"
        actions.append({"tool":"graphics_pack","reason":"Create a reproducible local graphics starter pack.","args":{"preset":preset,"project_name":command[:80],"seed":42,"run_blender":False}})
    if any(w in s for w in ("optimize", "lod", "package", "export", "refine", "mesh")) and any(ext in s for ext in (".glb", ".gltf", ".fbx", ".obj", ".blend", "model path")):
        match = re.search(r"(?:model(?:\s+path)?\s*[:=]?\s*)([\w./\\-]+\.(?:glb|gltf|fbx|obj|blend|ply|stl))", command, re.I)
        if match:
            actions.append({"tool":"studio_pipeline","reason":"Inspect and optionally optimize/package the specified existing mesh.","args":{"model_path":match.group(1).replace('\\','/'),"inspect":True,"optimize":True,"production":True,"target_faces":12000,"lod_count":3,"texture_size":2048,"detail_profile":"organic","detail_intensity":1.0,"optimize_faces":50000,"export_format":"glb","run_blender":True}})
    if any(w in s for w in ("install dependencies", "setup dependencies", "install requirements", "dependency setup")):
        actions.append({"tool":"setup_dependencies","reason":"Install only dependencies declared in a recognized project manifest.","args":{"relative_path":project_path or "."}})
    if any(w in s for w in ("visually inspect", "render preview", "visual review", "look at the model", "inspect the model visually")):
        match = re.search(r"([\w./\\-]+\.(?:glb|gltf|fbx|obj|blend|ply|stl))", command, re.I)
        if match: actions.append({"tool":"visual_inspect","reason":"Render a preview and request local vision critique when supported.","args":{"model_path":match.group(1).replace('\\','/')}})
    wants_fix = any(w in s for w in ("fix", "repair", "broken", "failing", "error"))
    wants_verify = any(w in s for w in ("test", "tests", "verify", "build", "compile", "run the project"))
    if wants_fix:
        profile = "python_tests" if any(w in s for w in ("test", "tests", "unit test")) else "python_compile"
        actions.append({"tool":"repair","reason":"Attempt a bounded repair with a fixed verifier.","args":{"relative_path":project_path or ".","profile":profile,"goal":command[:2000],"attempts":2}})
        if wants_verify:
            actions.append({"tool":"build","reason":"Independently verify the repaired project with the requested fixed build/test profile.","args":{"relative_path":project_path or ".","profile":profile}})
    elif wants_verify:
        profile = "python_tests" if any(w in s for w in ("test", "tests", "unit test")) else "python_compile"
        actions.append({"tool":"build","reason":"Run the closest safe fixed build/test profile.","args":{"relative_path":project_path or ".","profile":profile}})
    if not actions:
        actions.append({"tool":"coding","reason":"Implement the requested change using the repository-aware local coding agent.","args":{"relative_path":project_path or ".","task":command,"profile":"python_tests" if any(w in s for w in ("test", "tests")) else "python_compile","max_steps":3}})
    return {"summary":"Rule-based local fallback plan (local language model was unavailable or returned an unusable plan).", "actions":actions[:6], "planner":"fallback"}


def _normalize_plan(plan: dict, command: str, project_path: str) -> dict:
    if not isinstance(plan, dict) or not isinstance(plan.get("actions"), list):
        raise ValueError("Planner output must contain an actions list.")
    actions=[]
    for item in plan["actions"][:6]:
        if not isinstance(item, dict): continue
        tool=item.get("tool")
        if tool not in ALLOWED_ACTIONS: continue
        args=item.get("args") if isinstance(item.get("args"),dict) else {}
        # Override risky or model-invented paths with the user's explicit workspace-relative project root.
        if tool in {"coding","repository","build","repair"}:
            args["relative_path"] = project_path or "."
        if tool == "coding":
            args["task"] = command
            args["profile"] = args.get("profile") if args.get("profile") in BUILD_PROFILES else ("python_tests" if "test" in command.lower() else "python_compile")
            args["max_steps"] = max(1,min(3,int(args.get("max_steps",3))))
        if tool in {"build","repair"} and args.get("profile") not in BUILD_PROFILES: args["profile"]="python_tests" if "test" in command.lower() else "python_compile"
        if tool == "repair": args["goal"] = command[:2000]; args["attempts"] = max(1,min(3,int(args.get("attempts",2))))
        if tool == "graphics_pack":
            if args.get("preset") not in {"post_apocalyptic","dark_forest","industrial","desert"}: args["preset"]="post_apocalyptic"
            args["project_name"] = str(args.get("project_name") or command[:80])[:100]
            args["seed"] = max(0,min(2147483647,int(args.get("seed",42))))
            args["run_blender"] = False # generate artifacts first; never unexpectedly launch a long render
        if tool == "unreal_game":
            args["project_name"] = str(args.get("project_name") or "AshfallSurvival")[:80]
            args["game_brief"] = command[:1800]
            args["ue_version"] = str(args.get("ue_version") or "5.4")[:12]
        if tool in {"capability_research", "capability_develop"}:
            args["goal"] = str(args.get("goal") or command)[:1200]
            args["online"] = bool(args.get("online", False))
        if tool in {"production_build","studio_pipeline","visual_inspect"}:
            model_path=str(args.get("model_path", ""))
            if not model_path or Path(model_path).is_absolute() or ".." in Path(model_path.replace('\\','/')).parts:
                continue
            args["model_path"] = model_path.replace('\\','/')
            args["run_blender"] = bool(args.get("run_blender", True))
        actions.append({"tool":tool,"reason":str(item.get("reason", "Selected by the local planner."))[:300],"args":args})
    if not actions:
        return _fallback_plan(command, project_path)
    return {"summary":str(plan.get("summary","Execute the requested task with available local tools."))[:1000],"actions":actions,"planner":"ollama"}

async def _plan(command: str, project_path: str) -> dict:
    try:
        from .coding_engine import select_local_model
        selection = await select_local_model()
        chosen_model = selection.get("selected_model")
        raw=await ask_model(SYSTEM + "\nUser project path: " + (project_path or ".") + "\nUser request: " + command,
            system="You are a strict JSON planner. Output only valid JSON and choose only registered actions.", model_override=chosen_model)
        raw=raw.strip()
        if raw.startswith("```"):
            raw=re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
        plan = _normalize_plan(json.loads(raw), command, project_path)
        plan["model"] = chosen_model
        return plan
    except Exception:
        return _fallback_plan(command, project_path)

async def _execute(action: dict) -> dict:
    tool, a = action["tool"], action["args"]
    if tool == "diagnostics":
        from .main import diagnostics
        return await diagnostics()
    if tool == "repository":
        from .repository import inspect_repository
        return await asyncio.to_thread(inspect_repository, a.get("relative_path", "."))
    if tool == "build":
        from .build_runner import run_profile
        return await asyncio.to_thread(run_profile, a.get("profile","python_compile"), a.get("relative_path","."))
    if tool == "repair":
        from .repair import repair_loop
        return await repair_loop(a.get("relative_path","."), a.get("profile","python_compile"), a.get("goal","Fix the requested issue safely."), a.get("attempts",2))
    if tool == "coding":
        from .coding_engine import run_coding_agent
        return await run_coding_agent(a.get("relative_path","."), a.get("task",""), a.get("profile","python_compile"), a.get("max_steps",3), True)
    if tool == "graphics_pack":
        from .graphics_lab import create_pack
        return await asyncio.to_thread(create_pack, a.get("preset","post_apocalyptic"), a.get("project_name","OmniForge Autonomous Pack"), a.get("seed",42), False)
    if tool == "graphics_validate":
        from .graphics_lab import validate_graphics_pipeline
        return await asyncio.to_thread(validate_graphics_pipeline)
    if tool == "production_build":
        from .production_pipeline import run_pipeline
        return await asyncio.to_thread(run_pipeline, a["model_path"], int(a.get("target_faces",12000)), int(a.get("lod_count",3)), int(a.get("texture_size",2048)), bool(a.get("run_blender",True)), a.get("detail_profile","organic"), float(a.get("detail_intensity",1.0)))
    if tool == "studio_pipeline":
        from .studio_pipeline import run_studio_pipeline
        return await asyncio.to_thread(run_studio_pipeline, a["model_path"], bool(a.get("inspect",True)), bool(a.get("optimize",True)), bool(a.get("production",True)), int(a.get("target_faces",12000)), int(a.get("lod_count",3)), int(a.get("texture_size",2048)), a.get("detail_profile","organic"), float(a.get("detail_intensity",1.0)), int(a.get("optimize_faces",50000)), a.get("export_format","glb"), bool(a.get("run_blender",True)))
    if tool == "3d_validate":
        from .local_3d_tools import validate_local_pipeline
        return await asyncio.to_thread(validate_local_pipeline)
    if tool == "vision_status":
        from .config import OLLAMA_MODEL
        return {"local_only": True, "configured_model": OLLAMA_MODEL, "note": "Image understanding requires a locally installed Ollama vision-capable model."}
    if tool == "setup_dependencies":
        from .dependency_setup import setup_dependencies
        return await asyncio.to_thread(setup_dependencies, a.get("relative_path", "."))
    if tool == "visual_inspect":
        from .visual_inspection import inspect_visual
        return await asyncio.to_thread(inspect_visual, a.get("model_path", ""))
    if tool == "unreal_game":
        from .unreal_game_factory import generate_unreal_game, build_and_repair_generated_game
        from .project_delivery import prepare_delivery
        generated = await asyncio.to_thread(generate_unreal_game, a.get("project_name", "AshfallSurvival"), a.get("game_brief", ""), a.get("ue_version", "5.4"))
        built = await build_and_repair_generated_game(generated, max_repair_attempts=1)
        try:
            delivery = await asyncio.to_thread(prepare_delivery, built.get("project_path", ""), [], "MainSurvivalLevel", "Win64")
            built["delivery_pipeline"] = delivery
        except Exception as exc:
            built["delivery_pipeline"] = {"status":"PREPARATION_FAILED", "error":str(exc)}
        return built
    if tool == "unreal_deliver":
        from .project_delivery import prepare_delivery
        return await asyncio.to_thread(prepare_delivery, a.get("project_path", "."), a.get("asset_paths", []), a.get("level_name", "MainSurvivalLevel"), a.get("package_platform", "Win64"))
    if tool == "capability_research":
        from .capability_manager import research_capability
        return await asyncio.to_thread(research_capability, a.get("goal", "Missing capability"), bool(a.get("online", False)))
    if tool == "capability_registry":
        from .capability_manager import registry_status
        return registry_status()
    if tool == "capability_develop":
        from .capability_manager import develop_capability
        return await develop_capability(a.get("goal", ""), bool(a.get("online", False)))
    raise ValueError("Action is not registered.")

_DEPENDENCY_HINTS = (
    "no module named", "modulenotfounderror", "importerror", "not installed",
    "command not found", "is not recognized as an internal or external command",
    "cannot find the path", "missing dependency", "missing package", "no such file or directory",
)
_FAILURE_STATUSES = {"FAILED", "ERROR", "BLOCKED", "REPAIR_ATTEMPTS_EXHAUSTED_OR_FAILED",
                     "ROLLED_BACK_VERIFICATION_FAILED", "ERROR_ROLLED_BACK", "FAILED_VERIFICATION"}


def _result_failed(result: object) -> bool:
    """Interpret heterogeneous tool results conservatively; don't equate a returned dict with success."""
    if not isinstance(result, dict):
        return False
    status = str(result.get("status", "")).upper()
    if status in _FAILURE_STATUSES or status.endswith("_FAILED") or status.endswith("_BLOCKED"):
        return True
    if result.get("ok") is False:
        return True
    if isinstance(result.get("exit_code"), int) and result["exit_code"] != 0:
        return True
    for item in result.get("results", []) if isinstance(result.get("results"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("exit_code"), int) and item["exit_code"] != 0:
            return True
    # The coding agent's rollback status means the requested change was not verified.
    if status in {"ROLLED_BACK_VERIFICATION_FAILED", "ERROR_ROLLED_BACK", "NO_CHANGES_PROPOSED"}:
        return True
    return False


def _dependency_error(result: object) -> bool:
    try:
        body = json.dumps(result, ensure_ascii=False).lower()
    except Exception:
        body = str(result).lower()
    return any(hint in body for hint in _DEPENDENCY_HINTS)


async def _recover_failed_action(action: dict, result: object, command: str, project_path: str) -> dict:
    """Perform bounded, tool-specific recovery. Never executes model-authored shell commands."""
    tool = action["tool"]
    report = {"attempted": True, "steps": [], "recovered": False}
    args = action.get("args", {})

    # A missing Python dependency is the only case where installing declared dependencies
    # is attempted automatically. npm lifecycle scripts and arbitrary shell commands stay disabled.
    if tool != "setup_dependencies" and _dependency_error(result):
        try:
            setup = await _execute({"tool": "setup_dependencies", "reason": "Recover missing declared project dependencies", "args": {"relative_path": project_path or "."}})
            report["steps"].append({"step": "setup_declared_dependencies", "result": setup})
            setup_ok = isinstance(setup, dict) and setup.get("status") == "SUCCEEDED"
            if setup_ok:
                retry = await _execute(action)
                report["steps"].append({"step": "retry_after_dependency_setup", "result": retry})
                if not _result_failed(retry):
                    report.update(recovered=True, recovered_result=retry, strategy="dependency_setup_and_retry")
                    return report
                result = retry
        except Exception as exc:
            report["steps"].append({"step": "setup_declared_dependencies", "error": str(exc)[:2000]})

    # Code/build failures get a targeted repair cycle, followed by an independent verifier.
    # A repair action has already consumed its own attempts, so do not recursively repair it.
    if tool in {"coding", "build", "repair"} and tool != "repair":
        profile = args.get("profile", "python_tests" if any(w in command.lower() for w in ("test", "tests")) else "python_compile")
        if profile not in BUILD_PROFILES:
            profile = "python_compile"
        try:
            from .repair import repair_loop
            repaired = await repair_loop(relative_path=project_path or ".", profile=profile,
                                         goal=f"Original request: {command}\nFailed action: {tool}\nFailure evidence: {json.dumps(result, ensure_ascii=False)[:10000]}",
                                         attempts=2)
            report["steps"].append({"step": "targeted_repair", "result": repaired})
            if repaired.get("status") == "repaired_and_verified":
                verification = await _execute({"tool": "build", "reason": "Independent verification after recovery", "args": {"relative_path": project_path or ".", "profile": profile}})
                report["steps"].append({"step": "independent_verification", "result": verification})
                if isinstance(verification, dict) and verification.get("ok") is True:
                    report.update(recovered=True, recovered_result={"status": "RECOVERED_AND_VERIFIED", "repair": repaired, "verification": verification}, strategy="targeted_repair_and_verification")
                    return report
        except Exception as exc:
            report["steps"].append({"step": "targeted_repair", "error": str(exc)[:2000]})

    # Diagnostics are observational and help distinguish a software failure from a missing tool.
    try:
        diagnostics = await _execute({"tool": "diagnostics", "reason": "Collect blocker evidence", "args": {}})
        report["steps"].append({"step": "diagnostics", "result": diagnostics})
    except Exception as exc:
        report["steps"].append({"step": "diagnostics", "error": str(exc)[:1000]})
    report["blocker"] = "The bounded recovery strategies did not establish that this action succeeded. See recovery steps and diagnostics."
    return report


async def run_autonomous_task(command: str, project_path: str = ".", max_actions: int = 4) -> dict:
    if not isinstance(command,str) or len(command.strip()) < 3: raise ValueError("Tell OmniForge what you want done (at least 3 characters).")
    if len(command) > 12000: raise ValueError("Task description is limited to 12,000 characters.")
    if Path(project_path).is_absolute() or ".." in Path(project_path.replace('\\','/')).parts: raise ValueError("Project path must be workspace-relative.")
    plan=await _plan(command,project_path)
    plan["actions"]=plan["actions"][:max(1,min(6,int(max_actions)))]
    job_id=uuid.uuid4().hex
    job={"job_id":job_id,"created_at":time.time(),"status":"RUNNING","command":command,"project_path":project_path,"planner":plan.get("planner"),"summary":plan.get("summary"),"local_only":True,"paid_api_calls":False,"actions":[],"outputs":[],"warnings":[]}
    manifest=ROOT/f"{job_id}.json"
    manifest.write_text(json.dumps(job,indent=2),encoding="utf-8")
    for index,action in enumerate(plan["actions"],1):
        entry={"index":index,"tool":action["tool"],"reason":action["reason"],"status":"RUNNING","started_at":time.time()}
        job["actions"].append(entry); manifest.write_text(json.dumps(job,indent=2),encoding="utf-8")
        try:
            result=await _execute(action)
            entry.update(status="SUCCEEDED",result=result)
            if isinstance(result,dict):
                for key in ("output","output_dir","package","manifest","report_path"):
                    if result.get(key): job["outputs"].append(result[key])
                if _result_failed(result):
                    entry["status"]="FAILED"
                elif str(result.get("status", "")).upper() == "COMPLETED_WITH_WARNINGS":
                    entry["status"]="COMPLETED_WITH_WARNINGS"
        except Exception as exc:
            result={"status":"ERROR","error":str(exc)}
            entry.update(status="FAILED",error=str(exc)); job["warnings"].append(f"{action['tool']}: {exc}")
        if entry["status"] == "FAILED":
            entry["recovery"] = {"status":"RUNNING", "started_at":time.time()}
            manifest.write_text(json.dumps(job,indent=2),encoding="utf-8")
            try:
                recovery = await _recover_failed_action(action, result, command, project_path)
                entry["recovery"] = recovery
                if recovery.get("recovered"):
                    entry["status"] = "SUCCEEDED"
                    entry["result"] = recovery.get("recovered_result", result)
                    job["recovery_count"] = int(job.get("recovery_count", 0)) + 1
                else:
                    job["warnings"].append(f"{action['tool']}: recovery did not verify success")
            except Exception as recovery_exc:
                entry["recovery"] = {"attempted":True,"recovered":False,"error":str(recovery_exc)[:2000]}
                job["warnings"].append(f"{action['tool']} recovery: {recovery_exc}")
        entry["finished_at"]=time.time(); manifest.write_text(json.dumps(job,indent=2),encoding="utf-8")
        # Never continue with downstream work after an unrecovered code/build failure.
        if entry["status"] == "FAILED" and action["tool"] in {"coding","repair","build","setup_dependencies"}:
            job["blocker"] = (entry.get("recovery") or {}).get("blocker", "Action failed and recovery could not verify a fix.")
            break
    statuses=[x["status"] for x in job["actions"]]
    if statuses and all(s == "SUCCEEDED" for s in statuses):
        job["status"] = "SUCCEEDED"
    elif any(s == "FAILED" for s in statuses):
        job["status"] = "BLOCKED" if job.get("blocker") else ("COMPLETED_WITH_WARNINGS" if any(s == "SUCCEEDED" for s in statuses) else "FAILED")
    elif any(s in {"SUCCEEDED", "COMPLETED_WITH_WARNINGS"} for s in statuses):
        job["status"] = "COMPLETED_WITH_WARNINGS"
    else:
        job["status"] = "FAILED"
    job["finished_at"]=time.time(); manifest.write_text(json.dumps(job,indent=2),encoding="utf-8")
    return job

def list_autonomous_jobs(limit: int=30) -> list[dict]:
    items=[]
    for path in sorted(ROOT.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:max(1,min(100,limit))]:
        try:
            data=json.loads(path.read_text(encoding="utf-8")); items.append({k:data.get(k) for k in ("job_id","created_at","finished_at","status","command","summary","planner")})
        except Exception: continue
    return items
