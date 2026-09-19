import hashlib, json, sqlite3
from datetime import datetime, timezone
from intelligence.content_brain import ContentPlan, get_plan, validate_content_plan
from intelligence.content_plan_service import evaluate_and_persist_novelty
from data.database_path import database_path
from intelligence.policy_signals import collect_policy_signals

POLICY_VERSION = 'g3-v2'
POLICY_STAGE = 'content_plan'
DECISIONS = {'AUTO','REVIEW','BLOCK'}
REQUIRED_GATES = ('safety','novelty','duplicate_risk','account_health','platform_health','frequency','business','quality','cost','ai_confidence')
CONTENT_PLAN_REQUIRED_GATES = ('safety','novelty','duplicate_risk','account_health','platform_health','business','ai_confidence')
CONTENT_PLAN_DEFERRED_GATES = {'frequency':'DEFERRED_TO_PUBLISH_POLICY','quality':'DEFERRED_TO_ASSET_QUALITY_GATE','cost':'DEFERRED_TO_PRODUCTION_POLICY'}

def _now(): return datetime.now(timezone.utc).isoformat()
def _conn():
    c=sqlite3.connect(database_path()); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence_policy_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, content_plan_id INTEGER NOT NULL, content_plan_revision INTEGER NOT NULL, policy_version TEXT NOT NULL, decision TEXT NOT NULL, reason_codes_json TEXT NOT NULL, evidence_json TEXT NOT NULL, source_fingerprint TEXT NOT NULL, evaluated_at TEXT NOT NULL, superseded_at TEXT)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_policy_plan ON intelligence_policy_decisions(content_plan_id, content_plan_revision)')
    c.execute('BEGIN IMMEDIATE')
    existing = c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_policy_current'").fetchone()
    sql = (existing[0] or '') if existing else ''
    # Migrate the G3-C1 per-version index to the stronger cross-version
    # invariant. Preserve every row as history and deterministically retain
    # the current-version row (or newest row when no v2 row exists).
    if 'content_plan_revision, policy_version' in sql:
        groups = c.execute('''SELECT content_plan_id, content_plan_revision FROM intelligence_policy_decisions
                              WHERE superseded_at IS NULL GROUP BY content_plan_id, content_plan_revision''').fetchall()
        now = _now()
        for group in groups:
            rows = c.execute('''SELECT id, policy_version FROM intelligence_policy_decisions
                                WHERE content_plan_id=? AND content_plan_revision=? AND superseded_at IS NULL
                                ORDER BY id DESC''', (group[0], group[1])).fetchall()
            if len(rows) > 1:
                keep = next((r for r in rows if r['policy_version'] == POLICY_VERSION), rows[0])
                c.execute('UPDATE intelligence_policy_decisions SET superseded_at=? WHERE content_plan_id=? AND content_plan_revision=? AND superseded_at IS NULL AND id<>?', (now, group[0], group[1], keep['id']))
        c.execute('DROP INDEX uq_policy_current')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_current ON intelligence_policy_decisions(content_plan_id, content_plan_revision) WHERE superseded_at IS NULL')
    c.commit(); return c

def _canonical(value): return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False)
def source_fingerprint(plan_record, signals):
    plan=plan_record.get('plan') or {}
    stable_plan={k:plan.get(k) for k in ('content_id','topic','angle','target_audience','hook','script','cta','title','description','visual_direction','production_notes','strategy_type')}
    stable_plan['generation_provider'] = plan.get('generation_provider', 'unknown')
    stable_plan['generation_evidence'] = plan.get('generation_evidence') or {}
    payload={'policy_version':POLICY_VERSION,'content_plan_id':plan_record['id'],'revision':plan_record['revision'],'status':plan_record['status'],'plan':stable_plan,'signals':signals}
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()

