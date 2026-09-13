import json, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('content_novelty',ROOT/'video-factory'/'content_novelty.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
def evaluate_content_plan_novelty(plan):
    histories=[]
    for p in (ROOT/'video-factory').glob('tasks-*.jsonl'):
        for line in p.read_text(encoding='utf-8').splitlines():
            try: histories.append(json.loads(line))
            except Exception: pass
    candidate={'video_subject':f'{plan.topic} {plan.angle}','video_script':f'{plan.hook}\n{plan.script}\n{plan.cta}'}
    best=None
    for h in histories:
        try:
            r=mod.compare(candidate['video_subject'],candidate['video_script'],h)
            if best is None or r.get('score',0)>best.get('score',0): best=r|{'content_id':h.get('content_id')}
        except Exception: pass
    best=best or {'score':0,'concept_overlap':0,'subject_similarity':0,'script_similarity':0}
    score=float(best.get('score',0)); concept=float(best.get('concept_overlap',0)); decision='BLOCK' if score>=.42 and concept>=.35 else 'WARN' if score>=.25 else 'PASS'
    return {'decision':decision,'highest_match_content_id':best.get('content_id'),'subject_similarity':best.get('subject_similarity',0),'script_similarity':best.get('script_similarity',0),'concept_overlap':concept}
