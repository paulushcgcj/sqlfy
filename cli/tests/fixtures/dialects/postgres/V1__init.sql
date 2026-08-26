CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount NUMERIC(10,2) DEFAULT 0,
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_orders_user ON orders(user_id);

ALTER TABLE users ADD COLUMN last_login TIMESTAMP;

DROP TABLE orders;

-- Unsupported: MySQL specific ENGINE clause
CREATE TABLE temp (id INT) ENGINE=InnoDB;
