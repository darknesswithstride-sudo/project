import json
from pathlib import Path
from app import unreal_game_factory as factory

def test_factory_generates_project_scaffold(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, 'ROOT', tmp_path/'games')
    result=factory.generate_unreal_game('Ashfall Test','Zombie survival with hordes')
    root=Path(result['project_path'])
    assert result['static_validation_passed'] is True
    assert (root/'AshfallTest.uproject').is_file()
    assert json.loads((root/'AshfallTest.uproject').read_text())['Modules'][0]['Name']=='AshfallTest'
    assert 'SpawnHorde' in (root/'Source/AshfallTest/Private/OFGameMode.cpp').read_text()
    assert 'Harvest' in (root/'Config/DefaultEngine.ini').read_text()
    assert result['build_verified'] is False

def test_factory_preserves_existing_project(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, 'ROOT', tmp_path/'games')
    first=factory.generate_unreal_game('SameName')
    second=factory.generate_unreal_game('SameName')
    assert first['project_path'] != second['project_path']
    assert Path(first['uproject_path']).exists()
    assert Path(second['uproject_path']).exists()

def test_factory_static_validation_includes_save_and_chase_systems(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, 'ROOT', tmp_path/'games')
    result = factory.generate_unreal_game('NightHorde', 'Survival game with escalating hordes')
    root = Path(result['project_path'])
    assert result['static_validation_passed'] is True
    assert result['checks']['save_system_present'] is True
    assert result['checks']['zombie_chase_present'] is True
    assert 'F5 save' in (root/'Source/NightHorde/Private/OFHUD.cpp').read_text()
    assert 'SaveProgress' in (root/'Config/DefaultEngine.ini').read_text()


def test_build_helper_does_not_claim_compile_without_unreal(tmp_path, monkeypatch):
    import asyncio
    from app import config
    monkeypatch.setattr(factory, 'ROOT', tmp_path/'games')
    monkeypatch.setattr(config, 'UNREAL_BUILD_TOOL', '')
    manifest = factory.generate_unreal_game('NoEngine', 'Test project')
    result = asyncio.run(factory.build_and_repair_generated_game(manifest))
    assert result['build_verified'] is False
    assert result['build_status'] == 'ENGINE_OR_BUILD_TOOL_NOT_CONFIGURED'
