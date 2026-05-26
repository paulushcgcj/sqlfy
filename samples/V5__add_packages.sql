-- PL/SQL Packages for business logic encapsulation

-- ============================================================
-- PACKAGE: Order Management
-- ============================================================

-- Package Specification
CREATE OR REPLACE PACKAGE app.pkg_order_management AS
    -- Public types
    TYPE t_order_rec IS RECORD (
        order_id        NUMBER,
        user_id         NUMBER,
        status          VARCHAR2(20),
        total_amount    NUMBER,
        item_count      NUMBER
    );
    
    TYPE t_order_table IS TABLE OF t_order_rec INDEX BY PLS_INTEGER;
    
    -- Public constants
    c_max_items_per_order CONSTANT NUMBER := 100;
    c_default_shipping_days CONSTANT NUMBER := 5;
    
    -- Public procedures and functions
    FUNCTION get_order_count(
        p_user_id IN NUMBER,
        p_status IN VARCHAR2 DEFAULT NULL
    ) RETURN NUMBER;
    
    FUNCTION get_user_orders(
        p_user_id IN NUMBER,
        p_status IN VARCHAR2 DEFAULT NULL
    ) RETURN t_order_table;
    
    PROCEDURE cancel_order(
        p_order_id IN NUMBER,
        p_refund_amount OUT NUMBER,
        p_status OUT VARCHAR2,
        p_message OUT VARCHAR2
    );
    
    PROCEDURE ship_order(
        p_order_id IN NUMBER,
        p_tracking_number IN VARCHAR2,
        p_status OUT VARCHAR2,
        p_message OUT VARCHAR2
    );
    
    FUNCTION calculate_shipping_cost(
        p_order_id IN NUMBER,
        p_shipping_method IN VARCHAR2 DEFAULT 'STANDARD'
    ) RETURN NUMBER;
    
END pkg_order_management;
/

