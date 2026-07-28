"""
Script de prueba para verificar adjuntos en Salesforce.
Uso: python test_adjuntos_sf.py [claim_number]
Ejemplo: python test_adjuntos_sf.py 002019
"""

import sys

from API_Salesforce import connect_salesforce


def test_adjuntos_case(claim_number: str):
    """Prueba la obtención de adjuntos para un reclamo específico."""
    print(f"\n{'='*60}")
    print(f"PRUEBA DE ADJUNTOS - Claim: {claim_number}")
    print(f"{'='*60}\n")

    # 1. Conectar a Salesforce
    print("1. Conectando a Salesforce...")
    try:
        sf = connect_salesforce()
        print("   OK - Conexion exitosa\n")
    except Exception as e:
        print(f"   ERROR - Error de conexion: {e}\n")
        return

    # 2. Obtener el claim y su TSI (Case ID)
    print("2. Obteniendo claim y TSI...")
    query_claim = f"""
        SELECT Id, Name, TSINumber__c, ClaimType, Status
        FROM Claim 
        WHERE Name = '{claim_number}'
    """
    data = sf.query_all(query_claim)
    claims = data.get("records", [])

    if not claims:
        print(f"   ERROR - No se encontro el claim {claim_number}\n")
        return

    claim = claims[0]
    tsi_id = claim.get("TSINumber__c")
    print(f"   OK - Claim encontrado:")
    print(f"      - ID: {claim.get('Id')}")
    print(f"      - Name: {claim.get('Name')}")
    print(f"      - TSI (Case ID): {tsi_id}")
    print(f"      - ClaimType: {claim.get('ClaimType')}")
    print(f"      - Status: {claim.get('Status')}\n")

    if not tsi_id:
        print("   WARN - No hay TSI asociado a este claim\n")
        return

    # 3. Obtener adjuntos del Case (TSI)
    print("3. Obteniendo adjuntos del Case (TSI)...")
    query_adjuntos = f"""
        SELECT ContentDocumentId, ContentDocument.Title, 
               ContentDocument.FileType, ContentDocument.CreatedDate,
               ContentDocument.ContentSize
        FROM ContentDocumentLink 
        WHERE LinkedEntityId = '{tsi_id}'
    """
    data_adjuntos = sf.query(query_adjuntos)
    adjuntos = data_adjuntos.get("records", [])

    if not adjuntos:
        print("   WARN - No se encontraron adjuntos en este Case\n")
    else:
        print(f"   OK - Se encontraron {len(adjuntos)} adjuntos:\n")
        print(f"   {'No.':<5} {'Titulo':<50} {'Tipo':<10} {'Tamano':<15}")
        print(f"   {'-'*80}")
        
        for i, adj in enumerate(adjuntos, 1):
            doc = adj.get("ContentDocument", {})
            title = doc.get("Title", "Sin titulo")
            file_type = doc.get("FileType", "N/A")
            size = doc.get("ContentSize", 0)
            
            if size > 1024 * 1024:
                size_str = f"{size / (1024*1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"
            
            print(f"   {i:<5} {title:<50} {file_type:<10} {size_str:<15}")

    print()

    # 4. Clasificar adjuntos por nombre
    print("4. Clasificando adjuntos por nombre...")
    classifications = {
        "plm": [],
        "analisis_aceite": [],
        "datapacks": [],
        "reporte_tecnico": [],
        "fotografias": [],
    }

    keywords = {
        "plm": ["plm", "product lifecycle", "gestion de producto"],
        "analisis_aceite": ["oil analysis", "analisis de aceite", "aceite", "oil", "lubricacion"],
        "datapacks": ["datapack", "dsc", "diagnostic"],
        "reporte_tecnico": ["reporte", "technical", "informe", "failure analysis"],
        "fotografias": ["foto", "photo", "imagen", "image", "evidencia"],
    }

    for adj in adjuntos:
        doc = adj.get("ContentDocument", {})
        title = doc.get("Title", "").lower()
        
        for tipo, kw_list in keywords.items():
            if any(kw in title for kw in kw_list):
                classifications[tipo].append(doc.get("Title"))
                break

    print("\n   Resultado de clasificacion:")
    print(f"   {'Tipo':<20} {'Estado':<15} {'Documentos'}")
    print(f"   {'-'*70}")
    
    for tipo, docs in classifications.items():
        estado = "ENCONTRADO" if docs else "NO ENCONTRADO"
        docs_str = ", ".join(docs) if docs else "-"
        print(f"   {tipo:<20} {estado:<15} {docs_str}")

    print()

    # 5. Resumen
    print("5. Resumen:")
    total_required = 5
    found = sum(1 for docs in classifications.values() if docs)
    print(f"   Documentos requeridos: {total_required}")
    print(f"   Documentos encontrados: {found}")
    print(f"   Documentos faltantes: {total_required - found}")
    
    if found == total_required:
        print("\n   OK - Todos los documentos requeridos estan presentes")
    else:
        missing = [tipo for tipo, docs in classifications.items() if not docs]
        print(f"\n   WARN - Documentos faltantes: {', '.join(missing)}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        claim_number = sys.argv[1]
    else:
        claim_number = input("Ingrese el numero de reclamo (ej: 002019): ").strip()
    
    test_adjuntos_case(claim_number)
