import sys
sys.path.insert(0,"video-factory")
from visual_provenance import compare_material_identity,check_within_video_diversity
assert compare_material_identity({"materials":[{"provider":"p","source_id":"x"}]},[{"materials":[{"provider":"p","source_id":"x"}]}])["decision"]=="BLOCK"
assert compare_material_identity({"materials":[{"source_url":"https://EXAMPLE.com/a/?q=1"}]},[{"materials":[{"source_url":"https://example.com/a"}]}])["decision"]=="BLOCK"
assert compare_material_identity({"materials":[{"source_url":"https://a","sha256":"same"}]},[{"materials":[{"source_url":"https://b","sha256":"same"}]}])["decision"]=="BLOCK"
assert compare_material_identity({"materials":[{"provider":"p","source_id":"old"}]},[{"materials":[{"provider":"p","source_id":"old"}]}]+[{"materials":[]}]*10)["decision"]=="PASS"
assert not check_within_video_diversity(["phone home office checking payment"]*5)["pass"]
open_vocab=["freelancer checking payment in hotel lobby","hands reviewing transaction receipt at kitchen table","remote worker discussing invoice in conference room","close shot confirmation screen on train","person organizing payment records beside window"]
assert check_within_video_diversity(open_vocab)["pass"]
same_device=["person reading message on phone at cafe","person typing invoice on phone in hotel","person reviewing receipt on phone at desk","person discussing payment on phone outdoors","person organizing notes on phone in kitchen"]
assert check_within_video_diversity(same_device)["pass"]
print("Visual guard calibration smoke passed")
