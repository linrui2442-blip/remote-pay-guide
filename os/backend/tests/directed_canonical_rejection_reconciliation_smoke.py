"""Offline canonical-output rejection reconciliation and duplicate-risk contract."""
from test_database_helper import TEST_DATABASE_PATH

import io
import json
import socket
import sqlite3
import sys
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin import reconcile_directed_request as cli
from intelligence import directed_reconciliation as service
from intelligence.content_brain import directed_creation_identity
from intelligence.feedback_bridge import get_directed_request_status, record_directed_generation_intent


REASON = 'CANONICAL_GENERATED_OUTPUT_REJECTED'
PAIRS = (
    ('DIRECTED_GENERATION_PARSE_ERROR', 'CONTENT_EXTRACTED'),
    ('DIRECTED_GENERATION_SCHEMA_ERROR', 'JSON_PARSED'),
    ('DIRECTED_GENERATION_SAFETY_REJECTED', 'SCHEMA_VALIDATED'),
    ('DIRECTED_GENERATION_MUST_INCLUDE_REJECTED', 'SAFETY_VALIDATED'),
    ('DIRECTED_GENERATION_MUST_AVOID_REJECTED', 'SAFETY_VALIDATED'),
    ('DIRECTED_GENERATION_CONTENT_PLAN_VALIDATION_ERROR', 'CONSTRAINTS_VALIDATED'),
)


def denied(fn, code):
    try:
        fn()
    except (ValueError, PermissionError) as exc:
        assert code in str(exc), (code, exc)
    else:
        raise AssertionError('expected ' + code)


def read_intents():
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        return json.loads(conn.execute('SELECT directed_requests_json FROM intelligence_feedback_snapshots WHERE id=11').fetchone()[0])


def write_record(identity, transform):
    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        intents = read_intents()
        transform(intents[identity])
        conn.execute('UPDATE intelligence_feedback_snapshots SET directed_requests_json=? WHERE id=11', (json.dumps(intents),))


def fixture(code='DIRECTED_GENERATION_MUST_INCLUDE_REJECTED', stage='SAFETY_VALIDATED', **changes):
    token = uuid.uuid4()
    identity, _ = directed_creation_identity(token, 11, 'Offline brief', {})
    # A prior terminal sibling can require acknowledgement; this fixture never calls a provider.
    record_directed_generation_intent(11, identity, str(token), duplicate_risk_ack=True)
    observation = {'provider_returned_at': '2026-10-03T00:00:00+00:00',
                   'last_stage': stage, 'failure_code': code,
                   'failure_at': '2026-10-03T00:00:01+00:00'}
    def fill(record):
        record['generation_observation'] = observation
        for name, value in changes.items():
            if name.startswith('observation_'):
                name = name.removeprefix('observation_')
                if value is None: observation.pop(name, None)
                else: observation[name] = value
            elif value is None: record.pop(name, None)
            else: record[name] = value
    write_record(identity, fill)
    return str(token), identity


def reconcile(token, *, evidence='incident:offline-evidence', target='CONFIRMED_FAILED', reason=REASON):
    return service.reconcile_directed_request(11, token, expected_state='UNRESOLVED_UNKNOWN',
        target_state=target, reason_code=reason, evidence_reference=evidence)


