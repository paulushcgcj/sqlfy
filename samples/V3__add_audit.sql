-- Audit trail
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
CREATE INDEX app.idx_audit_user  ON app.audit_log(changed_by, changed_at);
