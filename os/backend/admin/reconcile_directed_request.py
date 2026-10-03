"""Explicit local-only administrator entry point; never an HTTP endpoint."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.directed_operator import authorize_directed_reconciliation
from intelligence.directed_reconciliation import (
    FAILED_REASONS, CLOSED_REASONS, _EVIDENCE_REF, _SENSITIVE_REF,
    inspect_directed_reconciliation, reconcile_directed_request,
)


def main(argv=None, *, confirm=input):
    parser = argparse.ArgumentParser(description='Reconcile one directed unknown intent')
    parser.add_argument('snapshot_id', type=int)
    parser.add_argument('request_id')
    parser.add_argument('target_state', choices=('CONFIRMED_FAILED', 'CLOSED_UNKNOWN'))
    parser.add_argument('reason_code')
    parser.add_argument('evidence_reference')
    parser.add_argument('--duplicate-risk-ack', action='store_true')
    args = parser.parse_args(argv)
    authorize_directed_reconciliation()
    allowed = FAILED_REASONS if args.target_state == 'CONFIRMED_FAILED' else CLOSED_REASONS
    if (args.reason_code not in allowed or not _EVIDENCE_REF.fullmatch(args.evidence_reference)
            or _SENSITIVE_REF.search(args.evidence_reference)):
        raise ValueError('DIRECTED_REASON_OR_EVIDENCE_INVALID')
    summary = inspect_directed_reconciliation(args.snapshot_id, args.request_id)
    print('snapshot_id=' + str(args.snapshot_id))
    print('request_id=' + args.request_id)
    print('current_state=' + summary['effective_state'])
    print('target_state=' + args.target_state)
    print('reason_code=' + args.reason_code)
    print('evidence_reference=' + args.evidence_reference)
    if args.reason_code == 'CANONICAL_GENERATED_OUTPUT_REJECTED':
        print('The provider returned a response; canonical generation validation rejected the output.')
        print('No canonical ContentPlan was persisted. This does not mean the provider failed to execute or returned no result.')
        print('A future new request may duplicate provider cost or content generation effort.')
    elif args.target_state == 'CONFIRMED_FAILED':
        print('This action asserts external evidence proves the original provider attempt produced no usable result.')
    else:
        print('The original provider outcome remains unknown.')
        print('Closing this request does not prove the original generation failed.')
        print('A future new request may duplicate content or cost.')
    if confirm('Type RECONCILE to confirm [default No]: ').strip() != 'RECONCILE':
        print('DECLINED')
        return 1
    result = reconcile_directed_request(args.snapshot_id, args.request_id,
        expected_state='UNRESOLVED_UNKNOWN', target_state=args.target_state,
        reason_code=args.reason_code, evidence_reference=args.evidence_reference,
        duplicate_risk_ack=args.duplicate_risk_ack)
    print('effective_state=' + result['effective_state'])
    print('replayed=' + str(result['replayed']).lower())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, PermissionError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
