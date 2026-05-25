-- Order management
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
CREATE INDEX app.idx_items_order   ON app.order_items(order_id);
