from app.autodetect import detect_tools, _valid_file
from pathlib import Path
def test_detect_tools_returns_expected_keys():
    assert set(detect_tools()) == {"blender_exe","ollama_exe","unreal_build_tool","triposr_dir"}
def test_valid_file_rejects_missing_path(tmp_path):
    assert _valid_file(tmp_path / "missing.exe") is None
def test_valid_file_accepts_file(tmp_path):
    p=tmp_path/"tool.exe"; p.write_text("test")
    assert Path(_valid_file(p)) == p.resolve()
