-- Advanced database objects: procedures, triggers, functions, views

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Order summary with user and item details
CREATE OR REPLACE VIEW app.vw_order_summary AS
SELECT 
    o.order_id,
    o.user_id,
    u.username,
    u.email,
    o.status,
    o.total_amount,
    o.created_at,
    o.completed_at,
    COUNT(oi.item_id) as item_count,
    SUM(oi.quantity) as total_items
FROM app.orders o
JOIN app.users u ON o.user_id = u.user_id
LEFT JOIN app.order_items oi ON o.order_id = oi.order_id
GROUP BY 
    o.order_id, o.user_id, u.username, u.email, 
    o.status, o.total_amount, o.created_at, o.completed_at;

COMMENT ON TABLE app.vw_order_summary IS 'Consolidated view of orders with user information';

-- View: Product inventory status
CREATE OR REPLACE VIEW app.vw_inventory_status AS
SELECT 
    p.product_id,
    p.name,
    p.category,
    p.stock_qty,
    p.price,
    CASE 
        WHEN p.stock_qty = 0 THEN 'OUT_OF_STOCK'
        WHEN p.stock_qty < 10 THEN 'LOW_STOCK'
        WHEN p.stock_qty < 50 THEN 'ADEQUATE'
        ELSE 'WELL_STOCKED'
    END as stock_status,
    COALESCE(sales.total_sold, 0) as total_sold,
    p.price * p.stock_qty as inventory_value
FROM app.products p
LEFT JOIN (
    SELECT product_id, SUM(quantity) as total_sold
    FROM app.order_items
    GROUP BY product_id
) sales ON p.product_id = sales.product_id;

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Function: Calculate order total (for validation)
CREATE OR REPLACE FUNCTION app.fn_calculate_order_total(
    p_order_id IN NUMBER
) RETURN NUMBER IS
    v_total NUMBER(12,2);
BEGIN
    SELECT SUM(quantity * unit_price)
    INTO v_total
    FROM app.order_items
    WHERE order_id = p_order_id;
    
    RETURN COALESCE(v_total, 0);
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN 0;
    WHEN OTHERS THEN
        RAISE;
END fn_calculate_order_total;
/

-- Function: Check product availability
CREATE OR REPLACE FUNCTION app.fn_check_stock(
    p_product_id IN NUMBER,
    p_quantity IN NUMBER
) RETURN VARCHAR2 IS
    v_stock_qty NUMBER(10);
BEGIN
    SELECT stock_qty
    INTO v_stock_qty
    FROM app.products
    WHERE product_id = p_product_id;
    
    IF v_stock_qty >= p_quantity THEN
        RETURN 'AVAILABLE';
    ELSIF v_stock_qty > 0 THEN
        RETURN 'PARTIAL';
    ELSE
        RETURN 'OUT_OF_STOCK';
    END IF;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN 'PRODUCT_NOT_FOUND';
    WHEN OTHERS THEN
        RAISE;
END fn_check_stock;
/

-- ============================================================
-- STORED PROCEDURES
-- ============================================================

-- Procedure: Create new order with validation
CREATE OR REPLACE PROCEDURE app.sp_create_order(
    p_user_id IN NUMBER,
    p_shipping_addr IN VARCHAR2,
    p_order_id OUT NUMBER,
    p_status OUT VARCHAR2,
    p_message OUT VARCHAR2
) IS
    v_user_status VARCHAR2(20);
BEGIN
    -- Validate user
    SELECT status INTO v_user_status
    FROM app.users
    WHERE user_id = p_user_id;
    
    IF v_user_status != 'ACTIVE' THEN
        p_status := 'ERROR';
        p_message := 'User account is not active';
        RETURN;
    END IF;
    
    -- Generate new order ID
    SELECT app.seq_orders.NEXTVAL INTO p_order_id FROM DUAL;
    
    -- Create order
    INSERT INTO app.orders (
        order_id, user_id, total_amount, status, 
        shipping_addr, created_at
    ) VALUES (
        p_order_id, p_user_id, 0, 'PENDING',
        p_shipping_addr, SYSTIMESTAMP
    );
    
    p_status := 'SUCCESS';
    p_message := 'Order created successfully';
    COMMIT;
    
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        p_status := 'ERROR';
        p_message := 'User not found';
        ROLLBACK;
    WHEN OTHERS THEN
        p_status := 'ERROR';
        p_message := 'Error: ' || SQLERRM;
        ROLLBACK;
END sp_create_order;
/

-- Procedure: Add item to order with stock validation
CREATE OR REPLACE PROCEDURE app.sp_add_order_item(
    p_order_id IN NUMBER,
    p_product_id IN NUMBER,
    p_quantity IN NUMBER,
    p_item_id OUT NUMBER,
    p_status OUT VARCHAR2,
    p_message OUT VARCHAR2
) IS
    v_stock_qty NUMBER(10);
    v_unit_price NUMBER(10,2);
    v_order_status VARCHAR2(20);
    v_order_total NUMBER(12,2);
