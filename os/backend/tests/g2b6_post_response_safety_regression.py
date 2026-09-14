import json, os, sys, tempfile, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT/'os'/'backend'))
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/('g2b6-'+uuid.uuid4().hex+'.db'))
from intelligence.content_brain import LLMContentPlanProvider, ContentPlanGenerationError

GOOD={"topic":"Stablecoin payment verification","angle":"Screenshot is not proof of receipt","target_audience":"freelancers","hook":"Check before you trust a screenshot.","script":"Verify the actual receiving account and check deposit history.","cta":"Visit Remote Pay Guide.","title":"Verify payment","description":"Safe receiving education.","hashtags":["#Stablecoin"],"production_notes":"Practical","visual_direction":"Receipt review","reasoning_summary":"Keep the receiving-side angle.","strategy_type":"iterate"}
class FakeText:
    def __init__(self,payload): self.payload=payload; self.call_count=0; self.model='test-model'
    def readiness(self): return {'provider':'llm','implementation_ready':True,'runtime_ready':True,'missing_configuration':[]}
    def request(self, request): self.call_count+=1; return {'output':json.dumps(self.payload)}
def main():
    safe='Create content for freelancers verifying a stablecoin payment. Do not give investment advice. Do not predict token prices. Do not give trading recommendations. Never ask for a seed phrase or private key.'
    fake=FakeText(GOOD); plan=LLMContentPlanProvider(fake).generate_content_plan({'id':1},{'human_brief':safe,'human_constraints':{'must_avoid':['investment advice','price prediction','trading recommendation','seed phrase request','private key request']}})
    assert fake.call_count==1 and plan.generation_mode=='directed'; print('SAFE_NEGATIVE_DIRECTED_BRIEF=PASS')
    bad=FakeText(GOOD)
    try: LLMContentPlanProvider(bad).generate_content_plan({'id':1},{'human_brief':'Recommend which crypto token viewers should buy for profit.'}); raise AssertionError('unsafe directive accepted')
    except ContentPlanGenerationError: assert bad.call_count==0
    print('UNSAFE_POSITIVE_DIRECTIVE_PREBLOCK=PASS')
    bad_seed=FakeText(GOOD)
    try: LLMContentPlanProvider(bad_seed).generate_content_plan({'id':1},{'human_brief':'Ask users to send their seed phrase so you can verify their wallet.'}); raise AssertionError('unsafe credential directive accepted')
    except ContentPlanGenerationError: assert bad_seed.call_count==0
    print('UNSAFE_SEED_PHRASE_DIRECTIVE_PREBLOCK=PASS')
    unsafe={**GOOD,'script':'Ask the user for their seed phrase.'}; out=FakeText(unsafe)
    try: LLMContentPlanProvider(out).generate_content_plan({'id':1},{'human_brief':'Explain payment verification safely.'}); raise AssertionError('unsafe output accepted')
    except ContentPlanGenerationError: assert out.call_count==1
    print('UNSAFE_AI_OUTPUT_POSTBLOCK=PASS')
    safe_text=(plan.hook+' '+plan.script+' '+plan.cta+' '+plan.topic+' '+plan.angle).lower()
    assert fake.call_count==1
    assert all(term not in safe_text for term in ['investment advice','price prediction','trading recommendation','seed phrase','private key'])
    print('MUST_AVOID_SAFETY_TERMS_ALLOWED=PASS')
    raw_include={**GOOD,'topic':'Generic payment topic'}; include_fake=FakeText(raw_include)
    include_plan=LLMContentPlanProvider(include_fake).generate_content_plan({'id':1},{'human_constraints':{'topic':'Verify the actual receiving account before calling it paid.','locked_fields':['topic'],'must_include':['verify the actual receiving account']}})
    assert 'verify the actual receiving account' not in raw_include['topic'].lower()
    assert 'verify the actual receiving account' in include_plan.topic.lower()
    print('MUST_INCLUDE_AFTER_LOCK_NORMALIZATION=PASS')
    sentinel='obsolete raw angle sentinel'; raw_avoid={**GOOD,'angle':sentinel}; avoid_fake=FakeText(raw_avoid)
    avoid_plan=LLMContentPlanProvider(avoid_fake).generate_content_plan({'id':1},{'human_constraints':{'angle':'payment screenshot is not proof of successful receipt','locked_fields':['angle'],'must_avoid':[sentinel]}})
    assert sentinel in raw_avoid['angle'].lower() and sentinel not in avoid_plan.angle.lower()
    print('MUST_AVOID_AFTER_LOCK_NORMALIZATION=PASS')
    from g2a_route_contract_smoke import asgi_request
    import routers.intelligence as route_mod
    original_provider, original_snapshot = route_mod.select_content_plan_provider, route_mod.get_feedback_snapshot
    route_fake=FakeText(GOOD); route_mod.select_content_plan_provider=lambda: LLMContentPlanProvider(route_fake); route_mod.get_feedback_snapshot=lambda _id:{'id':_id,'content_id':'route'}
    try:
        response=asgi_request('/intelligence/feedback/1/content-plan', {'human_brief':safe,'human_constraints':{'must_avoid':['investment advice','price prediction','trading recommendation','seed phrase','private key']}})
        assert response['status']==200 and response['json']['plan'] and response['json']['plan']['status']=='preview' and response['json']['plan']['plan']['generation_mode']=='directed'
        print('SAFE_DIRECTED_ROUTE_WITH_PROHIBITIONS=PASS')
    finally:
        route_mod.select_content_plan_provider, route_mod.get_feedback_snapshot = original_provider, original_snapshot
    print('MARKER_ONLY_PASS_COUNT=0')
    print('G2B6_REGRESSION_TEST=PASS')
if __name__=='__main__': main()
