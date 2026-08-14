import os

import pandas as pd

from config import (
    SQL_TABLE,
    SQL_DATABASE,
    WC_TYPE_FIELD_CAMPAIGN,
    WC_TYPE_STANDARD,
    WC_TYPE_IGNORED,
    SQIS_STATUS_UNDER_APPLICATION,
    DEFAULT_CREATEDON_FILTER,
)
from logger import log

from Promps import (
    InformeTecnico,
    OrdenTrabajo,
    facturas_promp,
    fotografias,
    validar_adjunto_con_ia,
    validar_photographs_con_ia,
    extraer_fecha_instalacion_parte,
    validar_work_order_con_ia,
    validar_purchase_invoice_con_ia,
)
from ValidacionStandart import ValidacionStandadWC, ValidacionStandartPartes, Stanrate
from ValidacionFC_SF import ValidacionFC_SF, ValidacionCostCoverage_SF, ValidacionStandard
from ValidacionFC import (
    DatosGeneralesCampana,
    ValidacionCampanaGeneral,
    ValidacionCampanaPartes,
    ValidacionCostCoverage,
)
from API_SQIS import Allgetwarrantyclaim, getWarrantyclaimid, get_offerstatus_labels
from API_Salesforce import (
    process_salesforce_data,
    reclamos_pendientes,
    obtener_chatter_case_dict,
    obtener_modelo_serial_tsi,
    descargar_y_subir_adjuntos_ia,
    validar_adjuntos_requeridos,
    obtener_repair_date,
    obtener_coverage_type,
)
from Ponderaciones import PONDERACIONES_STD, PONDERACIONES_FC, PONDERACIONES_STD_SF, PONDERACIONES_STD_SF_PC
from Adjuntos_SQIS import AdjuntosSQIS
from Archivo_to_excel import encolar_registro, actualizar_status_masivo, sincronizar_pendientes_excel
from sql_storage import is_sql_enabled, get_processed_claim_keys_sql
from utils import calcular_score_adjuntos

# Configurar la tabla SQL
os.environ["SQL_DATABASE"] = SQL_DATABASE
import sql_storage
sql_storage.TABLE_NAME = SQL_TABLE


def convertir_sas_dict_a_imagenes_con_paginacion(sas_dict: dict, max_imagenes: int = 49) -> list[dict]:
    """Convierte un diccionario de URLs SAS en bloques de mensajes para IA."""
    bloques = []
    contador = 0

    for doc_name, urls in sas_dict.items():
        for i, url in enumerate(urls, start=1):
            if contador >= max_imagenes:
                return bloques

            bloques.append({"type": "text", "text": f"{doc_name} - página {i}"})
            bloques.append({"type": "image_url", "image_url": {"url": url}})

            contador += 1
            if contador >= max_imagenes:
                return bloques

    return bloques


def Analisis():
    """Analiza reclamos pendientes de SQIS y Salesforce, retorna los no procesados."""
    df_wc = Allgetwarrantyclaim()
    df_wc["Plataforma"] = "SQIS"

    df_sf = reclamos_pendientes()[["Name", "Status"]]
    df_sf["Plataforma"] = "Salesforce"
    df_sf.rename(columns={"Name": "kom_claimnumber", "Status": "status_origen"}, inplace=True)

    df_wc = df_wc[df_wc["createdon"] >= DEFAULT_CREATEDON_FILTER]

    # Obtener reclamos ya procesados desde SQL
    df_procesado_list = []
    if not is_sql_enabled():
        log.info("SQL deshabilitado. Asumiendo que no hay reclamos procesados.")
    else:
        try:
            processed_keys = get_processed_claim_keys_sql()
            df_procesado_list = [str(claim).strip() for (claim, _plat) in processed_keys if claim]
            log.info("Reclamos procesados en SQL: %d", len(df_procesado_list))
        except Exception as e:
            log.error("Error al leer reclamos procesados desde SQL: %s", e)
            df_procesado_list = []

    df_wc["createdon"] = pd.to_datetime(df_wc["createdon"])
    df_wc = df_wc[df_wc["_kom_offerclaimtype_value"].isin([WC_TYPE_FIELD_CAMPAIGN, WC_TYPE_STANDARD])]

    status_map_sqis = get_offerstatus_labels()
    df_wc["status_origen"] = df_wc["kom_offerstatus"].map(status_map_sqis).fillna(df_wc["kom_offerstatus"].astype(str))

    df_todos = pd.concat([df_wc, df_sf], ignore_index=True, sort=False)

    status_por_reclamo = {
        (str(row["kom_claimnumber"]), str(row["Plataforma"])): row.get("status_origen")
        for _, row in df_todos.iterrows()
        if pd.notna(row.get("kom_claimnumber"))
    }

    df_wc_pendiente = df_wc[df_wc["kom_offerstatus"] == SQIS_STATUS_UNDER_APPLICATION]
    df_sf_procesar = df_sf[df_sf["status_origen"] == "Submitted"]
    df_candidatos_procesar = pd.concat([df_wc_pendiente, df_sf_procesar], ignore_index=True, sort=False)

    df_no_procesados = df_candidatos_procesar[~df_candidatos_procesar["kom_claimnumber"].isin(df_procesado_list)]

    reclamos_no_procesados = {
        row["kom_claimnumber"]: (
            row.get("createdon"),
            row.get("_kom_offerclaimtype_value"),
            row.get("Plataforma"),
            row.get("status_origen"),
        )
        for _, row in df_no_procesados.iterrows()
    }

    return reclamos_no_procesados, status_por_reclamo


