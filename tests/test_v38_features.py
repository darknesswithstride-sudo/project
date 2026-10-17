import os, tempfile, subprocess
from pathlib import Path
import pytest
from app import advanced_3d, vision_director, sandbox_runner, worktrees, benchmark_suite
from app.config import WORKSPACE_DIR

def test_advanced_backend_inventory_is_local_only():
    data=advanced_3d.inventory()
    assert data['free_local_only'] is True
    assert {x['name'] for x in data['tools']} >= {'TripoSR','Microsoft TRELLIS','Tencent Hunyuan3D'}

def test_vision_path_rejects_traversal():
    with pytest.raises(ValueError): vision_director._safe_image('../../outside.png')

def test_vision_path_rejects_missing_file():
    with pytest.raises(ValueError): vision_director._safe_image('no-such-image.png')

def test_isolated_build_rejects_workspace_root():
    with pytest.raises(ValueError): sandbox_runner.run_isolated('python_compile','.')

def test_isolated_build_rejects_unknown_profile():
    with pytest.raises(ValueError): sandbox_runner.run_isolated('git_status','some-project')

def test_worktree_path_branch_sanitization(monkeypatch, tmp_path):
    repo=WORKSPACE_DIR/'test_repo_v38_tmp'
    if repo.exists():
        import shutil; shutil.rmtree(repo)
    repo.mkdir(parents=True)
    try:
        subprocess.run(['git','init','-q'],cwd=repo,check=True)
        subprocess.run(['git','config','user.email','test@example.invalid'],cwd=repo,check=True)
        subprocess.run(['git','config','user.name','OmniForge Test'],cwd=repo,check=True)
        (repo/'README.md').write_text('test\n')
        subprocess.run(['git','add','README.md'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','init'],cwd=repo,check=True)
        result=worktrees.create_worktree('test_repo_v38_tmp','feature/test branch')
        assert result['ok'] and result['branch']=='feature/test-branch'
        wt=WORKSPACE_DIR/result['worktree_path']
        (wt/'README.md').write_text('changed\n')
        diff=worktrees.worktree_diff(result['worktree_path'])
        assert 'changed' in diff['diff']
        assert worktrees.remove_worktree(result['worktree_path'], force=True)['ok']
    finally:
        import shutil; shutil.rmtree(repo,ignore_errors=True)

def test_benchmark_suite_has_repeatable_cases():
    assert len(benchmark_suite.CASES) >= 5
    assert len({x['id'] for x in benchmark_suite.CASES}) == len(benchmark_suite.CASES)

def test_isolated_build_runs_on_copy_and_cleans_it():
    project=WORKSPACE_DIR/'isolated_fixture_v38'
    project.mkdir(exist_ok=True)
    (project/'hello.py').write_text('answer = 42\n')
    try:
        result=sandbox_runner.run_isolated('python_compile','isolated_fixture_v38',keep_copy=False)
        assert result['ok'] is True
        assert result['copy_retained'] is False
        assert not (WORKSPACE_DIR/result['isolated_copy']).exists()
        assert (project/'hello.py').read_text()=='answer = 42\n'
    finally:
        import shutil; shutil.rmtree(project,ignore_errors=True)
