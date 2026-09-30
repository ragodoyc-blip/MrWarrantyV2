import json
import math
from datetime import datetime

import pyodbc

from mr_warranty.config.config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD
from mr_warranty.core.logger import log


TABLE_NAME = "mr_warranty.reclamos_procesados"

KEY_TO_DB_COLUMN = {
    "ClaimNumber": "claim_number",
    "Plataforma": "plataforma",
    "createdon": "createdon",
    "Status": "status",
    "TipoGarantia": "tipo_garantia",
    "FC expiration": "fc_expiration",
    "Repair deadline": "repair_deadline",
    "Claim deadline": "claim_deadline",
    "Technical report": "technical_report",
    "Invoices": "invoices",
    "Work order": "work_order",
    "Photographs": "photographs",
    "FC expiration reason": "fc_expiration_reason",
    "Repair deadline reason": "repair_deadline_reason",
    "Claim deadline reason": "claim_deadline_reason",
    "Technical report reason": "technical_report_reason",
    "Invoices reason": "invoices_reason",
    "work order reason": "work_order_reason",
    "Photographs reason": "photographs_reason",
    "Cost Coverage Labor": "cost_coverage_labor",
    "Cost Coverage Labor reason": "cost_coverage_labor_reason",
    "Cost Coverage Other Expenses": "cost_coverage_other_expenses",
    "Cost Coverage Other Expenses reason": "cost_coverage_other_expenses_reason",
    "Cost Coverage Mileage": "cost_coverage_mileage",
    "Cost Coverage Mileage reason": "cost_coverage_mileage_reason",
    "Comentario": "comentario",
    "__PowerAppsId__": "powerapps_id",
    "Modelo": "modelo",
    "Serial Number": "serial_number",
    "Submitted Date": "submitted_date",
    "Coverage Type": "coverage_type",
    "Repair Date": "repair_date",
    "Part Installation Date": "part_installation_date",
    "Part Installation Date reason": "part_installation_date_reason",
    "Work Order": "work_order",
    "Work Order reason": "work_order_reason",
    "Purchase Invoice": "purchase_invoice",
    "Purchase Invoice reason": "purchase_invoice_reason",
    "Within standard warranty": "within_standard_warranty",
    "Within standard warranty reason": "within_standard_warranty_reason",
    "Standard Rate": "standard_rate",
    "Standard Rate reason": "standard_rate_reason",
    "Root Cause Analysis": "root_cause_analysis",
    "Root Cause Analysis reason": "root_cause_analysis_reason",
    "Cost Coverage Parts ": "cost_coverage_parts",
    "Cost Coverage Parts reason": "cost_coverage_parts_reason",
    # ── Nuevas columnas para EDT Factory Warranty (Adjuntos) ──
    "Attachments PLM": "attachments_plm",
    "Attachments PLM reason": "attachments_plm_reason",
    "Attachments Oil Analysis": "attachments_oil_analysis",
    "Attachments Oil Analysis reason": "attachments_oil_analysis_reason",
    "Attachments Datapacks": "attachments_datapacks",
    "Attachments Datapacks reason": "attachments_datapacks_reason",
    "Attachments Technical Report SF": "attachments_technical_report_sf",
    "Attachments Technical Report SF reason": "attachments_technical_report_sf_reason",
    "Attachments Photographs SF": "attachments_photographs_sf",
    "Attachments Photographs SF reason": "attachments_photographs_sf_reason",
    # ── SPCR informativo 0-1 para PA - Special Policy (no resta peso) ──
    "SPCR": "attachments_special_policy",
    "SPCR reason": "attachments_special_policy_reason",
    "Total Adjuntos": "total_adjuntos",
    "Adjuntos en Claim": "adjuntos_en_claim",
    "Adjuntos en Case": "adjuntos_en_case",
    "Claim_Type__c": "claim_type__c",
    "IA calls": "ia_calls",
    "IA input tokens": "ia_input_tokens",
    "IA output tokens": "ia_output_tokens",
    "IA estimated cost USD": "ia_estimated_cost_usd",
}
SCORE_COLUMNS = {
    "fc_expiration",
    "repair_deadline",
    "claim_deadline",
    "technical_report",
    "invoices",
    "work_order",
    "photographs",
    "cost_coverage_labor",
    "cost_coverage_other_expenses",
    "cost_coverage_mileage",
    "within_standard_warranty",
    "standard_rate",
    "root_cause_analysis",
    "cost_coverage_parts",
    # ── Nuevas columnas de adjuntos ──
    "attachments_plm",
    "attachments_oil_analysis",
    "attachments_datapacks",
    "attachments_technical_report_sf",
    "attachments_photographs_sf",
    # ── SPCR informativo 0-1 (PA) ──
    "attachments_special_policy",
    # ── Costo IA ──
    "ia_estimated_cost_usd",
}

