# V1 Release Acceptance

## Canonical status

```text
V1_SCOPE_DECISION=RESTORE_PRE_FREEZE_V1_SCOPE
FEATURE_DEVELOPMENT=REOPENED_FOR_PRE_FREEZE_V1_COMPLETION
V1_CODE_STATUS=ACTIVE_RELEASE_COMPLETION
V1_RELEASE_PHASE=PRE_RELEASE_INTEGRATION
V1_LIVE_ACCEPTANCE=INCOMPLETE
V1_RELEASE_STATUS=NOT_CLOSED
EXECUTABLE_BASELINE_SHA=af265df7403983107c1b141839a66c5def1359d9
```

Commit `285c51cdf5d94847a9b3d884792523fe57a50cc5` introduced an
explicit V1 scope contraction which has now been superseded by a later explicit
scope decision. It remains valid historical documentation evidence and is not
reverted. This checklist restores the immediately pre-freeze canonical V1
Definition of Done; it does not promote every historical blueprint idea into a
V1 requirement.

## Preserved proofs

```text
G4_A=IMPLEMENTATION_COMPLETE
G4_B_GITHUB=LIVE_PROVEN
G4_D=LIVE_PROVEN
G5_AUTONOMOUS_IMPLEMENTATION=IMPLEMENTATION_COMPLETE
G5_YOUTUBE_PUBLIC=LIVE_PROVEN
G6_REAL_FEEDBACK=LIVE_PROVEN
G7_OFFLINE=IMPLEMENTATION_COMPLETE
G8_ACCELERATED_OFFLINE_HARNESS=IMPLEMENTATION_COMPLETE
G9_OFFLINE_HARDENING=IMPLEMENTATION_COMPLETE
```

Implementation completion and offline certification do not by themselves
satisfy a live V1 release gate.

## Required V1 gates

| Gate | Implementation | Live state | V1 requirement |
| --- | --- | --- | --- |
| G4-C real AI production | `IMPLEMENTATION_COMPLETE`; offline proven | `EXTERNAL_CONFIGURATION_BLOCKED` | `LIVE_PROOF_REQUIRED` |
| Instagram official publish | `IMPLEMENTATION_COMPLETE`; offline proven | `EXTERNAL_CONFIGURATION_BLOCKED` | `LIVE_PROOF_REQUIRED` |
| Facebook official publish | `IMPLEMENTATION_COMPLETE`; offline proven | `EXTERNAL_CONFIGURATION_BLOCKED` | `LIVE_PROOF_REQUIRED` |
| YouTube + Instagram + Facebook closeout | YouTube proven; adapters implemented | `LIVE_PARTIAL` | `LIVE_PROOF_REQUIRED` |
| Autonomous AUTO E2E | canonical stages implemented/offline proven | `NOT_RUN` | `LIVE_PROOF_REQUIRED` |
| Real elapsed-time soak >=72h | accelerated harness passed | `NOT_RUN` | `REQUIRED_V1_RELEASE_GATE` |
| Fresh-machine/release validation | offline hardening prepared | `NOT_RUN` | `REQUIRED` |

The multi-platform proof requires official adapters, real platform credentials,
one bounded real write per platform, durable canonical evidence, duplicate-write
protection and readback/reconciliation where the provider supports it. Postiz
remains legacy/compatibility only.

## Autonomous acceptance chain

The required real autonomous proof is:

```text
real persisted mature analytics
→ G6
→ real GPT ContentPlan
→ raw G3 AUTO
→ G4 route and production
→ ProductionResult
→ G4-D PASS
→ VideoAsset
→ G5 AUTO
→ publishing
→ official/readable platform evidence
→ attribution
→ feedback state
→ safe control restoration
```

YouTube may be the first full autonomous public proof, but it does not replace
the required Instagram/Facebook live proofs or multi-platform closeout. A valid
raw G3 `REVIEW` or `BLOCK` remains correct policy behavior and must not be
overridden by prompt or threshold tuning merely to manufacture AUTO.

## Real soak and release validation

`G8_REAL_72H_SOAK=NOT_RUN`. The real soak begins only after required live
integration paths are sufficiently ready for meaningful observation. The
accelerated harness is offline evidence, not an elapsed-time substitute.

Fresh-machine/release validation must cover documented setup and startup,
dependency verification, canonical backend startup, production-DB boundary,
required configuration readiness, health/read-only operational checks, absence
of hidden development-machine dependencies and documentation consistency.

## Attribution boundary

Qualified intent/referral attribution is live proven. Trusted exchange
registration/revenue conversion remains provider-dependent and deferred;
referral click and `new_to_exchange_identified` are not conversions. This is
not silently added as a V1 blocker.

## Snapshot 34 terminal evidence

Snapshot 34 remains terminal historical evidence:

```text
CAN_RECOVER_AGAIN=false
CLASSIFICATION=OPERATIONAL_PROVIDER_FAILURE_AFTER_LOCAL_DEFECT_WAS_FIXED
```

It must never be retried and is not reopened by this scope decision.

## Exact execution order

1. **G4-C live proof:** configure only the required AI-video endpoint/key, run
   one bounded proof, then run G4-D on that result.
2. **Instagram live proof:** resolve Meta credential/binding and run one bounded
   official-adapter proof.
3. **Facebook live proof:** resolve Meta developer/account/token/binding and run
   one bounded official-adapter proof.
4. **Multi-platform closeout:** confirm independent YouTube, Instagram and
   Facebook canonical live proofs.
5. **Autonomous E2E:** use a fresh mature real G6 opportunity, require natural
   raw G3 AUTO, then run the canonical autonomous G4→G5 chain.
6. **Real 72-hour soak:** perform elapsed-time operational observation.
7. **Fresh-machine/release validation:** finish release hardening.
8. **V1 close:** only then set `V1_RELEASE_STATUS=CLOSED` and recommend
   `remote-pay-guide-v1.0.0`.

## Development boundary

Allowed work is limited to configuration/integration required by this existing
V1 contract, bounded release-blocker fixes found by real proofs, and release
validation/hardening. New product features, new platforms, dashboard redesign,
new architecture, gratuitous prompt/novelty changes and new provider families
are outside scope unless strictly required to make the existing G4-C contract
operational.
