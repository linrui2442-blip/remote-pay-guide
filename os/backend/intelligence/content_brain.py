from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Protocol
import json, sqlite3, os, re, hashlib, unicodedata
from contextlib import closing
from datetime import datetime, timezone
from data.database_path import database_path


@dataclass
class ContentPlan:
    content_id: str
    topic: str
    angle: str
    target_audience: str
    hook: str
    script: str
    cta: str
    title: str
    description: str
    hashtags: List[str] = field(default_factory=list)
    production_notes: str = ""
    visual_direction: str = ""
    reasoning_summary: str = ""
    source_snapshot_id: Any = None
    source_content_id: str | None = None
    strategy_type: str = "iterate"
    novelty_status: str = "unverified"
    novelty_evidence: Dict[str, Any] = field(default_factory=dict)
    production_spec: Dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "autonomous"
    human_brief: str = ""
    human_constraints: Dict[str, Any] = field(default_factory=dict)
    # Server-owned generation provenance.  These fields are never accepted
    # from model output; providers and lifecycle code populate them.
    generation_provider: str = "unknown"
    generation_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def build_content_brain_prompt(snapshot, strategy, history=None, production_history=None, novelty_history=None):
    return """You are the Remote Pay Guide content planner. Audience: freelancer, remote worker, digital nomad, overseas service provider, and first-time stablecoin payment receiver. Funnel: Short video -> Profile/Bio -> Remote Pay Guide -> stablecoin payment education -> Binance referral click. Never give investment advice, price prediction, trading recommendations, seed phrase/private key requests, or unsafe crypto instructions. Preserve effective variables, test a limited explicit variable, and explain preserved_variable, tested_variable, and why. Do not copy recent topics, hooks, angles, or visual plans.\n\nDATA CENTER SNAPSHOT:\n{snapshot}\nSTRATEGY:\n{strategy}\nRECENT CONTENT:\n{history}\nRECENT PRODUCTION:\n{production_history}\nRECENT NOVELTY:\n{novelty_history}""".format(snapshot=snapshot, strategy=strategy, history=history or [], production_history=production_history or [], novelty_history=novelty_history or [])


class ContentPlanProvider(Protocol):
    def generate_content_plan(self, snapshot, context) -> ContentPlan: ...