INT_COLUMNS = {
    "total_adjuntos",
    "adjuntos_en_claim",
    "adjuntos_en_case",
    "ia_calls",
    "ia_input_tokens",
    "ia_output_tokens",
}

DATE_COLUMNS = {
    "createdon",
    "submitted_date",
    "repair_date",
    "part_installation_date",
}

UPSERT_COLUMNS = [
    "claim_number",
    "plataforma",
    "createdon",
    "status",
    "tipo_garantia",
    "fc_expiration",
    "repair_deadline",
    "claim_deadline",
    "technical_report",
    "invoices",
    "work_order",
    "photographs",
    "fc_expiration_reason",
    "repair_deadline_reason",
    "claim_deadline_reason",
    "technical_report_reason",
    "invoices_reason",
    "work_order_reason",
    "photographs_reason",
    "cost_coverage_labor",
    "cost_coverage_labor_reason",
    "cost_coverage_other_expenses",
    "cost_coverage_other_expenses_reason",
    "cost_coverage_mileage",
    "cost_coverage_mileage_reason",
    "comentario",
    "powerapps_id",
    "within_standard_warranty",
    "within_standard_warranty_reason",
    "standard_rate",
    "standard_rate_reason",
    "root_cause_analysis",
    "root_cause_analysis_reason",
    "cost_coverage_parts",
    "cost_coverage_parts_reason",
    # ── Nuevas columnas para EDT Factory Warranty (Adjuntos) ──
    "attachments_plm",
    "attachments_plm_reason",
    "attachments_oil_analysis",
    "attachments_oil_analysis_reason",
    "attachments_datapacks",
    "attachments_datapacks_reason",
    "attachments_technical_report_sf",
    "attachments_technical_report_sf_reason",
    "attachments_photographs_sf",
    "attachments_photographs_sf_reason",
    "total_adjuntos",
    "adjuntos_en_claim",
    "adjuntos_en_case",
    "modelo",
    "serial_number",
    "submitted_date",
    "coverage_type",
    "claim_type__c",
    "repair_date",
    "part_installation_date",
    "part_installation_date_reason",
    "purchase_invoice",
    "purchase_invoice_reason",
    "attachments_special_policy",
    "attachments_special_policy_reason",
    "ia_calls",
    "ia_input_tokens",
    "ia_output_tokens",
    "ia_estimated_cost_usd",
    "raw_payload_json",
]


def is_sql_enabled():
    from mr_warranty.config.config import SQL_ENABLED
    return SQL_ENABLED


def _connection_string():
    server = SQL_SERVER
    database = SQL_DATABASE
    username = SQL_USERNAME
    password = SQL_PASSWORD
    driver = SQL_DRIVER

    if not server or not database or not username or not password:
        raise ValueError(
            "Faltan variables SQL_SERVER, SQL_DATABASE, SQL_USERNAME o SQL_PASSWORD en el entorno."
        )

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def _connect():
    return pyodbc.connect(_connection_string())


