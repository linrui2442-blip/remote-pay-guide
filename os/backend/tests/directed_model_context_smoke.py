"""Capture the real LLM boundary with synthetic evidence and a fake transport."""
import copy
import json
from g2a_real_ai_content_brain_smoke import GOOD, provider
from intelligence.content_brain import project_generation_snapshot


def main():
    private = ['snapshot_key', 'account_id', 'platform_video_id', 'fingerprint',
               'learning_state', 'learning_plan_id', 'learning_reason', 'learning_updated_at',
               'directed_requests_json', 'created_at', 'received_at', 'metric_collected_at',
               'feedback_json', 'strategy_json', 'metrics_json', 'funnel_json', 'content_id']
    snapshot = {key: 'private-sentinel-' + key for key in private}
    snapshot.update(id=11, platform='youtube',
        metrics_snapshot={'learning_evidence': {'window': ['2026-08-13', '2026-09-09'],
            'sample_size': 1, 'metrics': [{'views': 0, 'likes': 0, 'content_id': 'private-row-id'}],
            'reason_codes': ['OBSERVED_PERFORMANCE_ONLY', 'NO_CAUSAL_INFERENCE']}},
        growth_funnel={'traffic': {'landing_views': 0}, 'intent': {'total': 0, 'by_type': {'referral': 0}},
                       'conversion': {'total': 0, 'value': 0}},
        feedback={'recommendations': ['Teach payment verification.'], 'weak_patterns': [], 'successful_patterns': []},
        strategy={'objective': 'Payment education', 'parameters': {'strategy_type': 'iterate'}})
    for key in private:
        snapshot['feedback']['recommendations'].extend([
            json.dumps({key: snapshot[key]}),
            json.dumps(json.dumps({key: snapshot[key]})),
            'Embedded ' + key + ': ' + snapshot[key],
            'Reference ' + snapshot[key]])
    before = copy.deepcopy(snapshot)
    brief = 'Create payment education for remote workers.'
    constraints = {'target_audience': GOOD['target_audience'], 'locked_fields': ['topic'],
                   'locked_topic': GOOD['topic'], 'locked_angle': GOOD['angle'],
                   'locked_target_audience': GOOD['target_audience'],
                   'cta_direction': GOOD['cta'], 'locked_cta_direction': GOOD['cta'],
                   'must_include': ['verify'], 'must_avoid': ['guaranteed income claims']}
    context = {'content_id': 'directed-server-only', 'human_brief': brief, 'human_constraints': constraints,
               'history': [{'content_id': 'private-history-id', 'topic': 'Previous invoice lesson'}]}
    context_before = copy.deepcopy(context)
    llm = provider({**GOOD, 'content_id': 'model-injected'})
    plan = llm.generate_content_plan(snapshot, context)
    prompt = llm.text_provider.session.calls[0][1]['json']['messages'][-1]['content']
    assert brief in prompt and json.dumps(constraints, ensure_ascii=False) in prompt
    assert plan.human_constraints == constraints and plan.human_brief == brief
    print('BRIEF_AND_ALL_CONSTRAINTS_PRESERVED=PASS')
    projected = project_generation_snapshot(snapshot, context)
    assert json.dumps(projected, ensure_ascii=False) in prompt
    assert projected['platform'] == 'youtube' and projected['window'] == ['2026-08-13', '2026-09-09']
    assert projected['sample_size'] == 1 and projected['metrics'] == [{'views': 0, 'likes': 0}]
    assert projected['growth_funnel'] == snapshot['growth_funnel']
    assert projected['feedback']['recommendations'] == ['Teach payment verification.']
    assert projected['strategy'] == snapshot['strategy']
    assert projected['reason_codes'] == ['OBSERVED_PERFORMANCE_ONLY', 'NO_CAUSAL_INFERENCE']
    assert 'Previous invoice lesson' in prompt
    print('MODEL_CONTEXT_ALLOWED_FIELDS=PASS')
    for key in private:
        assert key not in prompt and snapshot[key] not in prompt, key
    assert 'private-row-id' not in prompt and 'private-history-id' not in prompt
    assert 'directed-server-only' not in prompt
    print('FINAL_PROMPT_NESTED_METADATA_ABSENT=PASS')
    assert snapshot == before and context == context_before
    assert plan.content_id == 'directed-server-only' and plan.source_snapshot_id == 11
    assert project_generation_snapshot({}, {'strategy': 'Test invoice clarity'})['strategy']['objective'] == 'Test invoice clarity'
    print('PURE_PROJECTION_SERVER_IDENTITY=PASS')
    assert 'observed measurements' in prompt and 'not causal evidence' in prompt
    assert 'Do not infer that the topic/category is inherently ineffective' in prompt
    assert 'human brief remains the primary creative direction' in prompt
    assert 'content failed' not in prompt.lower() and 'topic failed' not in prompt.lower()
    print('ZERO_OBSERVATIONS_NON_CAUSAL=PASS')
    print('DIRECTED_MODEL_CONTEXT=PASS')


if __name__ == '__main__':
    main()
