import json
from pathlib import Path
import pytest
from app.project_delivery import prepare_delivery, inspect_delivery_report
from app.unreal_game_factory import generate_unreal_game
from app.config import WORKSPACE_DIR


def test_delivery_prepares_editor_pipeline_and_qa(tmp_path):
    m = generate_unreal_game('DeliverySmokeProject', 'test delivery pipeline')
    report = prepare_delivery(m['project_path'], [], 'TestSurvivalLevel', 'Win64')
    root = Path(m['project_path'])
    assert report['status'] == 'PREPARED'
    assert report['engine_import_executed'] is False
    assert (root/'Delivery/UnrealEditor-ImportAssets-And-BuildLevel.py').is_file()
    assert (root/'Delivery/qa_test_plan.json').is_file()
    assert (root/'Delivery/Build-Test-Package-Windows.bat').is_file()
    script=(root/'Delivery/UnrealEditor-ImportAssets-And-BuildLevel.py').read_text()
    assert 'AssetImportTask' in script and 'new_level' in script and 'save_current_level' in script
    qa=json.loads((root/'Delivery/qa_test_plan.json').read_text())
    assert len(qa['tests']) >= 5
    assert all(t['status']=='NOT_RUN' for t in qa['tests'])
    assert inspect_delivery_report(m['project_path'])['status']=='PREPARED'


def test_delivery_rejects_outside_workspace(tmp_path):
    with pytest.raises(ValueError):
        prepare_delivery(str(tmp_path), [])


def test_asset_staging_and_unsupported_asset_warning(tmp_path):
    m=generate_unreal_game('DeliveryAssetSmoke','asset staging')
    asset=tmp_path/'prop.obj'; asset.write_text('# minimal obj\nv 0 0 0\n')
    unsupported=tmp_path/'notes.xyz'; unsupported.write_text('no')
    report=prepare_delivery(m['project_path'], [str(asset), str(unsupported)])
    assert report['asset_count_staged']==1
    staged=Path(report['assets'][0]['staged_path'])
    assert staged.is_file() and staged.suffix=='.obj'
    assert report['warnings']
    manifest=json.loads((Path(m['project_path'])/'Delivery/asset_manifest.json').read_text())
    assert manifest['assets'][0]['imported_into_unreal'] is False
