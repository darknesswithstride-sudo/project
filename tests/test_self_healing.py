import asyncio
from app import autonomous_engine as ae


def test_failed_tool_results_are_not_misreported_as_success():
    assert ae._result_failed({"status": "FAILED", "error": "renderer crashed"})
    assert ae._result_failed({"ok": False, "exit_code": 2})
    assert ae._result_failed({"status": "ROLLED_BACK_VERIFICATION_FAILED"})
    assert not ae._result_failed({"ok": True, "exit_code": 0})


def test_missing_dependency_detection_is_narrow_and_case_insensitive():
    assert ae._dependency_error({"stderr": "ModuleNotFoundError: No module named 'numpy'"})
    assert ae._dependency_error({"error": "Blender is not installed"})
    assert not ae._dependency_error({"error": "mesh topology looks uneven"})


def test_recovery_attempts_targeted_repair_and_verifies(monkeypatch):
    calls = []
    async def fake_execute(action):
        calls.append(action["tool"])
        return {"ok": True, "exit_code": 0, "status": "SUCCEEDED"}
    class FakeRepair:
        async def repair_loop(self, **kwargs):
            return {"status": "repaired_and_verified", "changes": ["src.py"]}
    monkeypatch.setattr(ae, "_execute", fake_execute)
    import app.repair as repair
    monkeypatch.setattr(repair, "repair_loop", FakeRepair().repair_loop)
    result = asyncio.run(ae._recover_failed_action(
        {"tool": "build", "args": {"profile": "python_tests"}},
        {"ok": False, "exit_code": 1, "output": "SyntaxError"},
        "Fix the failing tests", "."
    ))
    assert result["recovered"] is True
    assert result["strategy"] == "targeted_repair_and_verification"
    assert calls == ["build"]


def test_recovery_records_blocker_if_repair_does_not_verify(monkeypatch):
    async def fake_execute(action):
        return {"status": "SUCCEEDED", "ok": True}
    class FakeRepair:
        async def repair_loop(self, **kwargs):
            return {"status": "repair_attempts_exhausted_or_failed"}
    monkeypatch.setattr(ae, "_execute", fake_execute)
    import app.repair as repair
    monkeypatch.setattr(repair, "repair_loop", FakeRepair().repair_loop)
    result = asyncio.run(ae._recover_failed_action(
        {"tool": "build", "args": {"profile": "python_compile"}},
        {"ok": False, "exit_code": 1, "output": "compile error"},
        "Fix compile errors", "."
    ))
    assert result["recovered"] is False
    assert "blocker" in result
    assert result["steps"][-1]["step"] == "diagnostics"
