import argparse
import os

import pandas as pd

from mr_warranty.config.config import (
    SQL_TABLE,
    SQL_DATABASE,
    WC_TYPE_FIELD_CAMPAIGN,
    WC_TYPE_STANDARD,
    WC_TYPE_IGNORED,
    SQIS_STATUS_UNDER_APPLICATION,
    DEFAULT_CREATEDON_FILTER,
)
from mr_warranty.core.logger import log

from mr_warranty.services.prompts import (
    InformeTecnico,
    OrdenTrabajo,
    facturas_promp,
    fotografias,
    validar_adjunto_con_ia,
    validar_oil_analysis_con_ia,
    validar_photographs_con_ia,
    extraer_fecha_instalacion_parte,
    validar_work_order_con_ia,
    validar_purchase_invoice_con_ia,
)
from mr_warranty.domain.validation_standard import ValidacionStandadWC, ValidacionStandartPartes, Stanrate
from mr_warranty.domain.validation_fc_sf import ValidacionFC_SF, ValidacionCostCoverage_SF, ValidacionStandard
from mr_warranty.domain.validation_fc import (
    DatosGeneralesCampana,
    ValidacionCampanaGeneral,
    ValidacionCampanaPartes,
    ValidacionCostCoverage,
)
from mr_warranty.adapters.sqis_client import Allgetwarrantyclaim, getWarrantyclaimid, get_offerstatus_labels
from mr_warranty.adapters.salesforce_client import (
    process_salesforce_data,
    reclamos_pendientes,
    obtener_chatter_case_dict,
    obtener_modelo_serial_tsi,
    descargar_y_subir_adjuntos_ia,
    validar_adjuntos_requeridos,
    obtener_repair_date,
    obtener_coverage_type,
)
from mr_warranty.core.ponderaciones import PONDERACIONES_STD, PONDERACIONES_FC, PONDERACIONES_STD_SF, PONDERACIONES_STD_SF_PC
from mr_warranty.infrastructure.blob import AdjuntosSQIS
from mr_warranty.infrastructure.excel_sink import encolar_registro, actualizar_status_masivo, sincronizar_pendientes_excel
from mr_warranty.infrastructure.sql_storage import is_sql_enabled, get_processed_claim_keys_sql
from mr_warranty.core.utils import (
    calcular_periodo_plm,
    calcular_score_adjuntos,
    componente_usa_aceite_hidraulico,
)

# Configurar la tabla SQL
os.environ["SQL_DATABASE"] = SQL_DATABASE
import mr_warranty.infrastructure.sql_storage as sql_storage
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


def Analisis(fuente: str = "ambos"):
    """Analiza reclamos pendientes de la fuente seleccionada."""
    procesar_sqis = fuente in {"sqis", "ambos"}
    procesar_salesforce = fuente in {"salesforce", "ambos"}

    if procesar_sqis:
        df_wc = Allgetwarrantyclaim()
        df_wc["Plataforma"] = "SQIS"
    else:
        df_wc = pd.DataFrame(
            columns=[
                "createdon",
                "kom_claimnumber",
                "_kom_offerclaimtype_value",
                "kom_offerstatus",
                "Plataforma",
            ]
        )

    if procesar_salesforce:
        df_sf = reclamos_pendientes()[["Name", "Status"]].copy()
        df_sf["Plataforma"] = "Salesforce"
        df_sf.rename(columns={"Name": "kom_claimnumber", "Status": "status_origen"}, inplace=True)
    else:
        df_sf = pd.DataFrame(
            columns=["kom_claimnumber", "status_origen", "Plataforma"]
        )

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
    from mr_warranty.adapters.salesforce_client import connect_salesforce
    import pyodbc
    from mr_warranty.config.config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER

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


