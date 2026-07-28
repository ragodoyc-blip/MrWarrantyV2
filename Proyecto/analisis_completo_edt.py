"""
Análisis completo de Claims Factory Warranty - Electric Drive Truck
Genera reportes Excel y Word con validaciones y scores.
"""

import os
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from API_Salesforce import (
    connect_salesforce,
    process_salesforce_data,
    obtener_chatter_case_dict,
    validar_adjuntos_requeridos,
)
from ValidacionFC_SF import ValidacionStandard
from Ponderaciones import PONDERACIONES_STD_SF
from logger import log


# ── Estilos para Excel ──────────────────────────────────────
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
SCORE_HIGH = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
SCORE_MED = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
SCORE_LOW = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def get_claims_factory_warranty() -> list[dict]:
    """Obtiene todos los claims Factory Warranty con status Submitted para Electric Drive Truck."""
    sf = connect_salesforce()
    query = """
        SELECT Name, Status, ClaimType, Servicing_Distributor__c, 
               CreatedDate, Account__c, Product_Code__c
        FROM Claim 
        WHERE Status = 'Submitted'
        AND Product_Code__c = 'Electric Drive Truck'
        AND ClaimType = 'Factory Warranty'
    """
    data = sf.query_all(query)
    return data.get("records", [])


def analizar_claim(claim_name: str) -> dict:
    """Realiza el análisis completo de un claim."""
    log.info("Analizando claim %s...", claim_name)
    
    try:
        # 1. Obtener datos del reclamo
        diccionario = process_salesforce_data(claim_name)
        
        claim_id = diccionario.get("Id_claim")
        tsi_id = diccionario.get("Id_case")
        
        # 2. Validaciones principales
        std_validation = ValidacionStandard(diccionario)
        
        # 3. Chatter (mantener para uso en otras funciones)
        chatter = obtener_chatter_case_dict(tsi_id) if tsi_id else {"CantidadPosts": 0, "Posts": []}
        
        # 4. Validación de adjuntos
        adjuntos = validar_adjuntos_requeridos(claim_id, tsi_id)
        
        # 5. Calcular scores
        scores = {
            "repair_deadline": std_validation.get("Repair_deadline_ponderacion", 0),
            "repair_deadline_reason": std_validation.get("Repair_deadline_reason", ""),
            "claim_deadline": std_validation.get("Claim_Deadline_ponderacion", 0),
            "claim_deadline_reason": std_validation.get("Claim_Deadline_reason", ""),
            "within_warranty": std_validation.get("within_standard_warranty_ponderacion", 0),
            "within_warranty_reason": std_validation.get("within_standard_warranty_reason", ""),
            "plm": PONDERACIONES_STD_SF["plm"] if adjuntos["clasificacion"].get("plm") else 0,
            "plm_docs": ", ".join(adjuntos["clasificacion"].get("plm", [])) or "No encontrado",
            "oil_analysis": PONDERACIONES_STD_SF["analisis_aceite"] if adjuntos["clasificacion"].get("analisis_aceite") else 0,
            "oil_docs": ", ".join(adjuntos["clasificacion"].get("analisis_aceite", [])) or "No encontrado",
            "datapacks": PONDERACIONES_STD_SF["datapacks"] if adjuntos["clasificacion"].get("datapacks") else 0,
            "datapacks_docs": ", ".join(adjuntos["clasificacion"].get("datapacks", [])) or "No encontrado",
            "technical_report": PONDERACIONES_STD_SF["technical_report"] if adjuntos["clasificacion"].get("reporte_tecnico") else 0,
            "technical_report_docs": ", ".join(adjuntos["clasificacion"].get("reporte_tecnico", [])) or "No encontrado",
            "photographs": PONDERACIONES_STD_SF["photographs"] if adjuntos["clasificacion"].get("fotografias") else 0,
            "photographs_docs": ", ".join(adjuntos["clasificacion"].get("fotografias", [])) or "No encontrado",
            "total_adjuntos": adjuntos["total_adjuntos"],
            "adjuntos_en_claim": adjuntos["adjuntos_en_claim"],
            "adjuntos_en_case": adjuntos["adjuntos_en_case"],
        }
        
        # Calcular score total (sin root_cause)
        score_total = sum([
            scores["repair_deadline"],
            scores["claim_deadline"],
            scores["within_warranty"],
            scores["plm"],
            scores["oil_analysis"],
            scores["datapacks"],
            scores["technical_report"],
            scores["photographs"],
        ])
        
        return {
            "claim": claim_name,
            "claim_id": claim_id,
            "tsi_id": tsi_id,
            "status": diccionario.get("Status", ""),
            "created_date": diccionario.get("CreatedDate", "")[:10],
            "distributor": diccionario.get("Servicing_Distributor__c", ""),
            "account": diccionario.get("Account__c", ""),
            "phenomenon": diccionario.get("Phenomenon__c", ""),
            "cause": diccionario.get("Cause__c", ""),
            "correction": diccionario.get("Correction__c", ""),
            "description": diccionario.get("Description", "")[:200] if diccionario.get("Description") else "",
            "failure_date": diccionario.get("FailureDate__c", "")[:10] if diccionario.get("FailureDate__c") else "",
            "repair_date": diccionario.get("MachineRepairCompletionDate__c", "")[:10] if diccionario.get("MachineRepairCompletionDate__c") else "",
            "commissioned_date": diccionario.get("MachineCommissionedDate__c", "")[:10] if diccionario.get("MachineCommissionedDate__c") else "",
            "chatter_posts": chatter.get("CantidadPosts", 0),
            **scores,
            "score_total": round(score_total, 2),
        }
        
    except Exception as e:
        log.error("Error analizando claim %s: %s", claim_name, e)
        return {
            "claim": claim_name,
            "error": str(e),
            "score_total": 0,
        }


