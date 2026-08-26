CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note VARCHAR(100) COMMENT 'User notes'
) ENGINE=InnoDB;

CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(10,2) DEFAULT 0,
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_orders_user ON orders(user_id);

ALTER TABLE users ADD COLUMN last_login TIMESTAMP NULL;

DROP COLUMN note FROM users;

-- Unsupported: Oracle specific sequence syntax
CREATE SEQUENCE users_seq START WITH 1;
