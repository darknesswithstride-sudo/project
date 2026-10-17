import pytest
from app import capability_manager as cm

def test_builtin_registry_contains_unreal_factory():
    result=cm.registry_status()
    assert result['status']=='SUCCEEDED'
    assert any(x['id']=='unreal_cpp_project_factory' for x in result['capabilities'])

def test_candidate_smoke_test_passes_and_promotes_only_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, 'ROOT', tmp_path)
    monkeypatch.setattr(cm, 'REGISTRY', tmp_path/'registry.json')
    manifest={'id':'sample_verified_tool','name':'Sample Tool','description':'A test capability.'}
    source='assert 2 + 2 == 4\nprint("ok")\n'
    tested=cm.validate_candidate(manifest, source)
    assert tested['status']=='VERIFIED'
    promoted=cm.promote_candidate(manifest, source, tested)
    assert promoted['status']=='SUCCEEDED'
    assert any(x['id']=='sample_verified_tool' for x in cm.registry()['capabilities'])

def test_candidate_with_restricted_api_is_not_executed():
    result=cm.validate_candidate({'id':'unsafe_candidate','name':'Unsafe','description':'test'}, 'import subprocess\n')
    assert result['status']=='REJECTED'
    assert not result['verified']

def test_candidate_cannot_be_promoted_without_verification():
    with pytest.raises(ValueError):
        cm.promote_candidate({'id':'unverified_tool','name':'No','description':'No'}, 'print(1)', {'status':'FAILED','verified':False})

def test_candidate_smoke_test_rejects_imports_and_attribute_access():
    manifest={'id':'restricted_candidate','name':'Restricted','description':'policy test'}
    imported=cm.validate_candidate(manifest, 'import os\nassert True\n')
    attribute=cm.validate_candidate(manifest, 'assert ().__class__\n')
    assert imported['status']=='REJECTED' and not imported['verified']
    assert attribute['status']=='REJECTED' and not attribute['verified']
