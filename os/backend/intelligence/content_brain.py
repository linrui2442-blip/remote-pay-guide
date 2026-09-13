from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Protocol
import json, sqlite3
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

    def to_dict(self):
        return asdict(self)


def build_content_brain_prompt(snapshot, strategy, history=None, production_history=None, novelty_history=None):
    return """You are the Remote Pay Guide content planner. Audience: freelancer, remote worker, digital nomad, overseas service provider, and first-time stablecoin payment receiver. Funnel: Short video -> Profile/Bio -> Remote Pay Guide -> stablecoin payment education -> Binance referral click. Never give investment advice, price prediction, trading recommendations, seed phrase/private key requests, or unsafe crypto instructions. Preserve effective variables, test a limited explicit variable, and explain preserved_variable, tested_variable, and why. Do not copy recent topics, hooks, angles, or visual plans.\n\nDATA CENTER SNAPSHOT:\n{snapshot}\nSTRATEGY:\n{strategy}\nRECENT CONTENT:\n{history}\nRECENT PRODUCTION:\n{production_history}\nRECENT NOVELTY:\n{novelty_history}""".format(snapshot=snapshot, strategy=strategy, history=history or [], production_history=production_history or [], novelty_history=novelty_history or [])


class ContentPlanProvider(Protocol):
    def generate_content_plan(self, snapshot, context) -> ContentPlan: ...


class DeterministicContentPlanProvider:
    def generate_content_plan(self, snapshot, context):
        return ContentPlan(
            content_id="plan-preview",
            topic="Verify a stablecoin payment arrived",
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
        )

def _conn():
    c=sqlite3.connect(database_path()); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS intelligence_content_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_key TEXT UNIQUE, source_snapshot_id INTEGER, content_id TEXT, status TEXT, payload_json TEXT, created_at TEXT, updated_at TEXT)'''); c.commit(); return c

def validate_content_plan(plan):
    for f in ('content_id','topic','hook','script','cta','title'):
        if not getattr(plan, f, '').strip(): raise ValueError(f'{f} is required')
    forbidden=('seed phrase','private key','trading recommendation','price prediction')
    text=' '.join((plan.hook,plan.script,plan.cta,plan.description)).lower()
    if any(x in text for x in forbidden): raise ValueError('unsafe content constraint')
    if not isinstance(plan.production_spec, dict): raise ValueError('production_spec must be a dict')
    return plan

def save_plan(plan, source_snapshot_id=None):
    validate_content_plan(plan); payload=plan.to_dict(); key=f"{source_snapshot_id}:{plan.content_id}:{plan.hook}:{plan.title}"
    with _conn() as c:
        row=c.execute('SELECT * FROM intelligence_content_plans WHERE plan_key=?',(key,)).fetchone()
        if row: return _row(row)
        cur=c.execute('INSERT INTO intelligence_content_plans(plan_key,source_snapshot_id,content_id,status,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(key,source_snapshot_id,plan.content_id,'preview',json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),datetime.now(timezone.utc).isoformat())); c.commit(); return _row(c.execute('SELECT * FROM intelligence_content_plans WHERE id=?',(cur.lastrowid,)).fetchone())

def _row(row):
    d=dict(row); d['plan']=json.loads(d.pop('payload_json')); return d
def get_plan(plan_id):
    with _conn() as c: return _row(c.execute('SELECT * FROM intelligence_content_plans WHERE id=?',(plan_id,)).fetchone())
def list_plans():
    with _conn() as c: return [_row(r) for r in c.execute('SELECT * FROM intelligence_content_plans ORDER BY id DESC').fetchall()]
def update_plan(plan_id, changes):
    row=get_plan(plan_id); p=ContentPlan(**{**row['plan'], **changes}); validate_content_plan(p)
    with _conn() as c: c.execute('UPDATE intelligence_content_plans SET payload_json=?,updated_at=? WHERE id=?',(json.dumps(p.to_dict(),ensure_ascii=False),datetime.now(timezone.utc).isoformat(),plan_id)); c.commit()
    return get_plan(plan_id)
def set_plan_status(plan_id,status):
    if status not in ('approved','materialized','superseded'): raise ValueError('invalid plan status')
    with _conn() as c: c.execute('UPDATE intelligence_content_plans SET status=?,updated_at=? WHERE id=?',(status,datetime.now(timezone.utc).isoformat(),plan_id)); c.commit()
    return get_plan(plan_id)
