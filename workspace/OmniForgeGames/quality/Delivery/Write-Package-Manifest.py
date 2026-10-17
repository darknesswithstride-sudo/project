from pathlib import Path
import json,time,sys
r=Path(__file__).resolve().parents[1]; build=r/"Build"/"Win64"
files=[str(p.relative_to(r)) for p in build.rglob("*") if p.is_file()] if build.exists() else []
status="PACKAGED" if files else "BUILD_OUTPUT_MISSING"
report={"project":r.name,"created_at":time.time(),"package_status":status,"file_count":len(files),"files":files[:500],"verified_launch":False,"note":"File presence is not proof of successful launch; mark verified_launch only after running the packaged game."}
(r/"Delivery"/"package_manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2));sys.exit(0 if files else 2)