BEGIN
    -- Check order status
    SELECT status INTO v_order_status
    FROM app.orders
    WHERE order_id = p_order_id;
    
    IF v_order_status != 'PENDING' THEN
        p_status := 'ERROR';
        p_message := 'Cannot modify order in ' || v_order_status || ' status';
        RETURN;
    END IF;
    
    -- Check product availability
    SELECT stock_qty, price
    INTO v_stock_qty, v_unit_price
    FROM app.products
    WHERE product_id = p_product_id
    FOR UPDATE;
    
    IF v_stock_qty < p_quantity THEN
        p_status := 'ERROR';
        p_message := 'Insufficient stock. Available: ' || v_stock_qty;
        ROLLBACK;
        RETURN;
    END IF;
    
    -- Generate item ID
    SELECT app.seq_orders.NEXTVAL INTO p_item_id FROM DUAL;
    
    -- Add order item
    INSERT INTO app.order_items (
        item_id, order_id, product_id, quantity, unit_price
    ) VALUES (
        p_item_id, p_order_id, p_product_id, p_quantity, v_unit_price
    );
    
    -- Update product stock
    UPDATE app.products
    SET stock_qty = stock_qty - p_quantity
    WHERE product_id = p_product_id;
    
    -- Update order total
    SELECT SUM(quantity * unit_price)
    INTO v_order_total
    FROM app.order_items
    WHERE order_id = p_order_id;
    
    UPDATE app.orders
    SET total_amount = v_order_total
    WHERE order_id = p_order_id;
    
    p_status := 'SUCCESS';
    p_message := 'Item added successfully';
    COMMIT;
    
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        p_status := 'ERROR';
        p_message := 'Order or product not found';
        ROLLBACK;
    WHEN OTHERS THEN
        p_status := 'ERROR';
        p_message := 'Error: ' || SQLERRM;
        ROLLBACK;
END sp_add_order_item;
/

-- Procedure: Complete order
CREATE OR REPLACE PROCEDURE app.sp_complete_order(
    p_order_id IN NUMBER,
    p_status OUT VARCHAR2,
    p_message OUT VARCHAR2
) IS
    v_current_status VARCHAR2(20);
    v_item_count NUMBER;
BEGIN
    -- Get current order status
    SELECT status INTO v_current_status
    FROM app.orders
    WHERE order_id = p_order_id
    FOR UPDATE;
    
    IF v_current_status != 'PENDING' THEN
        p_status := 'ERROR';
        p_message := 'Order is already ' || v_current_status;
        RETURN;
    END IF;
    
    -- Verify order has items
    SELECT COUNT(*) INTO v_item_count
    FROM app.order_items
    WHERE order_id = p_order_id;
    
    IF v_item_count = 0 THEN
        p_status := 'ERROR';
        p_message := 'Cannot complete order with no items';
        RETURN;
    END IF;
    
    -- Update order status
    UPDATE app.orders
    SET status = 'PROCESSING',
        completed_at = SYSTIMESTAMP
    WHERE order_id = p_order_id;
    
    p_status := 'SUCCESS';
    p_message := 'Order marked as processing';
    COMMIT;
    
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        p_status := 'ERROR';
        p_message := 'Order not found';
        ROLLBACK;
    WHEN OTHERS THEN
        p_status := 'ERROR';
        p_message := 'Error: ' || SQLERRM;
        ROLLBACK;
END sp_complete_order;
/

-- Procedure: User login tracking
CREATE OR REPLACE PROCEDURE app.sp_record_login(
    p_user_id IN NUMBER,
    p_status OUT VARCHAR2
) IS
BEGIN
    UPDATE app.users
    SET last_login = SYSTIMESTAMP,
        login_count = login_count + 1
    WHERE user_id = p_user_id
      AND status = 'ACTIVE';
    
    IF SQL%ROWCOUNT = 0 THEN
        p_status := 'INACTIVE_OR_NOT_FOUND';
    ELSE
        p_status := 'SUCCESS';
        COMMIT;
    END IF;
    
EXCEPTION
    WHEN OTHERS THEN
        p_status := 'ERROR';
        ROLLBACK;
END sp_record_login;
/

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Trigger: Audit changes on users table
CREATE OR REPLACE TRIGGER app.trg_users_audit
    AFTER INSERT OR UPDATE OR DELETE ON app.users
    FOR EACH ROW
DECLARE
    v_log_id NUMBER;
    v_action VARCHAR2(10);
    v_old_values CLOB;
    v_new_values CLOB;
