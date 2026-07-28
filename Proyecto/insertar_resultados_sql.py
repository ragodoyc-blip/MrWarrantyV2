"""
Inserta los resultados del análisis EDT Factory Warranty en SQL.
"""

import json
import pyodbc
from config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD
from analisis_completo_edt import main as ejecutar_analisis


def get_connection_string():
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def preparar_registro_para_sql(resultado: dict) -> dict:
    """Convierte el resultado del análisis a formato SQL."""
    return {
        "claim_number": resultado.get("claim", ""),
        "plataforma": "Salesforce",
        "createdon": resultado.get("created_date"),
        "status": resultado.get("status", ""),
        "tipo_garantia": "Factory Warranty",
        # Validaciones principales
        "repair_deadline": resultado.get("repair_deadline", 0),
        "repair_deadline_reason": resultado.get("repair_deadline_reason", ""),
        "claim_deadline": resultado.get("claim_deadline", 0),
        "claim_deadline_reason": resultado.get("claim_deadline_reason", ""),
        "within_standard_warranty": resultado.get("within_warranty", 0),
        "within_standard_warranty_reason": resultado.get("within_warranty_reason", ""),
        "root_cause_analysis": resultado.get("root_cause", 0),
        "root_cause_analysis_reason": resultado.get("root_cause_reason", ""),
        # Adjuntos EDT
        "attachments_plm": resultado.get("plm", 0),
        "attachments_plm_reason": resultado.get("plm_docs", ""),
        "attachments_oil_analysis": resultado.get("oil_analysis", 0),
        "attachments_oil_analysis_reason": resultado.get("oil_docs", ""),
        "attachments_datapacks": resultado.get("datapacks", 0),
        "attachments_datapacks_reason": resultado.get("datapacks_docs", ""),
        "attachments_technical_report_sf": resultado.get("technical_report", 0),
        "attachments_technical_report_sf_reason": resultado.get("technical_report_docs", ""),
        "attachments_photographs_sf": resultado.get("photographs", 0),
        "attachments_photographs_sf_reason": resultado.get("photographs_docs", ""),
        "total_adjuntos": resultado.get("total_adjuntos", 0),
        "adjuntos_en_claim": resultado.get("adjuntos_en_claim", 0),
        "adjuntos_en_case": resultado.get("adjuntos_en_case", 0),
    }


def upsert_to_sql(records: list[dict]):
    """Inserta o actualiza registros en SQL."""
    conn_str = get_connection_string()
    
    with pyodbc.connect(conn_str) as conn:
        cursor = conn.cursor()
        
        for record in records:
            sql = """
                MERGE dbo.reclamos_procesados AS target
                USING (SELECT ? AS claim_number, ? AS plataforma) AS src
                ON target.claim_number = src.claim_number 
                AND target.plataforma = src.plataforma
                WHEN MATCHED THEN
                    UPDATE SET
                        status = ?,
                        tipo_garantia = ?,
                        repair_deadline = ?,
                        repair_deadline_reason = ?,
                        claim_deadline = ?,
                        claim_deadline_reason = ?,
                        within_standard_warranty = ?,
                        within_standard_warranty_reason = ?,
                        root_cause_analysis = ?,
                        root_cause_analysis_reason = ?,
                        attachments_plm = ?,
                        attachments_plm_reason = ?,
                        attachments_oil_analysis = ?,
                        attachments_oil_analysis_reason = ?,
                        attachments_datapacks = ?,
                        attachments_datapacks_reason = ?,
                        attachments_technical_report_sf = ?,
                        attachments_technical_report_sf_reason = ?,
                        attachments_photographs_sf = ?,
                        attachments_photographs_sf_reason = ?,
                        total_adjuntos = ?,
                        adjuntos_en_claim = ?,
                        adjuntos_en_case = ?,
                        updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (claim_number, plataforma, status, tipo_garantia,
                            repair_deadline, repair_deadline_reason,
                            claim_deadline, claim_deadline_reason,
                            within_standard_warranty, within_standard_warranty_reason,
                            root_cause_analysis, root_cause_analysis_reason,
                            attachments_plm, attachments_plm_reason,
                            attachments_oil_analysis, attachments_oil_analysis_reason,
                            attachments_datapacks, attachments_datapacks_reason,
                            attachments_technical_report_sf, attachments_technical_report_sf_reason,
                            attachments_photographs_sf, attachments_photographs_sf_reason,
                            total_adjuntos, adjuntos_en_claim, adjuntos_en_case)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            
            params = (
                record["claim_number"], record["plataforma"],
                record["status"], record["tipo_garantia"],
                record["repair_deadline"], record["repair_deadline_reason"],
                record["claim_deadline"], record["claim_deadline_reason"],
                record["within_standard_warranty"], record["within_standard_warranty_reason"],
                record["root_cause_analysis"], record["root_cause_analysis_reason"],
                record["attachments_plm"], record["attachments_plm_reason"],
                record["attachments_oil_analysis"], record["attachments_oil_analysis_reason"],
                record["attachments_datapacks"], record["attachments_datapacks_reason"],
                record["attachments_technical_report_sf"], record["attachments_technical_report_sf_reason"],
                record["attachments_photographs_sf"], record["attachments_photographs_sf_reason"],
                record["total_adjuntos"], record["adjuntos_en_claim"], record["adjuntos_en_case"],
                # Para INSERT
                record["claim_number"], record["plataforma"],
                record["status"], record["tipo_garantia"],
                record["repair_deadline"], record["repair_deadline_reason"],
                record["claim_deadline"], record["claim_deadline_reason"],
                record["within_standard_warranty"], record["within_standard_warranty_reason"],
                record["root_cause_analysis"], record["root_cause_analysis_reason"],
                record["attachments_plm"], record["attachments_plm_reason"],
                record["attachments_oil_analysis"], record["attachments_oil_analysis_reason"],
                record["attachments_datapacks"], record["attachments_datapacks_reason"],
                record["attachments_technical_report_sf"], record["attachments_technical_report_sf_reason"],
                record["attachments_photographs_sf"], record["attachments_photographs_sf_reason"],
                record["total_adjuntos"], record["adjuntos_en_claim"], record["adjuntos_en_case"],
            )
            
            cursor.execute(sql, params)
        
        conn.commit()
        print(f"[OK] {len(records)} registros insertados/actualizados en SQL")


def main():
    print("\n=== Inserción de Resultados EDT en SQL ===\n")
    
    # 1. Ejecutar análisis
    print("1. Ejecutando análisis...")
    resultados = ejecutar_analisis()
    
    # 2. Preparar registros para SQL
    print("\n2. Preparando registros...")
    registros_sql = []
    for r in resultados:
        if "error" not in r:
            registros_sql.append(preparar_registro_para_sql(r))
    
    print(f"   Registros válidos: {len(registros_sql)}")
    
    # 3. Insertar en SQL
    print("\n3. Insertando en SQL...")
    upsert_to_sql(registros_sql)
    
    print("\n=== Proceso completado ===")


if __name__ == "__main__":
    main()
