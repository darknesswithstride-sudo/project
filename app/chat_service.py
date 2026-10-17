"""Chat-first autonomous supervisor with durable jobs and bounded iterative correction."""
from __future__ import annotations
import asyncio, json, time, uuid, re
from pathlib import Path
from .config import WORKSPACE_DIR
from .project_brain import add_message, history, recall, remember, save_run, create_session
ROOT=(WORKSPACE_DIR/'omniforge_assets'/'chat_jobs').resolve(); ROOT.mkdir(parents=True,exist_ok=True)
_TASKS: dict[str,asyncio.Task]={}

def _criteria_for(command: str) -> list[str]:
    s=command.lower(); criteria=['Every required action completes successfully or a concrete blocker is reported.']
    if any(w in s for w in ('test','tests','verify','verification','compile','build')):
        criteria.append('The relevant build/test verifier reports a successful exit.')
    if any(w in s for w in ('create','generate','produce','export','package','render','make a')):
        criteria.append('At least one requested output artifact is produced and its path is recorded.')
    if any(w in s for w in ('visually inspect','visual review','preview','render preview')):
        criteria.append('A preview image is rendered, or the visual-review blocker is explicitly reported.')
    return criteria


def _path(job_id: str) -> Path:
    if len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id.lower()): raise ValueError('Invalid job id.')
    p=(ROOT/f'{job_id}.json').resolve()
    if not p.is_relative_to(ROOT): raise ValueError('Invalid job path.')
    return p

def get_job(job_id: str):
    p=_path(job_id)
    if not p.is_file(): raise ValueError('Job not found.')
    return json.loads(p.read_text(encoding='utf-8'))

def _save(job): _path(job['job_id']).write_text(json.dumps(job,indent=2,ensure_ascii=False),encoding='utf-8')

def list_jobs(limit=20):
    out=[]
    for p in sorted(ROOT.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:max(1,min(100,limit))]:
        try:
            j=json.loads(p.read_text(encoding='utf-8')); out.append({k:j.get(k) for k in ('job_id','session_id','status','command','created_at','updated_at','assistant_message','iteration','blocker')})
        except Exception: pass
    return out

async def start_chat_job(message: str, session_id: str|None='default', project_path: str='.', max_iterations: int=3, image_info: dict|None=None):
    message=(message or '').strip()
    if len(message)<2: raise ValueError('Tell OmniForge what you want to do.')
    if len(message)>12000: raise ValueError('Message limit is 12,000 characters.')
    from pathlib import PurePosixPath
    explicit_path=re.search(r"(?:project path|project folder|workspace path)\s*[:=]\s*([A-Za-z0-9_./\\-]+)",message,re.I)
    if project_path == '.' and explicit_path:
        project_path=explicit_path.group(1)
    rp=PurePosixPath((project_path or '.').replace('\\','/'))
    if rp.is_absolute() or '..' in rp.parts: raise ValueError('Project path must be workspace-relative.')
    sid=(session_id or uuid.uuid4().hex)[:80]
    create_session(sid, message[:100])
    add_message(sid,'user',message)
    remember(str(rp),'user_goal',message[:1000])
    job_id=uuid.uuid4().hex; now=time.time()
    job={'job_id':job_id,'session_id':sid,'command':message,'project_path':str(rp),'acceptance_criteria':_criteria_for(message),'status':'QUEUED','created_at':now,'updated_at':now,'iteration':0,'max_iterations':max(1,min(4,int(max_iterations))),'iterations':[],'assistant_message':'OmniForge is preparing a plan.','image_info':image_info,'blocker':None,'local_only':True,'paid_api_calls':False}
    _save(job); save_run(job_id,sid,message,'QUEUED','')
    task=asyncio.create_task(_run(job)); _TASKS[job_id]=task
    task.add_done_callback(lambda _t, jid=job_id: _TASKS.pop(jid,None))
    return {'job_id':job_id,'session_id':sid,'status':'QUEUED','assistant_message':'I’m on it. I’ll plan the work, use the best configured local tools, verify results, and correct failures within a bounded number of iterations.'}

