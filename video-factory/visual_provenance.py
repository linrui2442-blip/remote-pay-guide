"""Deterministic visual-plan and material identity novelty checks."""
import hashlib, re
from pathlib import Path

def _tokens(value): return set(re.findall(r"[a-z0-9]+", " ".join(value or []).lower()))
def _url(value): return re.sub(r"[?#].*$", "", (value or "").strip().lower()).rstrip("/")

def compare_material_identity(candidate, history, cooldown=10):
    prior=history[-cooldown:]
    for c in candidate.get("materials",[]):
        for h in prior:
            for p in h.get("materials",[]):
                if c.get("provider") and c.get("provider")==p.get("provider") and c.get("source_id") and c.get("source_id")==p.get("source_id"): return {"decision":"BLOCK","reason":"same provider/source_id"}
                if _url(c.get("source_url")) and _url(c.get("source_url"))==_url(p.get("source_url")): return {"decision":"BLOCK","reason":"same source_url"}
                if c.get("sha256") and c.get("sha256")==p.get("sha256"): return {"decision":"BLOCK","reason":"same sha256"}
    return {"decision":"PASS","reason":None}

def compare_scene_terms(candidate_terms, history, cooldown=10):
    ct=_tokens(candidate_terms); best=0
    for h in history[-max(0, int(cooldown)):]:
        ht=_tokens(h.get("scene_terms",[])); best=max(best,len(ct&ht)/max(1,len(ct|ht)))
    return {"overlap":round(best,3),"decision":"BLOCK" if best>=.55 else ("WARN" if best>=.3 else "PASS")}

def check_within_video_diversity(terms):
    text=[str(t).lower() for t in terms]
    normalized=[_tokens([s]) for s in text]
    overlaps=[]
    for i in range(len(normalized)):
        for j in range(i): overlaps.append(len(normalized[i]&normalized[j])/max(1,len(normalized[i]|normalized[j])))
    near_duplicate = bool(overlaps) and sum(x >= .75 for x in overlaps) / len(overlaps) >= .7
    return {"distinct_combinations":len(set(text)),"location_composition_families":None,"pass":not near_duplicate}

def extract_material_provenance(task_dir):
    """Best-effort extraction; absence is explicit and never fabricated."""
    root=Path(task_dir); materials=[]
    for path in root.rglob("*") if root.exists() else []:
        if path.suffix.lower() in {".json",".csv"}:
            try:
                data=path.read_text(encoding="utf-8",errors="ignore")
                obj=None
                try: obj=__import__("json").loads(data)
                except Exception: pass
                records=obj if isinstance(obj,list) else [obj] if isinstance(obj,dict) else []
                for rec in records:
                    if not isinstance(rec,dict): continue
                    url=rec.get("source_url") or rec.get("video_url") or rec.get("download_url")
                    source_id=rec.get("source_id") or rec.get("video_id") or rec.get("clip_id")
                    provider=str(rec.get("provider") or "").lower()
                    if url and (provider=="pexels" or "pexels.com/video" in str(url).lower()):
                        materials.append({"provider":"pexels","source_id":source_id,"source_url":url,"local_filename":None,"sha256":None,"matched_term":rec.get("matched_term")})
            except OSError: pass
    return {"provenance_status":"available" if materials else "unavailable","materials":materials}

def fingerprint_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