def release_fixture(identity):
    """Only in this isolated DB: finish a denied fixture so another may claim."""
    write_record(identity, lambda r: r.update({'state': 'CONFIRMED_FAILED',
        'reconciliation': {'reason_code': 'UPSTREAM_CONFIRMED_NOT_EXECUTED'}}))


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        with sqlite3.connect(TEST_DATABASE_PATH) as conn:
            conn.execute('CREATE TABLE intelligence_feedback_snapshots(id INTEGER PRIMARY KEY, directed_requests_json TEXT)')
            conn.execute('CREATE TABLE intelligence_content_plans(id INTEGER PRIMARY KEY, plan_key TEXT UNIQUE)')
            conn.execute('INSERT INTO intelligence_feedback_snapshots VALUES(11, ?)', ('{}',))

        token, identity = fixture()
        denied(lambda: reconcile(token), 'ALLOWLIST')
        release_fixture(identity)
        with patch.object(service, 'authorize_directed_reconciliation', return_value='offline-actor'):
            for code, stage in PAIRS:
                token, identity = fixture(code, stage)
                result = reconcile(token)
                assert result['effective_state'] == 'CONFIRMED_FAILED' and not result['replayed']
                status = get_directed_request_status(11, identity)
                assert status['requires_duplicate_risk_ack'] and status['can_create_new_request']
                assert reconcile(token)['replayed']
                denied(lambda: reconcile(token, evidence='incident:changed'), 'STATE_CONFLICT')
                print(code + '=PASS')
            print('OPERATOR_AUTH_AND_IDEMPOTENCY=PASS')

            for code, stage in PAIRS:
                token, identity = fixture(code, 'JSON_PARSED' if stage != 'JSON_PARSED' else 'SAFETY_VALIDATED')
                denied(lambda: reconcile(token), 'EVIDENCE_REQUIRED')
                release_fixture(identity)
            print('CODE_STAGE_MISMATCH_REJECTED=PASS')

            for code, stage in (('DIRECTED_GENERATION_UNKNOWN_VALIDATION_ERROR', 'SAFETY_VALIDATED'),
                                ('HTTP_502', 'PROVIDER_RETURNED'), ('TIMEOUT', 'PROVIDER_RETURNED')):
                token, identity = fixture(code, stage)
                denied(lambda: reconcile(token), 'EVIDENCE_REQUIRED')
                release_fixture(identity)
            print('UNKNOWN_HTTP_502_TIMEOUT_REJECTED=PASS')

            for missing in ('provider_attempt_claimed_at', 'generation_observation',
                            'observation_provider_returned_at', 'observation_failure_at',
                            'observation_failure_code', 'observation_last_stage'):
                token, identity = fixture(**{missing: None})
                denied(lambda: reconcile(token, evidence='provider:looks-convincing'), 'EVIDENCE_REQUIRED')
                release_fixture(identity)
            print('REQUIRED_PERSISTED_EVIDENCE=PASS')
            print('EVIDENCE_REFERENCE_CANNOT_BYPASS=PASS')

            token, identity = fixture()
            with sqlite3.connect(TEST_DATABASE_PATH) as conn:
                conn.execute('INSERT INTO intelligence_content_plans(plan_key) VALUES(?)', ('directed-request:' + identity,))
            assert get_directed_request_status(11, identity)['effective_state'] == 'COMPLETED'
            denied(lambda: reconcile(token), 'CANONICAL_PLAN_ALREADY_EXISTS')
            print('PLAN_EXISTS_REJECTED=PASS')

            for state, reason in (('CLOSED_UNKNOWN', 'OUTCOME_EVIDENCE_UNAVAILABLE'),
                                  ('CONFIRMED_FAILED', 'UPSTREAM_CONFIRMED_NOT_EXECUTED')):
                token, identity = fixture()
                write_record(identity, lambda r: r.update({'state': state,
                    'reconciliation': {'reason_code': reason, 'actor_id': 'offline-actor'}}))
                denied(lambda: reconcile(token), 'STATE_CONFLICT')
                assert get_directed_request_status(11, identity)['requires_duplicate_risk_ack'] == (state == 'CLOSED_UNKNOWN')
            print('TERMINAL_STATES_REJECTED=PASS')
            print('OTHER_CONFIRMED_FAILED_NOT_BLANKET_ACK=PASS')
            print('CLOSED_UNKNOWN_DUPLICATE_ACK=PASS')

            token, identity = fixture()
            reconcile(token)
            sibling = uuid.uuid4()
            sibling_identity, _ = directed_creation_identity(sibling, 11, 'Sibling', {})
            denied(lambda: record_directed_generation_intent(11, sibling_identity, 'sibling'), 'RISK_ACK_REQUIRED')
            assert sibling_identity not in read_intents()
            record_directed_generation_intent(11, sibling_identity, 'sibling', duplicate_risk_ack=True)
            assert sibling_identity in read_intents()
            release_fixture(sibling_identity)
            print('CANONICAL_REJECTION_SIBLING_ACK=PASS')

            for old_reason in ('PROVIDER_CONFIRMED_NO_RESULT', 'PRE_GENERATION_REJECTION_CONFIRMED',
                               'UPSTREAM_CONFIRMED_NOT_EXECUTED'):
                token, identity = fixture()
                assert reconcile(token, reason=old_reason)['effective_state'] == 'CONFIRMED_FAILED'
                assert not get_directed_request_status(11, identity)['requires_duplicate_risk_ack']
            token, identity = fixture()
            closed = service.reconcile_directed_request(11, token,
                expected_state='UNRESOLVED_UNKNOWN', target_state='CLOSED_UNKNOWN',
                reason_code='OUTCOME_EVIDENCE_UNAVAILABLE', evidence_reference='audit:offline-proof',
                duplicate_risk_ack=True)
            assert closed['effective_state'] == 'CLOSED_UNKNOWN'
            assert get_directed_request_status(11, identity)['requires_duplicate_risk_ack']
            print('ALL_OLD_REASONS_UNCHANGED=PASS')

            token, identity = fixture()
            with patch.object(cli, 'authorize_directed_reconciliation', return_value='offline-actor'):
                output = io.StringIO()
                with redirect_stdout(output):
                    assert cli.main(['11', token, 'CONFIRMED_FAILED', REASON, 'incident:offline-proof'],
                                    confirm=lambda _: '') == 1
                warning = output.getvalue()
                assert all(fragment in warning for fragment in ('provider returned a response',
                    'canonical generation validation rejected the output', 'No canonical ContentPlan was persisted',
                    'does not mean the provider failed to execute or returned no result',
                    'duplicate provider cost or content generation effort', 'DECLINED'))
                assert get_directed_request_status(11, identity)['effective_state'] == 'UNRESOLVED_UNKNOWN'
            print('CLI_REASON_AWARE_DEFAULT_DENY=PASS')
        print('NETWORK_TRIPWIRE=PASS')


if __name__ == '__main__':
    main()
