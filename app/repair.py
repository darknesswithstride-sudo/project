import json
from .agent import ask_model, parse_file_response, safe_workspace_path
from .build_runner import run_profile
from .config import WORKSPACE_DIR, MAX_REPAIR_ATTEMPTS
from .repository import inspect_repository
from pathlib import Path

def _snapshot_files(root):
    snapshot={}
    for p in root.rglob("*"):
        if p.is_file() and not any(part in {".git",".venv","node_modules","build","Binaries","Intermediate","Saved"} for part in p.parts):
            try:
                if p.stat().st_size <= 800_000:
                    snapshot[p.relative_to(root).as_posix()] = p.read_bytes()
            except OSError: pass
    return snapshot

def _restore(root, snapshot):
    # Restore files that existed before the repair attempt. Newly created files are removed.
    existing=set(snapshot)
    for p in list(root.rglob("*")):
        if p.is_file() and not any(part in {".git",".venv","node_modules","build","Binaries","Intermediate","Saved"} for part in p.parts):
            rel=p.relative_to(root).as_posix()
            if rel not in existing:
                try: p.unlink()
                except OSError: pass
    for rel,data in snapshot.items():
        p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)

async def repair_loop(relative_path=".", profile="python_compile", goal="", attempts=None):
    root=safe_workspace_path(relative_path)
    # Keep one known-good snapshot for rollback if all recovery attempts fail.
    original_snapshot = _snapshot_files(root)
    max_attempts=MAX_REPAIR_ATTEMPTS if attempts is None else max(0,min(5,attempts))
    history=[]
    baseline=run_profile(profile,relative_path)
    history.append({"stage":"baseline","result":baseline})
    if baseline["ok"]: return {"status":"already_passing","history":history,"changes":[]}
    for i in range(max_attempts):
        snapshot=_snapshot_files(root)
        repo=inspect_repository(relative_path)
        prompt=("Repair the following project with the smallest safe change. Return JSON only.\n"
                f"Goal: {goal}\nBuild profile: {profile}\nBuild output:\n{baseline.get('output','')[-12000:]}\n"
                f"Repository map:\n{json.dumps(repo,ensure_ascii=False)[:25000]}\n"
                "Return only changed files, with full content. Avoid dependency changes unless necessary.")
        try:
            answer=await ask_model(prompt)
            data=parse_file_response(answer)
            changed=[]
            for item in data["files"]:
                p=safe_workspace_path(str(Path(relative_path)/item["path"]))
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(item["content"],encoding="utf-8")
                changed.append(str(p.relative_to(WORKSPACE_DIR)))
            result=run_profile(profile,relative_path)
            history.append({"stage":f"attempt_{i+1}","summary":data.get("summary",""),"changed":changed,"result":result})
            if result["ok"]:
                return {"status":"repaired_and_verified","history":history,"changes":changed}
            # Keep a failing candidate only long enough to provide its errors to the next repair attempt.
            baseline=result
        except Exception as e:
            _restore(root,snapshot)
            history.append({"stage":f"attempt_{i+1}","error":str(e),"rollback":True})
            break
    # Never leave an unverified repair candidate as the project's final state.
    _restore(root, original_snapshot)
    history.append({"stage":"final_rollback", "restored_original_snapshot":True})
    return {"status":"repair_attempts_exhausted_or_failed","history":history,
            "rollback": "Restored the pre-repair snapshot because no candidate passed verification.",
            "warning":"Autonomous repair could not establish a verified fix; the original project files were restored."}