def _evaluate_acceptance(job: dict) -> list[dict]:
    checks=[]; iterations=job.get('iterations',[]); last=iterations[-1] if iterations else {}
    actions=last.get('actions',[])
    bad=[a for a in actions if a.get('status') in ('FAILED','COMPLETED_WITH_WARNINGS')]
    image_ok=bool(job.get('image_info')) and last.get('status')=='SUCCEEDED'
    checks.append({'criterion':job.get('acceptance_criteria',['Every required action succeeds.'])[0], 'passed':(bool(actions) and not bad) or image_ok, 'evidence':('Character pipeline succeeded.' if image_ok else 'All final-iteration actions succeeded.' if actions and not bad else 'See failed or warning actions in the execution record.')})
    cmd=job.get('command','').lower()
    if any(w in cmd for w in ('test','tests','verify','verification','compile','build')):
        verifier=[a for a in actions if a.get('tool') in ('build','repair','coding') and a.get('status')=='SUCCEEDED']
        checks.append({'criterion':'The relevant build/test verifier reports a successful exit.','passed':bool(verifier),'evidence':', '.join(a.get('tool','') for a in verifier) if verifier else 'No successful verifier action was recorded.'})
    if any(w in cmd for w in ('create','generate','produce','export','package','render','make a')):
        outputs=[]
        for a in actions:
            r=a.get('result') or {}
            if isinstance(r,dict):
                for k in ('output','output_dir','package','report_path','preview_path','final_model_path','generated_model_path','project_path','uproject_path'):
                    v=r.get(k)
                    if isinstance(v,str) and v: outputs.append(v)
        if job.get('image_info') and isinstance(last.get('result'),dict):
            r=last['result']
            for k in ('final_model_path','generated_model_path','package','report_path'):
                v=r.get(k)
                if isinstance(v,str) and v: outputs.append(v)
        existing=[]
        for v in outputs:
            p=Path(v)
            if not p.is_absolute(): p=(WORKSPACE_DIR/p).resolve()
            if p.exists() and (p==WORKSPACE_DIR or WORKSPACE_DIR in p.parents): existing.append(v)
        checks.append({'criterion':'At least one requested output artifact is produced and its path is recorded.','passed':bool(existing),'evidence':existing[:10] if existing else 'No existing output path was verified in the final iteration.'})
    return checks

