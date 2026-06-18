import re
from dataclasses import dataclass

from ..domain.schema_state import SchemaState


@dataclass
class PiiColumnFinding:
    table_name: str
    column_name: str
    column_type: str
    pii_categories: list[str]
    confidence: float
    evidence: str


@dataclass
class PiiScanResult:
    findings: list[PiiColumnFinding]
    tables_scanned: int
    columns_scanned: int
    pii_table_count: int
    pii_column_count: int


PII_PATTERNS: dict[str, list[str]] = {
    "name":        [r"(first|last|full|display|user|person|customer|client)_?name", r"\bname\b"],
    "email":       [r"e_?mail", r"email_?addr"],
    "phone":       [r"(phone|mobile|cell|fax|tel)(_?num(ber)?)?"],
    "address":     [r"(addr|address|street|city|state|province|postal|zip|postcode)"],
    "date_of_birth": [r"(dob|birth_?date|birth_?dt|birthdate|date_of_birth)"],
    "ssn":         [r"(ssn|social_?security|sin\b|national_?id|tax_?id|vat_?id)"],
    "gender":      [r"\bgender\b", r"\bsex\b"],
    "ip_address":  [r"ip_?addr(ess)?", r"\bip\b"],
    "location":    [r"(latitude|longitude|lat\b|lon\b|lng\b|geo_?loc)"],
    "national_id": [r"(passport|driver_?licen[cs]e|driving_?licen[cs]e|id_?number|govt_?id)"],
    "financial":   [r"(credit_?card|card_?number|iban|account_?num|bank_?account|routing_?num)"],
    "health":      [r"(diagnosis|medication|health|medical|patient|icd_?\d)", r"\bweight\b", r"\bheight\b"],
    "username":    [r"(username|login|user_?id|screen_?name|handle)"],
    "password":    [r"(password|passwd|pwd|secret|token|api_?key|auth_?key)"],
    "cookie":      [r"(session_?id|cookie|jwt|bearer)"],
}


_CANONICAL_NAMES: dict[str, set[str]] = {
    "name": {"name", "full_name", "first_name", "last_name", "user_name", "display_name", "person_name", "customer_name", "client_name"},
    "email": {"email", "e_mail", "email_address"},
    "phone": {"phone", "phone_number", "mobile", "mobile_number", "cell", "cell_number", "fax_number", "tel_number"},
    "address": {"address", "street", "city", "state", "province", "postal_code", "zip", "zip_code", "postcode"},
    "date_of_birth": {"dob", "date_of_birth", "birth_date", "birthdate"},
    "ssn": {"ssn", "social_security", "social_security_number", "national_id", "tax_id", "vat_id"},
    "gender": {"gender", "sex"},
    "ip_address": {"ip", "ip_address"},
    "location": {"latitude", "longitude", "lat", "lon", "lng", "geo_loc"},
    "national_id": {"passport", "passport_number", "driver_license", "drivers_license", "driving_license", "id_number", "govt_id"},
    "financial": {"credit_card", "credit_card_number", "card_number", "iban", "account_number", "bank_account", "routing_number"},
    "health": {"diagnosis", "diagnosis_code", "icd", "icd_code"},
    "username": {"username", "login", "user_id", "screen_name", "handle"},
    "password": {"password", "passwd"},
    "cookie": {"session_id", "cookie"},
}


_STRONG_TERMS: dict[str, set[str]] = {
    "name": {"name"},
    "email": {"email", "mail"},
    "phone": {"phone", "mobile", "cell", "fax", "tel"},
    "address": {"address", "street", "city", "state", "province", "postal", "zip", "postcode"},
    "date_of_birth": {"dob", "birth", "birthdate"},
    "ssn": {"ssn", "social", "security", "national", "tax", "vat"},
    "gender": {"gender", "sex"},
    "ip_address": {"ip", "address"},
    "location": {"latitude", "longitude", "lat", "lon", "lng", "geo"},
    "national_id": {"passport", "license", "licence", "id", "govt"},
    "financial": {"credit", "card", "iban", "account", "bank", "routing"},
    "health": {"diagnosis", "medication", "health", "medical", "patient", "icd", "weight", "height"},
    "username": {"username", "login", "user", "screen", "handle"},
    "password": {"password", "passwd", "pwd", "secret", "token", "key"},
    "cookie": {"session", "cookie", "jwt", "bearer"},
}


