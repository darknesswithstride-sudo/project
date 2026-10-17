import httpx, json
from .config import MODEL_BASE_URL, MODEL_API_KEY, MODEL_NAME, WORKSPACE_DIR, AI_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL

SYSTEM_PROMPT = """You are OmniForge, a careful software engineering agent.
Be explicit about uncertainty. Never claim a build passed unless tool output proves it.
Generated code is untrusted. Do not create malware, credential theft, destructive commands, or arbitrary shell execution.
For file generation/repair return ONLY JSON: {"summary":"...","files":[{"path":"relative/path","content":"full file content"}]}.
Only return files necessary for the requested change. Never use absolute paths or '..' path components.
When repairing, preserve unrelated code and make the smallest targeted changes."""

async def ask_model(prompt: str, system: str = SYSTEM_PROMPT, model_override: str | None = None) -> str:
    if AI_PROVIDER == "ollama":
        base_url, model, api_key = OLLAMA_BASE_URL, (model_override or OLLAMA_MODEL), "ollama"
    else:
        raise RuntimeError("OmniForge Free Edition only supports local Ollama. Remote/paid model providers are disabled so this app does not incur API charges.")
    url = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"temperature":0.15}
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

def safe_workspace_path(relative: str):
    path = (WORKSPACE_DIR / relative).resolve()
    if path != WORKSPACE_DIR and WORKSPACE_DIR not in path.parents:
        raise ValueError("Path escapes the configured workspace.")
    return path

def parse_file_response(answer: str):
    # Accept a plain JSON response only; avoid silently executing fenced/ambiguous output.
    data = json.loads(answer)
    if not isinstance(data.get("files"), list) or len(data["files"]) > 60:
        raise ValueError("Model response must contain a files list with at most 60 entries.")
    for item in data["files"]:
        rel, content = item.get("path"), item.get("content")
        if not isinstance(rel, str) or not isinstance(content, str) or len(content) > 800_000:
            raise ValueError("Invalid file entry.")
        if rel.startswith(("/", "\\")) or ".." in rel.replace("\\", "/").split("/"):
            raise ValueError(f"Unsafe generated path rejected: {rel}")
    return data
