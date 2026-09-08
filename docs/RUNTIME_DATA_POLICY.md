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

## Runtime Secret Boundary

| Data | Location | Lifecycle |
|---|---|---|
| Source code | GitHub repository | Git-managed |
| Runtime database and OAuth tokens | `os/database/os.db` | Local runtime data; preserve separately |
| OAuth Client secure configuration | Windows CurrentUser secure store | DPAPI-protected local user data |
| OAuth Client recovery JSON | `%LOCALAPPDATA%\RemotePayGuide\secrets\youtube-oauth-client.json` | Bootstrap / recovery material only |

OAuth Client Configuration contains `client_id` and `client_secret`; OAuth Tokens contain access token, refresh token, scopes and expiry. These are separate data classes. Client configuration must not be stored in `os.db`, and token material remains in the existing `oauth_tokens` storage.

The recovery JSON is outside the Git repository. A fresh clone does not contain it. Moving the OS to another computer therefore requires separately transferring or re-providing the OAuth Client recovery material, importing it into that Windows user's secure store, and separately restoring the required runtime database.

The recovery JSON may use Google `installed`, Google `web`, or Remote Pay Guide minimal recovery format. It must never be committed, logged, returned through an API, or exposed to the frontend.
