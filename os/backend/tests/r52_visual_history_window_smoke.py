import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,"video-factory")
from visual_provenance import compare_scene_terms,extract_material_provenance
scene=["freelancer checking payment at cafe"]
assert compare_scene_terms(scene,[{"scene_terms":scene}],cooldown=10)["decision"] in ("WARN","BLOCK")
assert compare_scene_terms(scene,[{"scene_terms":scene}]+[{"scene_terms":[]}]*10,cooldown=10)["decision"]=="PASS"
root=Path(tempfile.mkdtemp()); (root/"links.json").write_text(json.dumps({"url":"https://example.com/page","next":"https://github.com/x"}))
assert extract_material_provenance(root)["materials"]==[]
(root/"material.json").write_text(json.dumps({"provider":"pexels","source_id":"77","source_url":"https://www.pexels.com/video/abc"}))
r=extract_material_provenance(root); assert r["provenance_status"]=="available" and r["materials"][0]["source_id"]=="77"
empty=Path(tempfile.mkdtemp()); r=extract_material_provenance(empty); assert r=={"provenance_status":"unavailable","materials":[]}
print("Visual history window and provenance smoke passed")
