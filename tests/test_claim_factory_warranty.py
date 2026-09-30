"""
Test unitario por Claim Number para Factory Warranty (Salesforce).

Replica la rama Factory Warranty de pipelines/main.py (pasos 0-10),
pero NO escribe en SQL: retorna/imprime el diccionario para revision.

Uso:
    python tests/test_claim_factory_warranty.py 002391
    python tests/test_claim_factory_warranty.py 002318

Salida:
    - Diccionario impreso por secciones en consola + score total.
    - JSON guardado en data/test_claim_<number>.json

Nota: ejecuta el flujo FULL con IA (descarga adjuntos, blob, prompts),
igual que el pipeline real. Requiere credenciales (.env).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.adapters.salesforce_client import (
    process_salesforce_data,
    obtener_chatter_case_dict,
    obtener_modelo_serial_tsi,
    descargar_y_subir_adjuntos_ia,
    validar_adjuntos_requeridos,
    obtener_repair_date,
    obtener_coverage_type,
)
from mr_warranty.core.logger import log
from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF, PONDERACIONES_STD_SF_PC
from mr_warranty.core.utils import (
    calcular_periodo_plm,
    calcular_score_adjuntos,
    componente_usa_aceite_hidraulico,
    plm_no_requerido,
    puntaje_plm_presencia,
    requiere_factura,
    usa_prompt_sap,
)
from mr_warranty.domain.validation_fc_sf import ValidacionStandard
from mr_warranty.domain.validation_fc_sf import es_pa_special_policy, es_pc_db_installed
from mr_warranty.services.prompts import (
    extraer_fecha_instalacion_parte,
    extraer_partes_db_installed,
    validar_adjunto_con_ia,
    validar_oil_analysis_con_ia,
    validar_purchase_invoice_con_ia,
    validar_purchase_invoice_db_installed_con_ia,
    validar_spcr_con_ia,
    validar_work_order_con_ia,
)


def evaluar_factory_warranty(claim_number: str) -> dict:
    """Evalua un reclamo Factory Warranty y retorna el diccionario resultado."""
    from mr_warranty.core.ia_cost import iniciar_medicion, resumen as resumen_costo_ia

    iniciar_medicion()
    log.info("[%s] Datos desde Salesforce (TEST, sin SQL)", claim_number)
    dic = process_salesforce_data(claim_number)

    if dic.get("ClaimType") != "Factory Warranty":
        return {
            "ClaimNumber": claim_number,
            "Error": f"ClaimType='{dic.get('ClaimType')}' omitido (solo Factory Warranty)",
        }

    tsi_id = dic.get("Id_case")
    claim_id = dic.get("Id_claim")

    # 0. CoverageType y Repair Date
    coverage = obtener_coverage_type(claim_id)
    coverage_type = coverage.get("coverage_type", "")
    claim_type__c = (coverage.get("claim_group", "") or "").strip()
    es_pc = (coverage_type == "PC - Parts and Components")
    es_pc_db = es_pc_db_installed(claim_type__c)
    es_pa = es_pa_special_policy(claim_type__c)
    repair_date = obtener_repair_date(claim_id)

    # 1. Modelo y serial del TSI + Chatter
    modelo_serial = (
        obtener_modelo_serial_tsi(tsi_id)
        if tsi_id
        else {"modelo": "", "serial": ""}
    )
    chatter = (
        obtener_chatter_case_dict(dic.get("TSINumber__c"))
        if dic.get("TSINumber__c")
        else {}
    )

    claim_context = {
        "complaint": dic.get("Complaint__c", "") or "",
        "cause": dic.get("Cause__c", "") or "",
        "correction": dic.get("Correction__c", "") or "",
        "summary": dic.get("Summary", "") or "",
        "case_description": dic.get("Description", "") or "",
        "case_resolution": dic.get("Resolution_Details__c", "") or "",
    }
    plm_start, plm_end = calcular_periodo_plm(
        dic.get("FailureDate__c"),
        dic.get("MachineCommissionedDate__c"),
    )
    claim_context.update({
        "failure_date": dic.get("FailureDate__c", "") or "",
        "plm_period_start": plm_start,
        "plm_period_end": plm_end,
    })

    # Clasificar adjuntos antes de descargar categorias para IA
    adjuntos_validacion = validar_adjuntos_requeridos(
        claim_id,
        tsi_id,
        claim_data={
            "modelo": modelo_serial.get("modelo", ""),
            "serial": modelo_serial.get("serial", ""),
        },
        es_pc=es_pc,
        es_pa=es_pa,
    )
    clasif = adjuntos_validacion["clasificacion"]

    # 2. Descargar adjuntos y subir a Blob
    categorias_descarga = ["reporte_tecnico", "plm", "analisis_aceite", "work_order", "purchase_invoice"]
    if es_pa:
        categorias_descarga.append("special_policy")
    adjuntos_ia = descargar_y_subir_adjuntos_ia(
        claim_id,
        tsi_id,
        categorias_descarga,
        classifications=clasif,
        attachment_details=adjuntos_validacion.get("classification_details", {}),
    )

    # 3-4. Technical Report y PLM con IA (abortan como en main.py)
    pond_tr = PONDERACIONES_STD_SF_PC["technical_report"] if es_pc else PONDERACIONES_STD_SF["technical_report"]
    try:
        tr_result = validar_adjunto_con_ia(
            adjuntos_ia["reporte_tecnico"]["urls_sas"],
            modelo_serial["modelo"],
            modelo_serial["serial"],
            "reporte técnico",
            pond_tr,
            claim_context=claim_context,
        )
    except Exception as e:
        return {"ClaimNumber": claim_number, "Error": f"Error IA TR: {e}"}

    pond_plm = PONDERACIONES_STD_SF_PC["plm"] if es_pc else PONDERACIONES_STD_SF["plm"]
    plm_urls = adjuntos_ia["plm"]["urls_sas"]
    plm_titulos = adjuntos_ia["plm"]["titulos"]
    if plm_no_requerido(claim_type__c):
        plm_result = {"score": pond_plm, "reason": "no es requerido PLM."}
        log.info("[%s] PLM no requerido (SK/MA): score=%.2f", claim_number, pond_plm)
    elif not plm_urls and plm_titulos:
        plm_result = puntaje_plm_presencia(plm_titulos, pond_plm)
        log.info("[%s] PLM por presencia: score=%.2f", claim_number, plm_result["score"])
    else:
        try:
            plm_result = validar_adjunto_con_ia(
                plm_urls,
                modelo_serial["modelo"],
                modelo_serial["serial"],
                "PLM",
                pond_plm,
                claim_context=claim_context,
            )
        except Exception as e:
            return {"ClaimNumber": claim_number, "Error": f"Error IA PLM: {e}"}

    photo_result = {
        "score": 0,
        "reason": "Integrado en la validación del informe técnico",
    }

    # 5b. Oil Analysis
    component = coverage.get("causal_part", "") or dic.get("Product_Code__c", "") or ""
    hydraulic_context = " ".join([
        dic.get("Complaint__c", "") or "",
        dic.get("Cause__c", "") or "",
        dic.get("Correction__c", "") or "",
    ])
    pond_oil = PONDERACIONES_STD_SF_PC["analisis_aceite"] if es_pc else PONDERACIONES_STD_SF["analisis_aceite"]
    if not componente_usa_aceite_hidraulico(component, hydraulic_context):
        oil_result = {
            "score": pond_oil,
            "reason": "No aplica: el componente no utiliza aceite hidráulico",
        }
    else:
        try:
            oil_result = validar_oil_analysis_con_ia(
                adjuntos_ia["analisis_aceite"]["urls_sas"],
                modelo_serial["modelo"],
                modelo_serial["serial"],
                component,
                pond_oil,
            )
        except Exception as e:
            oil_result = {"score": 0, "reason": f"ALERTA: Error validando Oil Analysis: {e}"}

    # 7. Fecha de instalacion (PC normal) o partes failing/installed (PC DB Installed)
    fecha_instalacion = None
    fecha_instalacion_reason = "No se pudo determinar la fecha de instalación"
    failing_part = ""
    installed_part = ""
    partes_reason = ""
    if es_pc_db:
        fecha_instalacion_reason = "No aplica para PC DB Installed, se valida con doble factura."
        try:
            partes = extraer_partes_db_installed(
                dic, chatter if chatter else {},
                causal_part=component,
                product_code=dic.get("Product_Code__c", "") or "",
            )
            failing_part = partes.get("failing", "")
            installed_part = partes.get("installed", "")
            partes_reason = partes.get("razon", "")
        except Exception as e:
            partes_reason = f"Error: {e}"
    else:
        try:
            resultado_fi = extraer_fecha_instalacion_parte(dic, chatter if chatter else {})
            fecha_instalacion = resultado_fi.get("fecha")
            fecha_instalacion_reason = resultado_fi.get("razon", "")
        except Exception as e:
            fecha_instalacion_reason = f"Error: {e}"

    claim_validation_data = {
        **dic,
        "Modelo": modelo_serial.get("modelo", ""),
        "Serial": modelo_serial.get("serial", ""),
        "CausalPart__c": component,
        "PartInstallationDate": fecha_instalacion or "",
        "FailingPart__c": failing_part or component,
        "InstalledPart__c": installed_part,
        "Parts_Requested_Quantity__c": coverage.get("parts_quantity", 0),
        "RepairDate": repair_date or "",
    }

    try:
        work_order_result = validar_work_order_con_ia(
            adjuntos_ia["work_order"]["urls_sas"],
            claim_validation_data,
        )
    except Exception as e:
        work_order_result = {"score": 0, "reason": f"ALERTA: Error validando Work Order: {e}"}

    # Gate: sin partes solicitadas en el Claim no se exigen facturas (salvo PC DB Installed: siempre doble).
    if es_pc_db:
        try:
            invoice_urls = adjuntos_ia["purchase_invoice"]["urls_sas"]
            invoice_docs = len(adjuntos_ia["purchase_invoice"].get("titulos", []))
            if not invoice_urls and usa_prompt_sap(claim_validation_data):
                fotos_ia = descargar_y_subir_adjuntos_ia(
                    claim_id,
                    tsi_id,
                    ["fotografias"],
                    classifications=clasif,
                    attachment_details=adjuntos_validacion.get("classification_details", {}),
                )
                invoice_urls = fotos_ia["fotografias"]["urls_sas"]
                invoice_docs = len(fotos_ia["fotografias"].get("titulos", []))
            purchase_invoice_result = validar_purchase_invoice_db_installed_con_ia(
                invoice_urls, claim_validation_data, num_docs=invoice_docs,
            )
            if partes_reason:
                purchase_invoice_result["reason"] = (
                    f"[Partes: falla={failing_part or '?'} instalada={installed_part or '?'}: {partes_reason}] "
                    + str(purchase_invoice_result.get("reason", ""))
                )
        except Exception as e:
            purchase_invoice_result = {"score": 0, "reason": f"ALERTA: Error validando Purchase Invoice DB: {e}"}
    elif not requiere_factura(dic.get("PartsRequestedQuantity__c")):
        pond_inv = PONDERACIONES_STD_SF_PC["purchase_invoice"] if es_pc else PONDERACIONES_STD_SF["purchase_invoice"]
        purchase_invoice_result = {
            "score": pond_inv,
            "reason": "no es requerida la factura, partes solicitadas = 0.",
        }
        log.info("[%s] Purchase Invoice no requerida (partes=0): score=%.2f", claim_number, pond_inv)
    else:
        try:
            invoice_urls = adjuntos_ia["purchase_invoice"]["urls_sas"]
            if not invoice_urls and usa_prompt_sap(claim_validation_data):
                # Fallback: la captura SAP suele venir como imagen (fotografias).
                fotos_ia = descargar_y_subir_adjuntos_ia(
                    claim_id,
                    tsi_id,
                    ["fotografias"],
                    classifications=clasif,
                    attachment_details=adjuntos_validacion.get("classification_details", {}),
                )
                invoice_urls = fotos_ia["fotografias"]["urls_sas"]
                if invoice_urls:
                    log.info("[%s] Invoice fallback a fotografias (posible captura SAP)", claim_number)
            purchase_invoice_result = validar_purchase_invoice_con_ia(
                invoice_urls,
                claim_validation_data,
            )
        except Exception as e:
            purchase_invoice_result = {"score": 0, "reason": f"ALERTA: Error validando Purchase Invoice: {e}"}

    # 7b. SPCR informativo 0-1 (solo PA - Special Policy, no resta peso).
    if es_pa:
        try:
            spcr_result = validar_spcr_con_ia(
                adjuntos_ia["special_policy"]["urls_sas"],
                modelo_serial.get("modelo", ""),
                modelo_serial.get("serial", ""),
                claim_name=dic.get("Name", "") or claim_number,
            )
        except Exception as e:
            spcr_result = {"score": 0.0, "reason": f"ALERTA: Error validando SPCR: {e}"}
    else:
        spcr_result = {"score": None, "reason": None}

    # 8-10. Validacion estandar + scores adjuntos
    valid_std = ValidacionStandard(
        dic,
        es_pc=es_pc,
        fecha_instalacion_parte=fecha_instalacion,
        claim_type__c=claim_type__c,
        es_pc_db=es_pc_db,
    )
    pond = PONDERACIONES_STD_SF_PC if es_pc else PONDERACIONES_STD_SF
    adj_scores = calcular_score_adjuntos(
        clasif, pond, tr_result, plm_result, photo_result, oil_result=oil_result,
    )

    registro = {
        "ClaimNumber": dic.get("Name"),
        "Plataforma": "Salesforce",
        "createdon": dic.get("CreatedDate"),
        "Submitted Date": dic.get("SubmittedDate__c"),
        "Status": dic.get("Status"),
        "TipoGarantia": "Factory Warranty",
        "Coverage Type": coverage_type,
        "Claim_Type__c": claim_type__c,
        "Repair Date": repair_date,
        "Within standard warranty": valid_std.get("within_standard_warranty_ponderacion"),
        "Within standard warranty reason": valid_std.get("within_standard_warranty_reason"),
        "Repair deadline": valid_std.get("Repair_deadline_ponderacion"),
        "Repair deadline reason": valid_std.get("Repair_deadline_reason"),
        "Claim deadline": valid_std.get("Claim_Deadline_ponderacion"),
        "Claim deadline reason": valid_std.get("Claim_Deadline_reason"),
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
        "SPCR": spcr_result["score"],
        "SPCR reason": spcr_result["reason"],
    }
    costo_ia = resumen_costo_ia()
    registro.update({
        "IA calls": costo_ia["calls"],
        "IA input tokens": costo_ia["input_tokens"],
        "IA output tokens": costo_ia["output_tokens"],
        "IA estimated cost USD": costo_ia["cost_usd"],
    })
    return registro


def _imprimir(registro: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"TEST CLAIM: {registro.get('ClaimNumber')} | {registro.get('Status')} | {registro.get('Coverage Type')} | {registro.get('Claim_Type__c')}")
    print(f"{'=' * 60}\n")
    if registro.get("Error"):
        print(f"  ERROR: {registro['Error']}")
        return
    secciones = {
        "FECHAS/VIGENCIA": ["Within standard warranty", "Repair deadline", "Claim deadline"],
        "ADJUNTOS": ["Attachments PLM", "Attachments Oil Analysis", "Attachments Datapacks",
                     "Attachments Technical Report SF", "Attachments Photographs SF"],
        "DOCUMENTOS": ["Work Order", "Invoices"],
        "SPCR (informativo 0-1)": ["SPCR"],
    }
    for titulo, claves in secciones.items():
        print(f"--- {titulo} ---")
        for k in claves:
            print(f"  {k}: {registro.get(k)}")
            print(f"    -> {registro.get(k + ' reason')}")
        print()
    print(f"  Total Adjuntos: {registro.get('Total Adjuntos')} "
          f"(Claim: {registro.get('Adjuntos en Claim')}, Case: {registro.get('Adjuntos en Case')})")
    print(f"  Modelo: {registro.get('Modelo')} | Serial: {registro.get('Serial Number')}")
    print(f"  IA: {registro.get('IA calls')} llamadas | "
          f"in={registro.get('IA input tokens')} out={registro.get('IA output tokens')} tokens | "
          f"costo est. USD {registro.get('IA estimated cost USD')}")
    _SCORE_KEYS = [
        "Within standard warranty", "Repair deadline", "Claim deadline",
        "Attachments PLM", "Attachments Oil Analysis", "Attachments Datapacks",
        "Attachments Technical Report SF", "Attachments Photographs SF",
        "Work Order", "Invoices",
    ]
    total = sum(registro.get(k) or 0 for k in _SCORE_KEYS
                if isinstance(registro.get(k), (int, float)))
    print(f"\n  SCORE TOTAL: {total:.4f}")
    print(f"\n{'=' * 60}\n")


def main() -> None:
    claim = sys.argv[1] if len(sys.argv) > 1 else "002318"
    registro = evaluar_factory_warranty(claim)
    _imprimir(registro)

    out_path = REPO_ROOT / "data" / f"test_claim_{claim}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2, default=str)
    print(f"[OK] JSON guardado: {out_path}")
    print("[INFO] Test sin escritura SQL.")


if __name__ == "__main__":
    main()
