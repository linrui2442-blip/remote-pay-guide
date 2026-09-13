"""Deterministic pre-production content novelty gate."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

STOP = {"a","an","and","the","to","of","for","on","in","is","it","your","you","before","how","should","what","when","with","can","use"}
CONCEPTS = {"usdt","usdc","network","address","wallet","receive","receiving","payment","client","freelancer","transfer","test","seed","private","key","transaction","confirmations","balance","hash","invoice","pending","issuer","token","platform"}

def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP and len(t) > 2}

def _similar(a, b):
    return SequenceMatcher(None, " ".join(sorted(_tokens(a))), " ".join(sorted(_tokens(b)))).ratio()

def compare(candidate_subject, candidate_script, historical):
    ct = _tokens(candidate_subject + " " + candidate_script)
    best = None
    for item in historical:
        ht = _tokens((item.get("video_subject") or "") + " " + (item.get("video_script") or ""))
        union = ct | ht
        jaccard = len(ct & ht) / len(union) if union else 0
        ss = _similar(candidate_subject, item.get("video_subject"))
        ts = _similar(candidate_script, item.get("video_script"))
        concepts = len((ct & ht) & CONCEPTS) / max(1, len((ct | ht) & CONCEPTS))
        score = (jaccard + ts + concepts) / 3
        row = {"content_id": item.get("content_id"), "subject_similarity": round(ss, 3), "script_similarity": round(ts, 3), "concept_overlap": round(concepts, 3), "jaccard": round(jaccard, 3), "score": score}
        if best is None or score > best["score"]: best = row
    if not best: return {"highest_match_content_id": None, "subject_similarity": 0, "script_similarity": 0, "concept_overlap": 0, "decision": "PASS"}
    decision = "BLOCK" if best["score"] >= 0.42 and best["concept_overlap"] >= 0.35 else ("WARN" if best["score"] >= 0.25 else "PASS")
    return {"highest_match_content_id": best["content_id"], **{k: best[k] for k in ("subject_similarity","script_similarity","concept_overlap")}, "decision": decision}

def scan_tasks(root=None):
    root = Path(root or Path(__file__).parent)
    rows=[]
    for path in sorted(root.glob("tasks-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    item=json.loads(line); item["content_id"]=item.get("content_id") or path.stem.removeprefix("tasks-"); rows.append(item)
                except json.JSONDecodeError: pass
    return rows

def check(candidate_subject, candidate_script, root=None):
    return compare(candidate_subject, candidate_script, scan_tasks(root))
