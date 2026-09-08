from test_database_helper import TEST_DATABASE_PATH
import base64, hashlib, hmac, json, os, shutil, sqlite3, tempfile, time
from pathlib import Path
from data.growth import get_content_funnel
from data.models import ConversionRecord, IntentEvent
from data.growth import record_intent, record_conversion
from publish.manager import create_publish_task, update_publish_status
from publish.models import PublishTask
from attribution import service

def _setup():
    from accounts.manager import create_account
    from accounts.models import Account
    create_account(Account(platform='youtube', account_name='attr', status='connected'))
    task=create_publish_task(PublishTask(asset_id='asset-x', video_id='content-x', platform='youtube', account_id=1, status='published'))
    update_publish_status(task['id'], 'published', platform_video_id='video-x')

def _signed(payload, ts=None):
    ts=int(ts or time.time()); raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(); sig=hmac.new(b'test-secret',str(ts).encode()+b'.'+raw,hashlib.sha256).hexdigest(); return str(ts),sig

def main():
    os.environ['OS_ATTRIBUTION_INGEST_SECRET']='test-secret'; os.environ['OS_ATTRIBUTION_DESTINATION_BINANCE_REFERRAL']='https://example.test/ref'
    _setup()
    base={'content_id':'content-x','account_id':1,'platform':'youtube','platform_video_id':'video-x','session_id':'opaque-s1','source':'landing','campaign_id':'c1','event_type':'landing_view','event_id':'evt-1','metadata':{}}
    ts,sig=_signed(base); service.verify_signed_request(base,ts,sig)
    first=service.ingest_intent(base); second=service.ingest_intent(base); assert first['created'] and second['duplicate']
    other=dict(base,event_id='evt-2',event_type='cta_click'); service.ingest_intent(other)
    try: service.verify_signed_request(base, str(int(time.time())-600), sig); raise AssertionError
    except ValueError: pass
    try: service.verify_signed_request(base, ts, 'bad'); raise AssertionError
    except ValueError: pass
    try: service.ingest_intent(dict(base,event_id='evt-big',metadata={'x':'a'*9000})); raise AssertionError
    except ValueError: pass
    try: service.ingest_intent(dict(base,event_id='evt-bad',platform_video_id='other')); raise AssertionError
    except ValueError: pass
    conv=dict(content_id='content-x',account_id=1,platform='youtube',platform_video_id='video-x',session_id='opaque-s1',source='referral',intent_event_id=first['id'],external_conversion_id='conv-1',conversion_type='referral_conversion',value=1,currency='USD',metadata={})
    c1=service.ingest_conversion('synthetic',conv); c2=service.ingest_conversion('synthetic',conv); assert c1['created'] and c2['duplicate']
    funnel=get_content_funnel('content-x'); assert funnel['intent']['total']==2 and funnel['conversion']['total']==1
    token=service.encode_redirect_token(dict(content_id='content-x',account_id=1,platform='youtube',platform_video_id='video-x',campaign_id='c1',destination_key='binance_referral')); assert service.decode_redirect_token(token)['content_id']=='content-x'
    try: service.decode_redirect_token(token[:-1]+'x'); raise AssertionError
    except ValueError: pass
    os.environ.pop('OS_ATTRIBUTION_INGEST_SECRET'); assert service.status()['configured'] is False
    print('Attribution ingestion smoke test passed')
    print('intent dedupe; HMAC; expiry; privacy; linkage; conversion dedupe; redirect signing; funnel integration')

if __name__=='__main__': main()
