"""Repeatable, local-only smoke benchmark for the configured coding model."""
from __future__ import annotations
import json, time, uuid
from datetime import datetime, timezone
from .agent import ask_model
from .config import LOG_DIR, OLLAMA_MODEL

CASES=[
 {"id":"python_bugfix","prompt":"Given `def average(xs): return sum(xs)/len(xs)`, identify the empty-list bug and return a minimal corrected function plus one pytest test for empty input.","checks":["average","empty","test"]},
 {"id":"edge_cases","prompt":"Write a Python function `clamp(value, low, high)` and pytest tests for low boundary, high boundary, and normal values. Return code only.","checks":["clamp","assert","low","high"]},
 {"id":"safe_path","prompt":"Write a Python helper that resolves a user-supplied relative path under a root and raises ValueError if the resolved path escapes root. Return code only.","checks":["resolve","ValueError","root"]},
 {"id":"json_contract","prompt":"Return exactly valid JSON with keys summary (string) and files (array of objects containing path and content), proposing one new Python file that defines `hello()`.","checks":["summary","files","path","content"]},
 {"id":"debug_reasoning","prompt":"A test fails only on empty input because code indexes values[0]. Give the likely cause, a minimal fix, and one regression test. Separate cause, fix, and test.","checks":["empty","fix","test"]},
]
async def run_benchmark():
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    results=[]; started=time.time()
    for case in CASES:
        t=time.time()
        try:
            answer=await ask_model(case['prompt'],system='You are being evaluated on coding correctness. Follow the requested output format. Do not claim tests were run unless actually run.')
            lower=answer.lower(); hits=[c for c in case['checks'] if c.lower() in lower]
            score=round(len(hits)/len(case['checks']),2)
            results.append({"case_id":case['id'],"ok":score>=0.75,"heuristic_score":score,"checks_hit":hits,"checks_total":len(case['checks']),"duration_seconds":round(time.time()-t,2),"answer":answer[:8000]})
        except Exception as e: results.append({"case_id":case['id'],"ok":False,"heuristic_score":0,"duration_seconds":round(time.time()-t,2),"error":str(e)})
    passed=sum(bool(x['ok']) for x in results)
    report={"suite":"OmniForge Local Coding Smoke Benchmark","suite_version":"1.0","run_id":run_id,"model":OLLAMA_MODEL,"local_only":True,"paid_api_calls":False,"cases":len(CASES),"passed_heuristic":passed,"score":round(passed/len(CASES),2),"duration_seconds":round(time.time()-started,2),"results":results,"limitations":"String/format heuristic only; not a substitute for executable unit tests, SWE-bench, or a blinded model comparison. Compare models on the same machine and prompts."}
    LOG_DIR.mkdir(parents=True,exist_ok=True); path=LOG_DIR/f'benchmark_{run_id}.json'; path.write_text(json.dumps(report,indent=2),encoding='utf-8'); report['report_file']=str(path)
    return report
