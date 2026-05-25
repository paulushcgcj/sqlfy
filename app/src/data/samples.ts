import type { MigrationFile } from '../core/types';

export const SAMPLE_MIGRATIONS: MigrationFile[] = [
  {
    filename: 'V1__create_core_tables.sql',
    sql: `-- Core user and product tables
CREATE TABLE app.users (
    user_id     NUMBER(10)      NOT NULL,
    username    VARCHAR2(50)    NOT NULL,
    email       VARCHAR2(100)   NOT NULL,
    status      VARCHAR2(20)    DEFAULT 'ACTIVE' NOT NULL,
    created_at  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (user_id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE','INACTIVE','SUSPENDED'))
);
CREATE SEQUENCE app.seq_users START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
CREATE TABLE app.products (
    product_id  NUMBER(10)      NOT NULL,
    name        VARCHAR2(200)   NOT NULL,
    description CLOB,
    price       NUMBER(10,2)    NOT NULL,
    stock_qty   NUMBER(10)      DEFAULT 0 NOT NULL,
    category    VARCHAR2(50),
    CONSTRAINT pk_products PRIMARY KEY (product_id),
    CONSTRAINT ck_products_price CHECK (price >= 0)
);
CREATE SEQUENCE app.seq_products START WITH 1 INCREMENT BY 1 NOCACHE;
COMMENT ON TABLE app.users IS 'Core user accounts';
COMMENT ON COLUMN app.users.status IS 'Account lifecycle status';`,
  },
  {
    filename: 'V2__create_orders.sql',
    sql: `-- Order management
CREATE TABLE app.orders (
    order_id        NUMBER(10)      NOT NULL,
    user_id         NUMBER(10)      NOT NULL,
    total_amount    NUMBER(12,2)    NOT NULL,
    status          VARCHAR2(20)    DEFAULT 'PENDING' NOT NULL,
    shipping_addr   VARCHAR2(500),
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    completed_at    TIMESTAMP,
    CONSTRAINT pk_orders PRIMARY KEY (order_id),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id)
        REFERENCES app.users(user_id) ON DELETE CASCADE,
    CONSTRAINT ck_orders_status CHECK (status IN ('PENDING','PROCESSING','SHIPPED','DELIVERED','CANCELLED'))
);
CREATE SEQUENCE app.seq_orders START WITH 1000 INCREMENT BY 1 NOCACHE;
CREATE TABLE app.order_items (
    item_id     NUMBER(10)   NOT NULL,
    order_id    NUMBER(10)   NOT NULL,
    product_id  NUMBER(10)   NOT NULL,
    quantity    NUMBER(5)    NOT NULL,
    unit_price  NUMBER(10,2) NOT NULL,
    CONSTRAINT pk_order_items PRIMARY KEY (item_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id)
        REFERENCES app.orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id)
        REFERENCES app.products(product_id),
    CONSTRAINT ck_items_qty CHECK (quantity > 0)
);
CREATE INDEX app.idx_orders_user   ON app.orders(user_id);
CREATE INDEX app.idx_orders_status ON app.orders(status, created_at);
CREATE INDEX app.idx_items_order   ON app.order_items(order_id);`,
  },
  {
    filename: 'V3__add_audit.sql',
    sql: `-- Audit trail
CREATE TABLE app.audit_log (
    log_id      NUMBER(15)      NOT NULL,
    table_name  VARCHAR2(100)   NOT NULL,
    record_id   NUMBER(15)      NOT NULL,
    action      VARCHAR2(10)    NOT NULL,
    changed_by  NUMBER(10),
    changed_at  TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    old_values  CLOB,
    new_values  CLOB,
    CONSTRAINT pk_audit_log PRIMARY KEY (log_id),
    CONSTRAINT fk_audit_user FOREIGN KEY (changed_by)
        REFERENCES app.users(user_id),
    CONSTRAINT ck_audit_action CHECK (action IN ('INSERT','UPDATE','DELETE'))
);
CREATE SEQUENCE app.seq_audit START WITH 1 INCREMENT BY 1 CACHE 100;
ALTER TABLE app.users ADD (last_login TIMESTAMP, login_count NUMBER(10) DEFAULT 0);
ALTER TABLE app.products ADD CONSTRAINT uq_products_name UNIQUE (name);
CREATE INDEX app.idx_audit_table ON app.audit_log(table_name, record_id);
CREATE INDEX app.idx_audit_user  ON app.audit_log(changed_by, changed_at);`,
  },
];