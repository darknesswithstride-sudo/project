import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", BASE_DIR / "workspace")).resolve()
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "build_logs")).resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
from .autodetect import detect_tools
_DETECTED_TOOLS = detect_tools()
BLENDER_EXE = os.getenv("BLENDER_EXE", "").strip() or (_DETECTED_TOOLS.get("blender_exe") or "")
UNREAL_BUILD_TOOL = os.getenv("UNREAL_BUILD_TOOL", "").strip() or (_DETECTED_TOOLS.get("unreal_build_tool") or "")
MAX_REPAIR_ATTEMPTS = max(0, min(5, int(os.getenv("MAX_REPAIR_ATTEMPTS", "2"))))

MESHY_API_KEY = os.getenv("MESHY_API_KEY", "")
MESHY_BASE_URL = os.getenv("MESHY_BASE_URL", "https://api.meshy.ai").rstrip("/")

# Free/local-first providers. No paid API is required when using these settings.
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
TRIPOSR_DIR = os.getenv("TRIPOSR_DIR", "").strip() or (_DETECTED_TOOLS.get("triposr_dir") or "")
TRIPOSR_PYTHON = os.getenv("TRIPOSR_PYTHON", "python").strip()
# Free edition intentionally locks image-to-3D to local processing; paid providers are not selected.
THREED_PROVIDER = "local"
