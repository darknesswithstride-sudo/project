"""Command-line dependency diagnostics for OmniForge AI Free Edition."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import diagnostics

if __name__ == "__main__":
    print(json.dumps(asyncio.run(diagnostics()), indent=2))
