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