def evaluate_policy_signals(plan_record, signals):
    gates={k:str((signals or {}).get(k,'UNKNOWN')).upper() for k in REQUIRED_GATES}
    invalid_deferred = False
    for key in CONTENT_PLAN_DEFERRED_GATES: gates[key]='NOT_APPLICABLE'
    for key in CONTENT_PLAN_REQUIRED_GATES:
        if gates[key]=='NOT_APPLICABLE': gates[key]='UNKNOWN'
        elif gates[key] not in {'PASS','WARN','BLOCK','UNKNOWN'}: gates[key]='UNKNOWN'
    # Deferred values are valid only as N/A at this stage. Any internal
    # malformed value is fail-closed rather than silently satisfied.
    for key in CONTENT_PLAN_DEFERRED_GATES:
        supplied = str((signals or {}).get(key, 'NOT_APPLICABLE')).upper()
        if supplied not in {'NOT_APPLICABLE'}: gates[key] = 'UNKNOWN'; invalid_deferred = True
    reasons=[]
    if plan_record.get('status') in {'superseded','materialized'}: reasons.append('PLAN_NOT_ACTIONABLE')
    if plan_record.get('status') == 'approved': reasons.append('PLAN_ALREADY_MANUALLY_APPROVED')
    if gates['safety']=='BLOCK': reasons.append('CONTENT_SAFETY_BLOCK')
    elif gates['safety']=='PASS': reasons.append('CONTENT_SAFETY_PASS')
    novelty=gates['novelty']
    if novelty=='BLOCK': reasons.append('NOVELTY_BLOCK')
    elif novelty=='WARN': reasons.append('NOVELTY_WARN')
    elif novelty=='PASS': reasons.append('NOVELTY_PASS')
    for key in CONTENT_PLAN_REQUIRED_GATES:
        if gates[key]=='BLOCK': reasons.append({'duplicate_risk':'DUPLICATE_BLOCK','account_health':'ACCOUNT_HARD_FAILURE','platform_health':'PLATFORM_HARD_FAILURE'}.get(key,key.upper()+'_BLOCK'))
        elif gates[key] in {'UNKNOWN','WARN'}:
            reasons.append({'duplicate_risk':'DUPLICATE_RISK_UNKNOWN','account_health':'ACCOUNT_HEALTH_UNKNOWN','platform_health':'PLATFORM_HEALTH_UNKNOWN','business':'BUSINESS_POLICY_UNKNOWN','ai_confIDENCE':'AI_CONFIDENCE_UNKNOWN','ai_confidence':'AI_CONFIDENCE_UNKNOWN'}.get(key,key.upper()+'_UNKNOWN'))
    if invalid_deferred: reasons.append('DEFERRED_GATE_INVALID')
    if any(gates[k]=='BLOCK' for k in CONTENT_PLAN_REQUIRED_GATES) or any(x in reasons for x in ('PLAN_NOT_ACTIONABLE','CONTENT_SAFETY_BLOCK','NOVELTY_BLOCK')): decision='BLOCK'
    elif invalid_deferred or any(gates[k] in {'UNKNOWN','WARN'} for k in CONTENT_PLAN_REQUIRED_GATES) or plan_record.get('status')=='approved': decision='REVIEW'
    else: decision='AUTO'; reasons=['AUTO_ELIGIBLE']
    return {'decision':decision,'reason_codes':list(dict.fromkeys(reasons)),'evidence':{'stage':POLICY_STAGE,'gates':gates,'revision':plan_record['revision'],'gate_applicability':{'required':list(CONTENT_PLAN_REQUIRED_GATES),'deferred':dict(CONTENT_PLAN_DEFERRED_GATES)}}}

def _row(r):
    if not r: return None
    d=dict(r); d['reason_codes']=json.loads(d.pop('reason_codes_json')); d['evidence']=json.loads(d.pop('evidence_json')); d['current']=d.get('superseded_at') is None; return d

def _signals_for_plan(p):
    collected=collect_policy_signals(p)
    return collected['signals'], p, collected['evidence']

def evaluate_policy(plan_id, signals=None):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    evidence={}
    if signals is None: current, p, evidence = _signals_for_plan(p)
    else: current, p = signals, p
    result=evaluate_policy_signals(p,current); result['evidence']['policy_signal_evidence']=evidence; fp=source_fingerprint(p,{'signals':current,'evidence':evidence})
    with _conn() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM intelligence_policy_decisions WHERE content_plan_id=? AND content_plan_revision=? AND policy_version=? AND source_fingerprint=? AND superseded_at IS NULL',(plan_id,p['revision'],POLICY_VERSION,fp)).fetchone()
        if row: return _row(row)
        c.execute('UPDATE intelligence_policy_decisions SET superseded_at=? WHERE content_plan_id=? AND content_plan_revision=? AND superseded_at IS NULL',(_now(),plan_id,p['revision']))
        cur=c.execute('INSERT INTO intelligence_policy_decisions(content_plan_id,content_plan_revision,policy_version,decision,reason_codes_json,evidence_json,source_fingerprint,evaluated_at) VALUES(?,?,?,?,?,?,?,?)',(plan_id,p['revision'],POLICY_VERSION,result['decision'],_canonical(result['reason_codes']),_canonical(result['evidence']),fp,_now())); c.commit()
        return _row(c.execute('SELECT * FROM intelligence_policy_decisions WHERE id=?',(cur.lastrowid,)).fetchone())

def get_current_policy_decision(plan_id):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    with _conn() as c: row=c.execute('SELECT * FROM intelligence_policy_decisions WHERE content_plan_id=? AND policy_version=? AND superseded_at IS NULL ORDER BY id DESC LIMIT 1',(plan_id,POLICY_VERSION)).fetchone()
    d=_row(row)
    if d and d['content_plan_revision'] != p['revision']: return None
    return d
def list_policy_history(plan_id):
    with _conn() as c: return [_row(r) for r in c.execute('SELECT * FROM intelligence_policy_decisions WHERE content_plan_id=? ORDER BY id',(plan_id,)).fetchall()]
def list_review_queue():
    with _conn() as c: rows=c.execute('SELECT * FROM intelligence_policy_decisions WHERE decision="REVIEW" AND policy_version=? AND superseded_at IS NULL ORDER BY id',(POLICY_VERSION,)).fetchall()
    out=[]
    for r in rows:
        d=_row(r); p=get_plan(d['content_plan_id'])
        if p and p['revision']==d['content_plan_revision'] and p['status'] not in {'materialized','superseded'}: out.append(d)
    return out
