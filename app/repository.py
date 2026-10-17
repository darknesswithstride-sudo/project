import os, subprocess
from pathlib import Path
from .config import WORKSPACE_DIR
from .agent import safe_workspace_path

IGNORE = {".git", ".venv", "node_modules", "Binaries", "Intermediate", "Saved", "__pycache__", ".idea"}
MAX_FILES = 1200
MAX_BYTES = 200_000

def inspect_repository(relative_path="."):
    root = safe_workspace_path(relative_path)
    if not root.exists() or not root.is_dir():
        raise ValueError("Repository directory not found inside workspace.")
    files, languages, project_hints = [], {}, []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE]
        for name in names:
            p = Path(base) / name
            rel = str(p.relative_to(root))
            ext = p.suffix.lower()
            languages[ext or "(no extension)"] = languages.get(ext or "(no extension)", 0) + 1
            if name in {"pyproject.toml","requirements.txt","package.json","Cargo.toml","go.mod","pom.xml","build.gradle","CMakeLists.txt","*.sln"} or ext in {".uproject",".sln",".csproj"}:
                project_hints.append(rel)
            if len(files) < MAX_FILES:
                item = {"path": rel, "bytes": p.stat().st_size}
                if p.stat().st_size <= MAX_BYTES and ext in {".py",".js",".ts",".tsx",".jsx",".json",".toml",".yml",".yaml",".md",".txt",".cs",".cpp",".h",".hpp",".c",".go",".rs",".java",".html",".css",".cmake"}:
                    try: item["preview"] = p.read_text(encoding="utf-8", errors="replace")[:4000]
                    except OSError: pass
                files.append(item)
    return {"root":str(root),"file_count":len(files),"languages_by_extension":languages,"project_hints":project_hints[:100],"files":files}

def git_command(relative_path, args):
    root = safe_workspace_path(relative_path)
    if not (root / ".git").exists():
        return {"ok":False,"output":"This folder is not a Git repository."}
    result = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30, shell=False)
    return {"ok":result.returncode == 0,"exit_code":result.returncode,"output":(result.stdout+result.stderr)[-30000:]}

def checkpoint(relative_path="."):
    root = safe_workspace_path(relative_path)
    if not (root / ".git").exists():
        return {"ok":False,"output":"Initialize a Git repository first to use checkpoints."}
    # Staging is deliberately not automatic; checkpoint only reports state.
    return git_command(relative_path, ["status","--short"])
