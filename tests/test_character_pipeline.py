import asyncio
from pathlib import Path
import pytest
from app import character_pipeline as cp
from app.config import WORKSPACE_DIR
from app.asset_studio import OUTPUT_DIR


def test_invalid_image_id_rejected():
    with pytest.raises(ValueError):
        asyncio.run(cp.run_character_pipeline('../bad'))


def test_invalid_settings_rejected():
    with pytest.raises(ValueError):
        asyncio.run(cp.run_character_pipeline('a' * 32, target_faces=10))


def test_full_pipeline_records_outputs(monkeypatch):
    mesh = OUTPUT_DIR / 'test_character_pipeline_input.glb'
    mesh.write_bytes(b'fake mesh fixture')
    optimized = OUTPUT_DIR / 'test_character_pipeline_optimized.glb'
    optimized.write_bytes(b'fake optimized fixture')
    rigged = OUTPUT_DIR / 'test_character_pipeline_rigged.fbx'
    rigged.write_bytes(b'fake rigged fixture')
    animated = OUTPUT_DIR / 'test_character_pipeline_animated.fbx'
    animated.write_bytes(b'fake animated fixture')

    async def fake_create(ids, prompt, model_type):
        return {'task_id':'testtask12345678','status':'SUCCEEDED','files':[str(mesh.relative_to(WORKSPACE_DIR))]}
    monkeypatch.setattr(cp.asset_studio, 'create_model', fake_create)
    monkeypatch.setattr(cp, 'inspect_model', lambda p: {'ok':True,'input':p})
    monkeypatch.setattr(cp, 'optimize_model', lambda p, faces, fmt: {'ok':True,'output':str(optimized.relative_to(WORKSPACE_DIR))})
    monkeypatch.setattr(cp, 'run_pipeline', lambda *args: {'ok':True,'manifest':'omniforge_assets/manifest.json','package':'omniforge_assets/package.zip'})
    monkeypatch.setattr(cp, 'auto_rig_humanoid', lambda p, fmt: {'ok':True,'output':str(rigged.relative_to(WORKSPACE_DIR))})
    monkeypatch.setattr(cp, 'animate_rig', lambda p, action, fps: {'ok':True,'output':str(animated.relative_to(WORKSPACE_DIR))})
    result = asyncio.run(cp.run_character_pipeline('a'*32))
    assert result['status'] == 'SUCCEEDED'
    assert result['final_model_path'] == str(animated.relative_to(WORKSPACE_DIR))
    assert [s['name'] for s in result['stages'] if s['status']=='SUCCEEDED'] == [
        'image_to_3d_generation','inspect_generated_mesh','optimize_mesh','production_package','humanoid_auto_rig','procedural_animation']
    assert cp.get_character_job(result['job_id'])['job_id'] == result['job_id']
    for path in (mesh, optimized, rigged, animated): path.unlink(missing_ok=True)


def test_optional_rig_failure_keeps_generated_mesh(monkeypatch):
    mesh = OUTPUT_DIR / 'test_character_pipeline_partial.glb'
    mesh.write_bytes(b'fake mesh fixture')
    async def fake_create(ids, prompt, model_type):
        return {'task_id':'testtask87654321','status':'SUCCEEDED','files':[str(mesh.relative_to(WORKSPACE_DIR))]}
    monkeypatch.setattr(cp.asset_studio, 'create_model', fake_create)
    monkeypatch.setattr(cp, 'inspect_model', lambda p: {'ok':True})
    monkeypatch.setattr(cp, 'optimize_model', lambda *args: (_ for _ in ()).throw(RuntimeError('Blender unavailable')))
    monkeypatch.setattr(cp, 'auto_rig_humanoid', lambda *args: (_ for _ in ()).throw(RuntimeError('not humanoid')))
    result = asyncio.run(cp.run_character_pipeline('b'*32, optimize=True, rig=True, animate=True, package=False))
    assert result['status'] == 'COMPLETED_WITH_WARNINGS'
    assert result['final_model_path'] == str(mesh.relative_to(WORKSPACE_DIR))
    assert any(s['status']=='FAILED' for s in result['stages'])
    mesh.unlink(missing_ok=True)
