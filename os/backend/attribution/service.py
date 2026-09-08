import base64, hashlib, hmac, json, os, time
from datetime import datetime, timezone
from accounts.manager import get_account
from data.growth import get_intent_events, record_conversion, record_intent
from data.models import ConversionRecord, IntentEvent
from data.tracking import get_tracking_records
from publish.manager import get_publish_tasks
from attribution.adapters import get_conversion_adapter, list_conversion_adapters

MAX_METADATA_BYTES = 8192
MAX_SKEW_SECONDS = 300
ALLOWED_INTENT_TYPES = {"landing_view", "cta_click", "referral_click", "binance_referral_click"}

def _secret(): return os.getenv("OS_ATTRIBUTION_INGEST_SECRET")
def _destination(key):
    return os.getenv("OS_ATTRIBUTION_DESTINATION_BINANCE_REFERRAL") if str(key or '').lower() == 'binance_referral' else None
def status():
    configured = bool(_secret())
    return {'configured': configured, 'intent_ingestion_ready': configured, 'conversion_providers': list_conversion_adapters(), 'public_base_configured': bool(os.getenv('OS_ATTRIBUTION_PUBLIC_BASE_URL')), 'signing_configured': configured, 'binance_source': 'not_configured'}
def _body(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def verify_signed_request(body, timestamp, signature):
    if not _secret(): raise RuntimeError('attribution ingestion is not configured')
    try: ts = int(timestamp)
    except (TypeError, ValueError): raise ValueError('invalid attribution timestamp')
    if abs(int(time.time()) - ts) > MAX_SKEW_SECONDS: raise ValueError('attribution timestamp expired')
    expected = hmac.new(_secret().encode(), str(ts).encode()+b'.'+_body(body), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, str(signature)): raise ValueError('invalid attribution signature')
def _metadata(value):
    value = value or {}
    if not isinstance(value, dict): raise ValueError('metadata must be an object')
    if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_METADATA_BYTES: raise ValueError('metadata exceeds maximum size')
    forbidden = {'ip','ip_address','email','phone','user_agent','authorization','cookie','access_token','refresh_token'}
    if forbidden.intersection(str(k).lower() for k in value): raise ValueError('metadata contains forbidden personal or secret field')
    return value
def _resolve(data):
    cid, aid, platform, pvid = data.get('content_id'), data.get('account_id'), str(data.get('platform') or '').lower() or None, data.get('platform_video_id') or data.get('video_id')
    if aid is not None and not get_account(int(aid)): return 'UNRESOLVED'
    candidates = [t for t in get_publish_tasks() if pvid and t.get('platform_video_id') == pvid]
    if pvid and aid is not None: candidates += [t for t in get_tracking_records(aid, platform=platform) if t.get('platform_video_id') == pvid]
    for item in candidates:
        if aid is not None and item.get('account_id') is not None and int(item['account_id']) != int(aid): return 'REJECT'
        if platform and str(item.get('platform') or '').lower() != platform: return 'REJECT'
        item_cid = item.get('video_id') or item.get('content_id')
        if cid and item_cid and str(item_cid) != str(cid): return 'REJECT'
    return 'RESOLVE' if candidates else 'UNRESOLVED'
def ingest_intent(data):
    _metadata(data.get('metadata'))
    if data.get('event_type') not in ALLOWED_INTENT_TYPES: raise ValueError('unsupported intent event_type')
    if _resolve(data) != 'RESOLVE': raise ValueError('attribution identifiers unresolved or conflicting')
    payload = dict(data); payload['video_id'] = data.get('video_id') or data.get('platform_video_id'); payload['received_at'] = datetime.now(timezone.utc).isoformat()
    return record_intent(IntentEvent(**payload))
def ingest_conversion(provider, data):
    _metadata(data.get('metadata'))
    if not provider or not data.get('external_conversion_id'): raise ValueError('provider and external_conversion_id are required')
    adapter = get_conversion_adapter(provider)
    if adapter:
        data = adapter.normalize_conversion(adapter.verify_request(data))
    if _resolve(data) != 'RESOLVE': raise ValueError('attribution identifiers unresolved or conflicting')
    if data.get('intent_event_id') is not None:
        linked = next((item for item in get_intent_events(data.get('content_id')) if int(item.get('id') or 0) == int(data['intent_event_id'])), None)
        if not linked or (data.get('session_id') and linked.get('session_id') != data.get('session_id')):
            raise ValueError('intent_event_id is not linked to the supplied attribution')
    payload = dict(data); payload['provider'] = provider; payload['video_id'] = data.get('video_id') or data.get('platform_video_id'); payload['received_at'] = datetime.now(timezone.utc).isoformat()
    return record_conversion(ConversionRecord(**payload))
def encode_redirect_token(data):
    if not _secret(): raise RuntimeError('attribution signing is not configured')
    payload = dict(data); payload['issued_at'] = int(payload.get('issued_at') or time.time()); payload['expires_at'] = int(payload.get('expires_at') or payload['issued_at']+900)
    raw = base64.urlsafe_b64encode(_body(payload)).rstrip(b'='); sig = hmac.new(_secret().encode(), raw, hashlib.sha256).hexdigest(); return raw.decode()+'.'+sig
def decode_redirect_token(token):
    try:
        raw, supplied = str(token).split('.', 1); expected = hmac.new(_secret().encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied): raise ValueError('invalid attribution token')
        payload = json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)))
        if int(payload.get('expires_at', 0)) < int(time.time()): raise ValueError('attribution token expired')
        if not payload.get('destination_key') or not _destination(payload['destination_key']): raise ValueError('unknown attribution destination')
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc: raise ValueError(str(exc) or 'invalid attribution token') from exc
