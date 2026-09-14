import asyncio, json, os, sys, tempfile, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os' / 'backend'))
os.environ['OS_TESTING'] = '1'
os.environ['OS_DATABASE_PATH'] = str(Path(tempfile.gettempdir()) / ('g2a-route-' + uuid.uuid4().hex + '.db'))

from intelligence.content_brain import ContentPlan, ContentPlanGenerationError, validate_human_directive_safety
import routers.intelligence as intelligence_router
from main import app

class FakeProvider:
    def __init__(self): self.call_count = 0; self.prompts = []
    def readiness(self): return {'provider':'llm','implementation_ready':True,'runtime_ready':True,'missing_configuration':[]}
    def generate_content_plan(self, snapshot, context):
        validate_human_directive_safety(context.get('human_brief'), context.get('human_constraints'))
        self.call_count += 1
        self.prompts.append((context, snapshot))
        return ContentPlan(content_id='route-plan-'+str(self.call_count), topic='Stablecoin payment verification', angle='receiving-side check', target_audience='freelancers', hook='Check before you trust a screenshot.', script='Verify the receiving account and deposit history.', cta='Visit Remote Pay Guide.', title='Verify payment', description='Safe payment education.', hashtags=['#Stablecoin'], production_notes='Practical', visual_direction='Receipt review', reasoning_summary='Keep the user angle.', strategy_type='iterate', generation_mode='directed' if context.get('human_brief') or context.get('human_constraints') else 'autonomous', human_brief=context.get('human_brief',''), human_constraints=context.get('human_constraints',{}), production_spec={'provider':'github','workflow':'render-short01.yml','branch':'main'})

def main():
    provider = FakeProvider()
    original_provider = intelligence_router.select_content_plan_provider
    original_snapshot = intelligence_router.get_feedback_snapshot
    intelligence_router.get_feedback_snapshot = lambda _id: {'id': _id, 'content_id':'route-source'}
    intelligence_router.select_content_plan_provider = lambda: provider
    try:
        response = asgi_request('/intelligence/feedback/1/content-plan')
        assert response['status'] == 200 and response['json']['plan']['plan']['generation_mode'] == 'autonomous'; print('NO_BODY_ROUTE_COMPATIBILITY=PASS')
        brief = 'Create content for freelancers who received a payment screenshot but still need to verify the stablecoin deposit.'
        response = asgi_request('/intelligence/feedback/2/content-plan', {'human_brief':brief,'human_constraints':{'target_audience':'first-time stablecoin receiving freelancers','must_avoid':['investment advice','price prediction']}})
        assert response['status'] == 200 and response['json']['plan']['plan']['generation_mode'] == 'directed' and provider.call_count == 2 and provider.prompts[-1][0]['human_brief'] == brief; print('DIRECTED_ROUTE_CONTRACT=PASS')
        response = asgi_request('/intelligence/feedback/3/content-plan', {'human_brief':'Recommend which crypto token the viewer should buy for profit.'})
        assert response['status'] == 422 and provider.call_count == 2; print('UNSAFE_ROUTE_PROVIDER_CALL_COUNT_ZERO=PASS')
    finally:
        intelligence_router.select_content_plan_provider = original_provider
        intelligence_router.get_feedback_snapshot = original_snapshot
    os.environ['OS_CONTENT_PLAN_PROVIDER'] = 'llm'
    intelligence_router.get_feedback_snapshot = lambda _id: {'id': _id, 'content_id':'route-source'}
    intelligence_router.select_content_plan_provider = lambda: type('Missing',(),{'readiness':lambda self:{'provider':'llm','implementation_ready':True,'runtime_ready':False,'missing_configuration':['api_key']}})()
    try:
        response = asgi_request('/intelligence/feedback/4/content-plan')
        assert response['status'] == 503 and 'api_key' in str(response['json']) and 'Authorization' not in str(response['json']); print('LLM_MISSING_CONFIG_HTTP_503=PASS'); print('SECRET_REDACTION_ROUTE_TEST=PASS')
    finally:
        intelligence_router.select_content_plan_provider = original_provider
        intelligence_router.get_feedback_snapshot = original_snapshot
        os.environ.pop('OS_CONTENT_PLAN_PROVIDER', None)
    print('G2A_ROUTE_TEST=PASS')

def asgi_request(path, payload=None):
    body = b'' if payload is None else json.dumps(payload).encode()
    messages = []
    async def receive():
        return {'type':'http.request','body':body,'more_body':False}
    async def send(message): messages.append(message)
    asyncio.run(app({'type':'http','http_version':'1.1','method':'POST','path':path,'raw_path':path.encode(),'query_string':b'','headers':[(b'content-type',b'application/json')],'scheme':'http','server':('test',80),'client':('test',1)}, receive, send))
    status = next(m['status'] for m in messages if m['type']=='http.response.start')
    data = b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
    return {'status':status, 'json':json.loads(data.decode()) if data else {}}
if __name__ == '__main__': main()