def generar_excel(resultados: list[dict], filename: str):
    """Genera el reporte Excel con hoja resumen y detalle."""
    wb = Workbook()
    
    # ── Hoja Resumen ────────────────────────────────────────
    ws_resumen = wb.active
    ws_resumen.title = "Resumen"
    
    headers_resumen = [
        "Claim", "Status", "Fecha", "Distribuidor", "Cuenta",
        "Repair\nDeadline", "Claim\nDeadline", "Within\nWarranty", "Root\nCause",
        "PLM", "Oil\nAnalysis", "Data\npacks", "Technical\nReport", "Photos",
        "Score\nTotal"
    ]
    
    # Escribir headers
    for col, header in enumerate(headers_resumen, 1):
        cell = ws_resumen.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    
    # Escribir datos
    for row_idx, r in enumerate(resultados, 2):
        if "error" in r:
            ws_resumen.cell(row=row_idx, column=1, value=r["claim"])
            ws_resumen.cell(row=row_idx, column=2, value=f"ERROR: {r['error'][:50]}")
            continue
            
        values = [
            r["claim"],
            r["status"],
            r["created_date"],
            (r.get("distributor") or "N/A")[:40],
            (r.get("account") or "N/A")[:40],
            r["repair_deadline"],
            r["claim_deadline"],
            r["within_warranty"],
            r["root_cause"],
            r["plm"],
            r["oil_analysis"],
            r["datapacks"],
            r["technical_report"],
            r["photographs"],
            r["score_total"],
        ]
        
        for col, val in enumerate(values, 1):
            cell = ws_resumen.cell(row=row_idx, column=col, value=val)
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Colorear scores
            if col >= 6 and col <= 15:
                if isinstance(val, (int, float)):
                    if val >= 0.10:
                        cell.fill = SCORE_HIGH
                    elif val > 0:
                        cell.fill = SCORE_MED
                    else:
                        cell.fill = SCORE_LOW
    
    # Ajustar anchos de columna
    widths = [10, 12, 12, 35, 35, 10, 10, 10, 10, 8, 8, 8, 8, 8, 10]
    for i, w in enumerate(widths, 1):
        ws_resumen.column_dimensions[get_column_letter(i)].width = w
    
    # ── Hoja Detalle ────────────────────────────────────────
    ws_detalle = wb.create_sheet("Detalle")
    
    headers_detalle = [
        "Claim", "TSI", "Status", "Fecha Creación", "Fecha Falla", 
        "Fecha Reparación", "Fecha Puesta Marcha", "Distribuidor", "Cuenta",
        "Fenómeno", "Causa", "Corrección", "Descripción",
        "Repair Deadline", "Repair Deadline Reason",
        "Claim Deadline", "Claim Deadline Reason",
        "Within Warranty", "Within Warranty Reason",
        "Root Cause", "Root Cause Reason",
        "PLM", "PLM Docs",
        "Oil Analysis", "Oil Docs",
        "Datapacks", "Datapacks Docs",
        "Technical Report", "TR Docs",
        "Photographs", "Photos Docs",
        "Total Adjuntos", "En Claim", "En Case",
        "Score Total"
    ]
    
    # Escribir headers
    for col, header in enumerate(headers_detalle, 1):
        cell = ws_detalle.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    
    # Escribir datos
    for row_idx, r in enumerate(resultados, 2):
        if "error" in r:
            ws_detalle.cell(row=row_idx, column=1, value=r["claim"])
            ws_detalle.cell(row=row_idx, column=2, value=f"ERROR: {r['error'][:100]}")
            continue
            
        values = [
            r["claim"],
            r.get("tsi_id", ""),
            r["status"],
            r["created_date"],
            r.get("failure_date", ""),
            r.get("repair_date", ""),
            r.get("commissioned_date", ""),
            r.get("distributor", ""),
            r.get("account", ""),
            r.get("phenomenon", ""),
            r.get("cause", ""),
            r.get("correction", ""),
            r.get("description", ""),
            r["repair_deadline"],
            r["repair_deadline_reason"],
            r["claim_deadline"],
            r["claim_deadline_reason"],
            r["within_warranty"],
            r["within_warranty_reason"],
            r["root_cause"],
            r["root_cause_reason"],
            r["plm"],
            r["plm_docs"],
            r["oil_analysis"],
            r["oil_docs"],
            r["datapacks"],
            r["datapacks_docs"],
            r["technical_report"],
            r["technical_report_docs"],
            r["photographs"],
            r["photographs_docs"],
            r["total_adjuntos"],
            r["adjuntos_en_claim"],
            r["adjuntos_en_case"],
            r["score_total"],
        ]
        
        for col, val in enumerate(values, 1):
            cell = ws_detalle.cell(row=row_idx, column=col, value=val)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    
    # Ajustar anchos
    ws_detalle.column_dimensions["A"].width = 10
    ws_detalle.column_dimensions["B"].width = 20
    ws_detalle.column_dimensions["C"].width = 12
    ws_detalle.column_dimensions["D"].width = 12
    ws_detalle.column_dimensions["E"].width = 12
    ws_detalle.column_dimensions["F"].width = 12
    ws_detalle.column_dimensions["G"].width = 12
    ws_detalle.column_dimensions["H"].width = 35
    ws_detalle.column_dimensions["I"].width = 35
    ws_detalle.column_dimensions["J"].width = 40
    ws_detalle.column_dimensions["K"].width = 40
    ws_detalle.column_dimensions["L"].width = 20
    ws_detalle.column_dimensions["M"].width = 50
    
    # Guardar
    wb.save(filename)
    log.info("Excel generado: %s", filename)


