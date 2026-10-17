import json
import pytest
from app import project_brain
from app.dependency_setup import setup_dependencies
from app.visual_inspection import inspect_visual
from app.config import WORKSPACE_DIR


def test_project_brain_persists_conversation_and_memory(tmp_path, monkeypatch):
    db=tmp_path/'brain.sqlite3'
    monkeypatch.setattr(project_brain,'DB',db)
    project_brain.create_session('test-session','hello')
    project_brain.add_message('test-session','user','Build a forest level')
    project_brain.add_message('test-session','assistant','I created the starter pack.')
    project_brain.remember('.','decision','Use local tools only')
    assert [x['role'] for x in project_brain.history('test-session')] == ['user','assistant']
    assert project_brain.recall('.')[0]['content'] == 'Use local tools only'


def test_dependency_setup_does_not_execute_unknown_commands(tmp_path):
    rel='test_no_manifest_' + str(__import__('uuid').uuid4().hex)
    root=WORKSPACE_DIR/rel
    root.mkdir(parents=True)
    try:
        result=setup_dependencies(rel)
        assert result['status']=='NO_MANIFEST'
    finally:
        root.rmdir()


def test_visual_inspection_rejects_path_traversal():
    with pytest.raises(ValueError):
        inspect_visual('../../outside.glb')


def test_chat_service_job_id_validation():
    from app.chat_service import get_job
    with pytest.raises(ValueError):
        get_job('../bad')