BEGIN
    -- Determine action
    IF INSERTING THEN
        v_action := 'INSERT';
        v_new_values := 'user_id=' || :NEW.user_id || 
                       ',username=' || :NEW.username ||
                       ',email=' || :NEW.email ||
                       ',status=' || :NEW.status;
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
        v_old_values := 'user_id=' || :OLD.user_id || 
                       ',username=' || :OLD.username ||
                       ',email=' || :OLD.email ||
                       ',status=' || :OLD.status ||
                       ',login_count=' || :OLD.login_count;
        v_new_values := 'user_id=' || :NEW.user_id || 
                       ',username=' || :NEW.username ||
                       ',email=' || :NEW.email ||
                       ',status=' || :NEW.status ||
                       ',login_count=' || :NEW.login_count;
    ELSIF DELETING THEN
        v_action := 'DELETE';
        v_old_values := 'user_id=' || :OLD.user_id || 
                       ',username=' || :OLD.username ||
                       ',email=' || :OLD.email ||
                       ',status=' || :OLD.status;
    END IF;
    
    -- Get next log ID
    SELECT app.seq_audit.NEXTVAL INTO v_log_id FROM DUAL;
    
    -- Insert audit record
    INSERT INTO app.audit_log (
        log_id, table_name, record_id, action,
        changed_by, changed_at, old_values, new_values
    ) VALUES (
        v_log_id, 'USERS', 
        COALESCE(:NEW.user_id, :OLD.user_id),
        v_action, 
        COALESCE(:NEW.user_id, :OLD.user_id),
        SYSTIMESTAMP,
        v_old_values,
        v_new_values
    );
END;
/

-- Trigger: Audit changes on orders table
CREATE OR REPLACE TRIGGER app.trg_orders_audit
    AFTER INSERT OR UPDATE OR DELETE ON app.orders
    FOR EACH ROW
DECLARE
    v_log_id NUMBER;
    v_action VARCHAR2(10);
    v_old_values CLOB;
    v_new_values CLOB;
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
        v_new_values := 'order_id=' || :NEW.order_id ||
                       ',user_id=' || :NEW.user_id ||
                       ',status=' || :NEW.status ||
                       ',total_amount=' || :NEW.total_amount;
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
        v_old_values := 'order_id=' || :OLD.order_id ||
                       ',status=' || :OLD.status ||
                       ',total_amount=' || :OLD.total_amount;
        v_new_values := 'order_id=' || :NEW.order_id ||
                       ',status=' || :NEW.status ||
                       ',total_amount=' || :NEW.total_amount;
    ELSIF DELETING THEN
        v_action := 'DELETE';
        v_old_values := 'order_id=' || :OLD.order_id ||
                       ',status=' || :OLD.status ||
                       ',total_amount=' || :OLD.total_amount;
    END IF;
    
    SELECT app.seq_audit.NEXTVAL INTO v_log_id FROM DUAL;
    
    INSERT INTO app.audit_log (
        log_id, table_name, record_id, action,
        changed_by, changed_at, old_values, new_values
    ) VALUES (
        v_log_id, 'ORDERS',
        COALESCE(:NEW.order_id, :OLD.order_id),
        v_action,
        COALESCE(:NEW.user_id, :OLD.user_id),
        SYSTIMESTAMP,
        v_old_values,
        v_new_values
    );
END;
/

-- Trigger: Prevent negative stock
CREATE OR REPLACE TRIGGER app.trg_products_stock_check
    BEFORE UPDATE OF stock_qty ON app.products
    FOR EACH ROW
BEGIN
    IF :NEW.stock_qty < 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 
            'Stock quantity cannot be negative for product ' || :NEW.product_id);
    END IF;
END;
/

-- Trigger: Auto-update order timestamp on status change
CREATE OR REPLACE TRIGGER app.trg_orders_status_change
    BEFORE UPDATE OF status ON app.orders
    FOR EACH ROW
BEGIN
    IF :NEW.status != :OLD.status THEN
        IF :NEW.status IN ('DELIVERED', 'CANCELLED') AND :OLD.completed_at IS NULL THEN
            :NEW.completed_at := SYSTIMESTAMP;
        END IF;
    END IF;
END;
/

-- ============================================================
-- MATERIALIZED VIEW (for performance)
-- ============================================================

CREATE MATERIALIZED VIEW app.mv_product_sales
BUILD IMMEDIATE
REFRESH COMPLETE ON DEMAND
AS
SELECT 
    p.product_id,
    p.name,
    p.category,
    COUNT(DISTINCT oi.order_id) as order_count,
    SUM(oi.quantity) as total_quantity_sold,
    SUM(oi.quantity * oi.unit_price) as total_revenue,
    AVG(oi.unit_price) as avg_selling_price,
    MAX(o.created_at) as last_sale_date
FROM app.products p
LEFT JOIN app.order_items oi ON p.product_id = oi.product_id
LEFT JOIN app.orders o ON oi.order_id = o.order_id
WHERE o.status NOT IN ('CANCELLED')
   OR o.status IS NULL
GROUP BY p.product_id, p.name, p.category;

CREATE INDEX app.idx_mv_sales_category ON app.mv_product_sales(category);
CREATE INDEX app.idx_mv_sales_revenue ON app.mv_product_sales(total_revenue DESC);

COMMENT ON MATERIALIZED VIEW app.mv_product_sales IS 'Aggregated product sales metrics';