async def _run(job):
    from .autonomous_engine import run_autonomous_task
    job['status']='RUNNING'; job['updated_at']=time.time(); job['assistant_message']='Planning the task and checking the project context…'; _save(job); save_run(job['job_id'],job['session_id'],job['command'],'RUNNING','')
    try:
        if job.get('image_info'):
            image=job['image_info']
            job['assistant_message']='Reference image received. Running the configured local image-to-3D character pipeline…'; _save(job)
            from .character_pipeline import run_character_pipeline
            result=await run_character_pipeline(image['id'],job['command'],50000,2048,3,'organic',1.0,True,True,True,'walk',24,True)
            job['iterations'].append({'iteration':1,'status':result.get('status','UNKNOWN'),'result':result})
            if result.get('status') not in ('SUCCEEDED','COMPLETED_WITH_WARNINGS'):
                job['blocker']=result.get('error') or 'Character pipeline failed; inspect the stage report and local backend configuration.'
        else:
            memories=recall(job['project_path'],18)
            turns=history(job['session_id'],10)
            # Prior turns are context only; the newest user message remains the instruction of record.
            context='\n'.join(f"{x['role']}: {x['content'][:1200]}" for x in turns[:-1])
            brain='\n'.join(f"- [{m['kind']}] {m['content']}" for m in memories)
            command=job['command']
            if context: command='Conversation context (use only if relevant):\n'+context+'\n\nCurrent request:\n'+command
            if brain: command='Persistent project brain notes:\n'+brain+'\n\n'+command
            max_it=job['max_iterations']
            last=None
            for i in range(1,max_it+1):
                job['iteration']=i; job['updated_at']=time.time(); job['assistant_message']=f'Working iteration {i}/{max_it}: selecting tools, executing, and verifying…'; _save(job)
                request=command if i==1 else ('SELF-CORRECTION ITERATION. The original user goal is: '+job['command']+'\nPrevious execution result and failures:\n'+json.dumps(last,ensure_ascii=False)[:9000]+'\nInspect the failed acceptance criteria, make a targeted correction, and verify it. Do not repeat successful work unnecessarily. If the result is complete, select a safe verification action or no-op by returning an explanation through an empty action list (the fallback may be used otherwise).')
                result=await run_autonomous_task(request,job['project_path'],6)
                last=result
                job['iterations'].append({'iteration':i,'status':result.get('status'),'summary':result.get('summary'),'planner':result.get('planner'),'actions':result.get('actions',[]),'outputs':result.get('outputs',[]),'warnings':result.get('warnings',[])})
                job['updated_at']=time.time(); _save(job)
                statuses=[a.get('status') for a in result.get('actions',[])]
                failures=[a for a in result.get('actions',[]) if a.get('status') in ('FAILED','COMPLETED_WITH_WARNINGS')]
                if result.get('status')=='SUCCEEDED' and not failures:
                    break
                if failures and i < max_it:
                    # Feed only failure summaries to the next loop; the planner remains constrained to registered actions.
                    command=job['command']
            if last and last.get('status')!='SUCCEEDED' and not job.get('blocker'):
                failed=[a for it in job['iterations'] for a in it.get('actions',[]) if a.get('status') in ('FAILED','COMPLETED_WITH_WARNINGS')]
                if failed: job['blocker']='Bounded self-correction iterations ended without satisfying all checks. Review the failed action output.'
        # Store compact persistent learning, not hidden chain-of-thought.
        for iteration in job['iterations']:
            for action in iteration.get('actions',[]):
                result=action.get('result') or {}
                if isinstance(result,dict) and result.get('status') in ('SUCCEEDED','FAILED','COMPLETED_WITH_WARNINGS'):
                    remember(job['project_path'],'run_outcome',f"Request: {job['command'][:240]} | action: {action.get('tool')} | status: {action.get('status')} | result status: {result.get('status')}")
        job['acceptance_evaluation']=_evaluate_acceptance(job)
        failed_acceptance=[x for x in job['acceptance_evaluation'] if not x.get('passed')]
        if failed_acceptance and not job.get('blocker'):
            job['blocker']='Acceptance criteria remain unmet: '+ '; '.join(x['criterion'] for x in failed_acceptance)
        if job.get('blocker'):
            job['status']='BLOCKED' if not job['iterations'] or all(x.get('status') in ('FAILED','BLOCKED') for x in job['iterations']) else 'COMPLETED_WITH_WARNINGS'
            job['assistant_message']='I made the progress possible with the configured tools, but I hit a blocker: '+job['blocker']
        else:
            statuses=[x.get('status') for x in job['iterations']]
            job['status']='SUCCEEDED' if statuses and all(x=='SUCCEEDED' for x in statuses) else 'COMPLETED_WITH_WARNINGS'
            outputs=[]
            for it in job['iterations']:
                outputs.extend(it.get('outputs',[]))
                for action in it.get('actions',[]):
                    r=action.get('result') or {}
                    if isinstance(r,dict): outputs.extend(r.get(k) for k in ('output','output_dir','package','report_path','preview_path','project_path','uproject_path') if r.get(k))
            build_notes=[]
            for it in job['iterations']:
                for action in it.get('actions',[]):
                    result=action.get('result') or {}
                    if isinstance(result,dict) and result.get('build_status'):
                        build_notes.append({'build_status':result.get('build_status'),'build_verified':result.get('build_verified'),'warning':result.get('warning'),'uproject_path':result.get('uproject_path')})
            job['assistant_message']=('Done. I completed the workflow and recorded the outputs.' if job['status']=='SUCCEEDED' else 'I completed the available stages. Some checks or optional stages need attention; details and output paths are attached below.')+'\n\n'+json.dumps({'status':job['status'],'iterations':len(job['iterations']),'outputs':list(dict.fromkeys(outputs))[-30:],'summary':job['iterations'][-1].get('summary') if job['iterations'] else '', 'build_notes':build_notes[-5:]},indent=2,ensure_ascii=False)
        job['acceptance_evaluation']=_evaluate_acceptance(job); job['updated_at']=time.time(); job['finished_at']=time.time(); _save(job)
        add_message(job['session_id'],'assistant',job['assistant_message'])
        save_run(job['job_id'],job['session_id'],job['command'],job['status'],job['assistant_message'])
    except Exception as exc:
        job['status']='BLOCKED'; job['blocker']=str(exc)[:3000]; job['assistant_message']='I could not finish the task because of a runtime blocker: '+str(exc); job['acceptance_evaluation']=_evaluate_acceptance(job); job['updated_at']=time.time(); job['finished_at']=time.time(); _save(job)
        add_message(job['session_id'],'assistant',job['assistant_message']); save_run(job['job_id'],job['session_id'],job['command'],'BLOCKED',job['assistant_message'])

def get_chat_history(session_id: str='default'):
    return {'session_id':session_id,'messages':history(session_id,40),'memory':recall('.',12)}
