from pathlib import Path
import json,sys
r=Path(__file__).resolve().parents[1]; errors=[]
try: d=json.loads((r/(r.name+".uproject")).read_text())
except Exception as e: errors.append(str(e)); d={}
for x in ["Config/DefaultEngine.ini","README_OMNIFORGE.md","Source"]:
 if not (r/x).exists(): errors.append("missing "+x)
for p in (r/"Source").rglob("*.cpp") if (r/"Source").exists() else []:
 if p.stat().st_size<20: errors.append("empty source "+str(p))
print(json.dumps({"project":r.name,"modules":d.get("Modules",[]),"errors":errors,"status":"PASS" if not errors else "FAIL"},indent=2));sys.exit(bool(errors))
