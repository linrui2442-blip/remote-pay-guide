"""Deterministic visual-plan and material identity novelty checks."""
import hashlib, re

def _tokens(value): return set(re.findall(r"[a-z0-9]+", " ".join(value or []).lower()))
def _url(value): return re.sub(r"[?#].*$", "", (value or "").strip().lower().rstrip("/"))

def compare_material_identity(candidate, history, cooldown=10):
    prior=history[-cooldown:]
    for c in candidate.get("materials",[]):
        for h in prior:
            for p in h.get("materials",[]):
                if c.get("provider") and c.get("provider")==p.get("provider") and c.get("source_id") and c.get("source_id")==p.get("source_id"): return {"decision":"BLOCK","reason":"same provider/source_id"}
                if _url(c.get("source_url")) and _url(c.get("source_url"))==_url(p.get("source_url")): return {"decision":"BLOCK","reason":"same source_url"}
                if c.get("sha256") and c.get("sha256")==p.get("sha256"): return {"decision":"BLOCK","reason":"same sha256"}
    return {"decision":"PASS","reason":None}

def compare_scene_terms(candidate_terms, history):
    ct=_tokens(candidate_terms); best=0
    for h in history:
        ht=_tokens(h.get("scene_terms",[])); best=max(best,len(ct&ht)/max(1,len(ct|ht)))
    return {"overlap":round(best,3),"decision":"BLOCK" if best>=.55 else ("WARN" if best>=.3 else "PASS")}

def check_within_video_diversity(terms):
    text=[" ".join(t).lower() if isinstance(t,list) else str(t).lower() for t in terms]
    families=[]
    for s in text:
        action=next((x for x in ("reading","typing","copying","checking","writing","reviewing","walking","talking","comparing") if x in s),"other")
        location=next((x for x in ("home office","coworking","cafe","airport","hotel","office","outdoor","transit") if x in s),"other")
        composition=next((x for x in ("close-up","wide","hands-only","over-shoulder","portrait","screen") if x in s),"other")
        families.append((action,location,composition))
    return {"distinct_combinations":len(set(families)),"location_composition_families":len(set((x[1],x[2]) for x in families)),"pass":len(set(families))>=3 and len(set((x[1],x[2]) for x in families))>=2}

def fingerprint_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
