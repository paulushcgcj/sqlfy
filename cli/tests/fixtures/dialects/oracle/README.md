# oracle dialect fixture

## Coverage
- CREATE TABLE with PK, NOT NULL, DEFAULT, UNIQUE, and comment where dialect supports it
- Second table and foreign key
- ALTER TABLE add column
- Index creation
- Destructive operation DROP table/column/index
- Intentionally unsupported schema-changing statement

## Files
- V1__init.sql – sample migration statements

## Expected final objects
See expected-schema.json