-- Package Body
CREATE OR REPLACE PACKAGE BODY app.pkg_order_management AS
    
    -- Private function: Validate order exists
    FUNCTION order_exists(p_order_id IN NUMBER) RETURN BOOLEAN IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM app.orders
        WHERE order_id = p_order_id;
        
        RETURN v_count > 0;
    END order_exists;
    
    -- Public function: Get order count
    FUNCTION get_order_count(
        p_user_id IN NUMBER,
        p_status IN VARCHAR2 DEFAULT NULL
    ) RETURN NUMBER IS
        v_count NUMBER;
    BEGIN
        IF p_status IS NULL THEN
            SELECT COUNT(*)
            INTO v_count
            FROM app.orders
            WHERE user_id = p_user_id;
        ELSE
            SELECT COUNT(*)
            INTO v_count
            FROM app.orders
            WHERE user_id = p_user_id
              AND status = p_status;
        END IF;
        
        RETURN v_count;
    END get_order_count;
    
    -- Public function: Get user orders
    FUNCTION get_user_orders(
        p_user_id IN NUMBER,
        p_status IN VARCHAR2 DEFAULT NULL
    ) RETURN t_order_table IS
        v_orders t_order_table;
        v_idx PLS_INTEGER := 1;
    BEGIN
        FOR rec IN (
            SELECT 
                o.order_id,
                o.user_id,
                o.status,
                o.total_amount,
                COUNT(oi.item_id) as item_count
            FROM app.orders o
            LEFT JOIN app.order_items oi ON o.order_id = oi.order_id
            WHERE o.user_id = p_user_id
              AND (p_status IS NULL OR o.status = p_status)
            GROUP BY o.order_id, o.user_id, o.status, o.total_amount
            ORDER BY o.created_at DESC
        ) LOOP
            v_orders(v_idx).order_id := rec.order_id;
            v_orders(v_idx).user_id := rec.user_id;
            v_orders(v_idx).status := rec.status;
            v_orders(v_idx).total_amount := rec.total_amount;
            v_orders(v_idx).item_count := rec.item_count;
            v_idx := v_idx + 1;
        END LOOP;
        
        RETURN v_orders;
    END get_user_orders;
    
    -- Public procedure: Cancel order
    PROCEDURE cancel_order(
        p_order_id IN NUMBER,
        p_refund_amount OUT NUMBER,
        p_status OUT VARCHAR2,
        p_message OUT VARCHAR2
    ) IS
        v_current_status VARCHAR2(20);
        v_total_amount NUMBER(12,2);
    BEGIN
        -- Check if order exists and get current status
        IF NOT order_exists(p_order_id) THEN
            p_status := 'ERROR';
            p_message := 'Order not found';
            p_refund_amount := 0;
            RETURN;
        END IF;
        
        SELECT status, total_amount
        INTO v_current_status, v_total_amount
        FROM app.orders
        WHERE order_id = p_order_id
        FOR UPDATE;
        
        -- Validate cancellation is allowed
        IF v_current_status IN ('DELIVERED', 'CANCELLED') THEN
            p_status := 'ERROR';
            p_message := 'Cannot cancel order in ' || v_current_status || ' status';
            p_refund_amount := 0;
            RETURN;
        END IF;
        
        -- Restore product stock
        FOR item IN (
            SELECT product_id, quantity
            FROM app.order_items
            WHERE order_id = p_order_id
        ) LOOP
            UPDATE app.products
            SET stock_qty = stock_qty + item.quantity
            WHERE product_id = item.product_id;
        END LOOP;
        
        -- Update order status
        UPDATE app.orders
        SET status = 'CANCELLED',
            completed_at = SYSTIMESTAMP
        WHERE order_id = p_order_id;
        
        p_refund_amount := v_total_amount;
        p_status := 'SUCCESS';
        p_message := 'Order cancelled and stock restored';
        COMMIT;
        
    EXCEPTION
        WHEN OTHERS THEN
            p_status := 'ERROR';
            p_message := 'Error: ' || SQLERRM;
            p_refund_amount := 0;
            ROLLBACK;
    END cancel_order;
    
    -- Public procedure: Ship order
    PROCEDURE ship_order(
        p_order_id IN NUMBER,
        p_tracking_number IN VARCHAR2,
        p_status OUT VARCHAR2,
        p_message OUT VARCHAR2
    ) IS
        v_current_status VARCHAR2(20);
    BEGIN
        IF NOT order_exists(p_order_id) THEN
            p_status := 'ERROR';
            p_message := 'Order not found';
            RETURN;
        END IF;
        
        SELECT status INTO v_current_status
        FROM app.orders
        WHERE order_id = p_order_id
        FOR UPDATE;
        
        IF v_current_status != 'PROCESSING' THEN
            p_status := 'ERROR';
            p_message := 'Order must be in PROCESSING status to ship';
            RETURN;
        END IF;
        
        UPDATE app.orders
        SET status = 'SHIPPED'
        WHERE order_id = p_order_id;
        
        -- Store tracking number (would need a new column, simulated here)
        p_status := 'SUCCESS';
        p_message := 'Order shipped with tracking: ' || p_tracking_number;
        COMMIT;
        
    EXCEPTION
        WHEN OTHERS THEN
            p_status := 'ERROR';
            p_message := 'Error: ' || SQLERRM;
            ROLLBACK;
    END ship_order;
    
    -- Public function: Calculate shipping cost
    FUNCTION calculate_shipping_cost(
        p_order_id IN NUMBER,
        p_shipping_method IN VARCHAR2 DEFAULT 'STANDARD'
    ) RETURN NUMBER IS
        v_total_amount NUMBER(12,2);
        v_item_count NUMBER;
        v_shipping_cost NUMBER(8,2);
    BEGIN
        SELECT total_amount, COUNT(*)
        INTO v_total_amount, v_item_count
        FROM app.orders o
        JOIN app.order_items oi ON o.order_id = oi.order_id
        WHERE o.order_id = p_order_id
        GROUP BY total_amount;
        
        -- Base calculation
        v_shipping_cost := CASE p_shipping_method
            WHEN 'EXPRESS' THEN 25.00
            WHEN 'OVERNIGHT' THEN 45.00
            ELSE 10.00  -- STANDARD
        END;
        
        -- Add per-item fee
        v_shipping_cost := v_shipping_cost + (v_item_count * 2.00);
        
        -- Free shipping for orders over $100
        IF v_total_amount > 100 THEN
            v_shipping_cost := 0;
        END IF;
        
        RETURN v_shipping_cost;
        
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RETURN 0;
        WHEN OTHERS THEN
            RAISE;
    END calculate_shipping_cost;
    
END pkg_order_management;
/

-- ============================================================
-- PACKAGE: Analytics and Reporting
-- ============================================================

CREATE OR REPLACE PACKAGE app.pkg_analytics AS
    -- Public types
    TYPE t_sales_metric IS RECORD (
        period_label    VARCHAR2(50),
        order_count     NUMBER,
        total_revenue   NUMBER,
        avg_order_value NUMBER
    );
    
    TYPE t_sales_metrics IS TABLE OF t_sales_metric INDEX BY PLS_INTEGER;
    
    -- Public functions
    FUNCTION get_daily_sales(
        p_start_date IN DATE,
        p_end_date IN DATE
    ) RETURN t_sales_metrics;
    
    FUNCTION get_top_products(
        p_limit IN NUMBER DEFAULT 10
    ) RETURN SYS_REFCURSOR;
    
    FUNCTION get_customer_lifetime_value(
        p_user_id IN NUMBER
    ) RETURN NUMBER;
    
    FUNCTION get_average_order_size RETURN NUMBER;
    
    PROCEDURE generate_monthly_report(
        p_year IN NUMBER,
        p_month IN NUMBER,
        p_cursor OUT SYS_REFCURSOR
    );
    
END pkg_analytics;
/

