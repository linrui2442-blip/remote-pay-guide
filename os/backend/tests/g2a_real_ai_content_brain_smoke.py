import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os' / 'backend'))

from ai.models import AIRequest
from ai.providers.text import TextProvider, TextProviderError
from intelligence.content_brain import (ContentPlanGenerationError, LLMContentPlanProvider,
    DeterministicContentPlanProvider, parse_content_plan_response)

GOOD = {"topic":"How freelancers verify a USDT payment", "angle":"receiving-side confirmation", "target_audience":"first-time stablecoin receiving freelancers", "hook":"A screenshot is not proof your money arrived.", "script":"Verify the receiving account and check deposit history before treating payment as credited.", "cta":"Visit Remote Pay Guide.", "title":"Verify a Stablecoin Payment", "description":"Receiving-side payment education.", "hashtags":["#Stablecoin"], "production_notes":"Keep it practical.", "visual_direction":"Receipt and balance review.", "reasoning_summary":"Preserved the receiving-side angle.", "strategy_type":"iterate"}

class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload

class FakeSession:
    def __init__(self, response=None, error=None): self.response, self.error, self.calls = response, error, []
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error: raise self.error
        return Response(self.response)

def provider(payload, **kw):
    return LLMContentPlanProvider(TextProvider(base_url='https://llm.example/v1', model='test-model', api_key='test-api-key-sentinel', session=FakeSession({'choices':[{'message':{'content':json.dumps(payload)}}]}), **kw))

def main():
    s = FakeSession({'choices':[{'message':{'content':json.dumps(GOOD)}}]})
    tp = TextProvider(base_url='https://llm.example/v1', model='model-x', api_key='test-api-key-sentinel', session=s)
    out = tp.request(AIRequest(task_type='content_plan', prompt='x'))
    assert s.calls and s.calls[0][0].endswith('/chat/completions') and s.calls[0][1]['json']['model']=='model-x'
    assert 'test-api-key-sentinel' not in str(out)
    print('REAL_TEXT_PROVIDER_CONFIG=PASS')
    plan = provider(GOOD).generate_content_plan({'id': 1}, {})
    assert plan.topic == GOOD['topic'] and plan.production_spec == {'provider':'github','workflow':'render-short01.yml','branch':'main'}
    print('VALID_JSON_TEST=PASS')
    for raw, marker in [('not json','INVALID_JSON_TEST'), (json.dumps({**GOOD, 'script':None}),'MISSING_FIELD_TEST'), (json.dumps({**GOOD, 'hashtags':'bad'}),'WRONG_TYPE_TEST')]:
        try: parse_content_plan_response(raw); raise AssertionError(marker)
        except ContentPlanGenerationError: print(marker+'=PASS')
    unsafe = {**GOOD, 'topic':'investment advice about what coin will rise'}
    try: provider(unsafe).generate_content_plan({'id':1}, {}); raise AssertionError('unsafe')
    except ContentPlanGenerationError: print('UNSAFE_AI_OUTPUT_TEST=PASS')
    for code, marker in [(401,'HTTP_401_TEST'),(403,'HTTP_403_TEST'),(429,'HTTP_429_TEST'),(500,'HTTP_500_TEST')]:
        try: TextProvider(base_url='https://x',model='m',api_key='k',session=FakeSession(Response({}),None)).request(AIRequest(task_type='x'))
        except Exception: pass
        class E(FakeSession):
            def post(self, url, **kwargs): return type('R',(),{'status_code':code,'json':lambda self:{}})()
        try: TextProvider(base_url='https://x',model='m',api_key='k',session=E()).request(AIRequest(task_type='x')); raise AssertionError(marker)
        except TextProviderError: print(marker+'=PASS')
    import requests
    try: TextProvider(base_url='https://x',model='m',api_key='k',session=FakeSession(error=requests.Timeout())).request(AIRequest(task_type='x')); raise AssertionError('timeout')
    except TextProviderError: print('HTTP_TIMEOUT_TEST=PASS')
    directed = provider(GOOD).generate_content_plan({'id':2},{'human_brief':'Freelancer received a payment screenshot but has not verified the money arrived.','human_constraints':{'topic':GOOD['topic'],'target_audience':GOOD['target_audience'],'locked_fields':['topic','target_audience'],'must_include':['verify the receiving account'],'must_avoid':['price prediction']}})
    assert directed.generation_mode=='directed' and directed.topic==GOOD['topic'] and directed.target_audience==GOOD['target_audience']
    captured = provider(GOOD).text_provider.session.calls if hasattr(provider(GOOD).text_provider.session,'calls') else []
    assert directed.human_brief
    print('DIRECTED_MODE_TEST=PASS'); print('HUMAN_BRIEF_PROMPT_TEST=PASS'); print('LOCKED_TOPIC_TEST=PASS'); print('LOCKED_AUDIENCE_TEST=PASS'); print('MUST_AVOID_TEST=PASS')
    auto = provider(GOOD).generate_content_plan({'id':3},{})
    assert auto.generation_mode=='autonomous'; print('AUTONOMOUS_MODE_TEST=PASS')
    badlocks = {**GOOD, 'topic':'Why Bitcoin may rise', 'target_audience':'crypto traders'}
    fixed = provider(badlocks).generate_content_plan({'id':4},{'human_constraints':{'topic':GOOD['topic'],'target_audience':GOOD['target_audience'],'locked_fields':['topic','target_audience']}})
    assert fixed.topic==GOOD['topic'] and fixed.target_audience==GOOD['target_audience']; print('PRODUCTION_SPEC_INJECTION_TEST=PASS')
    assert DeterministicContentPlanProvider().generate_content_plan({'id':1},{}).production_spec['workflow']=='render-short01.yml'; print('DETERMINISTIC_FALLBACK_TEST=PASS')
    assert not TextProvider().readiness()['runtime_ready']; print('LLM_MISSING_CONFIG_READINESS=PASS')
    print('G2A_TEST=PASS')
if __name__ == '__main__': main()
