from pathlib import Path
import pytest
from app import local_3d_tools


def test_asset_path_rejects_workspace_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(local_3d_tools, 'WORKSPACE_DIR', tmp_path.resolve())
    outside = tmp_path.parent / 'outside.glb'
    outside.write_bytes(b'not really a model')
    with pytest.raises(ValueError):
        local_3d_tools._asset_path('../outside.glb')


def test_asset_path_rejects_unsupported_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(local_3d_tools, 'WORKSPACE_DIR', tmp_path.resolve())
    bad = tmp_path / 'file.exe'
    bad.write_bytes(b'x')
    with pytest.raises(ValueError, match='Supported inputs'):
        local_3d_tools._asset_path('file.exe')


def test_animation_action_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(local_3d_tools, 'WORKSPACE_DIR', tmp_path.resolve())
    model = tmp_path / 'model.glb'
    model.write_bytes(b'x')
    with pytest.raises(ValueError, match='Action must be'):
        local_3d_tools.animate_rig('model.glb', action='moonwalk')


def test_optimize_target_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(local_3d_tools, 'WORKSPACE_DIR', tmp_path.resolve())
    model = tmp_path / 'model.glb'
    model.write_bytes(b'x')
    with pytest.raises(ValueError, match='Target face count'):
        local_3d_tools.optimize_model('model.glb', target_faces=1)
