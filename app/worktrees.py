"""Git worktree operations with paths constrained to OmniForge workspace."""
from __future__ import annotations
import re, shutil, subprocess, uuid
from pathlib import Path
from .agent import safe_workspace_path
from .config import WORKSPACE_DIR

def _git(args, cwd, timeout=30):
    if not shutil.which('git'): raise RuntimeError('Git is not installed.')
    p=subprocess.run(['git',*args],cwd=str(cwd),capture_output=True,text=True,timeout=timeout,shell=False)
    return {"ok":p.returncode==0,"exit_code":p.returncode,"stdout":p.stdout[-20000:],"stderr":p.stderr[-10000:]}
def create_worktree(relative_path='.', branch_name='omniforge-task'):
    root=safe_workspace_path(relative_path)
    if not root.is_dir(): raise ValueError('Repository path must be an existing workspace directory.')
    top=_git(['rev-parse','--show-toplevel'],root)
    if not top['ok']: raise ValueError('Selected project is not inside a Git repository.')
    repo=Path(top['stdout'].strip()).resolve()
    if repo != WORKSPACE_DIR and WORKSPACE_DIR not in repo.parents: raise ValueError('Git repository root must remain inside workspace.')
    branch=re.sub(r'[^A-Za-z0-9._/-]','-',branch_name).strip('./-')[:70]
    if not branch: branch='omniforge-'+uuid.uuid4().hex[:8]
    # Keep managed worktrees separate from the source repository.
    manager=(WORKSPACE_DIR/'.omniforge_worktrees').resolve(); manager.mkdir(parents=True,exist_ok=True)
    target=manager/(branch.replace('/','__')+'-'+uuid.uuid4().hex[:6])
    result=_git(['worktree','add','-b',branch,str(target),'HEAD'],repo,timeout=90)
    if not result['ok']:
        shutil.rmtree(target,ignore_errors=True)
        raise RuntimeError(result['stderr'] or 'Git worktree creation failed; branch may already exist.')
    return {"ok":True,"repository":str(repo.relative_to(WORKSPACE_DIR)),"branch":branch,"worktree_path":target.relative_to(WORKSPACE_DIR).as_posix(),"message":result['stdout']}
def worktree_diff(relative_path):
    root=safe_workspace_path(relative_path)
    if not root.is_dir(): raise ValueError('Worktree directory not found.')
    status=_git(['status','--short'],root); diff=_git(['diff','--'],root)
    return {"ok":status['ok'] and diff['ok'],"path":relative_path,"status":status['stdout'],"diff":diff['stdout'],"note":"Untracked files do not appear in git diff; inspect status before merging."}
def remove_worktree(relative_path, force=False):
    root=safe_workspace_path(relative_path)
    manager=(WORKSPACE_DIR/'.omniforge_worktrees').resolve()
    if root == manager or manager not in root.parents: raise ValueError('Only OmniForge-managed worktrees can be removed.')
    # Read the linked-worktree .git pointer to locate the owning main repository.
    git_pointer=root/'.git'
    if not git_pointer.is_file(): raise ValueError('Managed worktree .git pointer is missing; refusing to remove this path.')
    content=git_pointer.read_text(encoding='utf-8',errors='replace').strip()
    if not content.lower().startswith('gitdir:'): raise ValueError('Invalid Git worktree metadata.')
    gitdir=Path(content.split(':',1)[1].strip()).resolve()
    if len(gitdir.parents) < 3 or gitdir.parent.name != 'worktrees': raise ValueError('Unexpected Git worktree metadata layout.')
    repo=gitdir.parents[2]
    if not repo.is_dir(): raise ValueError('Owning repository no longer exists.')
    result=_git(['worktree','remove',*(['--force'] if force else []),str(root)],repo,timeout=90)
    if not result['ok']: raise RuntimeError(result['stderr'] or 'Could not remove worktree. Commit/stash changes or explicitly force removal.')
    if root.exists(): shutil.rmtree(root,ignore_errors=False)
    return {"ok":True,"removed":relative_path,"force":force}