def scan_pii(
    state: SchemaState,
    extra_patterns: dict[str, list[str]] | None = None,
) -> PiiScanResult:
    patterns = {**PII_PATTERNS}
    if extra_patterns:
        for cat, pats in extra_patterns.items():
            patterns.setdefault(cat, []).extend(pats)

    findings: list[PiiColumnFinding] = []
    pii_tables: set[str] = set()
    tables_scanned = len(state.tables)
    columns_scanned = 0

    for table_name, table in state.tables.items():
        table_has_pii = False
        for column in table.columns:
            columns_scanned += 1
            col_name = column.name.casefold()
            col_comment = column.comment.casefold() if column.comment else ""
            col_components = col_name.split("_")

            col_categories: list[tuple[str, float, str]] = []

            for category, category_patterns in patterns.items():
                name_matched = False
                matched_patterns: list[str] = []

                for pat in category_patterns:
                    if re.search(pat, col_name):
                        name_matched = True
                        matched_patterns.append(pat)
                    elif any(re.search(pat, comp) for comp in col_components):
                        name_matched = True
                        matched_patterns.append(pat)
                    elif col_comment and re.search(pat, col_comment):
                        matched_patterns.append(pat)

                if not matched_patterns:
                    continue

                evidence = matched_patterns[0]
                confidence = _compute_confidence(category, col_name, name_matched)
                col_categories.append((category, confidence, evidence))

            if col_categories:
                categories = [c[0] for c in col_categories]
                best = max(col_categories, key=lambda x: x[1])
                findings.append(PiiColumnFinding(
                    table_name=table_name,
                    column_name=column.name,
                    column_type=column.data_type,
                    pii_categories=categories,
                    confidence=best[1],
                    evidence=best[2],
                ))
                table_has_pii = True

        if table_has_pii:
            pii_tables.add(table_name)

    return PiiScanResult(
        findings=findings,
        tables_scanned=tables_scanned,
        columns_scanned=columns_scanned,
        pii_table_count=len(pii_tables),
        pii_column_count=len(findings),
    )


def _compute_confidence(
    category: str,
    col_name: str,
    name_matched: bool,
) -> float:
    if not name_matched:
        return 0.6

    if col_name in _CANONICAL_NAMES.get(category, set()):
        return 1.0

    components = set(col_name.split("_"))
    strong_terms = _STRONG_TERMS.get(category, set())
    if components & strong_terms:
        return 0.8

    return 0.6


def format_text(result: PiiScanResult) -> str:
    lines: list[str] = []
    a = lines.append

    a(f"PII Scan — {result.tables_scanned} tables, {result.columns_scanned} columns scanned")
    a(f"Found {result.pii_column_count} PII columns across {result.pii_table_count} tables.")
    a("")

    high = [f for f in result.findings if f.confidence >= 0.8]
    medium = [f for f in result.findings if 0.6 <= f.confidence < 0.8]

    if high:
        a("HIGH CONFIDENCE (\u22650.8)")
        for f in sorted(high, key=lambda x: (-x.confidence, x.table_name, x.column_name)):
            a(f"  {f.table_name}.{f.column_name:<30} {f.pii_categories[0]:<20} confidence={f.confidence:.2f}")
        a("")

    if medium:
        a("MEDIUM CONFIDENCE (0.6\u20130.8)")
        for f in sorted(medium, key=lambda x: (-x.confidence, x.table_name, x.column_name)):
            a(f"  {f.table_name}.{f.column_name:<30} {f.pii_categories[0]:<20} confidence={f.confidence:.2f}")
        a("")

    if not result.findings:
        a("No PII columns found.")
        a("")

    # Tables with most PII columns
    from collections import Counter
    table_counts = Counter(f.table_name for f in result.findings)
    top = table_counts.most_common(5)
    if top:
        a("Tables with most PII columns:")
        for tbl, cnt in top:
            a(f"  {tbl} ({cnt} columns)")
        a("")

    return "\n".join(lines)
