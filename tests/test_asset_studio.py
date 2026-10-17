from pathlib import Path
from app.asset_studio import _safe_name, _task_endpoint

def test_safe_name_removes_path_separators():
    assert "/" not in _safe_name("../../evil name.glb")

def test_task_endpoint_maps_supported_tasks():
    assert _task_endpoint("rigging") == "/openapi/v1/rigging"
    assert _task_endpoint("multi-image-to-3d") == "/openapi/v1/multi-image-to-3d"

def test_task_endpoint_rejects_unknown_task():
    try:
        _task_endpoint("unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown task type should fail")