def project_generation_snapshot(snapshot, context=None):
    """Pure model-input projection; never changes persisted evidence or identity."""
    source = snapshot if isinstance(snapshot, dict) else {}
    private = {'id', 'account_id', 'content_id', 'content_ids', 'video_id', 'platform_video_id',
               'snapshot_id', 'snapshot_key', 'fingerprint', 'learning_state', 'learning_plan_id',
               'learning_reason', 'learning_updated_at', 'directed_requests_json',
               'created_at', 'updated_at', 'received_at', 'metric_collected_at',
               'feedback_json', 'strategy_json', 'metrics_json', 'funnel_json'}
    context = context or {}
    identifiers = set()
    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in private and isinstance(item, str) and len(item) >= 4:
                    identifiers.add(item)
                if key in private and isinstance(item, list):
                    identifiers.update(x for x in item if isinstance(x, str) and len(x) >= 4)
                collect(item)
        elif isinstance(value, list):
            for item in value: collect(item)
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (ValueError, TypeError):
                return
            if isinstance(parsed, (dict, list)): collect(parsed)
    collect(source)
    collect({k: context.get(k) for k in ('strategy', 'history', 'production_history', 'novelty_history')})
    def safe_text(value):
        if not isinstance(value, str): return None
        # Serialized metadata is not creative prose, including nested JSON strings.
        if any(re.search(r'\b' + re.escape(key) + r'\b', value) for key in private): return None
        if any(item in value for item in identifiers): return None
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return value
        return None if isinstance(parsed, (dict, list, str)) else value
    def text_fields(value, keys):
        if not isinstance(value, dict): return {}
        result = {}
        for key in keys:
            item = value.get(key)
            if isinstance(item, list):
                result[key] = [clean for x in item if (clean := safe_text(x)) is not None]
            elif (clean := safe_text(item)) is not None: result[key] = clean
        return result
    def numbers(value, keys):
        if not isinstance(value, dict): return {}
        return {k: value[k] for k in keys if type(value.get(k)) in (int, float)}
    metrics = source.get('metrics_snapshot') or {}
    evidence = metrics.get('learning_evidence') or {}
    metric_keys = ('views', 'impressions', 'likes', 'comments', 'shares', 'watch_time',
                   'clicks', 'average_view_duration', 'average_view_percentage')
    funnel = source.get('growth_funnel') or {}
    projected_funnel = {}
    for section, keys in [('traffic', ('landing_views',)), ('intent', ('total',)), ('conversion', ('total', 'value'))]:
        value = funnel.get(section) or {}
        projected_funnel[section] = numbers(value, keys)
        if section == 'intent' and isinstance(value.get('by_type'), dict):
            projected_funnel[section]['by_type'] = {k: v for k, v in value['by_type'].items()
                if safe_text(k) is not None and type(v) in (int, float)}
    strategy = source.get('strategy') or context.get('strategy') or {}
    projected_strategy = text_fields(strategy, ('objective', 'topic_direction', 'reasoning_summary'))
    if isinstance(strategy, str) and safe_text(strategy) is not None:
        projected_strategy['objective'] = strategy
    projected_strategy['parameters'] = text_fields(strategy.get('parameters') if isinstance(strategy, dict) else {}, ('strategy_type', 'recommendations', 'successful_patterns', 'weak_patterns'))
    window = evidence.get('window') or [metrics.get('period_start'), metrics.get('period_end')]
    return {
        **text_fields(source, ('platform',)),
        'window': [x for x in window if isinstance(x, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', x)],
        **numbers(evidence, ('sample_size',)),
        'metrics': [numbers(row, metric_keys) for row in evidence['metrics']] if isinstance(evidence.get('metrics'), list) else numbers(metrics, metric_keys),
        'growth_funnel': projected_funnel,
        'feedback': text_fields(source.get('feedback'), ('recommendations', 'successful_patterns', 'weak_patterns')),
        'strategy': projected_strategy,
        'reason_codes': text_fields(evidence, ('reason_codes',)).get('reason_codes', []),
        # Creative history remains useful, but its server-side linkage is not.
        'creative_history': {key: [text_fields(row, ('topic', 'hook', 'angle', 'visual_direction', 'video_terms'))
                                  for row in context.get(key, []) if isinstance(row, dict)]
                             for key in ('history', 'production_history', 'novelty_history')
                             if isinstance(context.get(key), list)},
    }


class ContentPlanGenerationError(ValueError):
    pass


class ContentPlanParseError(ContentPlanGenerationError):
    pass


class ContentPlanSchemaError(ContentPlanGenerationError):
    pass


_DANGEROUS_DIRECTIVE_TERMS = ("investment advice", "trading recommendation", "price prediction", "guaranteed returns", "guarantee returns", "guarantees returns", "seed phrase", "private key", "what coin will rise", "which token to buy", "recommend which token", "recommend which crypto token", "should buy")

_SAFE_NEGATION_MARKERS = ("do not", "don't", "never", "avoid", "without", "should not", "must not", "don't share", "never share", "never ask", "do not ask", "not proof", "not request")


def validate_safe_educational_crypto_text(text):
    """Fail closed on dangerous instructions while allowing local warnings/prohibitions."""
    value = str(text or "")
    lowered = value.lower()
    for term in _DANGEROUS_DIRECTIVE_TERMS:
        start = 0
        while True:
            index = lowered.find(term, start)
            if index < 0:
                break
            boundaries = [m.end() for m in re.finditer(r"[.!?;:,]\s*|(?:,?\s+)(?:but|however|yet|except|although|though)\b", lowered[:index])]
            clause_start = max(boundaries, default=0)
            prefix = lowered[clause_start:index]
            if not any(marker in prefix for marker in _SAFE_NEGATION_MARKERS):
                return False
            start = index + len(term)
    return True


def validate_human_directive_safety(human_brief="", human_constraints=None):
    """Reject positive unsafe instructions before any provider call."""
    constraints = dict(human_constraints or {})
    required_phrases = constraints.get("must_include", [])
    if (not isinstance(required_phrases, list) or
            any(not isinstance(item, str) or not _normalize_required_phrase_text(item)
                for item in required_phrases)):
        raise ContentPlanGenerationError("must_include must be a list of non-empty required phrases")
    lowered = str(human_brief or "").lower()
    for term in _DANGEROUS_DIRECTIVE_TERMS:
        index = 0
        while True:
            index = lowered.find(term, index)
            if index < 0: break
            prefix = lowered[max(0, index - 48):index]
            if not any(marker in prefix for marker in ("do not", "don't", "never", "avoid", "without")):
                raise ContentPlanGenerationError("unsafe human directive")
            index += len(term)
    for item in required_phrases:
        if any(term in str(item).lower() for term in _DANGEROUS_DIRECTIVE_TERMS): raise ContentPlanGenerationError("unsafe human directive")
    for key in ("topic", "angle", "target_audience", "cta_direction", "locked_topic", "locked_angle", "locked_target_audience", "locked_cta_direction"):
        if any(term in str(constraints.get(key) or "").lower() for term in _DANGEROUS_DIRECTIVE_TERMS): raise ContentPlanGenerationError("unsafe human directive")
    return True


def validate_generated_content_safety(data):
    text = " ".join(str(data.get(k, "")) for k in ("topic", "angle", "hook", "script", "cta", "title", "description")).lower()
    if not validate_safe_educational_crypto_text(text):
        raise ContentPlanGenerationError("unsafe content constraint")
    return True


def _normalize_required_phrase_text(value):
    """Normalize presentation only; must_include remains literal, not semantic."""
    text = unicodedata.normalize("NFC", str(value))
    text = text.translate(str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'",
                                         "\u201c": '"', "\u201d": '"'}))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def parse_content_plan_response(raw):
    if not isinstance(raw, str): raise ContentPlanParseError("AI response must be JSON text")
    value = raw.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"): raise ContentPlanParseError("invalid JSON code fence")
        value = "\n".join(lines[1:-1]).strip()
    try: data = json.loads(value)
    except (TypeError, ValueError) as exc: raise ContentPlanParseError("AI response is invalid JSON") from exc
    if not isinstance(data, dict): raise ContentPlanSchemaError("AI response must be a JSON object")
    required = ("topic", "angle", "target_audience", "hook", "script", "cta", "title", "description", "production_notes", "visual_direction", "reasoning_summary", "strategy_type")
    for name in required:
        if not isinstance(data.get(name), str) or not data[name].strip(): raise ContentPlanSchemaError(f"AI field {name} must be a non-empty string")
    if not isinstance(data.get("hashtags", []), list) or not all(isinstance(x, str) and x.strip() for x in data.get("hashtags", [])): raise ContentPlanSchemaError("AI hashtags must be a list of strings")
    return data


