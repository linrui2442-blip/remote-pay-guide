# Remote Pay Guide — Project Status

## Current State

Remote Pay Guide OS is in active OS development and runtime validation.

The current repository is the source code baseline.

Runtime data is handled separately.

## Runtime Data Boundary

Active runtime database:

```text
os/database/os.db
```

Important:

- Git updates source code.
- Runtime database preserves local OS state.
- A fresh repository checkout does not contain previous runtime state.
- Do not replace the runtime database with an empty database during updates.

See:

```text
docs/RUNTIME_DATA_POLICY.md
```

## Current Principle

Code changes:

```
Git repository
```

Runtime state:

```
os/database/os.db
```

They are separate lifecycle objects.

## Historical Compatibility

Existing production, publish, OAuth, analytics and data capabilities must be extended from the current implementation.

Do not recreate completed systems from old phase documents.

## Verified Runtime Milestone

YouTube Analytics Real 7D E2E：**FULL E2E VERIFIED**（YouTube account 1，2026-08-31 → 2026-09-06，America/Los_Angeles）。结果为 50 个真实每日 snapshots 与 20 个 no-data observations；Query V2 与 Data Center gap semantics 已真实验证。Scheduled Daily Analytics Sync 仍为 code/test complete，真实无人值守 E2E 尚未完成。

CURRENT NEXT STEP：Scheduled Daily Analytics Sync — Real Unattended E2E Validation。该阶段尚未执行。
