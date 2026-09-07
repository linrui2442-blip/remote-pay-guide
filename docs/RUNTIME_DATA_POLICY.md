# Runtime Data Policy

## Purpose

This document defines the boundary between source code and runtime data for Remote Pay Guide OS.

## Runtime Data Boundary

Remote Pay Guide OS contains both source code and runtime state.

Source code can be updated through Git.

Runtime data must be preserved separately.

## Runtime Database

Runtime database:

```text
os/database/os.db
```

This database stores runtime state, including:

- platform account connections
- OAuth connection state
- publish task records
- local OS runtime records

## Important Rules

Do not:

- delete `os/database/os.db` during normal updates
- replace the active runtime database with a fresh empty database
- overwrite runtime data when updating source code
- treat a fresh repository checkout as a complete runtime restoration

## Update Procedure

For normal development updates:

1. Continue using the existing workspace
2. Update source code through Git
3. Keep runtime database unchanged
4. Verify application health after update

A source code update does not require replacing runtime state.

## Migration Procedure

When deploying to a new machine or environment:

1. Deploy the source code
2. Restore required runtime data separately
3. Verify accounts, integrations, and runtime records
4. Start the OS

A repository checkout contains source code, but runtime state must be handled separately.

## Principle

Code changes frequently.

Runtime state must remain stable.
