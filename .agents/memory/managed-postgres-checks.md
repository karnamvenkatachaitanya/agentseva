---
name: Managed PostgreSQL checks
description: Durable constraints for safe PostgreSQL integration checks in this project.
---

Standalone database tooling must normalize generic PostgreSQL URLs to the
installed psycopg v3 driver, just as application settings do. Integration
checks that exercise append-only audit tables should use a uniquely named
temporary schema and drop it afterward rather than attempting row cleanup.

**Why:** Managed development URLs may omit the driver suffix, and audit
immutability intentionally rejects DELETE/TRUNCATE, so direct disposable-row
cleanup can either fail or risk mixing test data with merchant history.

**How to apply:** Keep smoke checks explicitly opt-in, reject deployment
environments, run real migrations in the isolated schema, and make the
application restart inherit the schema-specific URL.