def generar_word(resultados: list[dict], filename: str):
    """Genera el reporte Word formateado."""
    doc = Document()
    
    # Título
    title = doc.add_heading("Análisis de Claims Factory Warranty", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Electric Drive Truck - Status: Submitted")
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    # Fecha del reporte
    fecha = doc.add_paragraph()
    fecha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fecha.add_run(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    run.font.size = Pt(10)
    
    doc.add_paragraph()
    
    # Resumen ejecutivo
    doc.add_heading("Resumen Ejecutivo", level=1)
    
    total_claims = len(resultados)
    claims_ok = sum(1 for r in resultados if r.get("score_total", 0) >= 0.80)
    claims_parcial = sum(1 for r in resultados if 0.50 <= r.get("score_total", 0) < 0.80)
    claims_bajo = sum(1 for r in resultados if r.get("score_total", 0) < 0.50)
    score_promedio = sum(r.get("score_total", 0) for r in resultados) / total_claims if total_claims > 0 else 0
    
    table_resumen = doc.add_table(rows=5, cols=2)
    table_resumen.style = "Table Grid"
    table_resumen.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    data_resumen = [
        ("Total Claims Analizados", str(total_claims)),
        ("Score Promedio", f"{score_promedio:.2f}"),
        ("Claims Completos (≥0.80)", f"{claims_ok} ({claims_ok/total_claims*100:.0f}%)"),
        ("Claims Parciales (0.50-0.79)", f"{claims_parcial} ({claims_parcial/total_claims*100:.0f}%)"),
        ("Claims Bajos (<0.50)", f"{claims_bajo} ({claims_bajo/total_claims*100:.0f}%)"),
    ]
    
    for i, (label, value) in enumerate(data_resumen):
        table_resumen.cell(i, 0).text = label
        table_resumen.cell(i, 1).text = value
        for cell in table_resumen.row_cells(i):
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    doc.add_paragraph()
    
    # Tabla resumen de scores
    doc.add_heading("Scores por Claim", level=1)
    
    headers = ["Claim", "Repair", "Claim DL", "Warranty", "Root Cause", "PLM", "Oil", "Data", "TR", "Photos", "Total"]
    table_scores = doc.add_table(rows=total_claims + 1, cols=len(headers))
    table_scores.style = "Table Grid"
    table_scores.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Headers
    for j, h in enumerate(headers):
        cell = table_scores.cell(0, j)
        cell.text = h
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(8)
    
    # Datos
    for i, r in enumerate(resultados, 1):
        if "error" in r:
            table_scores.cell(i, 0).text = r["claim"]
            table_scores.cell(i, 1).text = "ERROR"
            continue
        
        values = [
            r["claim"],
            str(r["repair_deadline"]),
            str(r["claim_deadline"]),
            str(r["within_warranty"]),
            str(r["root_cause"]),
            str(r["plm"]),
            str(r["oil_analysis"]),
            str(r["datapacks"]),
            str(r["technical_report"]),
            str(r["photographs"]),
            str(r["score_total"]),
        ]
        
        for j, val in enumerate(values):
            cell = table_scores.cell(i, j)
            cell.text = val
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.size = Pt(8)
    
    doc.add_page_break()
    
    # Detalle por claim
    doc.add_heading("Detalle por Claim", level=1)
    
    for r in resultados:
        if "error" in r:
            continue
        
        doc.add_heading(f"Claim {r['claim']}", level=2)
        
        # Datos generales
        p = doc.add_paragraph()
        p.add_run("Status: ").bold = True
        p.add_run(f"{r['status']}  |  ")
        p.add_run("Fecha: ").bold = True
        p.add_run(f"{r['created_date']}  |  ")
        p.add_run("Distribuidor: ").bold = True
        p.add_run((r.get("distributor") or "N/A")[:50])
        
        p = doc.add_paragraph()
        p.add_run("Cuenta: ").bold = True
        p.add_run((r.get("account") or "N/A")[:50])
        
        p = doc.add_paragraph()
        p.add_run("Fenómeno: ").bold = True
        p.add_run(r.get("phenomenon") or "N/A")
        
        p = doc.add_paragraph()
        p.add_run("Causa: ").bold = True
        p.add_run((r.get("cause") or "N/A")[:150])
        
        # Tabla de scores
        table = doc.add_table(rows=6, cols=3)
        table.style = "Table Grid"
        
        score_data = [
            ("Repair Deadline", r["repair_deadline"], r["repair_deadline_reason"][:80]),
            ("Claim Deadline", r["claim_deadline"], r["claim_deadline_reason"][:80]),
            ("Within Warranty", r["within_warranty"], r["within_warranty_reason"][:80]),
            ("Root Cause", r["root_cause"], r["root_cause_reason"][:80]),
            ("Adjuntos", f"{r['total_adjuntos']} total", f"Claim: {r['adjuntos_en_claim']}, Case: {r['adjuntos_en_case']}"),
            ("SCORE TOTAL", r["score_total"], ""),
        ]
        
        for i, (label, score, reason) in enumerate(score_data):
            table.cell(i, 0).text = label
            table.cell(i, 1).text = str(score)
            table.cell(i, 2).text = reason
            for cell in table.row_cells(i):
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8)
        
        # Documentos encontrados
        p = doc.add_paragraph()
        p.add_run("\nDocumentos: ").bold = True
        p.add_run(f"PLM: {'✓' if r['plm'] > 0 else '✗'}  |  ")
        p.add_run(f"Oil: {'✓' if r['oil_analysis'] > 0 else '✗'}  |  ")
        p.add_run(f"Data: {'✓' if r['datapacks'] > 0 else '✗'}  |  ")
        p.add_run(f"TR: {'✓' if r['technical_report'] > 0 else '✗'}  |  ")
        p.add_run(f"Photos: {'✓' if r['photographs'] > 0 else '✗'}")
        
        doc.add_paragraph()
    
    doc.save(filename)
    log.info("Word generado: %s", filename)


def main():
    """Función principal."""
    log.info("=== Iniciando análisis Factory Warranty EDT ===")
    
    # 1. Obtener claims
    log.info("Obteniendo claims Factory Warranty...")
    claims = get_claims_factory_warranty()
    log.info("Claims encontrados: %d", len(claims))
    
    # 2. Analizar cada claim
    resultados = []
    for i, claim in enumerate(claims, 1):
        claim_name = claim.get("Name")
        log.info("[%d/%d] Analizando %s...", i, len(claims), claim_name)
        resultado = analizar_claim(claim_name)
        resultados.append(resultado)
    
    # 3. Generar Excel
    excel_file = "analisis_edt_factory_warranty.xlsx"
    generar_excel(resultados, excel_file)
    
    # 4. Generar Word
    word_file = "analisis_edt_factory_warranty.docx"
    generar_word(resultados, word_file)
    
    # 5. Resumen
    log.info("=== Análisis completado ===")
    log.info("Claims analizados: %d", len(resultados))
    log.info("Excel: %s", excel_file)
    log.info("Word: %s", word_file)
    
    # Score promedio
    scores_validos = [r["score_total"] for r in resultados if "error" not in r]
    if scores_validos:
        promedio = sum(scores_validos) / len(scores_validos)
        log.info("Score promedio: %.2f", promedio)
    
    return resultados


if __name__ == "__main__":
    main()
