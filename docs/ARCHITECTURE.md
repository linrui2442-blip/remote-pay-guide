# Remote Pay Guide — Architecture

## Source Code and Runtime Boundary

Remote Pay Guide OS consists of two separate layers:

```
Source Code
    ↓
Git Repository

Runtime State
    ↓
os/database/os.db
```

Git synchronization updates source code.

Runtime database contains local operating state and must be preserved separately.

## Runtime Database

Primary runtime database:

```text
os/database/os.db
```

It must not be treated as disposable build output.

## Update Model

Normal update flow:

```
Git update
    ↓
Keep runtime database
    ↓
Verify services
    ↓
Continue operation
```

A clean repository checkout is not a complete OS restoration because runtime data is separate.

## System Architecture

```
Content
 ↓
Production
 ↓
Asset
 ↓
Publish
 ↓
Traffic
 ↓
Analytics
 ↓
Intelligence
 ↓
Next Production Decision
```

Existing Production, Publish, OAuth, Analytics and Intelligence capabilities should be extended from current code.

Do not create duplicate systems based on historical documents.

## Runtime Safety Principle

Code is replaceable.

Runtime state must remain stable.