def _to_datetime_or_none(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_float_or_none(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _normalize_record(record):
    normalized = {col: None for col in UPSERT_COLUMNS}

    for key, value in record.items():
        col = KEY_TO_DB_COLUMN.get(key)
        if col is None:
            continue
        if col in DATE_COLUMNS:
            normalized[col] = _to_datetime_or_none(value)
        elif col in SCORE_COLUMNS:
            normalized[col] = _to_float_or_none(value)
        elif col in INT_COLUMNS:
            normalized[col] = _to_int_or_none(value)
        else:
            if value is None:
                normalized[col] = None
            elif isinstance(value, float) and math.isnan(value):
                normalized[col] = None
            else:
                text = str(value).strip()
                normalized[col] = None if text.lower() in {"", "nan", "nat", "none"} else text

    normalized["claim_number"] = str(record.get("ClaimNumber", "")).strip()
    normalized["plataforma"] = str(record.get("Plataforma", "")).strip()
    normalized["raw_payload_json"] = json.dumps(record, ensure_ascii=False, default=str)

    if not normalized["claim_number"]:
        raise ValueError("El registro no contiene ClaimNumber.")
    if not normalized["plataforma"]:
        raise ValueError("El registro no contiene Plataforma.")

    return normalized


def ensure_sql_schema():
    ddl = f"""
IF OBJECT_ID('{TABLE_NAME}', 'U') IS NULL
BEGIN
    CREATE TABLE {TABLE_NAME} (
        claim_number NVARCHAR(100) NOT NULL,
        plataforma NVARCHAR(50) NOT NULL,
        createdon DATETIMEOFFSET NULL,
        status NVARCHAR(100) NULL,
        tipo_garantia NVARCHAR(100) NULL,
        fc_expiration DECIMAL(10,4) NULL,
        repair_deadline DECIMAL(10,4) NULL,
        claim_deadline DECIMAL(10,4) NULL,
        technical_report DECIMAL(10,4) NULL,
        invoices DECIMAL(10,4) NULL,
        work_order DECIMAL(10,4) NULL,
        photographs DECIMAL(10,4) NULL,
        fc_expiration_reason NVARCHAR(MAX) NULL,
        repair_deadline_reason NVARCHAR(MAX) NULL,
        claim_deadline_reason NVARCHAR(MAX) NULL,
        technical_report_reason NVARCHAR(MAX) NULL,
        invoices_reason NVARCHAR(MAX) NULL,
        work_order_reason NVARCHAR(MAX) NULL,
        photographs_reason NVARCHAR(MAX) NULL,
        cost_coverage_labor DECIMAL(10,4) NULL,
        cost_coverage_labor_reason NVARCHAR(MAX) NULL,
        cost_coverage_other_expenses DECIMAL(10,4) NULL,
        cost_coverage_other_expenses_reason NVARCHAR(MAX) NULL,
        cost_coverage_mileage DECIMAL(10,4) NULL,
        cost_coverage_mileage_reason NVARCHAR(MAX) NULL,
        comentario NVARCHAR(MAX) NULL,
        powerapps_id NVARCHAR(150) NULL,
        within_standard_warranty DECIMAL(10,4) NULL,
        within_standard_warranty_reason NVARCHAR(MAX) NULL,
        standard_rate DECIMAL(10,4) NULL,
        standard_rate_reason NVARCHAR(MAX) NULL,
        root_cause_analysis DECIMAL(10,4) NULL,
        root_cause_analysis_reason NVARCHAR(MAX) NULL,
        cost_coverage_parts DECIMAL(10,4) NULL,
        cost_coverage_parts_reason NVARCHAR(MAX) NULL,
        -- ── Nuevas columnas para EDT Factory Warranty (Adjuntos) ──
        attachments_plm DECIMAL(10,4) NULL,
        attachments_plm_reason NVARCHAR(MAX) NULL,
        attachments_oil_analysis DECIMAL(10,4) NULL,
        attachments_oil_analysis_reason NVARCHAR(MAX) NULL,
        attachments_datapacks DECIMAL(10,4) NULL,
        attachments_datapacks_reason NVARCHAR(MAX) NULL,
        attachments_technical_report_sf DECIMAL(10,4) NULL,
        attachments_technical_report_sf_reason NVARCHAR(MAX) NULL,
        attachments_photographs_sf DECIMAL(10,4) NULL,
        attachments_photographs_sf_reason NVARCHAR(MAX) NULL,
        total_adjuntos INT NULL,
        adjuntos_en_claim INT NULL,
        adjuntos_en_case INT NULL,
        modelo NVARCHAR(100) NULL,
        serial_number NVARCHAR(100) NULL,
        submitted_date DATETIMEOFFSET NULL,
        coverage_type NVARCHAR(100) NULL,
        claim_type__c NVARCHAR(100) NULL,
        repair_date DATETIMEOFFSET NULL,
        part_installation_date DATETIMEOFFSET NULL,
        part_installation_date_reason NVARCHAR(MAX) NULL,
        purchase_invoice DECIMAL(10,4) NULL,
        purchase_invoice_reason NVARCHAR(MAX) NULL,
        attachments_special_policy DECIMAL(10,4) NULL,
        attachments_special_policy_reason NVARCHAR(MAX) NULL,
        ia_calls INT NULL,
        ia_input_tokens BIGINT NULL,
        ia_output_tokens BIGINT NULL,
        ia_estimated_cost_usd DECIMAL(10,4) NULL,
        raw_payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT DF_reclamos_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT DF_reclamos_updated_at DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_reclamos_procesados PRIMARY KEY (claim_number, plataforma)
    );

    CREATE INDEX IX_reclamos_procesados_createdon ON {TABLE_NAME} (createdon);
END
"""

    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(ddl)
        conn.commit()


def _upsert_sql():
    src_select = ",\n            ".join([f"? AS {col}" for col in UPSERT_COLUMNS])
    update_set = ",\n            ".join(
        [f"target.{col} = src.{col}" for col in UPSERT_COLUMNS if col not in {"claim_number", "plataforma"}]
    )
    insert_cols = ", ".join(UPSERT_COLUMNS)
    insert_vals = ", ".join([f"src.{col}" for col in UPSERT_COLUMNS])

    return f"""
MERGE {TABLE_NAME} AS target
USING (
    SELECT
            {src_select}
) AS src
ON target.claim_number = src.claim_number
AND target.plataforma = src.plataforma
WHEN MATCHED THEN
    UPDATE SET
            {update_set},
            target.updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT ({insert_cols}, created_at, updated_at)
    VALUES ({insert_vals}, SYSUTCDATETIME(), SYSUTCDATETIME());
"""


def upsert_reclamo_sql(record, conn=None):
    normalized = _normalize_record(record)
    params = [normalized[col] for col in UPSERT_COLUMNS]
    sql = _upsert_sql()

    if conn is not None:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return

    with _connect() as own_conn:
        cursor = own_conn.cursor()
        cursor.execute(sql, params)
        own_conn.commit()


def bulk_upsert_reclamos(records):
    if not records:
        return 0

    ensure_sql_schema()
    total = 0
    with _connect() as conn:
        cursor = conn.cursor()
        for item in records:
            normalized = _normalize_record(item)
            params = [normalized[col] for col in UPSERT_COLUMNS]
            cursor.execute(_upsert_sql(), params)
            total += 1
        conn.commit()
    return total


def bulk_update_status_sql(status_por_reclamo):
    if not status_por_reclamo:
        return 0

    ensure_sql_schema()
    updated = 0
    with _connect() as conn:
        cursor = conn.cursor()
        for (claim_number, plataforma), status_val in status_por_reclamo.items():
            claim_text = str(claim_number).strip()
            plat_text = str(plataforma).strip()
            if not claim_text:
                continue

            cursor.execute(
                f"""
UPDATE {TABLE_NAME}
SET status = ?, updated_at = SYSUTCDATETIME()
WHERE claim_number = ? AND plataforma = ?;
""",
                status_val,
                claim_text,
                plat_text,
            )
            if cursor.rowcount and cursor.rowcount > 0:
                updated += cursor.rowcount
        conn.commit()

    return updated


def get_processed_claim_keys_sql():
    """Retorna un set de tuplas (claim_number, plataforma) ya presentes en SQL."""
    ensure_sql_schema()
    processed = set()

    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT claim_number, plataforma FROM {TABLE_NAME};")
        for claim_number, plataforma in cursor.fetchall():
            claim_text = str(claim_number).strip() if claim_number is not None else ""
            plataforma_text = str(plataforma).strip() if plataforma is not None else ""
            if claim_text:
                processed.add((claim_text, plataforma_text))

    return processed
