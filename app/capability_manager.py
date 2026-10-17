"""Research and verify candidate capabilities before adding registry metadata.
Online research is opt-in; arbitrary third-party code is never auto-installed or auto-imported.
"""
from __future__ import annotations
import ast, hashlib, json, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request, uuid
from pathlib import Path
from .config import WORKSPACE_DIR
ROOT=(WORKSPACE_DIR/'omniforge_assets'/'capabilities').resolve(); ROOT.mkdir(parents=True,exist_ok=True)
REGISTRY=ROOT/'registry.json'; CANDIDATES=ROOT/'candidates.json'
SAFE_ID=re.compile(r'^[a-z][a-z0-9_]{1,48}$')
BUILTINS=[
 {'id':'python_project_tests','name':'Python project tests','kind':'builtin','verified':True,'active':True,'description':'Run registered local Python verification profiles.'},
 {'id':'unreal_cpp_project_factory','name':'Unreal Engine project factory','kind':'builtin','verified':True,'active':True,'description':'Generate a C++ survival-game project scaffold.'},
 {'id':'blender_visual_inspection','name':'Blender visual inspection','kind':'builtin','verified':True,'active':True,'description':'Render previews of supported models when Blender is installed.'},
 {'id':'local_triposr_image_to_3d','name':'Local TripoSR image-to-3D','kind':'builtin','verified':True,'active':True,'description':'Reconstruct a rough mesh from one image when the local backend is configured.'},
]
def _read(path, default):
 try: return json.loads(path.read_text(encoding='utf-8'))
 except Exception: return default
def _write(path,data):
 tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(path)
def registry():
 saved=_read(REGISTRY,{'schema':1,'capabilities':[]}); items={x['id']:x for x in BUILTINS}
 for x in saved.get('capabilities',[]):
  if isinstance(x,dict) and x.get('id') and x.get('kind')!='builtin': items[x['id']]=x
 return {'schema':1,'capabilities':list(items.values()),'updated_at':saved.get('updated_at')}
def registry_status():
 d=registry(); return {'status':'SUCCEEDED','count':len(d['capabilities']),'verified_count':sum(bool(x.get('verified')) for x in d['capabilities']),'capabilities':d['capabilities'],'registry_path':str(REGISTRY)}
def _github_search(query, limit=8):
 q=urllib.parse.urlencode({'q':query+' in:name,description','sort':'stars','order':'desc','per_page':str(max(1,min(10,limit)))})
 req=urllib.request.Request('https://api.github.com/search/repositories?'+q,headers={'Accept':'application/vnd.github+json','User-Agent':'OmniForgeAI-CapabilityResearch/4.6'})
 with urllib.request.urlopen(req,timeout=7) as r:
  if r.status!=200: raise RuntimeError(f'GitHub search returned HTTP {r.status}')
  payload=json.loads(r.read().decode('utf-8'))
 return [{'name':x.get('full_name'),'description':(x.get('description') or '')[:400],'url':x.get('html_url'),'stars':x.get('stargazers_count',0),'language':x.get('language'),'updated_at':x.get('updated_at')} for x in payload.get('items',[])[:limit]]
def research_capability(goal: str, online: bool=False) -> dict:
 goal=(goal or '').strip()
 if len(goal)<3: raise ValueError('Describe the missing capability.')
 if len(goal)>1200: raise ValueError('Research query is limited to 1,200 characters.')
 result={'research_id':uuid.uuid4().hex,'goal':goal,'created_at':time.time(),'online_search_requested':bool(online),'sources':[],'status':'SUCCEEDED'}
 if online:
  try: result['sources']=_github_search(goal[:200]); result['research_source']='GitHub public repository metadata'
  except Exception as exc: result.update(status='COMPLETED_WITH_WARNINGS',warning=f'Online research unavailable: {str(exc)[:300]}')
 result['recommendations']=[
  {'step':'Check local tools and current registry first.','reason':'Avoid duplicate dependencies.'},
  {'step':'Choose a maintained, license-compatible project and a narrow adapter boundary.','reason':'Reduce supply-chain risk.'},
  {'step':'Implement the adapter in an isolated workspace with focused tests.','reason':'Keep unreviewed code away from the main process.'},
  {'step':'Run smoke tests and project verifiers before promotion.','reason':'Only verified candidates should be registered.'}]
 saved=_read(CANDIDATES,[]); saved.append(result); _write(CANDIDATES,saved[-100:]); result['report_path']=str(CANDIDATES)
 return result
def _candidate_ast_policy(source: str) -> str | None:
    """Allow a tiny assertion-only language; never run arbitrary adapter code as a smoke test."""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        return f"Candidate source has a syntax error: {exc.msg}."
    if len(list(ast.walk(tree))) > 1200:
        return "Candidate smoke test is too complex."
    allowed_nodes = (
        ast.Module, ast.Expr, ast.Assert, ast.Assign, ast.AnnAssign, ast.Name, ast.Load, ast.Store,
        ast.Constant, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
        ast.Pow, ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In,
        ast.NotIn, ast.Is, ast.IsNot, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
        ast.USub, ast.UAdd, ast.Call, ast.List, ast.Tuple, ast.Set, ast.Dict,
        ast.Subscript, ast.Slice, ast.IfExp, ast.keyword,
    )
    safe_calls = {"print", "len", "min", "max", "sum", "all", "any", "abs", "round", "sorted",
                  "bool", "int", "float", "str", "list", "tuple", "dict", "set"}
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            return f"Candidate smoke test uses disallowed syntax: {type(node).__name__}."
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in {"open", "eval", "exec", "compile", "input", "globals", "locals", "vars", "getattr", "setattr", "delattr", "breakpoint", "help"}):
            return f"Candidate smoke test references restricted name: {node.id}."
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in safe_calls):
            return "Candidate smoke test may call only the approved pure built-in functions."
    return None


