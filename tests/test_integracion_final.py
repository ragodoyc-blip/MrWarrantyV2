"""
Prueba final de integración para caso 002019.
Simula el flujo de main.py para Factory Warranty.
"""

import json
from mr_warranty.adapters.salesforce_client import process_salesforce_data, obtener_chatter_case_dict, validar_adjuntos_requeridos
from mr_warranty.domain.validation_fc_sf import ValidacionStandard
from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF


def test_integracion(claim_number: str):
    print(f"\n{'='*60}")
    print(f"PRUEBA INTEGRACION - Claim: {claim_number}")
    print(f"{'='*60}\n")

    # 1. Obtener datos del reclamo
    print("1. Obteniendo datos del reclamo...")
    Diccionario_Salesforce_Reclamo = process_salesforce_data(claim_number)
    print(f"   ClaimType: {Diccionario_Salesforce_Reclamo.get('ClaimType')}")
    print(f"   Status: {Diccionario_Salesforce_Reclamo.get('Status')}")
    print(f"   TSI: {Diccionario_Salesforce_Reclamo.get('TSINumber__c')}\n")

    # 2. Obtener Chatter
    print("2. Obteniendo Chatter del Case...")
    Diccionario_Chatter = obtener_chatter_case_dict(Diccionario_Salesforce_Reclamo.get("TSINumber__c"))
    print(f"   Posts: {Diccionario_Chatter.get('CantidadPosts')}\n")

    # 3. Validación estándar
    print("3. Ejecutando Validación Estándar...")
    DiccionarioValidacionSTD = ValidacionStandard(Diccionario_Salesforce_Reclamo)
    print(f"   Repair deadline: {DiccionarioValidacionSTD.get('Repair_deadline_ponderacion')}")
    print(f"   Claim deadline: {DiccionarioValidacionSTD.get('Claim_Deadline_ponderacion')}")
    print(f"   Within warranty: {DiccionarioValidacionSTD.get('within_standard_warranty_ponderacion')}\n")

    # 4. Validación de adjuntos
    print("4. Ejecutando Validación de Adjuntos...")
    claim_id = Diccionario_Salesforce_Reclamo.get("Id_claim")
    tsi_id = Diccionario_Salesforce_Reclamo.get("Id_case")
    ValidacionAdjuntos = validar_adjuntos_requeridos(claim_id, tsi_id)
    
    print(f"   Total adjuntos: {ValidacionAdjuntos.get('total_adjuntos')}")
    print(f"   En Claim: {ValidacionAdjuntos.get('adjuntos_en_claim')}")
    print(f"   En Case: {ValidacionAdjuntos.get('adjuntos_en_case')}")
    print(f"   Documentos encontrados: {ValidacionAdjuntos.get('documentos_encontrados')}/{ValidacionAdjuntos.get('documentos_requeridos')}")
    print(f"   Faltantes: {ValidacionAdjuntos.get('faltantes')}\n")

    # 5. Construir registro final
    print("5. Construyendo registro final...")
    registro_nuevo = {
        "ClaimNumber": Diccionario_Salesforce_Reclamo.get("Name"),
        "Plataforma": "Salesforce",
        "createdon": Diccionario_Salesforce_Reclamo.get("CreatedDate"),
        "Status": Diccionario_Salesforce_Reclamo.get("Status"),
        "TipoGarantia": "Factory Warranty",
        "Repair deadline": DiccionarioValidacionSTD.get("Repair_deadline_ponderacion"),
        "Repair deadline reason": DiccionarioValidacionSTD.get("Repair_deadline_reason"),
        "Claim deadline": DiccionarioValidacionSTD.get("Claim_Deadline_ponderacion"),
        "Claim deadline reason": DiccionarioValidacionSTD.get("Claim_Deadline_reason"),
        "Within standard warranty": DiccionarioValidacionSTD.get("within_standard_warranty_ponderacion"),
        "Within standard warranty reason": DiccionarioValidacionSTD.get("within_standard_warranty_reason"),
        "Attachments PLM": PONDERACIONES_STD_SF["plm"] if ValidacionAdjuntos["clasificacion"].get("plm") else 0,
        "Attachments PLM reason": ", ".join(ValidacionAdjuntos["clasificacion"].get("plm", [])) or "No encontrado",
        "Attachments Oil Analysis": PONDERACIONES_STD_SF["analisis_aceite"] if ValidacionAdjuntos["clasificacion"].get("analisis_aceite") else 0,
        "Attachments Oil Analysis reason": ", ".join(ValidacionAdjuntos["clasificacion"].get("analisis_aceite", [])) or "No encontrado",
        "Attachments Datapacks": PONDERACIONES_STD_SF["datapacks"] if ValidacionAdjuntos["clasificacion"].get("datapacks") else 0,
        "Attachments Datapacks reason": ", ".join(ValidacionAdjuntos["clasificacion"].get("datapacks", [])) or "No encontrado",
        "Attachments Technical Report": PONDERACIONES_STD_SF["technical_report"] if ValidacionAdjuntos["clasificacion"].get("reporte_tecnico") else 0,
        "Attachments Technical Report reason": ", ".join(ValidacionAdjuntos["clasificacion"].get("reporte_tecnico", [])) or "No encontrado",
        "Attachments Photographs": PONDERACIONES_STD_SF["photographs"] if ValidacionAdjuntos["clasificacion"].get("fotografias") else 0,
        "Attachments Photographs reason": ", ".join(ValidacionAdjuntos["clasificacion"].get("fotografias", [])) or "No encontrado",
    }

    print("\n--- REGISTRO FINAL ---")
    for key, value in registro_nuevo.items():
        print(f"  {key}: {value}")

    # Calcular score total
    score_total = sum(v for k, v in registro_nuevo.items() if k.endswith(("reason",)) is False and isinstance(v, (int, float)))
    print(f"\n  SCORE TOTAL: {score_total:.2f}")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import sys
    claim = sys.argv[1] if len(sys.argv) > 1 else "002019"
    test_integracion(claim)
