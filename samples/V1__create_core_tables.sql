-- Core user and product tables
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
COMMENT ON COLUMN app.users.status IS 'Account lifecycle status';
