"""
Sincroniza coverage_type desde ClaimCoverage para todos los Claims Salesforce en SQL
y re-procesa los que son PC - Parts and Components.
"""
import sys
import pyodbc
sys.path.insert(0, r'C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto')

from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER
from API_Salesforce import (
    connect_salesforce, process_salesforce_data, obtener_chatter_case_dict,
    obtener_modelo_serial_tsi, descargar_y_subir_adjuntos_ia,
    validar_adjuntos_requeridos, obtener_repair_date, obtener_coverage_type,
)
from Promps import (
    validar_adjunto_con_ia, validar_photographs_con_ia,
    extraer_fecha_instalacion_parte, validar_work_order_con_ia,
    validar_purchase_invoice_con_ia,
)
from ValidacionFC_SF import ValidacionStandard
from Ponderaciones import PONDERACIONES_STD_SF_PC
from utils import parse_datetime, strip_tz, calcular_score_adjuntos
from logger import log


def _connect_sql():
    return pyodbc.connect(
        f'DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};'
        f'UID={SQL_USERNAME};PWD={SQL_PASSWORD};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    )


def main():
    log.info("=" * 70)
    log.info("SINCRONIZAR coverage_type + RE-PROCESAR claims PC")
    log.info("=" * 70)

    sf = connect_salesforce()
    conn = _connect_sql()
    cursor = conn.cursor()

    # 1. Obtener todos los Claims Salesforce en SQL
    cursor.execute("SELECT claim_number FROM mr_warranty.reclamos_procesados WHERE plataforma = 'Salesforce'")
    all_claims = [row[0] for row in cursor.fetchall()]
    log.info("Claims Salesforce en SQL: %d", len(all_claims))

    # 2. Para cada claim, obtener CoverageType desde Salesforce
    actualizados_coverage = 0
    pc_claims = []

    for i, claim_name in enumerate(all_claims, 1):
        try:
            # Obtener Claim ID
            query_claim = f"SELECT Id FROM Claim WHERE Name = '{claim_name}'"
            data = sf.query(query_claim)
            records = data.get("records", [])
            if not records:
                continue
            claim_id = records[0]["Id"]

            # Obtener CoverageType
            coverage = obtener_coverage_type(claim_id)
            coverage_type = coverage.get("coverage_type", "")

            # Actualizar en SQL
            cursor.execute("""
                UPDATE mr_warranty.reclamos_procesados
                SET coverage_type = ?, updated_at = SYSUTCDATETIME()
                WHERE claim_number = ? AND plataforma = 'Salesforce'
            """, coverage_type if coverage_type else None, claim_name)

            if cursor.rowcount > 0:
                actualizados_coverage += 1

            if coverage_type == "PC - Parts and Components":
                pc_claims.append(claim_name)
                log.info("[%d/%d] %s: PC - Parts and Components", i, len(all_claims), claim_name)
            else:
                log.info("[%d/%d] %s: %s", i, len(all_claims), claim_name, coverage_type or "Sin coverage")

        except Exception as e:
            log.error("[%d/%d] Error con %s: %s", i, len(all_claims), claim_name, e)

    conn.commit()
    log.info("Coverage types actualizados: %d", actualizados_coverage)
    log.info("Claims PC encontrados: %d", len(pc_claims))

    # 3. Re-procesar claims PC
    if pc_claims:
        log.info("=" * 70)
        log.info("RE-PROCESANDO %d CLAIMS PC", len(pc_claims))
        log.info("=" * 70)

        procesados = 0
        errores = 0

        for i, claim_name in enumerate(pc_claims, 1):
            try:
                log.info("[%d/%d] Procesando %s (PC)...", i, len(pc_claims), claim_name)

                datos = process_salesforce_data(claim_name)
                claim_id = datos.get("Id_claim")
                tsi_id = datos.get("TSINumber__c")

                # Coverage y repair_date
                coverage = obtener_coverage_type(claim_id)
                repair_date_raw = obtener_repair_date(claim_id)
                repair_date_dt = strip_tz(parse_datetime(repair_date_raw)) if repair_date_raw else None

                # Modelo y serial
                modelo_serial = obtener_modelo_serial_tsi(tsi_id) if tsi_id else {"modelo": "", "serial": ""}

                # Chatter
                Diccionario_Chatter = obtener_chatter_case_dict(tsi_id) if tsi_id else {"CantidadPosts": 0, "Posts": []}

                # Descargar adjuntos
                adjuntos_ia = descargar_y_subir_adjuntos_ia(claim_id, tsi_id, ["reporte_tecnico", "plm", "fotografias"])

                # Validar TR
                tr_result = validar_adjunto_con_ia(
                    adjuntos_ia["reporte_tecnico"]["urls_sas"],
                    modelo_serial["modelo"], modelo_serial["serial"],
                    "reporte técnico", PONDERACIONES_STD_SF_PC["technical_report"]
                )

                # Validar PLM
                plm_result = validar_adjunto_con_ia(
                    adjuntos_ia["plm"]["urls_sas"],
                    modelo_serial["modelo"], modelo_serial["serial"],
                    "PLM", PONDERACIONES_STD_SF_PC["plm"]
                )

                # Validar Photos
                photo_result = validar_photographs_con_ia(
                    adjuntos_ia["fotografias"]["urls_sas"],
                    datos.get("Complaint__c", ""), datos.get("Cause__c", ""),
                    PONDERACIONES_STD_SF_PC["photographs"]
                )

                # Clasificación de presencia
                adjuntos_validacion = validar_adjuntos_requeridos(claim_id, tsi_id, claim_data={
                    "modelo": modelo_serial.get("modelo", ""),
                    "serial": modelo_serial.get("serial", ""),
                })
                clasif = adjuntos_validacion["clasificacion"]

                # Extraer fecha instalación
                resultado_fi = extraer_fecha_instalacion_parte(datos, Diccionario_Chatter)
                fecha_instalacion_str = resultado_fi.get("fecha")
                fecha_instalacion_dt = strip_tz(parse_datetime(fecha_instalacion_str)) if fecha_instalacion_str else None
                fecha_instalacion_reason = resultado_fi.get("razon", "")
                log.info("  Fecha instalacion: %s (conf=%.2f)", fecha_instalacion_str, resultado_fi.get("confianza", 0))

                # Validar Work Order
                all_urls = adjuntos_ia["fotografias"]["urls_sas"] + adjuntos_ia["reporte_tecnico"]["urls_sas"]
                work_order_result = validar_work_order_con_ia(all_urls, datos)
                log.info("  Work Order: score=%.2f", work_order_result["score"])

                # Validar Purchase Invoice
                purchase_invoice_result = validar_purchase_invoice_con_ia(all_urls, datos)
                log.info("  Purchase Invoice: score=%.2f", purchase_invoice_result["score"])

                # Validación estándar con lógica PC
                DiccionarioValidacionSTD = ValidacionStandard(
                    datos, es_pc=True, fecha_instalacion_parte=fecha_instalacion_str
                )

                # Calcular scores con Opción C (max keywords e IA)
                pond = PONDERACIONES_STD_SF_PC
                adj_scores = calcular_score_adjuntos(clasif, pond, tr_result, plm_result, photo_result)

                score_total = sum([
                    DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion", 0),
                    DiccionarioValidacionSTD.get("Repair_deadline_ponderacion", 0),
                    DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion", 0),
                    adj_scores["score_tr"], adj_scores["score_photos"], adj_scores["score_plm"],
                    adj_scores["score_aceite"], adj_scores["score_datapacks"],
                    work_order_result["score"], purchase_invoice_result["score"],
                ])

                log.info("  Score total: %.2f", score_total)
                log.info("  Warr=%.2f | Repair=%.2f | Claim=%.2f | TR=%.2f | Photos=%.2f | PLM=%.2f | Oil=%.2f | Data=%.2f | WO=%.2f | Inv=%.2f",
                         DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion", 0),
                         DiccionarioValidacionSTD.get("Repair_deadline_ponderacion", 0),
                         DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion", 0),
                         adj_scores["score_tr"], adj_scores["score_photos"], adj_scores["score_plm"],
                         adj_scores["score_aceite"], adj_scores["score_datapacks"],
                         work_order_result["score"], purchase_invoice_result["score"])

                # UPDATE en SQL
                cursor.execute("""
                    UPDATE mr_warranty.reclamos_procesados SET
                        modelo=?, serial_number=?, coverage_type=?, repair_date=?,
                        part_installation_date=?, part_installation_date_reason=?,
                        within_standard_warranty=?, within_standard_warranty_reason=?,
                        repair_deadline=?, repair_deadline_reason=?,
                        claim_deadline=?, claim_deadline_reason=?,
                        attachments_technical_report_sf=?, attachments_technical_report_sf_reason=?,
                        attachments_photographs_sf=?, attachments_photographs_sf_reason=?,
                        attachments_plm=?, attachments_plm_reason=?,
                        attachments_oil_analysis=?, attachments_oil_analysis_reason=?,
                        attachments_datapacks=?, attachments_datapacks_reason=?,
                        work_order=?, work_order_reason=?,
                        purchase_invoice=?, purchase_invoice_reason=?,
                        updated_at=SYSUTCDATETIME()
                    WHERE claim_number=? AND plataforma='Salesforce'
                """,
                    modelo_serial.get("modelo", ""), modelo_serial.get("serial", ""),
                    coverage.get("coverage_type", ""), repair_date_dt,
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
                    procesados += 1
                    log.info("  OK - Actualizado en SQL")

            except Exception as e:
                errores += 1
                log.error("[%d/%d] Error con %s: %s", i, len(pc_claims), claim_name, e)

        conn.commit()
        log.info("=" * 70)
        log.info("RE-PROCESAMIENTO COMPLETADO")
        log.info("  Claims PC:        %d", len(pc_claims))
        log.info("  Procesados:       %d", procesados)
        log.info("  Errores:          %d", errores)
        log.info("=" * 70)

    conn.close()


if __name__ == "__main__":
    main()