class LLMContentPlanProvider:
    supports_directed = True
    def __init__(self, text_provider=None):
        from ai.providers.text import TextProvider
        self.text_provider = text_provider or TextProvider()

    def readiness(self): return self.text_provider.readiness()

    def generate_content_plan(self, snapshot, context):
        context = dict(context or {}); brief = str(context.get("human_brief") or "").strip(); constraints = dict(context.get("human_constraints") or {})
        mode = "directed" if brief or constraints else "autonomous"
        validate_human_directive_safety(brief, constraints)
        model_snapshot = project_generation_snapshot(snapshot, context)
        prompt = build_content_brain_prompt(json.dumps(model_snapshot, ensure_ascii=False), "")
        prompt += "\nThese are observed measurements only. Zero measurements and absence of observed engagement are not causal evidence. Do not infer that the topic/category is inherently ineffective. The human brief remains the primary creative direction when provided."
        if mode == "directed": prompt += "\n\nHUMAN CREATIVE DIRECTIVE (HIGH PRIORITY)\nPreserve the user's intended topic, angle, audience and CTA direction. Expand rather than replace the idea. Obey must-avoid constraints. Every item in human_constraints.must_include is a required phrase. Each required phrase must appear explicitly, using its wording, in at least one generated topic, angle, hook, script, cta, title, or description field. A paraphrase alone does not satisfy a required phrase.\nHUMAN BRIEF:\n" + brief + "\nHUMAN CONSTRAINTS:\n" + json.dumps(constraints, ensure_ascii=False)
        prompt += "\n\nReturn exactly one valid JSON object with string fields topic, angle, target_audience, hook, script, cta, title, description, production_notes, visual_direction, reasoning_summary, strategy_type and hashtags as list[str]. No markdown or prose outside JSON."
        from ai.models import AIRequest
        response = self.text_provider.request(AIRequest(task_type="content_plan", model=getattr(self.text_provider, "model", "auto") or "auto", prompt=prompt))
        stage = "PROVIDER_RETURNED"
        failure_code = "DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR"
        try:
            output = response.get("output") if isinstance(response, dict) else getattr(response, "output", None)
            stage = "CONTENT_EXTRACTED"
            data = parse_content_plan_response(output)
            stage = "SCHEMA_VALIDATED"
            failure_code = "DIRECTED_GENERATION_SAFETY_REJECTED"
            validate_generated_content_safety(data)
            stage = "SAFETY_VALIDATED"
            failure_code = "DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR"
            locks = constraints.get("locked_fields", [])
            for key in ("topic", "angle", "target_audience"):
                if (key in locks or "locked_" + key in constraints) and constraints.get(key, constraints.get("locked_" + key)):
                    data[key] = constraints.get(key, constraints.get("locked_" + key))
            cta_lock = constraints.get("cta_direction") or constraints.get("locked_cta_direction")
            if cta_lock and ("cta_direction" in locks or "locked_cta_direction" in constraints):
                data["cta"] = cta_lock
            searched_fields = ("topic", "angle", "hook", "script", "cta", "title", "description")
            normalized_fields = tuple(_normalize_required_phrase_text(data.get(key, "")) for key in searched_fields)
            final_text = " ".join(str(data.get(k, "")) for k in searched_fields).lower()
            failure_code = "DIRECTED_GENERATION_MUST_INCLUDE_REJECTED"
            for index, required_item in enumerate(constraints.get("must_include", [])):
                phrase = _normalize_required_phrase_text(required_item)
                if not any(phrase in field for field in normalized_fields):
                    error = ContentPlanGenerationError("must_include constraint not satisfied")
                    error.forensic_requirement_index = index  # Zero-based, never the phrase text.
                    raise error
            failure_code = "DIRECTED_GENERATION_MUST_AVOID_REJECTED"
            for forbidden in constraints.get("must_avoid", []):
                if str(forbidden).lower() in final_text: raise ContentPlanGenerationError("must_avoid constraint violated")
            stage = "CONSTRAINTS_VALIDATED"
            failure_code = "DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR"
            data.update({"production_spec": {"provider": "github", "workflow": "render-short01.yml", "branch": "main"}, "content_id": context.get("content_id", "plan-preview"), "source_snapshot_id": snapshot.get("id") if isinstance(snapshot, dict) else None, "generation_mode": mode, "human_brief": brief, "human_constraints": constraints,
                         "generation_provider": "llm", "generation_evidence": {"source":"content_plan_provider", "schema_version":1, "provider": "llm", "provider_response_received": True, "json_parsed": True, "schema_validated": True, "safety_validated": True, "constraints_validated": True}})
            return validate_content_plan(ContentPlan(**data))
        except ValueError as exc:
            # Only fixed taxonomy values leave this function; exception text and
            # model output are never copied into directed-request metadata.
            exc.forensic_stage = "JSON_PARSED" if isinstance(exc, ContentPlanSchemaError) else stage
            exc.forensic_code = ("DIRECTED_GENERATION_PARSE_ERROR" if isinstance(exc, ContentPlanParseError)
                                 else "DIRECTED_GENERATION_SCHEMA_ERROR" if isinstance(exc, ContentPlanSchemaError)
                                 else failure_code)
            exc.forensic_provider_returned = True
            raise


