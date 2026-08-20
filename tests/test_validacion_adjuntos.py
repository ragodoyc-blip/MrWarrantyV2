"""
Prueba de las nuevas funciones de validación de adjuntos.
"""

import json
from API_Salesforce import connect_salesforce, validar_adjuntos_requeridos, buscar_adjuntos_sf, clasificar_adjuntos


def test_completo(claim_number: str):
    print(f"\n{'='*60}")
    print(f"PRUEBA VALIDACION ADJUNTOS - Claim: {claim_number}")
    print(f"{'='*60}\n")

    sf = connect_salesforce()

    # 1. Obtener Claim y TSI
    query_claim = f"""
        SELECT Id, Name, TSINumber__c
        FROM Claim WHERE Name = '{claim_number}'
    """
    data = sf.query_all(query_claim)
    claims = data.get("records", [])

    if not claims:
        print(f"Claim {claim_number} no encontrado")
        return

    claim = claims[0]
    claim_id = claim.get("Id")
    tsi_id = claim.get("TSINumber__c")
    
    print(f"Claim ID: {claim_id}")
    print(f"TSI ID: {tsi_id}\n")

    # 2. Ejecutar validación completa
    resultado = validar_adjuntos_requeridos(claim_id, tsi_id)

    # 3. Mostrar resultados
    print("--- RESULTADO VALIDACION ---")
    print(f"Total adjuntos: {resultado['total_adjuntos']}")
    print(f"Adjuntos en Claim: {resultado['adjuntos_en_claim']}")
    print(f"Adjuntos en Case: {resultado['adjuntos_en_case']}")
    print(f"Documentos encontrados: {resultado['documentos_encontrados']}/{resultado['documentos_requeridos']}")
    print(f"Faltantes: {resultado['faltantes']}\n")

    print("--- CLASIFICACION ---")
    for tipo, docs in resultado["clasificacion"].items():
        estado = "ENCONTRADO" if docs else "NO ENCONTRADO"
        print(f"\n  {tipo.upper()}: {estado}")
        if docs:
            for doc in docs:
                print(f"    - {doc}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    test_completo("002019")
