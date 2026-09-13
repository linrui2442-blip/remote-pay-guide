import sys
sys.path.insert(0,"video-factory")
from visual_provenance import compare_material_identity,compare_scene_terms,check_within_video_diversity
terms=["freelancer reading payment message on smartphone","remote worker checking network on laptop","person comparing network options on phone","copying receiving address at home office","reviewing payment instructions home office"]
assert compare_scene_terms(terms,[{"scene_terms":terms}])["decision"] in ("WARN","BLOCK")
assert compare_material_identity({"materials":[{"provider":"pexels","source_id":"1"}]},[{"materials":[{"provider":"pexels","source_id":"1"}]}])["decision"]=="BLOCK"
assert compare_material_identity({"materials":[{"source_url":"https://x/a"}]},[{"materials":[{"source_url":"https://y/b","sha256":"same"}]}])["decision"]=="PASS"
assert not check_within_video_diversity(["person phone home office"]*5)["pass"]
diverse=["close-up phone reading message at cafe","wide coworking desk typing","hands-only writing invoice in office","screen reviewing transaction at airport","walking meeting outdoors"]
assert check_within_video_diversity(diverse)["pass"]
assert compare_material_identity({"materials":[{"provider":"pexels","source_id":"old"}]},[{"materials":[{"provider":"pexels","source_id":"old"}]}]+[{"materials":[] }]*10,cooldown=10)["decision"]=="PASS"
print("Visual novelty gate smoke passed")