def validate_candidate(manifest: dict, source: str) -> dict:
    if not isinstance(manifest,dict): raise ValueError('Candidate manifest must be an object.')
    cid=str(manifest.get('id',''))
    if not SAFE_ID.fullmatch(cid): raise ValueError('Capability id must be lowercase snake_case (3-49 characters).')
    if not isinstance(source,str) or len(source)>20000: raise ValueError('Candidate smoke test source must be text under 20 KB.')
    if not manifest.get('name') or not manifest.get('description'): raise ValueError('Candidate name and description are required.')
    policy_error = _candidate_ast_policy(source)
    if policy_error:
        return {'status':'REJECTED','verified':False,'reason':policy_error,'candidate_id':cid,'execution':'not run'}
    with tempfile.TemporaryDirectory(prefix='omniforge_capability_') as tmp:
        p=Path(tmp)/'smoke_test.py'; p.write_text(source,encoding='utf-8')
        try:
            proc=subprocess.run([sys.executable,'-I',str(p)],cwd=tmp,capture_output=True,text=True,timeout=5,
                env={'PATH':str(Path(sys.executable).parent),'PYTHONIOENCODING':'utf-8'})
            passed=proc.returncode==0
            return {'status':'VERIFIED' if passed else 'FAILED','verified':passed,'exit_code':proc.returncode,
                'stdout':proc.stdout[-2000:],'stderr':proc.stderr[-2000:],
                'sandbox':'temporary directory, isolated Python mode, 5-second timeout, restricted assertion-only AST; no imports, loops, attributes, or filesystem/network/process calls',
                'candidate_id':cid}
        except subprocess.TimeoutExpired:
            return {'status':'FAILED','verified':False,'reason':'Smoke test exceeded 5 seconds.','candidate_id':cid}

def promote_candidate(manifest: dict, source: str, test_result: dict) -> dict:
 if not isinstance(test_result,dict) or test_result.get('status')!='VERIFIED' or test_result.get('verified') is not True: raise ValueError('Promotion requires a passing isolated smoke test.')
 cid=str(manifest.get('id',''))
 if not SAFE_ID.fullmatch(cid): raise ValueError('Invalid capability id.')
 data=registry(); items=[x for x in data['capabilities'] if x.get('id')!=cid]
 item={'id':cid,'name':str(manifest.get('name',''))[:120],'description':str(manifest.get('description',''))[:500],'kind':'verified_candidate','verified':True,'active':True,'verified_at':time.time(),'smoke_test_sha256':hashlib.sha256(source.encode()).hexdigest(),'note':'Metadata registered after smoke test. Source is not auto-imported or granted tool permissions.'}
 items.append(item); _write(REGISTRY,{'schema':1,'capabilities':items,'updated_at':time.time()})
 return {'status':'SUCCEEDED','capability':item,'registry_path':str(REGISTRY)}

async def develop_capability(goal: str, online: bool=False) -> dict:
 """Ask the local coding agent to build and test an adapter in a separate workspace project.
 The adapter is registered as a verified candidate only after the project's test profile passes.
 It is not imported into OmniForge's main process automatically.
 """
 import asyncio
 from .coding_engine import run_coding_agent
 goal=(goal or '').strip()
 if len(goal)<8: raise ValueError('Describe the missing integration in more detail.')
 research=await asyncio.to_thread(research_capability,goal,online)
 slug=re.sub(r'[^a-z0-9]+','_',goal.lower()).strip('_')[:32] or 'new_integration'
 cid='candidate_'+slug[:36]
 rel=f'omniforge_assets/capability_sandbox/{cid}'
 target=(WORKSPACE_DIR/rel).resolve()
 if not target.is_relative_to(WORKSPACE_DIR.resolve()): raise ValueError('Capability workspace escaped root.')
 target.mkdir(parents=True,exist_ok=True)
 task=("Create a small, reviewable Python adapter scaffold for this requested missing capability: "+goal+". "
       "Work only inside this isolated candidate folder. Create adapter.py with a clearly documented interface and safe failure behavior, tests/test_adapter.py with deterministic offline tests, and CAPABILITY.md documenting assumptions, limitations, dependencies, licensing questions, and what must be mapped to a registered OmniForge action before use. Do not install packages, make network calls, access secrets, execute shell commands, or modify files outside this folder. Make the tests pass. Do not claim that an external integration works unless the tests prove it.")
 coding=await run_coding_agent(rel,task,'python_tests',3,True)
 verified=coding.get('status')=='verified_changes_applied'
 report={'status':'VERIFIED_CANDIDATE' if verified else 'BLOCKED','goal':goal,'capability_id':cid,'workspace_relative_path':rel,'research':research,'coding_result':coding,'verified':verified,'registered':False,'note':'The adapter stays in an isolated candidate workspace. Registration does not automatically grant execution permissions; a maintainer must map and review it as a registered tool.'}
 if verified:
  data=registry(); items=[x for x in data['capabilities'] if x.get('id')!=cid]
  item={'id':cid,'name':goal[:120],'description':'Locally generated adapter candidate; see CAPABILITY.md.','kind':'verified_adapter_candidate','verified':True,'active':False,'available_for_planning':False,'registered_at':time.time(),'workspace_relative_path':rel,'coding_report':coding.get('report_file'),'note':'Tests passed in candidate workspace. Not executable by the autonomous planner until explicitly reviewed and mapped to a fixed tool handler.'}
  items.append(item); _write(REGISTRY,{'schema':1,'capabilities':items,'updated_at':time.time()}); report['registered']=True; report['registry_entry']=item
 report_path=ROOT/f'{cid}_development.json'; _write(report_path,report); report['report_path']=str(report_path)
 return report