def actualizar_estados_existentes():
    """
    Para cada claim Salesforce que ya existe en BD,
    actualiza solo el status y submitted_date desde Salesforce.
    No re-analiza los adjuntos.
    """
    from API_Salesforce import connect_salesforce
    import pyodbc
    from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER

    sf = connect_salesforce()

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
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT claim_number, status, ISNULL(CAST(submitted_date AS NVARCHAR(50)), '') as submitted_date
        FROM mr_warranty.reclamos_procesados
        WHERE plataforma = 'Salesforce'
    """)
    existentes = {row.claim_number: {"status": row.status, "submitted_date": row.submitted_date}
                   for row in cursor.fetchall()}

    log.info("Claims Salesforce en BD: %d", len(existentes))

    actualizados = 0
    sin_cambios = 0
    errores = 0

    for claim_number, info_bd in existentes.items():
        try:
            query = f"SELECT Status, SubmittedDate__c FROM Claim WHERE Name = '{claim_number}'"
            data = sf.query(query)
            records = data.get("records", [])

            if not records:
                continue

            status_sf = records[0].get("Status", "") or ""
            submitted_sf = records[0].get("SubmittedDate__c", "") or ""
            if submitted_sf and "T" in submitted_sf:
                submitted_sf = submitted_sf.split(".")[0].replace("T", " ")

            cambio = False
            if status_sf != (info_bd["status"] or ""):
                cambio = True
            if submitted_sf and submitted_sf != (info_bd["submitted_date"] or ""):
                cambio = True

            if cambio:
                cursor.execute("""
                    UPDATE mr_warranty.reclamos_procesados
                    SET status = ?, submitted_date = ?, updated_at = SYSUTCDATETIME()
                    WHERE claim_number = ? AND plataforma = 'Salesforce'
                """, status_sf, submitted_sf if submitted_sf else None, claim_number)
                actualizados += 1
                log.info("[STATUS] %s: status='%s', submitted='%s'", claim_number, status_sf, submitted_sf)
            else:
                sin_cambios += 1

        except Exception as e:
            errores += 1
            log.error("Error actualizando status de %s: %s", claim_number, e)

    conn.commit()
    conn.close()

    log.info("=" * 50)
    log.info("Sincronizacion de status:")
    log.info("  Claims en BD:    %d", len(existentes))
    log.info("  Actualizados:    %d", actualizados)
    log.info("  Sin cambios:     %d", sin_cambios)
    log.info("  Errores:         %d", errores)
    log.info("=" * 50)


def main():
    Reclamos_Revisar, status_por_reclamo = Analisis()

    # Sincronizar status de claims ya existentes en BD
    actualizar_estados_existentes()

    nuevos_registros = []
    actualizar_status_masivo(status_por_reclamo)

    total = len(Reclamos_Revisar)
    log.info("Reclamos a procesar: %d", total)

    for i, (Reclamo, (createdon, tipoWC, plataforma, status_origen)) in enumerate(Reclamos_Revisar.items(), 1):
        registro_nuevo = None

        if Reclamo == "0":
            log.info("Finalizando programa.")
            break

        log.info("=== [%d/%d] Reclamo %s | %s ===", i, total, Reclamo, plataforma)

        if plataforma == "SQIS":

            # ── FIELD CAMPAIGN ──────────────────────────────
            if tipoWC == WC_TYPE_FIELD_CAMPAIGN:
                log.info("[%s] Validación Field Campaign", Reclamo)
                RFNumber, IdReclamo, ServiceNews, DictFC = DatosGeneralesCampana(Reclamo)

                Diccionario_Reclamo, Dict_ponderaciones_fc = ValidacionCampanaGeneral(RFNumber, ServiceNews, DictFC)
                Diccionario_Reclamo_Partes = ValidacionCampanaPartes(IdReclamo, ServiceNews)
                Diccionario_cover_coverage = ValidacionCostCoverage(IdReclamo, ServiceNews, DictFC)

                Documento = convertir_sas_dict_a_imagenes_con_paginacion(AdjuntosSQIS(RFNumber))
                informetecnico_promp = InformeTecnico(Diccionario_Reclamo, Documento, "FC")
                ordendetrabajo_promp = OrdenTrabajo(Diccionario_Reclamo, Documento, "FC")
                fotogracias_promp = fotografias(Diccionario_Reclamo, Documento, "FC")

                if len(Diccionario_Reclamo_Partes) == 0:
                    Ponderacion_Facturas = {"score": PONDERACIONES_FC.get("invoices"), "reason": "No hay partes reclamadas"}
                else:
                    Ponderacion_Facturas = facturas_promp(Documento, Diccionario_Reclamo_Partes, "FC")

                registro_nuevo = {
                    "ClaimNumber": Reclamo,
                    "Plataforma": "SQIS",
                    "createdon": createdon,
                    "Status": status_origen,
                    "TipoGarantia": "Field Campaign",
                    "FC expiration": Dict_ponderaciones_fc.get("FC expiration"),
                    "FC expiration reason": Dict_ponderaciones_fc.get("FC expiration reason"),
                    "Repair deadline": Dict_ponderaciones_fc.get("Repair deadline"),
                    "Repair deadline reason": Dict_ponderaciones_fc.get("repair deadline reason"),
                    "Claim deadline": Dict_ponderaciones_fc.get("Claim deadline"),
                    "Claim deadline reason": Dict_ponderaciones_fc.get("Claim deadline reason"),
                    "Technical report": informetecnico_promp.get("score"),
                    "Technical report reason": informetecnico_promp.get("reason"),
                    "Invoices": Ponderacion_Facturas.get("score"),
                    "Invoices reason": Ponderacion_Facturas.get("reason"),
                    "Work order": ordendetrabajo_promp.get("score"),
                    "work order reason": ordendetrabajo_promp.get("reason"),
                    "Photographs": fotogracias_promp.get("score"),
                    "Photographs reason": fotogracias_promp.get("reason"),
                    "Cost Coverage Labor": Diccionario_cover_coverage.get("Labor Score"),
                    "Cost Coverage Labor reason": Diccionario_cover_coverage.get("Labor Reason"),
                    "Cost Coverage Other Expenses": Diccionario_cover_coverage.get("Other Expenses Score"),
                    "Cost Coverage Other Expenses reason": Diccionario_cover_coverage.get("Other Expenses Reason"),
                    "Cost Coverage Mileage": Diccionario_cover_coverage.get("Mileage Score"),
                    "Cost Coverage Mileage reason": Diccionario_cover_coverage.get("Mileage Reason"),
                }
                nuevos_registros.append(registro_nuevo)

            # ── STANDARD WARRANTY ───────────────────────────
            elif tipoWC == WC_TYPE_STANDARD:
                log.info("[%s] Validación Standard Warranty", Reclamo)
                IdReclamo = getWarrantyclaimid(Reclamo)

                Diccionario_Reclamo, Diccionario_std = ValidacionStandadWC(Reclamo)
                DiccionarioPartesSTD = ValidacionStandartPartes(Reclamo)
                Documento = convertir_sas_dict_a_imagenes_con_paginacion(AdjuntosSQIS(Reclamo))

                informetecnico_promp = InformeTecnico(Diccionario_Reclamo, Documento, "STD")

                if DiccionarioPartesSTD == 0:
                    Ponderacion_Facturas = {"score": PONDERACIONES_STD.get("invoices"), "reason": "No hay partes reclamadas"}
                else:
                    Ponderacion_Facturas = facturas_promp(Documento, DiccionarioPartesSTD, "STD")

                fotogracias_promp = fotografias(Diccionario_Reclamo, Documento, "STD")
                ordendetrabajo_promp = OrdenTrabajo(Diccionario_Reclamo, Documento, "STD")
                standard_rate = Stanrate(Reclamo)

                registro_nuevo = {
                    "ClaimNumber": Reclamo,
                    "Plataforma": "SQIS",
                    "createdon": createdon,
                    "Status": status_origen,
                    "TipoGarantia": "Standard",
                    "Within standard warranty": Diccionario_std.get("within standard warranty"),
                    "Within standard warranty reason": Diccionario_std.get("within standard warranty reason"),
                    "Repair deadline": Diccionario_std.get("Repair deadline"),
                    "Repair deadline reason": Diccionario_std.get("repair deadline reason"),
                    "Claim deadline": Diccionario_std.get("Claim deadline"),
                    "Claim deadline reason": Diccionario_std.get("Claim deadline reason"),
                    "Technical report": informetecnico_promp.get("score"),
                    "Technical report reason": informetecnico_promp.get("reason"),
                    "Work order": ordendetrabajo_promp.get("score"),
                    "work order reason": ordendetrabajo_promp.get("reason"),
                    "Invoices": Ponderacion_Facturas.get("score"),
                    "Invoices reason": Ponderacion_Facturas.get("reason"),
                    "Photographs": fotogracias_promp.get("score"),
                    "Photographs reason": fotogracias_promp.get("reason"),
                    "Standard Rate": standard_rate.get("standard_rate"),
                    "Standard Rate reason": standard_rate.get("standard_rate_reason"),
                }
                nuevos_registros.append(registro_nuevo)

            elif tipoWC == WC_TYPE_IGNORED:
                continue

            if registro_nuevo is not None:
                encolar_registro(registro_nuevo)
                log.info("Registro encolado: %s", registro_nuevo)

        # ── SALESFORCE ─────────────────────────────────────
        elif plataforma == "Salesforce":
            log.info("[%s] Datos desde Salesforce", Reclamo)
            Diccionario_Salesforce_Reclamo = process_salesforce_data(Reclamo)

            claim_type = Diccionario_Salesforce_Reclamo.get("ClaimType")
            if claim_type != "Factory Warranty":
                log.info("[%s] ClaimType='%s' omitido (solo Factory Warranty)", Reclamo, claim_type)
                continue

            Diccionario_Chatter = obtener_chatter_case_dict(Diccionario_Salesforce_Reclamo.get("TSINumber__c"))

            # Field Campaign
            if Diccionario_Salesforce_Reclamo.get("ClaimType") == "Field Campaign":
                log.info("[%s] Validación Field Campaign (Salesforce)", Reclamo)
                Diccionario_FC = ValidacionFC_SF(Diccionario_Salesforce_Reclamo)
                DiccionarioCostCoverage = ValidacionCostCoverage_SF(Diccionario_Salesforce_Reclamo)

                registro_nuevo = {
                    "ClaimNumber": Diccionario_Salesforce_Reclamo.get("Name"),
                    "Plataforma": "Salesforce",
                    "createdon": Diccionario_Salesforce_Reclamo.get("CreatedDate"),
                    "Status": Diccionario_Salesforce_Reclamo.get("Status"),
                    "TipoGarantia": "Field Campaign",
                    "FC expiration": Diccionario_FC.get("FC_expiration_score"),
                    "FC expiration reason": Diccionario_FC.get("FC_expiration_reason"),
                    "Claim deadline": Diccionario_FC.get("Claim_Deadline_score"),
                    "Claim deadline reason": Diccionario_FC.get("Claim_Deadline_reason"),
                    "Cost Coverage Labor": DiccionarioCostCoverage.get("Labor_score"),
                    "Cost Coverage Labor reason": DiccionarioCostCoverage.get("Labor_reason"),
                    "Cost Coverage Parts ": DiccionarioCostCoverage.get("Parts_score"),
                    "Cost Coverage Parts reason": DiccionarioCostCoverage.get("Parts_reason"),
                    "Cost Coverage Mileage": DiccionarioCostCoverage.get("Mileage_score"),
                    "Cost Coverage Mileage reason": DiccionarioCostCoverage.get("Mileage_reason"),
                }
                nuevos_registros.append(registro_nuevo)

            # Factory Warranty
            elif Diccionario_Salesforce_Reclamo.get("ClaimType") == "Factory Warranty":
                log.info("[%s] Validación Factory Warranty (Salesforce)", Reclamo)
                tsi_id = Diccionario_Salesforce_Reclamo.get("Id_case")
                claim_id = Diccionario_Salesforce_Reclamo.get("Id_claim")

                # 0. Obtener CoverageType y Repair Date
                coverage = obtener_coverage_type(claim_id)
                coverage_type = coverage.get("coverage_type", "")
                es_pc = (coverage_type == "PC - Parts and Components")
                repair_date = obtener_repair_date(claim_id)

                if es_pc:
                    log.info("[%s] CoverageType: PC - Parts and Components", Reclamo)

                # 1. Obtener modelo y serial del TSI
                modelo_serial = (
                    obtener_modelo_serial_tsi(tsi_id)
                    if tsi_id
                    else {"modelo": "", "serial": ""}
                )

                # 2. Descargar adjuntos y subir a Azure Blob
                try:
                    adjuntos_ia = descargar_y_subir_adjuntos_ia(
                        claim_id,
                        tsi_id,
                        ["reporte_tecnico", "plm", "fotografias"],
                    )
                except Exception as e:
                    log.error("[%s] Error descargando adjuntos: %s. Saltando.", Reclamo, e)
                    continue

                # 3. Validar technical_report con IA
                try:
                    pond_tr = PONDERACIONES_STD_SF_PC["technical_report"] if es_pc else PONDERACIONES_STD_SF["technical_report"]
                    tr_result = validar_adjunto_con_ia(
                        adjuntos_ia["reporte_tecnico"]["urls_sas"],
                        modelo_serial["modelo"],
                        modelo_serial["serial"],
                        "reporte técnico",
                        pond_tr,
                    )
                except Exception as e:
                    log.error("[%s] Error IA TR: %s. Saltando.", Reclamo, e)
                    continue

                # 4. Validar PLM con IA
                try:
                    pond_plm = PONDERACIONES_STD_SF_PC["plm"] if es_pc else PONDERACIONES_STD_SF["plm"]
                    plm_result = validar_adjunto_con_ia(
                        adjuntos_ia["plm"]["urls_sas"],
                        modelo_serial["modelo"],
                        modelo_serial["serial"],
                        "PLM",
                        pond_plm,
                    )
                except Exception as e:
                    log.error("[%s] Error IA PLM: %s. Saltando.", Reclamo, e)
                    continue

                # 5. Validar photographs con IA
                try:
                    photo_result = validar_photographs_con_ia(
                        adjuntos_ia["fotografias"]["urls_sas"],
                        Diccionario_Salesforce_Reclamo.get("Complaint__c", ""),
                        Diccionario_Salesforce_Reclamo.get("Cause__c", ""),
                        PONDERACIONES_STD_SF_PC["photographs"] if es_pc else PONDERACIONES_STD_SF["photographs"],
                    )
                except Exception as e:
                    log.error("[%s] Error IA Photos: %s. Saltando.", Reclamo, e)
                    continue

                # 6. Validaciones de presencia (sin IA)
                adjuntos_validacion = validar_adjuntos_requeridos(claim_id, tsi_id, claim_data={
                    "modelo": modelo_serial.get("modelo", ""),
                    "serial": modelo_serial.get("serial", ""),
                })
                clasif = adjuntos_validacion["clasificacion"]

                # 7. Lógica PC: extraer fecha de instalación y validar Work Order / Purchase Invoice
                fecha_instalacion = None
                fecha_instalacion_reason = "No aplica"
                work_order_result = {"score": 0, "reason": "No aplica (Factory Warranty normal)"}
                purchase_invoice_result = {"score": 0, "reason": "No aplica (Factory Warranty normal)"}

                if es_pc:
                    log.info("[%s] Procesando lógica PC - Parts and Components", Reclamo)

                    # Extraer fecha de instalación con IA
                    try:
                        resultado_fi = extraer_fecha_instalacion_parte(
                            Diccionario_Salesforce_Reclamo,
                            Diccionario_Chatter if Diccionario_Chatter else {},
                        )
                        fecha_instalacion = resultado_fi.get("fecha")
                        fecha_instalacion_reason = resultado_fi.get("razon", "")
                        if fecha_instalacion:
                            log.info("[%s] Fecha instalación: %s", Reclamo, fecha_instalacion)
                    except Exception as e:
                        log.error("[%s] Error extrayendo fecha instalación: %s", Reclamo, e)
                        fecha_instalacion_reason = f"Error: {e}"

                    # Validar Work Order con IA
                    try:
                        work_order_result = validar_work_order_con_ia(
                            adjuntos_ia["fotografias"]["urls_sas"] + adjuntos_ia["reporte_tecnico"]["urls_sas"],
                            Diccionario_Salesforce_Reclamo,
                        )
                        log.info("[%s] Work Order: score=%.2f", Reclamo, work_order_result["score"])
                    except Exception as e:
                        log.error("[%s] Error validando Work Order: %s", Reclamo, e)

                    # Validar Purchase Invoice con IA
                    try:
                        purchase_invoice_result = validar_purchase_invoice_con_ia(
                            adjuntos_ia["fotografias"]["urls_sas"] + adjuntos_ia["reporte_tecnico"]["urls_sas"],
                            Diccionario_Salesforce_Reclamo,
                        )
                        log.info("[%s] Purchase Invoice: score=%.2f", Reclamo, purchase_invoice_result["score"])
                    except Exception as e:
                        log.error("[%s] Error validando Purchase Invoice: %s", Reclamo, e)

                # 8. Validación estándar (con lógica PC si aplica)
                DiccionarioValidacionSTD = ValidacionStandard(
                    Diccionario_Salesforce_Reclamo,
                    es_pc=es_pc,
                    fecha_instalacion_parte=fecha_instalacion,
                )

                # 9. Seleccionar ponderaciones según PC o FW normal
                pond = PONDERACIONES_STD_SF_PC if es_pc else PONDERACIONES_STD_SF

                # 10. Calcular scores de adjuntos con Opción C (max keywords e IA)
                adj_scores = calcular_score_adjuntos(clasif, pond, tr_result, plm_result, photo_result)

                registro_nuevo = {
                    "ClaimNumber": Diccionario_Salesforce_Reclamo.get("Name"),
                    "Plataforma": "Salesforce",
                    "createdon": Diccionario_Salesforce_Reclamo.get("CreatedDate"),
                    "Submitted Date": Diccionario_Salesforce_Reclamo.get("SubmittedDate__c"),
                    "Status": Diccionario_Salesforce_Reclamo.get("Status"),
                    "TipoGarantia": "Factory Warranty",
                    "Coverage Type": coverage_type,
                    "Repair Date": repair_date,
                    "Within standard warranty": DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion"),
                    "Within standard warranty reason": DiccionarioValidacionSTD.get("within_standard_warranty_reason"),
                    "Repair deadline": DiccionarioValidacionSTD.get("Repair_deadline_ponderacion"),
                    "Repair deadline reason": DiccionarioValidacionSTD.get("Repair_deadline_reason"),
                    "Claim deadline": DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion"),
                    "Claim deadline reason": DiccionarioValidacionSTD.get("Claim_Deadline_reason"),
                    "Attachments PLM": adj_scores["score_plm"],
                    "Attachments PLM reason": adj_scores["plm_reason"],
                    "Attachments Oil Analysis": adj_scores["score_aceite"],
                    "Attachments Oil Analysis reason": adj_scores["aceite_reason"],
                    "Attachments Datapacks": adj_scores["score_datapacks"],
                    "Attachments Datapacks reason": adj_scores["datapacks_reason"],
                    "Attachments Technical Report SF": adj_scores["score_tr"],
                    "Attachments Technical Report SF reason": adj_scores["tr_reason"],
                    "Attachments Photographs SF": adj_scores["score_photos"],
                    "Attachments Photographs SF reason": adj_scores["photos_reason"],
                    "Total Adjuntos": adjuntos_validacion["total_adjuntos"],
                    "Adjuntos en Claim": adjuntos_validacion["adjuntos_en_claim"],
                    "Adjuntos en Case": adjuntos_validacion["adjuntos_en_case"],
                    "Modelo": modelo_serial.get("modelo", ""),
                    "Serial Number": modelo_serial.get("serial", ""),
                    "Part Installation Date": fecha_instalacion,
                    "Part Installation Date reason": fecha_instalacion_reason,
                    "Work Order": work_order_result["score"],
                    "Work Order reason": work_order_result["reason"],
                    "Purchase Invoice": purchase_invoice_result["score"],
                    "Purchase Invoice reason": purchase_invoice_result["reason"],
                }
                nuevos_registros.append(registro_nuevo)

            if registro_nuevo is not None:
                encolar_registro(registro_nuevo)
                log.info("[%s] Registro encolado exitosamente", Reclamo)

    log.info("=== Procesamiento completado: %d reclamos procesados ===", len(nuevos_registros))
    sincronizar_pendientes_excel()


if __name__ == "__main__":
    main()