def select_content_plan_provider():
    return LLMContentPlanProvider() if os.getenv("OS_CONTENT_PLAN_PROVIDER", "deterministic").strip().lower() == "llm" else DeterministicContentPlanProvider()


class DeterministicContentPlanProvider:
    def generate_content_plan(self, snapshot, context):
        topics=['Prepare a stablecoin invoice for a client','Payment instructions checklist','Confirm receiving platform support','Keep stablecoin payment records','Pending versus credited balance']
        topic=topics[int((snapshot or {}).get('id',0) or 0)%len(topics)]
        return ContentPlan(
            content_id="plan-preview",
            topic=topic,
            angle="payment verification before declaring work paid",
            target_audience="freelancers and remote workers",
            hook="A payment screenshot is not proof that your money arrived.",
            script="Open the account that actually receives the deposit, check balance and deposit history, then confirm the transaction is credited.",
            cta="Follow Remote Pay Guide for safer payment workflows.",
            title="How to Verify a Stablecoin Payment Arrived",
            description="A practical receiving-side check for freelancers.",
            hashtags=["#Stablecoin", "#Freelancer", "#RemoteWork"],
            reasoning_summary="Keep the receiving-side education signal while testing a verification step.",
            source_snapshot_id=snapshot.get("id") if isinstance(snapshot, dict) else None,
            strategy_type="iterate",
            novelty_status="preview",
            production_spec={"provider": "github", "workflow": "render-short01.yml", "branch": "main"},
            generation_provider="deterministic",
            generation_evidence={"source":"content_plan_provider", "schema_version":1, "provider": "deterministic", "content_plan_constructed": True, "canonical_validation_passed": True},
        )

