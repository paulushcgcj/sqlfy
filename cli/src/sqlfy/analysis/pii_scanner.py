from __future__ import annotations

import re
from dataclasses import dataclass

from sqlfy.domain.schema_state import SchemaState


@dataclass
class PiiColumnFinding:
    table_name: str
    column_name: str
    column_type: str
    pii_categories: list[str]  # e.g. ["email", "name", "phone"]
    confidence: float  # 0.0–1.0
    evidence: str  # the pattern that matched


@dataclass
class PiiScanResult:
    findings: list[PiiColumnFinding]
    tables_scanned: int
    columns_scanned: int
    pii_table_count: int
    pii_column_count: int


PII_PATTERNS: dict[str, list[str]] = {
    "name": [r"(first|last|full|display|user|person|customer|client)_?name", r"\bname\b"],
    "email": [r"e_?mail", r"email_?addr"],
    "phone": [r"(phone|mobile|cell|fax|tel)(_?num(ber)?)?"],
    "address": [r"(addr|address|street|city|state|province|postal|zip|postcode)"],
    "date_of_birth": [r"(dob|birth_?date|birth_?dt|birthdate|date_of_birth)"],
    "ssn": [r"(ssn|social_?security|sin\b|national_?id|tax_?id|vat_?id)"],
    "gender": [r"\bgender\b", r"\bsex\b"],
    "ip_address": [r"ip_?addr(ess)?", r"\bip\b"],
    "location": [r"(latitude|longitude|lat\b|lon\b|lng\b|geo_?loc)"],
    "national_id": [r"(passport|driver_?licen[cs]e|driving_?licen[cs]e|id_?number|govt_?id)"],
    "financial": [r"(credit_?card|card_?number|iban|account_?num|bank_?account|routing_?num)"],
    "health": [r"(diagnosis|medication|health|medical|patient|icd_?\d)", r"\bweight\b", r"\bheight\b"],
    "username": [r"(username|login|user_?id|screen_?name|handle)"],
    "password": [r"(password|passwd|pwd|secret|token|api_?key|auth_?key)"],
    "cookie": [r"(session_?id|cookie|jwt|bearer)"],
}


def scan_pii(
    state: SchemaState,
    extra_patterns: dict[str, list[str]] | None = None,
) -> PiiScanResult:
    """Scan a schema for PII columns.

    Returns:
        PiiScanResult: findings, counts
    """
    merged_patterns: dict[str, list[str]] = {
        category: patterns.copy()
        for category, patterns in PII_PATTERNS.items()
    }
    if extra_patterns:
        for category, patterns in extra_patterns.items():
            merged_patterns[category].extend(patterns)

    findings: list[PiiColumnFinding] = []
    tables_scanned = len(state.tables)
    columns_scanned = 0
    for table in state.tables.values():
        for column in table.columns:
            columns_scanned += 1
            column_name = column.name.casefold()
            categories: list[str] = []
            evidence = ""
            confidence = 0.0

            for category, patterns in merged_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, column_name):
                        categories.append(category)
                        evidence = pattern
                        confidence = max(confidence, 0.6)

            if column.comment:
                for category, patterns in merged_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, column.comment):
                            categories.append(category)
                            evidence = pattern
                            confidence = max(confidence, 0.6)

            if categories:
                # Exact match boost
                if any(re.fullmatch(p, column_name) for p in merged_patterns.get(categories[0], [])):
                    confidence = 1.0

                # Strong partial match boost
                strong_patterns = [p for cat, ps in merged_patterns.items() for p in ps if "_" in p]
                if any(re.search(p, column_name) for p in strong_patterns):
                    confidence = max(confidence, 0.8)

                findings.append(
                    PiiColumnFinding(
                        table_name=table.name,
                        column_name=column.name,
                        column_type=column.data_type,
                        pii_categories=categories,
                        confidence=confidence,
                        evidence=evidence,
                    )
                )

    pii_tables = len({f.table_name for f in findings})
    pii_columns = len(findings)

    return PiiScanResult(
        findings=findings,
        tables_scanned=tables_scanned,
        columns_scanned=columns_scanned,
        pii_table_count=pii_tables,
        pii_column_count=pii_columns,
    )
