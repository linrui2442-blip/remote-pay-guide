# Content Registry Database

Remote Pay Guide OS Phase 10 database layer.

Purpose:

- Store a SQLite representation of Content Registry data.
- Keep the existing JSON registry as the source for migration.
- Do not replace render, publish, Postiz, or OAuth flows.

Migration flow:

content-registry/registry.json

↓

migrate_registry.py

↓

 database/content.db

The migration is read-only against registry.json and preserves UNKNOWN values.
