"""Canonical, fail-closed local reconciliation of a directed generation intent."""

import json
import re
from datetime import datetime, timezone

from config.directed_operator import authorize_directed_reconciliation
from intelligence.content_brain import directed_creation_identity
from intelligence.feedback_bridge import _connect, _directed_plan_exists, _json, effective_directed_request_state


FAILED_REASONS = frozenset({'PROVIDER_CONFIRMED_NO_RESULT', 'PRE_GENERATION_REJECTION_CONFIRMED',
                            'UPSTREAM_CONFIRMED_NOT_EXECUTED', 'CANONICAL_GENERATED_OUTPUT_REJECTED'})
CLOSED_REASONS = frozenset({'OUTCOME_EVIDENCE_UNAVAILABLE'})
# The provider returned, but canonical validation rejected its generated output
# before a ContentPlan was persisted. This does not assert an upstream failure.
_CANONICAL_REJECTION_PAIRS = frozenset({
    ('DIRECTED_GENERATION_PARSE_ERROR', 'CONTENT_EXTRACTED'),
    ('DIRECTED_GENERATION_SCHEMA_ERROR', 'JSON_PARSED'),
    ('DIRECTED_GENERATION_SAFETY_REJECTED', 'SCHEMA_VALIDATED'),
    ('DIRECTED_GENERATION_MUST_INCLUDE_REJECTED', 'SAFETY_VALIDATED'),
    ('DIRECTED_GENERATION_MUST_AVOID_REJECTED', 'SAFETY_VALIDATED'),
    ('DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR', 'CONSTRAINTS_VALIDATED'),
})


def _is_canonical_generated_output_rejection_evidence(record):
    """Use only persisted server-owned evidence; never operator-supplied text."""
    if not isinstance(record, dict) or not record.get('provider_attempt_claimed_at'):
        return False
    observation = record.get('generation_observation')
    return (isinstance(observation, dict)
            and bool(observation.get('provider_returned_at'))
            and bool(observation.get('failure_at'))
            and (observation.get('failure_code'), observation.get('last_stage')) in _CANONICAL_REJECTION_PAIRS)
_EVIDENCE_REF = re.compile(r'(?:provider|audit|incident):[A-Za-z0-9._#-]{4,120}\Z')
_SENSITIVE_REF = re.compile(r'authorization|bearer|token|secret|credential|api.?key', re.IGNORECASE)


def _identity(snapshot_id, request_id):
    # The existing identity function also validates the UUID. Its fingerprint
    # output is irrelevant here: the original fingerprint remains immutable.
    return directed_creation_identity(request_id, snapshot_id, '', {})[0]


def inspect_directed_reconciliation(snapshot_id, request_id):
    """Read-only, secret-free summary used before an interactive CLI decision."""
    identity = _identity(snapshot_id, request_id)
    with _connect() as conn:
        row = conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                           (snapshot_id,)).fetchone()
        if row is None:
            raise ValueError('STRICT_SNAPSHOT_REQUIRED')
        record = json.loads(row[0] or '{}').get(identity)
        if not isinstance(record, dict) or not record.get('fingerprint') or not record.get('created_at'):
            raise ValueError('DIRECTED_REQUEST_NOT_FOUND_OR_CORRUPT')
        state = effective_directed_request_state(conn, identity, record)
        return {'snapshot_id': snapshot_id, 'request_id': str(request_id), 'effective_state': state,
                'state_conflict': state == 'COMPLETED' and record.get('state') in ('CONFIRMED_FAILED', 'CLOSED_UNKNOWN')}


def reconcile_directed_request(snapshot_id, request_id, *, expected_state, target_state,
                               reason_code, evidence_reference, duplicate_risk_ack=False):
    """One transaction, one actor, one immutable terminal transition."""
    actor_id = authorize_directed_reconciliation()
    if expected_state != 'UNRESOLVED_UNKNOWN':
        raise ValueError('DIRECTED_EXPECTED_STATE_INVALID')
    allowed = FAILED_REASONS if target_state == 'CONFIRMED_FAILED' else CLOSED_REASONS if target_state == 'CLOSED_UNKNOWN' else None
    if allowed is None:
        raise ValueError('DIRECTED_TARGET_STATE_INVALID')
    if reason_code not in allowed:
        raise ValueError('DIRECTED_REASON_CODE_INVALID')
    if (not isinstance(evidence_reference, str) or not _EVIDENCE_REF.fullmatch(evidence_reference)
            or _SENSITIVE_REF.search(evidence_reference)):
        raise ValueError('DIRECTED_EVIDENCE_REFERENCE_INVALID')
    if target_state == 'CLOSED_UNKNOWN' and duplicate_risk_ack is not True:
        raise ValueError('DIRECTED_DUPLICATE_RISK_ACK_REQUIRED')
    if target_state == 'CONFIRMED_FAILED' and duplicate_risk_ack:
        raise ValueError('DIRECTED_DUPLICATE_RISK_ACK_UNEXPECTED')
    identity = _identity(snapshot_id, request_id)
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=?',
                           (snapshot_id,)).fetchone()
        if row is None:
            raise ValueError('STRICT_SNAPSHOT_REQUIRED')
        intents = json.loads(row[0] or '{}')
        record = intents.get(identity)
        if not isinstance(record, dict) or not record.get('fingerprint') or not record.get('created_at'):
            raise ValueError('DIRECTED_REQUEST_NOT_FOUND_OR_CORRUPT')
        state = effective_directed_request_state(conn, identity, record)
        if state == 'COMPLETED' or _directed_plan_exists(conn, identity):
            raise ValueError('DIRECTED_CANONICAL_PLAN_ALREADY_EXISTS')
        reconciliation = record.get('reconciliation')
        if state == target_state and isinstance(reconciliation, dict):
            same = (reconciliation.get('actor_id') == actor_id
                    and reconciliation.get('reason_code') == reason_code
                    and reconciliation.get('evidence_reference') == evidence_reference)
            if same:
                return {'effective_state': state, 'replayed': True, 'actor_id': actor_id}
        if state != expected_state:
            raise ValueError('DIRECTED_RECONCILIATION_STATE_CONFLICT')
        if reconciliation is not None:
            raise ValueError('DIRECTED_RECONCILIATION_STATE_CONFLICT')
        if reason_code == 'CANONICAL_GENERATED_OUTPUT_REJECTED' and not _is_canonical_generated_output_rejection_evidence(record):
            raise ValueError('DIRECTED_CANONICAL_REJECTION_EVIDENCE_REQUIRED')
        record['state'] = target_state
        record['reconciliation'] = {'at': datetime.now(timezone.utc).isoformat(), 'actor_id': actor_id,
                                    'reason_code': reason_code, 'evidence_reference': evidence_reference}
        conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=?',
                     (_json(intents), snapshot_id))
    return {'effective_state': target_state, 'replayed': False, 'actor_id': actor_id}