def main(fuente: str = "ambos"):
    Reclamos_Revisar, status_por_reclamo = Analisis(fuente)

    # Sincronizar status de claims ya existentes en BD
    if fuente in {"salesforce", "ambos"}:
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
                guardado_sql = encolar_registro(registro_nuevo)
                destino = "SQL" if guardado_sql else "JSON de respaldo"
                log.info("Registro guardado en %s: %s", destino, registro_nuevo.get("ClaimNumber"))

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

                claim_context = {
                    "complaint": Diccionario_Salesforce_Reclamo.get("Complaint__c", "") or "",
                    "cause": Diccionario_Salesforce_Reclamo.get("Cause__c", "") or "",
                    "correction": Diccionario_Salesforce_Reclamo.get("Correction__c", "") or "",
                    "summary": Diccionario_Salesforce_Reclamo.get("Summary", "") or "",
                    "case_description": Diccionario_Salesforce_Reclamo.get("Description", "") or "",
                    "case_resolution": Diccionario_Salesforce_Reclamo.get("Resolution_Details__c", "") or "",
                }
                plm_period_start, plm_period_end = calcular_periodo_plm(
                    Diccionario_Salesforce_Reclamo.get("FailureDate__c"),
                    Diccionario_Salesforce_Reclamo.get("MachineCommissionedDate__c"),
                )
                claim_context.update({
                    "failure_date": Diccionario_Salesforce_Reclamo.get("FailureDate__c", "") or "",
                    "plm_period_start": plm_period_start,
                    "plm_period_end": plm_period_end,
                })

                # Clasificar todos los adjuntos antes de descargar las categorías para IA.
                # Esto permite detectar documentos con nombres genéricos mediante IA.
                adjuntos_validacion = validar_adjuntos_requeridos(
                    claim_id,
                    tsi_id,
                    claim_data={
                        "modelo": modelo_serial.get("modelo", ""),
                        "serial": modelo_serial.get("serial", ""),
                    },
                    es_pc=es_pc,
                )
                clasif = adjuntos_validacion["clasificacion"]

                # 2. Descargar adjuntos y subir a Azure Blob
                try:
                    categorias_ia = [
                        "reporte_tecnico",
                        "plm",
                        "analisis_aceite",
                        "work_order",
                        "purchase_invoice",
                    ]

                    adjuntos_ia = descargar_y_subir_adjuntos_ia(
                        claim_id,
                        tsi_id,
                        categorias_ia,
                        classifications=clasif,
                        attachment_details=adjuntos_validacion.get("classification_details", {}),
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
                        claim_context=claim_context,
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
                        claim_context=claim_context,
                    )
                except Exception as e:
                    log.error("[%s] Error IA PLM: %s. Saltando.", Reclamo, e)
                    continue

                # 5. Validar photographs con IA
                photo_result = {
                    "score": 0,
                    "reason": "Integrado en la validación del informe técnico",
                }

                # 5b. Validar Oil Analysis (máquina, serial y componente)
                component = coverage.get("causal_part", "") or Diccionario_Salesforce_Reclamo.get("Product_Code__c", "") or ""
                hydraulic_context = " ".join([
                    Diccionario_Salesforce_Reclamo.get("Complaint__c", "") or "",
                    Diccionario_Salesforce_Reclamo.get("Cause__c", "") or "",
                    Diccionario_Salesforce_Reclamo.get("Correction__c", "") or "",
                ])
                if not componente_usa_aceite_hidraulico(component, hydraulic_context):
                    oil_result = {
                        "score": PONDERACIONES_STD_SF_PC["analisis_aceite"] if es_pc else PONDERACIONES_STD_SF["analisis_aceite"],
                        "reason": "No aplica: el componente no utiliza aceite hidráulico",
                    }
                else:
                    try:
                        oil_result = validar_oil_analysis_con_ia(
                            adjuntos_ia["analisis_aceite"]["urls_sas"],
                            modelo_serial["modelo"],
                            modelo_serial["serial"],
                            component,
                            PONDERACIONES_STD_SF_PC["analisis_aceite"] if es_pc else PONDERACIONES_STD_SF["analisis_aceite"],
                        )
                    except Exception as e:
                        log.error("[%s] Error IA Oil Analysis: %s. Se asigna 0.", Reclamo, e)
                        oil_result = {"score": 0, "reason": f"ALERTA: Error validando Oil Analysis: {e}"}

                # 7. Extraer fecha de instalación y validar Work Order / Purchase Invoice
                fecha_instalacion = None
                fecha_instalacion_reason = "No se pudo determinar la fecha de instalación"
                if es_pc:
                    log.info("[%s] Procesando lógica PC - Parts and Components", Reclamo)

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

                claim_validation_data = {
                    **Diccionario_Salesforce_Reclamo,
                    "Modelo": modelo_serial.get("modelo", ""),
                    "Serial": modelo_serial.get("serial", ""),
                    "CausalPart__c": component,
                    "PartInstallationDate": fecha_instalacion or "",
                    "Parts_Requested_Quantity__c": coverage.get("parts_quantity", 0),
                    "RepairDate": repair_date or "",
                }

                try:
                    work_order_result = validar_work_order_con_ia(
                        adjuntos_ia["work_order"]["urls_sas"],
                        claim_validation_data,
                    )
                    log.info("[%s] Work Order: score=%.2f", Reclamo, work_order_result["score"])
                except Exception as e:
                    log.error("[%s] Error validando Work Order: %s", Reclamo, e)
                    work_order_result = {"score": 0, "reason": f"ALERTA: Error validando Work Order: {e}"}

                try:
                    purchase_invoice_result = validar_purchase_invoice_con_ia(
                        adjuntos_ia["purchase_invoice"]["urls_sas"],
                        claim_validation_data,
                    )
                    log.info("[%s] Purchase Invoice: score=%.2f", Reclamo, purchase_invoice_result["score"])
                except Exception as e:
                    log.error("[%s] Error validando Purchase Invoice: %s", Reclamo, e)
                    purchase_invoice_result = {"score": 0, "reason": f"ALERTA: Error validando Purchase Invoice: {e}"}

                # 8. Validación estándar (con lógica PC si aplica)
                DiccionarioValidacionSTD = ValidacionStandard(
                    Diccionario_Salesforce_Reclamo,
                    es_pc=es_pc,
                    fecha_instalacion_parte=fecha_instalacion,
                )

                # 9. Seleccionar ponderaciones según PC o FW normal
                pond = PONDERACIONES_STD_SF_PC if es_pc else PONDERACIONES_STD_SF

                # 10. Calcular scores de adjuntos con validación IA y presencia de Datapacks
                adj_scores = calcular_score_adjuntos(
                    clasif,
                    pond,
                    tr_result,
                    plm_result,
                    photo_result,
                    oil_result=oil_result,
                )

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
                    "Invoices": purchase_invoice_result["score"],
                    "Invoices reason": purchase_invoice_result["reason"],
                }
                nuevos_registros.append(registro_nuevo)

            if registro_nuevo is not None:
                guardado_sql = encolar_registro(registro_nuevo)
                destino = "SQL" if guardado_sql else "JSON de respaldo"
                log.info("[%s] Registro guardado en %s", Reclamo, destino)

    log.info("=== Procesamiento completado: %d reclamos procesados ===", len(nuevos_registros))
    sincronizar_pendientes_excel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Procesa reclamos de garantía de SQIS, Salesforce o ambas plataformas."
    )
    parser.add_argument(
        "fuente",
        nargs="?",
        choices=("sqis", "salesforce", "ambos"),
        default="ambos",
        help="Fuente a procesar (por defecto: ambos).",
    )
    args = parser.parse_args()
    main(args.fuente)
