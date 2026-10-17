import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.coding_engine import _validate_patch, select_local_model
from app.config import WORKSPACE_DIR

client = TestClient(app)


def test_agent_capabilities_route_is_local_only():
    response = client.get('/api/agent/capabilities')
    assert response.status_code == 200
    data = response.json()
    assert data['free_local_only'] is True
    assert data['paid_api_calls'] is False
    assert data['safety']['arbitrary_shell_from_model'] is False
    assert 'automatic rollback on failed verification' in data['features']


def test_agent_run_requires_task_and_bounds_iterations():
    response = client.post('/api/agent/run', json={'task': 'x', 'max_steps': 20})
    assert response.status_code == 422


def test_patch_rejects_path_traversal_and_secret_files():
    with pytest.raises(ValueError):
        _validate_patch({'files': [{'path': '../outside.py', 'content': 'x=1'}]}, '.')
    with pytest.raises(ValueError):
        _validate_patch({'files': [{'path': '.env', 'content': 'API_KEY=secret'}]}, '.')


def test_patch_accepts_safe_relative_file():
    patch = _validate_patch({'files': [{'path': 'src/example.py', 'content': 'value = 3\n'}]}, '.')
    assert patch[0]['path'] == 'src/example.py'


def test_local_model_selector_prefers_configured_installed_model():
    inventory = {'reachable': True, 'models': [
        {'name': 'qwen2.5-coder:7b', 'size_bytes': 5_000_000_000},
        {'name': 'llama3:8b', 'size_bytes': 5_500_000_000},
    ]}
    with patch('app.coding_engine.list_local_models', new=AsyncMock(return_value=inventory)):
        result = asyncio.run(select_local_model())
    assert result['selected_model'] == 'qwen2.5-coder:7b'


def test_agent_rolls_back_patch_when_verifier_fails(tmp_path, monkeypatch):
    # Use a temporary project folder within the configured workspace so path policy is exercised.
    project = WORKSPACE_DIR / 'agent_rollback_test_tmp'
    project.mkdir(exist_ok=True)
    original = project / 'example.py'
    original.write_text('value = 1\n', encoding='utf-8')
    generated = '{"summary":"change value", "files":[{"path":"example.py","content":"value = 2\\n"}]}'
    with patch('app.coding_engine.select_local_model', new=AsyncMock(return_value={
        'selected_model': 'local-test-model', 'selection_reason': 'test', 'inventory': {'reachable': True}
    })), patch('app.coding_engine.ask_model', new=AsyncMock(side_effect=['test plan', generated])), patch(
        'app.coding_engine.run_profile', return_value={'ok': False, 'output': 'intentional test failure'}
    ):
        result = asyncio.run(__import__('app.coding_engine', fromlist=['run_coding_agent']).run_coding_agent(
            'agent_rollback_test_tmp', 'Change the example value for test coverage.', 'python_compile', 1, True
        ))
    assert result['status'] == 'rolled_back_verification_failed'
    assert original.read_text(encoding='utf-8') == 'value = 1\n'
    import shutil
    shutil.rmtree(project, ignore_errors=True)
