"""
Re-analisis completo de TODOS los registros Salesforce en SQL.
Actualiza:
- modelo y serial_number desde TSI
- Clasificacion de adjuntos con logica hibrida (keywords + Azure OpenAI)
- Scores en columnas attachments_*
"""
import sys
import pyodbc

sys.path.insert(0, r'C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto')

from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER
from API_Salesforce import (
    connect_salesforce,
    obtener_modelo_serial_tsi,
    validar_adjuntos_requeridos,
    obtener_repair_date,
    obtener_coverage_type,
)
from logger import log
from Ponderaciones import PONDERACIONES_STD_SF, PONDERACIONES_STD_SF_PC


def _connect_sql():
    conn_str = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def _get_tsifacts_tsi(sf, claim_number: str) -> str | None:
    """Obtiene el TSI ID de un Claim."""
    try:
        query = f"SELECT TSINumber__c FROM Claim WHERE Name = '{claim_number}'"
        data = sf.query(query)
        records = data.get("records", [])
        if records:
            return records[0].get("TSINumber__c")
    except Exception as e:
        log.error("Error obteniendo TSI para %s: %s", claim_number, e)
    return None


def main():
    log.info("=" * 70)
    log.info("RE-ANALISIS COMPLETO: Salesforce Factory Warranty")
    log.info("=" * 70)

    sf = connect_salesforce()
    log.info("Conexion Salesforce OK")

    conn = _connect_sql()
    cursor = conn.cursor()

    # Obtener todos los Claims Salesforce
    cursor.execute("""
        SELECT claim_number
        FROM mr_warranty.reclamos_procesados
        WHERE plataforma = 'Salesforce'
        AND tipo_garantia = 'Factory Warranty'
        ORDER BY claim_number
    """)
    claims = [row[0] for row in cursor.fetchall()]
    log.info("Claims Salesforce Factory Warranty a re-analizar: %d", len(claims))

    actualizados = 0
    errores = 0
    sin_tsi = 0

    for i, claim_number in enumerate(claims, 1):
        try:
            log.info("[%d/%d] Procesando %s...", i, len(claims), claim_number)

            # 1. Obtener TSI ID
            tsi_id = _get_tsifacts_tsi(sf, claim_number)
            if not tsi_id:
                log.info("  Sin TSI asociado, saltando")
                sin_tsi += 1
                continue

            # 2. Obtener modelo y serial del TSI
            modelo_serial = obtener_modelo_serial_tsi(tsi_id)
            modelo = modelo_serial.get("modelo", "")
            serial = modelo_serial.get("serial", "")

            # 3. Obtener Claim ID (necesario para adjuntos)
            query_claim = f"SELECT Id FROM Claim WHERE Name = '{claim_number}'"
            data = sf.query(query_claim)
            claim_id = data["records"][0].get("Id") if data["records"] else None

            if not claim_id:
                log.warning("  No se pudo obtener Claim ID")
                errores += 1
                continue

            # 4. Clasificar adjuntos con logica hibrida
            adjuntos = validar_adjuntos_requeridos(claim_id, tsi_id, claim_data={
                "modelo": modelo,
                "serial": serial,
            })
            clasif = adjuntos["clasificacion"]

            # 5. Calcular scores segun PONDERACIONES_STD_SF
            score_plm = PONDERACIONES_STD_SF["plm"] if clasif["plm"] else 0
            score_aceite = PONDERACIONES_STD_SF["analisis_aceite"] if clasif["analisis_aceite"] else 0
            score_datapacks = PONDERACIONES_STD_SF["datapacks"] if clasif["datapacks"] else 0
            score_tr = PONDERACIONES_STD_SF["technical_report"] if clasif["reporte_tecnico"] else 0
            score_photos = PONDERACIONES_STD_SF["photographs"] if clasif["fotografias"] else 0

            tr_reason = (
                "; ".join(clasif["reporte_tecnico"])
                if clasif["reporte_tecnico"]
                else "No encontrado"
            )
            plm_reason = (
                "; ".join(clasif["plm"]) if clasif["plm"] else "No encontrado"
            )
            aceite_reason = (
                "; ".join(clasif["analisis_aceite"])
                if clasif["analisis_aceite"]
                else "No encontrado"
            )
            datapacks_reason = (
                "; ".join(clasif["datapacks"])
                if clasif["datapacks"]
                else "No encontrado"
            )
            photos_reason = (
                "; ".join(clasif["fotografias"])
                if clasif["fotografias"]
                else "No encontrado"
            )

            # 5b. Obtener CoverageType y Repair Date
            coverage = obtener_coverage_type(claim_id)
            coverage_type = coverage.get("coverage_type", "")
            es_pc = (coverage_type == "PC - Parts and Components")
            repair_date = obtener_repair_date(claim_id)

            # 5c. Seleccionar ponderaciones según PC o FW normal
            pond = PONDERACIONES_STD_SF_PC if es_pc else PONDERACIONES_STD_SF

            # 5d. Recalcular scores con ponderaciones correctas
            score_plm = pond["plm"] if clasif["plm"] else 0
            score_aceite = pond["analisis_aceite"] if clasif["analisis_aceite"] else 0
            score_datapacks = pond["datapacks"] if clasif["datapacks"] else 0
            score_tr = pond["technical_report"] if clasif["reporte_tecnico"] else 0
            score_photos = pond["photographs"] if clasif["fotografias"] else 0

            # 6. UPDATE en SQL
            cursor.execute("""
                UPDATE mr_warranty.reclamos_procesados
                SET
                    modelo = ?,
                    serial_number = ?,
                    coverage_type = ?,
                    repair_date = ?,
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
                WHERE claim_number = ? AND plataforma = 'Salesforce'
            """, modelo, serial, coverage_type, repair_date,
                score_plm, plm_reason,
                score_aceite, aceite_reason,
                score_datapacks, datapacks_reason,
                score_tr, tr_reason,
                score_photos, photos_reason,
                adjuntos["total_adjuntos"],
                adjuntos["adjuntos_en_claim"],
                adjuntos["adjuntos_en_case"],
                claim_number,
            )

            if cursor.rowcount > 0:
                actualizados += 1
                log.info("  modelo=%s serial=%s coverage=%s TR=%.2f PLM=%.2f PHOTOS=%.2f",
                        modelo, serial, coverage_type[:20], score_tr, score_plm, score_photos)

            if i % 5 == 0:
                conn.commit()
                log.info("  Checkpoint: %d/%d procesados (%d OK, %d sin TSI, %d errores)",
                        i, len(claims), actualizados, sin_tsi, errores)

        except Exception as e:
            errores += 1
            log.error("[%d/%d] %s: %s", i, len(claims), claim_number, e)
            continue

    conn.commit()
    conn.close()

    log.info("=" * 70)
    log.info("RE-ANALISIS COMPLETADO")
    log.info("  Total procesados:    %d", len(claims))
    log.info("  Actualizados:        %d", actualizados)
    log.info("  Sin TSI asociado:    %d", sin_tsi)
    log.info("  Errores:             %d", errores)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
