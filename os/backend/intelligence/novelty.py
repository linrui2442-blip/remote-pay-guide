import json, importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('content_novelty',ROOT/'video-factory'/'content_novelty.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
def evaluate_content_plan_novelty(plan):
    histories=mod.scan_tasks(ROOT/'video-factory')
    candidate={'video_subject':f'{plan.topic} {plan.angle}','video_script':f'{plan.hook}\n{plan.script}\n{plan.cta}'}
    best=None
    result=mod.compare(candidate['video_subject'],candidate['video_script'],histories)
    return result
