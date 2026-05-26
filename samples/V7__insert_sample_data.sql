-- Sample data (DML) for testing and development

-- ============================================================
-- INSERT: User Types
-- ============================================================

INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('CUSTOMER', 'Regular customer account', 'Y', 1);

INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('ADMIN', 'Administrator with full access', 'Y', 2);

INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('VENDOR', 'Vendor/supplier account', 'Y', 3);

INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('GUEST', 'Temporary guest account', 'Y', 4);

INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('PARTNER', 'Business partner account', 'Y', 5);

-- This one will be deleted in V8 to test destructive operations
INSERT INTO app.user_types (user_type_code, description, is_active, display_order)
VALUES ('LEGACY', 'Legacy user type - deprecated', 'N', 999);

-- ============================================================
-- INSERT: Product Categories
-- ============================================================

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('ELECTRONICS', 'Electronics', NULL, 'Y', 1);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('COMPUTERS', 'Computers', 'ELECTRONICS', 'Y', 10);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('PHONES', 'Phones & Accessories', 'ELECTRONICS', 'Y', 20);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('CLOTHING', 'Clothing & Apparel', NULL, 'Y', 2);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('MENS', 'Mens Clothing', 'CLOTHING', 'Y', 10);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('WOMENS', 'Womens Clothing', 'CLOTHING', 'Y', 20);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('BOOKS', 'Books & Media', NULL, 'Y', 3);

INSERT INTO app.product_categories (category_code, category_name, parent_category, is_active, display_order)
VALUES ('HOME', 'Home & Garden', NULL, 'Y', 4);

-- ============================================================
-- INSERT: Order Status Codes
-- ============================================================

INSERT INTO app.order_status_codes (status_code, status_name, description, is_terminal, is_active, color_hex, display_order)
VALUES ('PENDING', 'Pending', 'Order received, awaiting processing', 'N', 'Y', '#FFA500', 1);

INSERT INTO app.order_status_codes (status_code, status_name, description, is_terminal, is_active, color_hex, display_order)
VALUES ('PROCESSING', 'Processing', 'Order is being prepared', 'N', 'Y', '#1E90FF', 2);

INSERT INTO app.order_status_codes (status_code, status_name, description, is_terminal, is_active, color_hex, display_order)
VALUES ('SHIPPED', 'Shipped', 'Order has been shipped', 'N', 'Y', '#9370DB', 3);

INSERT INTO app.order_status_codes (status_code, status_name, description, is_terminal, is_active, color_hex, display_order)
VALUES ('DELIVERED', 'Delivered', 'Order delivered to customer', 'Y', 'Y', '#32CD32', 4);

INSERT INTO app.order_status_codes (status_code, status_name, description, is_terminal, is_active, color_hex, display_order)
VALUES ('CANCELLED', 'Cancelled', 'Order cancelled', 'Y', 'Y', '#DC143C', 5);

-- ============================================================
-- INSERT: Shipping Methods
-- ============================================================

INSERT INTO app.shipping_methods (method_code, method_name, base_cost, estimated_days, is_active, requires_signature, display_order)
VALUES ('STANDARD', 'Standard Shipping', 10.00, 5, 'Y', 'N', 1);

INSERT INTO app.shipping_methods (method_code, method_name, base_cost, estimated_days, is_active, requires_signature, display_order)
VALUES ('EXPRESS', 'Express Shipping', 25.00, 2, 'Y', 'N', 2);

INSERT INTO app.shipping_methods (method_code, method_name, base_cost, estimated_days, is_active, requires_signature, display_order)
VALUES ('OVERNIGHT', 'Overnight Delivery', 45.00, 1, 'Y', 'Y', 3);

INSERT INTO app.shipping_methods (method_code, method_name, base_cost, estimated_days, is_active, requires_signature, display_order)
VALUES ('PICKUP', 'Store Pickup', 0.00, 0, 'Y', 'N', 4);

-- ============================================================
-- INSERT: Users
-- ============================================================

-- Generate user IDs from sequence
INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'john.doe', 'john.doe@example.com', 'ACTIVE', 'CUSTOMER', 'STANDARD', SYSTIMESTAMP);

INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'jane.admin', 'jane.admin@example.com', 'ACTIVE', 'ADMIN', 'ENTERPRISE', SYSTIMESTAMP);

INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'bob.vendor', 'bob@vendor.com', 'ACTIVE', 'VENDOR', 'PREMIUM', SYSTIMESTAMP);

INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'alice.customer', 'alice@example.com', 'ACTIVE', 'CUSTOMER', 'PREMIUM', SYSTIMESTAMP);

INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'charlie.partner', 'charlie@partner.com', 'ACTIVE', 'PARTNER', 'ENTERPRISE', SYSTIMESTAMP);

INSERT INTO app.users (user_id, username, email, status, user_type_code, account_tier, created_at)
VALUES (app.seq_users.NEXTVAL, 'inactive.user', 'inactive@example.com', 'INACTIVE', 'CUSTOMER', 'STANDARD', SYSTIMESTAMP - 365);

-- ============================================================
-- INSERT: Products
-- ============================================================

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Laptop Pro 15"', 'High-performance laptop with 16GB RAM', 1299.99, 50, 'Electronics', 'COMPUTERS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Wireless Mouse', 'Ergonomic wireless mouse with USB receiver', 29.99, 200, 'Electronics', 'COMPUTERS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Smartphone X', 'Latest smartphone with 128GB storage', 899.99, 100, 'Electronics', 'PHONES');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'USB-C Cable', 'Durable 6ft USB-C charging cable', 12.99, 500, 'Electronics', 'PHONES');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Cotton T-Shirt', 'Premium cotton t-shirt in multiple colors', 24.99, 300, 'Clothing', 'MENS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Denim Jeans', 'Classic fit denim jeans', 59.99, 150, 'Clothing', 'MENS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Summer Dress', 'Lightweight summer dress', 49.99, 75, 'Clothing', 'WOMENS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Programming Guide', 'Complete guide to modern programming', 39.99, 120, 'Books', 'BOOKS');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Garden Tool Set', '10-piece garden tool kit', 79.99, 45, 'Home & Garden', 'HOME');

INSERT INTO app.products (product_id, name, description, price, stock_qty, category, category_code)
VALUES (app.seq_products.NEXTVAL, 'Coffee Maker', 'Programmable 12-cup coffee maker', 89.99, 80, 'Home & Garden', 'HOME');

-- ============================================================
-- INSERT: Orders (Sample completed orders)
-- ============================================================

-- Order 1: Completed order for john.doe
INSERT INTO app.orders (order_id, user_id, total_amount, status, shipping_addr, shipping_method, shipping_cost, created_at, completed_at)
VALUES (app.seq_orders.NEXTVAL, 1, 1342.97, 'DELIVERED', '123 Main St, Anytown, USA', 'STANDARD', 10.00, SYSTIMESTAMP - 30, SYSTIMESTAMP - 25);

-- Order items for order 1000
INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1000, 1, 1, 1299.99);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1000, 2, 1, 29.99);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1000, 4, 1, 12.99);

-- Order 2: Active order for alice.customer
INSERT INTO app.orders (order_id, user_id, total_amount, status, shipping_addr, shipping_method, shipping_cost, created_at)
VALUES (app.seq_orders.NEXTVAL, 4, 974.98, 'PROCESSING', '456 Oak Ave, Springfield', 'EXPRESS', 25.00, SYSTIMESTAMP - 2);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1001, 3, 1, 899.99);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1001, 5, 3, 24.99);

-- Order 3: Pending order for john.doe
INSERT INTO app.orders (order_id, user_id, total_amount, status, shipping_addr, shipping_method, shipping_cost, created_at)
VALUES (app.seq_orders.NEXTVAL, 1, 149.98, 'PENDING', '123 Main St, Anytown, USA', 'STANDARD', 0.00, SYSTIMESTAMP - 1);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1002, 6, 2, 59.99);

INSERT INTO app.order_items (item_id, order_id, product_id, quantity, unit_price)
VALUES (app.seq_orders.NEXTVAL, 1002, 2, 1, 29.99);

-- ============================================================
-- COMMIT
-- ============================================================

COMMIT;
