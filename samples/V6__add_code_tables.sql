-- Code tables (reference data) and schema modifications

-- ============================================================
-- CODE TABLE: User Types
-- ============================================================

CREATE TABLE app.user_types (
    user_type_code  VARCHAR2(20)    NOT NULL,
    description     VARCHAR2(100)   NOT NULL,
    is_active       CHAR(1)         DEFAULT 'Y' NOT NULL,
    display_order   NUMBER(3)       DEFAULT 999,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_user_types PRIMARY KEY (user_type_code),
    CONSTRAINT ck_user_types_active CHECK (is_active IN ('Y','N'))
);

COMMENT ON TABLE app.user_types IS 'Reference table for user classification types';
COMMENT ON COLUMN app.user_types.user_type_code IS 'Unique code identifier for user type';
COMMENT ON COLUMN app.user_types.is_active IS 'Whether this type is currently active for use';

-- ============================================================
-- CODE TABLE: Product Categories
-- ============================================================

CREATE TABLE app.product_categories (
    category_code   VARCHAR2(20)    NOT NULL,
    category_name   VARCHAR2(100)   NOT NULL,
    parent_category VARCHAR2(20),
    is_active       CHAR(1)         DEFAULT 'Y' NOT NULL,
    display_order   NUMBER(3)       DEFAULT 999,
    CONSTRAINT pk_product_categories PRIMARY KEY (category_code),
    CONSTRAINT fk_categories_parent FOREIGN KEY (parent_category)
        REFERENCES app.product_categories(category_code),
    CONSTRAINT ck_categories_active CHECK (is_active IN ('Y','N'))
);

COMMENT ON TABLE app.product_categories IS 'Hierarchical product category reference table';

-- ============================================================
-- CODE TABLE: Order Status Codes
-- ============================================================

CREATE TABLE app.order_status_codes (
    status_code     VARCHAR2(20)    NOT NULL,
    status_name     VARCHAR2(50)    NOT NULL,
    description     VARCHAR2(200),
    is_terminal     CHAR(1)         DEFAULT 'N' NOT NULL,
    is_active       CHAR(1)         DEFAULT 'Y' NOT NULL,
    color_hex       VARCHAR2(7),
    display_order   NUMBER(3)       DEFAULT 999,
    CONSTRAINT pk_order_status_codes PRIMARY KEY (status_code),
    CONSTRAINT ck_status_terminal CHECK (is_terminal IN ('Y','N')),
    CONSTRAINT ck_status_active CHECK (is_active IN ('Y','N'))
);

COMMENT ON TABLE app.order_status_codes IS 'Reference table for valid order status values';
COMMENT ON COLUMN app.order_status_codes.is_terminal IS 'Whether this status is a final/terminal state';
COMMENT ON COLUMN app.order_status_codes.color_hex IS 'UI color code for display purposes';

-- ============================================================
-- CODE TABLE: Shipping Methods
-- ============================================================

CREATE TABLE app.shipping_methods (
    method_code     VARCHAR2(20)    NOT NULL,
    method_name     VARCHAR2(50)    NOT NULL,
    base_cost       NUMBER(8,2)     NOT NULL,
    estimated_days  NUMBER(3)       NOT NULL,
    is_active       CHAR(1)         DEFAULT 'Y' NOT NULL,
    requires_signature CHAR(1)      DEFAULT 'N' NOT NULL,
    display_order   NUMBER(3)       DEFAULT 999,
    CONSTRAINT pk_shipping_methods PRIMARY KEY (method_code),
    CONSTRAINT ck_shipping_active CHECK (is_active IN ('Y','N')),
    CONSTRAINT ck_shipping_signature CHECK (requires_signature IN ('Y','N')),
    CONSTRAINT ck_shipping_cost CHECK (base_cost >= 0),
    CONSTRAINT ck_shipping_days CHECK (estimated_days > 0)
);

COMMENT ON TABLE app.shipping_methods IS 'Available shipping method options';

-- ============================================================
-- MODIFY EXISTING TABLES to use code tables
-- ============================================================

-- Add user_type_code to users table
ALTER TABLE app.users ADD (
    user_type_code  VARCHAR2(20),
    account_tier    VARCHAR2(20)    DEFAULT 'STANDARD'
);

ALTER TABLE app.users ADD CONSTRAINT fk_users_type 
    FOREIGN KEY (user_type_code) 
    REFERENCES app.user_types(user_type_code);

ALTER TABLE app.users ADD CONSTRAINT ck_users_tier
    CHECK (account_tier IN ('STANDARD','PREMIUM','ENTERPRISE'));

COMMENT ON COLUMN app.users.user_type_code IS 'User classification type reference';
COMMENT ON COLUMN app.users.account_tier IS 'Subscription tier level';

-- Add category_code to products table (replacing the free-text category)
ALTER TABLE app.products ADD (
    category_code   VARCHAR2(20)
);

ALTER TABLE app.products ADD CONSTRAINT fk_products_category
    FOREIGN KEY (category_code)
    REFERENCES app.product_categories(category_code);

-- Note: The old 'category' VARCHAR2 column still exists for now
-- Migration V8 will demonstrate removing it

-- Add shipping_method to orders table
ALTER TABLE app.orders ADD (
    shipping_method VARCHAR2(20),
    shipping_cost   NUMBER(8,2)     DEFAULT 0
);

ALTER TABLE app.orders ADD CONSTRAINT fk_orders_shipping
    FOREIGN KEY (shipping_method)
    REFERENCES app.shipping_methods(method_code);

ALTER TABLE app.orders ADD CONSTRAINT ck_orders_shipping_cost
    CHECK (shipping_cost >= 0);

COMMENT ON COLUMN app.orders.shipping_method IS 'Selected shipping method code';
COMMENT ON COLUMN app.orders.shipping_cost IS 'Calculated shipping cost for this order';

-- ============================================================
-- CREATE INDEXES on new foreign keys
-- ============================================================

CREATE INDEX app.idx_users_type ON app.users(user_type_code);
CREATE INDEX app.idx_products_category_code ON app.products(category_code);
CREATE INDEX app.idx_orders_shipping ON app.orders(shipping_method);

-- ============================================================
-- ADD SEQUENCE for code table management
-- ============================================================

CREATE SEQUENCE app.seq_code_tables
    START WITH 1
    INCREMENT BY 1
    CACHE 20
    NOCYCLE;

COMMENT ON SEQUENCE app.seq_code_tables IS 'General purpose sequence for code table surrogate keys if needed';
