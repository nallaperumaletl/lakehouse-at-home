# Schema Migrations

This directory contains SQL migrations for the lakehouse PostgreSQL database.

## Structure

```
schemas/
├── iceberg/                    # Iceberg catalog metadata
│   ├── v001_initial_medallion.sql
│   └── v002_add_order_tables.sql
└── unity_catalog/              # Unity Catalog integration
    └── v001_initial_catalogs.sql
```

## Running Migrations

Use the lakehouse CLI to run migrations:

```bash
# Preview migrations (dry run)
./lakehouse migrate --dry-run

# Apply migrations
./lakehouse migrate
```

## Migration Naming Convention

Migrations follow the pattern: `v{NNN}_{description}.sql`

- `v001`, `v002`, etc. - Version number (sorted alphabetically)
- `{description}` - Brief description with underscores

## Migration Tracking

Applied migrations are tracked in the `_migrations` table:

```sql
SELECT * FROM _migrations ORDER BY applied_at;
```

## Writing Migrations

1. **Idempotent**: Use `IF NOT EXISTS` and `ON CONFLICT` clauses
2. **Atomic**: Each migration should be a logical unit
3. **Reversible**: Document rollback steps in comments when possible
4. **Descriptive**: Include comments explaining the purpose

Example:

```sql
-- Migration: v003_add_audit_log
-- Description: Add audit logging table
-- Rollback: DROP TABLE IF EXISTS audit_log;

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    table_name VARCHAR(255),
    record_id VARCHAR(255),
    user_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Important Notes

- **Iceberg tables**: The SQL migrations track metadata only. Actual Iceberg tables
  are created via Spark SQL (see `scripts/` for examples).

- **Unity Catalog**: The unity_catalog migrations prepare for OSS Unity Catalog
  integration. The actual Unity Catalog service has its own storage backend.

- **Never modify applied migrations**: Create new migrations for changes.
