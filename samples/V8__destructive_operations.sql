-- Destructive operations: dropping columns, deleting data

-- ============================================================
-- WARNING: This migration contains destructive operations
-- ============================================================

-- ============================================================
-- DROP COLUMN: Remove stock_qty from products
-- ============================================================

-- Rationale: Moving to a separate inventory management system
-- Stock quantity will be tracked externally

ALTER TABLE app.products DROP COLUMN stock_qty;

COMMENT ON TABLE app.products IS 'Product catalog - inventory managed externally';

-- ============================================================
-- DROP COLUMN: Remove old free-text category from products
-- ============================================================

-- Now that we have category_code FK to product_categories,
-- the old VARCHAR2 category column is redundant

ALTER TABLE app.products DROP COLUMN category;

-- ============================================================
-- DELETE DATA: Remove deprecated user type
-- ============================================================

-- First, ensure no users are using this type
-- In a real migration, you'd migrate them to a different type first

-- Safety check: Update any users with LEGACY type to CUSTOMER
UPDATE app.users 
SET user_type_code = 'CUSTOMER'
WHERE user_type_code = 'LEGACY';

-- Now safe to delete the code table entry
DELETE FROM app.user_types
WHERE user_type_code = 'LEGACY';

-- ============================================================
-- DELETE DATA: Remove test/sample user
-- ============================================================

-- Remove the inactive test user (this will cascade to their orders due to FK)
DELETE FROM app.users
WHERE username = 'inactive.user';

-- ============================================================
-- DROP CONSTRAINT: Remove old check constraint that's too restrictive
-- ============================================================

-- The original status constraint is too limited now that we have a code table
ALTER TABLE app.orders DROP CONSTRAINT ck_orders_status;

-- Add new constraint that just validates NOT NULL
ALTER TABLE app.orders ADD CONSTRAINT ck_orders_status_not_null
    CHECK (status IS NOT NULL);

-- Ideally we'd add FK to order_status_codes table, but since existing data
-- uses different values, we'll just enforce non-null for now
-- A future migration could add the FK after data cleanup

-- ============================================================
-- DROP INDEX: Remove unused index
-- ============================================================

-- The idx_orders_status was built for the old status values
-- We'll recreate a better one in a future migration if needed
DROP INDEX app.idx_orders_status;

-- ============================================================
-- TRUNCATE: Clear audit log (dangerous - for testing only!)
-- ============================================================

-- WARNING: This removes all audit history
-- Only appropriate in development/testing environments
-- In production, you'd archive instead of truncate

TRUNCATE TABLE app.audit_log;

-- ============================================================
-- DROP SEQUENCE: Remove unused code table sequence
-- ============================================================

-- The seq_code_tables sequence was created but never actually used
DROP SEQUENCE app.seq_code_tables;

-- ============================================================
-- COMMIT
-- ============================================================

COMMIT;