CREATE OR REPLACE PACKAGE BODY app.pkg_analytics AS
    
    -- Public function: Get daily sales
    FUNCTION get_daily_sales(
        p_start_date IN DATE,
        p_end_date IN DATE
    ) RETURN t_sales_metrics IS
        v_metrics t_sales_metrics;
        v_idx PLS_INTEGER := 1;
    BEGIN
        FOR rec IN (
            SELECT 
                TO_CHAR(TRUNC(created_at), 'YYYY-MM-DD') as period_label,
                COUNT(*) as order_count,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_order_value
            FROM app.orders
            WHERE TRUNC(created_at) BETWEEN p_start_date AND p_end_date
              AND status NOT IN ('CANCELLED')
            GROUP BY TRUNC(created_at)
            ORDER BY TRUNC(created_at)
        ) LOOP
            v_metrics(v_idx).period_label := rec.period_label;
            v_metrics(v_idx).order_count := rec.order_count;
            v_metrics(v_idx).total_revenue := rec.total_revenue;
            v_metrics(v_idx).avg_order_value := rec.avg_order_value;
            v_idx := v_idx + 1;
        END LOOP;
        
        RETURN v_metrics;
    END get_daily_sales;
    
    -- Public function: Get top products
    FUNCTION get_top_products(
        p_limit IN NUMBER DEFAULT 10
    ) RETURN SYS_REFCURSOR IS
        v_cursor SYS_REFCURSOR;
    BEGIN
        OPEN v_cursor FOR
            SELECT 
                p.product_id,
                p.name,
                p.category,
                COUNT(DISTINCT oi.order_id) as order_count,
                SUM(oi.quantity) as total_sold,
                SUM(oi.quantity * oi.unit_price) as revenue
            FROM app.products p
            JOIN app.order_items oi ON p.product_id = oi.product_id
            JOIN app.orders o ON oi.order_id = o.order_id
            WHERE o.status NOT IN ('CANCELLED')
            GROUP BY p.product_id, p.name, p.category
            ORDER BY revenue DESC
            FETCH FIRST p_limit ROWS ONLY;
        
        RETURN v_cursor;
    END get_top_products;
    
    -- Public function: Customer lifetime value
    FUNCTION get_customer_lifetime_value(
        p_user_id IN NUMBER
    ) RETURN NUMBER IS
        v_total NUMBER(12,2);
    BEGIN
        SELECT COALESCE(SUM(total_amount), 0)
        INTO v_total
        FROM app.orders
        WHERE user_id = p_user_id
          AND status NOT IN ('CANCELLED');
        
        RETURN v_total;
    END get_customer_lifetime_value;
    
    -- Public function: Average order size
    FUNCTION get_average_order_size RETURN NUMBER IS
        v_avg NUMBER(12,2);
    BEGIN
        SELECT AVG(total_amount)
        INTO v_avg
        FROM app.orders
        WHERE status NOT IN ('CANCELLED');
        
        RETURN COALESCE(v_avg, 0);
    END get_average_order_size;
    
    -- Public procedure: Monthly report
    PROCEDURE generate_monthly_report(
        p_year IN NUMBER,
        p_month IN NUMBER,
        p_cursor OUT SYS_REFCURSOR
    ) IS
    BEGIN
        OPEN p_cursor FOR
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) as delivered_orders,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled_orders,
                SUM(CASE WHEN status NOT IN ('CANCELLED') THEN total_amount ELSE 0 END) as total_revenue,
                AVG(CASE WHEN status NOT IN ('CANCELLED') THEN total_amount END) as avg_order_value,
                COUNT(DISTINCT user_id) as unique_customers
            FROM app.orders
            WHERE EXTRACT(YEAR FROM created_at) = p_year
              AND EXTRACT(MONTH FROM created_at) = p_month;
    END generate_monthly_report;
    
END pkg_analytics;
/

-- ============================================================
-- SYNONYMS (for easier access)
-- ============================================================

CREATE OR REPLACE PUBLIC SYNONYM users FOR app.users;
CREATE OR REPLACE PUBLIC SYNONYM products FOR app.products;
CREATE OR REPLACE PUBLIC SYNONYM orders FOR app.orders;

-- ============================================================
-- ADDITIONAL SEQUENCES
-- ============================================================

-- Sequence for batch processing jobs
CREATE SEQUENCE app.seq_batch_jobs 
    START WITH 1 
    INCREMENT BY 1 
    MINVALUE 1
    MAXVALUE 999999999
    CACHE 50
    NOCYCLE
    ORDER;

-- Sequence for transaction IDs (with cycling for long-term use)
CREATE SEQUENCE app.seq_transactions
    START WITH 10000
    INCREMENT BY 1
    MINVALUE 10000
    MAXVALUE 99999999
    CACHE 1000
    CYCLE
    ORDER;

COMMENT ON SEQUENCE app.seq_batch_jobs IS 'Sequence for batch job IDs';
COMMENT ON SEQUENCE app.seq_transactions IS 'Sequence for transaction tracking';

-- ============================================================
-- GRANT PRIVILEGES (sample for testing detection)
-- ============================================================

-- Note: These would need actual users to exist
-- Included here to test privilege detection
-- GRANT SELECT, INSERT, UPDATE ON app.orders TO app_user;
-- GRANT EXECUTE ON app.pkg_order_management TO app_user;
-- GRANT SELECT ON app.vw_order_summary TO reporting_user;
