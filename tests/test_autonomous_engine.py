import asyncio
import json
import pytest
from app import autonomous_engine as ae


def test_fallback_routes_environment_to_graphics_pack():
    plan = ae._fallback_plan('Create a dark forest environment', '.')
    assert plan['actions'][0]['tool'] == 'graphics_pack'
    assert plan['actions'][0]['args']['preset'] == 'dark_forest'


def test_fallback_routes_code_request_to_coding_agent():
    plan = ae._fallback_plan('Add an inventory system to this project', '.')
    assert plan['actions'][0]['tool'] == 'coding'
    assert plan['actions'][0]['args']['task'] == 'Add an inventory system to this project'


def test_normalizer_rejects_unknown_tools_and_overrides_project_path():
    plan = ae._normalize_plan({'summary':'test','actions':[
        {'tool':'run_shell','args':{}},
        {'tool':'coding','args':{'relative_path':'../../secret','task':'ignore','profile':'rm -rf','max_steps':99}}
    ]}, 'Add tests', 'my-project')
    assert len(plan['actions']) == 1
    action = plan['actions'][0]
    assert action['tool'] == 'coding'
    assert action['args']['relative_path'] == 'my-project'
    assert action['args']['task'] == 'Add tests'
    assert action['args']['profile'] == 'python_tests'
    assert action['args']['max_steps'] == 3


def test_model_path_traversal_is_not_planned():
    plan = ae._normalize_plan({'actions':[{'tool':'studio_pipeline','args':{'model_path':'../../secret.glb'}}]}, 'optimize model', '.')
    assert plan['actions'][0]['tool'] == 'coding'  # safe fallback instead of an escaped path


def test_autonomy_rejects_absolute_and_parent_paths():
    with pytest.raises(ValueError):
        asyncio.run(ae.run_autonomous_task('Run tests', '../outside'))
    with pytest.raises(ValueError):
        asyncio.run(ae.run_autonomous_task('Run tests', '/tmp'))


def test_action_allowlist_is_finite():
    assert ae.ALLOWED_ACTIONS == {'diagnostics','repository','build','repair','coding','graphics_pack','graphics_validate','production_build','studio_pipeline','3d_validate','vision_status','setup_dependencies','visual_inspect','unreal_game','unreal_deliver','capability_research','capability_registry','capability_develop'}


def test_fallback_fixes_then_verifies_when_requested():
    plan = ae._fallback_plan('Fix the failing tests and run them again', '.')
    assert [a['tool'] for a in plan['actions']] == ['repair', 'build']
    assert all(a['args']['profile'] == 'python_tests' for a in plan['actions'])


def test_fallback_routes_unreal_survival_game_to_project_factory():
    plan = ae._fallback_plan('Build a complete zombie survival game in Unreal Engine with crafting and night hordes', '.')
    assert len(plan['actions']) == 1
    assert plan['actions'][0]['tool'] == 'unreal_game'

def test_capability_research_routes_to_registered_action():
    plan = ae._fallback_plan('Research suitable solutions online for a missing capability integration', '.')
    assert plan['actions'][0]['tool'] == 'capability_research'

def test_normalizer_accepts_unreal_project_factory_without_model_path():
    plan = ae._normalize_plan({'actions':[{'tool':'unreal_game','args':{'project_name':'My Survival Game'}}]}, 'Build a survival game in Unreal', '.')
    assert plan['actions'][0]['tool'] == 'unreal_game'
    assert plan['actions'][0]['args']['project_name'] == 'My Survival Game'
    assert plan['actions'][0]['args']['game_brief'] == 'Build a survival game in Unreal'


def test_fallback_routes_missing_integration_to_capability_developer():
    plan = ae._fallback_plan('Implement missing integration for a new Unreal asset import tool', '.')
    assert plan['actions'][0]['tool'] == 'capability_develop'
