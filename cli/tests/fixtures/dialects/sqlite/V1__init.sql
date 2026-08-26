CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX idx_orders_user ON orders(user_id);

ALTER TABLE users ADD COLUMN last_login TIMESTAMP;

DROP TABLE orders;

-- Unsupported: ALTER TABLE DROP COLUMN is limited in SQLite <3.35
ALTER TABLE users DROP COLUMN note;
