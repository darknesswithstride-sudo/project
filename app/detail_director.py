"""Local AI-assisted surface-detail direction for OmniForge's Blender production pipeline."""
import json, re
from .agent import ask_model
from .coding_engine import select_local_model

VALID_PROFILES = {"organic", "fabric", "hard_surface", "damaged", "skin_pores", "clothing"}


def heuristic_recommendation(description: str) -> dict:
    text = description.lower()
    if any(k in text for k in ("pore", "skin", "face", "zombie", "creature", "monster", "flesh", "human", "animal")):
        profile = "skin_pores" if any(k in text for k in ("close-up", "closeup", "pore", "facial", "face detail")) else "organic"
        intensity = 1.15 if any(k in text for k in ("rotting", "scar", "wound", "damaged", "weathered")) else 0.9
    elif any(k in text for k in ("cloth", "fabric", "shirt", "pants", "jacket", "coat", "hoodie", "dress", "uniform", "fold")):
        profile, intensity = "clothing", 1.0
    elif any(k in text for k in ("fabric", "canvas", "denim", "leather", "woven", "textile")):
        profile, intensity = "fabric", 0.9
    elif any(k in text for k in ("rust", "broken", "cracked", "battle-damaged", "damage", "weathered", "abandoned", "worn")):
        profile, intensity = "damaged", 1.2
    elif any(k in text for k in ("metal", "robot", "weapon", "armor", "machine", "vehicle", "sci-fi", "industrial", "hard surface")):
        profile, intensity = "hard_surface", 0.8
    else:
        profile, intensity = "organic", 0.8
    target_faces = 30000 if any(k in text for k in ("hero asset", "close-up", "closeup", "cinematic", "first person", "first-person")) else 12000
    texture_size = 4096 if any(k in text for k in ("hero asset", "close-up", "closeup", "cinematic", "high detail")) else 2048
    return {"profile": profile, "intensity": intensity, "target_faces": target_faces, "texture_size": texture_size,
            "reasoning": "Offline keyword-based fallback selected a surface profile from the asset description.",
            "detail_method": "procedural Blender displacement and texture baking; not neural sculpting",
            "source": "heuristic_fallback", "free_local_only": True}


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object in model response.")
    return json.loads(text[start:end+1])


async def recommend_detail(description: str) -> dict:
    if len(description.strip()) < 3:
        raise ValueError("Describe the asset to direct its detail profile.")
    fallback = heuristic_recommendation(description)
    try:
        model = await select_local_model()
        prompt = ("Recommend safe Blender surface-detail settings for this asset description. Choose exactly one profile from "
                  "organic, fabric, hard_surface, damaged, skin_pores, clothing. Do not claim to generate anatomy or geometry. "
                  "Use intensity 0.0–2.0, target_faces 1000–1000000, texture_size one of 512,1024,2048,4096. "
                  "Return JSON only with profile, intensity, target_faces, texture_size, reasoning.\nAsset description: " + description[:4000])
        answer = await ask_model(prompt, system="You are a 3D asset art director. Select conservative, asset-appropriate settings and explain tradeoffs briefly. Output valid JSON only.", model_override=model["selected_model"])
        data = _extract_json(answer)
        profile = str(data.get("profile", "")).lower().strip()
        if profile not in VALID_PROFILES:
            raise ValueError("Model returned an unsupported profile.")
        intensity = float(data.get("intensity", fallback["intensity"]))
        faces = int(data.get("target_faces", fallback["target_faces"]))
        texture_size = int(data.get("texture_size", fallback["texture_size"]))
        if not 0 <= intensity <= 2 or not 1000 <= faces <= 1_000_000 or texture_size not in {512, 1024, 2048, 4096}:
            raise ValueError("Model returned out-of-range asset settings.")
        return {"profile": profile, "intensity": intensity, "target_faces": faces, "texture_size": texture_size,
                "reasoning": str(data.get("reasoning", ""))[:1200], "detail_method": fallback["detail_method"],
                "source": "local_ollama_model", "model": model["selected_model"], "free_local_only": True, "paid_api_calls": False}
    except Exception as exc:
        fallback["fallback_reason"] = str(exc)[:500]
        return fallback