EDITABLE_FIELDS={'hook','script','cta','title','description','visual_direction','production_notes'}
def _conn():
    c=sqlite3.connect(database_path()); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence_content_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_key TEXT UNIQUE, source_snapshot_id INTEGER, content_id TEXT, status TEXT, revision INTEGER DEFAULT 1, approved_revision INTEGER, payload_json TEXT, created_at TEXT, updated_at TEXT)'''); c.commit(); return c

def validate_content_plan(plan):
    for f in ('content_id','topic','hook','script','cta','title'):
        if not getattr(plan, f, '').strip(): raise ValueError(f'{f} is required')
    forbidden=('seed phrase','private key','trading recommendation','price prediction','investment advice')
    text=' '.join((plan.topic,plan.angle,plan.hook,plan.script,plan.cta,plan.title,plan.description,plan.visual_direction,plan.production_notes)).lower()
    if not validate_safe_educational_crypto_text(text): raise ValueError('unsafe content constraint')
    if not isinstance(plan.production_spec, dict): raise ValueError('production_spec must be a dict')
    return plan

def directed_creation_identity(request_id, snapshot_id, brief, constraints):
    """Snapshot-scoped UUID replay token; the server derives the content identity."""
    from uuid import UUID
    token = str(UUID(str(request_id)))
    identity = 'directed-' + hashlib.sha256((f'content-plan-directed-v1:{snapshot_id}:' + token).encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({'snapshot_id': snapshot_id, 'human_brief': brief,
        'human_constraints': constraints}, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()
    return identity, fingerprint


def get_directed_replay(identity, fingerprint):
    with closing(_conn()) as c:
        row = c.execute('SELECT * FROM intelligence_content_plans WHERE plan_key=?', ('directed-request:' + identity,)).fetchone()
    if not row:
        return None
    record = _row(row)
    if record['plan'].get('generation_evidence', {}).get('request_fingerprint') != fingerprint:
        raise ValueError('DIRECTED_REPLAY_CONFLICT')
    return record


def save_plan(plan, source_snapshot_id=None, *, directed_request=False):
    validate_content_plan(plan); payload=plan.to_dict(); key=f"{source_snapshot_id}:{plan.content_id}:{plan.hook}:{plan.title}"
    if directed_request:
        if not re.fullmatch(r'directed-[0-9a-f]{64}', plan.content_id) or not plan.generation_evidence.get('request_fingerprint'):
            raise ValueError('DIRECTED_IDENTITY_REQUIRED')
        key = 'directed-request:' + plan.content_id
    with closing(_conn()) as c:
        c.execute('BEGIN IMMEDIATE')
        if directed_request:
            source = c.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                               (source_snapshot_id,)).fetchone()
            if source is None:
                raise ValueError('STRICT_SNAPSHOT_REQUIRED')
            intent = json.loads(source[0] or '{}').get(plan.content_id)
            if not isinstance(intent, dict) or intent.get('fingerprint') != plan.generation_evidence['request_fingerprint']:
                raise ValueError('DIRECTED_INTENT_MISSING_OR_CONFLICT')
            if intent.get('state', 'UNRESOLVED_UNKNOWN') != 'UNRESOLVED_UNKNOWN':
                raise ValueError('DIRECTED_RECONCILIATION_STATE_CONFLICT')
        row=c.execute('SELECT * FROM intelligence_content_plans WHERE plan_key=?',(key,)).fetchone()
        if row:
            record = _row(row)
            if directed_request and record['plan'].get('generation_evidence', {}).get('request_fingerprint') != plan.generation_evidence['request_fingerprint']:
                raise ValueError('DIRECTED_REPLAY_CONFLICT')
            return record
        cur=c.execute('INSERT INTO intelligence_content_plans(plan_key,source_snapshot_id,content_id,status,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(key,source_snapshot_id,plan.content_id,'preview',json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat())); c.commit(); return _row(c.execute('SELECT * FROM intelligence_content_plans WHERE id=?',(cur.lastrowid,)).fetchone())

def _row(row):
    d=dict(row); d['plan']=json.loads(d.pop('payload_json')); return d
def get_plan(plan_id):
    with _conn() as c:
        row=c.execute('SELECT * FROM intelligence_content_plans WHERE id=?',(plan_id,)).fetchone()
        return _row(row) if row else None
def list_plans():
    with _conn() as c: return [_row(r) for r in c.execute('SELECT * FROM intelligence_content_plans ORDER BY id DESC').fetchall()]
def update_plan(plan_id, changes):
    row=get_plan(plan_id)
    if not row: raise KeyError('plan not found')
    illegal=set(changes)-EDITABLE_FIELDS
    if illegal: raise ValueError('fields not editable: '+','.join(sorted(illegal)))
    p=ContentPlan(**{**row['plan'], **changes}); validate_content_plan(p)
    p.novelty_status='unverified'; p.novelty_evidence={}
    # Preserve provenance, but explicitly mark the current revision as human
    # authored so an older model assurance cannot be reused as current proof.
    evidence = dict(p.generation_evidence or {})
    evidence['current_revision_origin'] = 'human_edit'
    evidence['canonical_validation_passed'] = True
    p.generation_evidence = evidence
    with _conn() as c: c.execute('UPDATE intelligence_content_plans SET payload_json=?,revision=revision+1,status=\'preview\',approved_revision=NULL,updated_at=? WHERE id=?',(json.dumps(p.to_dict(),ensure_ascii=False),datetime.now(timezone.utc).isoformat(),plan_id)); c.commit()
    return get_plan(plan_id)
def set_plan_status(plan_id,status,expected_revision=None):
    row=get_plan(plan_id)
    if not row: raise KeyError('plan not found')
    if expected_revision is not None and row['revision'] != expected_revision: raise ValueError('revision status conflict')
    allowed={'preview':{'approved','superseded'},'approved':{'materialized','superseded'},'materialized':set(),'superseded':set()}
    if status not in allowed.get(row['status'],set()): raise ValueError('invalid plan status transition')
    with _conn() as c:
        if status=='approved': cur=c.execute('UPDATE intelligence_content_plans SET status=?,approved_revision=revision,updated_at=? WHERE id=? AND status=? AND revision=?',(status,datetime.now(timezone.utc).isoformat(),plan_id,row['status'],row['revision']))
        else: cur=c.execute('UPDATE intelligence_content_plans SET status=?,updated_at=? WHERE id=? AND status=? AND revision=?',(status,datetime.now(timezone.utc).isoformat(),plan_id,row['status'],row['revision']))
        c.commit()
        if cur.rowcount != 1: raise ValueError('concurrent plan status conflict')
    return get_plan(plan_id)
