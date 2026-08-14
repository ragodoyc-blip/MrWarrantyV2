"""
Procesamiento de Claims PC - Parts and Components con la logica nueva.
Solo procesa claims con CoverageType = 'PC - Parts and Components'.
"""
import sys
import pyodbc

sys.path.insert(0, r'C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto')

from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER
from API_Salesforce import (
    connect_salesforce,
    process_salesforce_data,
    obtener_chatter_case_dict,
    obtener_modelo_serial_tsi,
    descargar_y_subir_adjuntos_ia,
    validar_adjuntos_requeridos,
    obtener_repair_date,
    obtener_coverage_type,
)
from utils import parse_datetime, strip_tz, calcular_score_adjuntos
from Promps import (
    validar_adjunto_con_ia,
    validar_photographs_con_ia,
    extraer_fecha_instalacion_parte,
    validar_work_order_con_ia,
    validar_purchase_invoice_con_ia,
)
from ValidacionFC_SF import ValidacionStandard
from Ponderaciones import PONDERACIONES_STD_SF_PC
from logger import log


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


def main():
    log.info("=" * 70)
    log.info("PROCESAMIENTO PC - PARTS AND COMPONENTS (logica nueva)")
    log.info("=" * 70)

    sf = connect_salesforce()
    log.info("Conexion Salesforce OK")

    # Buscar todos los Claims con CoverageType = PC en Salesforce
    query_cc = "SELECT ClaimId FROM ClaimCoverage WHERE CoverageType = 'PC - Parts and Components'"
    data_cc = sf.query_all(query_cc)
    claim_ids_pc = list(set(r.get("ClaimId") for r in data_cc.get("records", []) if r.get("ClaimId")))
    log.info("Claims con CoverageType PC: %d", len(claim_ids_pc))

    # Obtener nombres de claims
    ids_str = "', '".join(claim_ids_pc[:100])
    query_claims = f"SELECT Id, Name, Status, TSINumber__c FROM Claim WHERE Id IN ('{ids_str}')"
    data_claims = sf.query_all(query_claims)
    claims_info = {r["Id"]: r for r in data_claims.get("records", [])}

    conn = _connect_sql()
    cursor = conn.cursor()

    actualizados = 0
    errores = 0

    for i, (claim_id, info) in enumerate(claims_info.items(), 1):
        claim_name = info.get("Name", "")
        status = info.get("Status", "")

        if status != "Submitted":
            log.info("[%d/%d] %s: Status=%s (no Submitted), saltando", i, len(claims_info), claim_name, status)
            continue

        try:
            log.info("[%d/%d] Procesando %s (PC)...", i, len(claims_info), claim_name)

            # 1. Obtener datos del reclamo
            datos = process_salesforce_data(claim_name)
            tsi_id = datos.get("TSINumber__c")

            # 2. Obtener CoverageType y Repair Date
            coverage = obtener_coverage_type(claim_id)
            coverage_type = coverage.get("coverage_type", "")
            repair_date_raw = obtener_repair_date(claim_id)
            repair_date_dt = strip_tz(parse_datetime(repair_date_raw)) if repair_date_raw else None

            # 3. Obtener modelo y serial
            modelo_serial = obtener_modelo_serial_tsi(tsi_id) if tsi_id else {"modelo": "", "serial": ""}
            modelo = modelo_serial.get("modelo", "")
            serial = modelo_serial.get("serial", "")

            # 4. Obtener Chatter
            Diccionario_Chatter = obtener_chatter_case_dict(tsi_id) if tsi_id else {"CantidadPosts": 0, "Posts": []}

            # 5. Descargar adjuntos
            try:
                adjuntos_ia = descargar_y_subir_adjuntos_ia(claim_id, tsi_id, ["reporte_tecnico", "plm", "fotografias"])
            except Exception as e:
                log.error("  Error descargando adjuntos: %s", e)
                adjuntos_ia = {"reporte_tecnico": {"urls_sas": [], "titulos": []}, "plm": {"urls_sas": [], "titulos": []}, "fotografias": {"urls_sas": [], "titulos": []}}

            # 6. Validar technical_report
            try:
                tr_result = validar_adjunto_con_ia(adjuntos_ia["reporte_tecnico"]["urls_sas"], modelo, serial, "reporte técnico", PONDERACIONES_STD_SF_PC["technical_report"])
            except Exception as e:
                log.error("  Error IA TR: %s", e)
                tr_result = {"score": 0, "reason": f"Error: {e}"}

            # 7. Validar PLM
            try:
                plm_result = validar_adjunto_con_ia(adjuntos_ia["plm"]["urls_sas"], modelo, serial, "PLM", PONDERACIONES_STD_SF_PC["plm"])
            except Exception as e:
                log.error("  Error IA PLM: %s", e)
                plm_result = {"score": 0, "reason": f"Error: {e}"}

            # 8. Validar photographs
            try:
                photo_result = validar_photographs_con_ia(adjuntos_ia["fotografias"]["urls_sas"], datos.get("Complaint__c", ""), datos.get("Cause__c", ""), PONDERACIONES_STD_SF_PC["photographs"])
            except Exception as e:
                log.error("  Error IA Photos: %s", e)
                photo_result = {"score": 0, "reason": f"Error: {e}"}

            # 9. Validaciones de presencia
            adjuntos_validacion = validar_adjuntos_requeridos(claim_id, tsi_id, claim_data={"modelo": modelo, "serial": serial})
            clasif = adjuntos_validacion["clasificacion"]

            # 10. Extraer fecha de instalacion con IA
            try:
                resultado_fi = extraer_fecha_instalacion_parte(datos, Diccionario_Chatter)
                fecha_instalacion_str = resultado_fi.get("fecha")
                fecha_instalacion_dt = strip_tz(parse_datetime(fecha_instalacion_str)) if fecha_instalacion_str else None
                fecha_instalacion_reason = resultado_fi.get("razon", "")
                log.info("  Fecha instalacion: %s (confianza=%.2f)", fecha_instalacion_str, resultado_fi.get("confianza", 0))
            except Exception as e:
                log.error("  Error extrayendo fecha instalacion: %s", e)
                fecha_instalacion = None
                fecha_instalacion_reason = f"Error: {e}"

            # 11. Validar Work Order
            try:
                all_urls = adjuntos_ia["fotografias"]["urls_sas"] + adjuntos_ia["reporte_tecnico"]["urls_sas"]
                work_order_result = validar_work_order_con_ia(all_urls, datos)
                log.info("  Work Order: score=%.2f", work_order_result["score"])
            except Exception as e:
                log.error("  Error Work Order: %s", e)
                work_order_result = {"score": 0, "reason": f"Error: {e}"}

            # 12. Validar Purchase Invoice
            try:
                purchase_invoice_result = validar_purchase_invoice_con_ia(all_urls, datos)
                log.info("  Purchase Invoice: score=%.2f", purchase_invoice_result["score"])
            except Exception as e:
                log.error("  Error Purchase Invoice: %s", e)
                purchase_invoice_result = {"score": 0, "reason": f"Error: {e}"}

            # 13. Validacion estandar con logica PC
            DiccionarioValidacionSTD = ValidacionStandard(datos, es_pc=True, fecha_instalacion_parte=fecha_instalacion_str)

            # 14. Calcular scores con Opción C (max keywords e IA)
            pond = PONDERACIONES_STD_SF_PC
            adj_scores = calcular_score_adjuntos(clasif, pond, tr_result, plm_result, photo_result)

            score_total = (
                DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion", 0) +
                DiccionarioValidacionSTD.get("Repair_deadline_ponderacion", 0) +
                DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion", 0) +
                adj_scores["score_tr"] + adj_scores["score_photos"] + adj_scores["score_plm"] +
                adj_scores["score_aceite"] + adj_scores["score_datapacks"] +
                work_order_result["score"] + purchase_invoice_result["score"]
            )

            log.info("  Score total: %.2f", score_total)
            log.info("  Warrant: %.2f | Repair: %.2f | Claim: %.2f | TR: %.2f | Photos: %.2f | PLM: %.2f | Oil: %.2f | Data: %.2f | WO: %.2f | Invoice: %.2f",
                     DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion", 0),
                     DiccionarioValidacionSTD.get("Repair_deadline_ponderacion", 0),
                     DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion", 0),
                     adj_scores["score_tr"], adj_scores["score_photos"], adj_scores["score_plm"],
                     adj_scores["score_aceite"], adj_scores["score_datapacks"],
                     work_order_result["score"], purchase_invoice_result["score"])

            # 15. UPDATE en SQL
            cursor.execute("""
                UPDATE mr_warranty.reclamos_procesados
                SET
                    modelo = ?,
                    serial_number = ?,
                    coverage_type = ?,
                    repair_date = ?,
                    part_installation_date = ?,
                    part_installation_date_reason = ?,
                    within_standard_warranty = ?,
                    within_standard_warranty_reason = ?,
                    repair_deadline = ?,
                    repair_deadline_reason = ?,
                    claim_deadline = ?,
                    claim_deadline_reason = ?,
                    attachments_technical_report_sf = ?,
                    attachments_technical_report_sf_reason = ?,
                    attachments_photographs_sf = ?,
                    attachments_photographs_sf_reason = ?,
                    attachments_plm = ?,
                    attachments_plm_reason = ?,
                    attachments_oil_analysis = ?,
                    attachments_oil_analysis_reason = ?,
                    attachments_datapacks = ?,
                    attachments_datapacks_reason = ?,
                    work_order = ?,
                    work_order_reason = ?,
                    purchase_invoice = ?,
                    purchase_invoice_reason = ?,
                    updated_at = SYSUTCDATETIME()
                WHERE claim_number = ? AND plataforma = 'Salesforce'
            """,
                modelo, serial, coverage_type, repair_date_dt,
                fecha_instalacion_dt, fecha_instalacion_reason,
                DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion", 0),
                DiccionarioValidacionSTD.get("within_standard_warranty_reason", ""),
                DiccionarioValidacionSTD.get("Repair_deadline_ponderacion", 0),
                DiccionarioValidacionSTD.get("Repair_deadline_reason", ""),
                DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion", 0),
                DiccionarioValidacionSTD.get("Claim_Deadline_reason", ""),
                adj_scores["score_tr"], adj_scores["tr_reason"],
                adj_scores["score_photos"], adj_scores["photos_reason"],
                adj_scores["score_plm"], adj_scores["plm_reason"],
                adj_scores["score_aceite"], adj_scores["aceite_reason"],
                adj_scores["score_datapacks"], adj_scores["datapacks_reason"],
                work_order_result["score"], work_order_result["reason"],
                purchase_invoice_result["score"], purchase_invoice_result["reason"],
                claim_name,
            )

            if cursor.rowcount > 0:
                actualizados += 1
                log.info("  OK - Actualizado en SQL")

            if i % 5 == 0:
                conn.commit()
                log.info("  Checkpoint: %d/%d procesados", i, len(claims_info))

        except Exception as e:
            errores += 1
            log.error("[%d/%d] %s: %s", i, len(claims_info), claim_name, e)
            continue

    conn.commit()
    conn.close()

    log.info("=" * 70)
    log.info("PROCESAMIENTO PC COMPLETADO")
    log.info("  Total procesados: %d", len(claims_info))
    log.info("  Actualizados:     %d", actualizados)
    log.info("  Errores:          %d", errores)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
