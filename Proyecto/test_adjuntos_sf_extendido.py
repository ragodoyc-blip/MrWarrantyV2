"""
Script de prueba extendido para verificar adjuntos en Salesforce.
Busca en ContentDocumentLink y también en Chatter.
"""

import sys

from API_Salesforce import connect_salesforce


def test_adjuntos_extendido(claim_number: str):
    """Prueba extendida con más detalle."""
    print(f"\n{'='*60}")
    print(f"PRUEBA EXTENDIDA - Claim: {claim_number}")
    print(f"{'='*60}\n")

    sf = connect_salesforce()

    # 1. Obtener el claim
    query_claim = f"""
        SELECT Id, Name, TSINumber__c, ClaimType, Status
        FROM Claim WHERE Name = '{claim_number}'
    """
    data = sf.query_all(query_claim)
    claims = data.get("records", [])

    if not claims:
        print(f"Claim {claim_number} no encontrado")
        return

    claim = claims[0]
    tsi_id = claim.get("TSINumber__c")
    print(f"Claim: {claim.get('Name')}")
    print(f"TSI (Case ID): {tsi_id}")
    print(f"ClaimType: {claim.get('ClaimType')}\n")

    if not tsi_id:
        print("No hay TSI asociado")
        return

    # 2. Buscar TODOS los ContentDocumentLink del Case
    print("--- ContentDocumentLink del Case ---")
    query = f"""
        SELECT Id, ContentDocumentId, LinkedEntityId, ShareType, Visibility
        FROM ContentDocumentLink 
        WHERE LinkedEntityId = '{tsi_id}'
    """
    data = sf.query_all(query)
    links = data.get("records", [])
    print(f"Total de links: {len(links)}")

    # 3. Obtener detalles de cada ContentDocument
    if links:
        print("\n--- Detalles de Documentos ---")
        for link in links:
            doc_id = link.get("ContentDocumentId")
            query_doc = f"""
                SELECT Id, Title, FileType, FileExtension, ContentSize, 
                       CreatedDate, LastModifiedDate
                FROM ContentDocument 
                WHERE Id = '{doc_id}'
            """
            data_doc = sf.query(query_doc)
            docs = data_doc.get("records", [])
            if docs:
                doc = docs[0]
                print(f"\n  Documento: {doc.get('Title')}")
                print(f"  - ID: {doc.get('Id')}")
                print(f"  - Tipo: {doc.get('FileType')}")
                print(f"  - Extension: {doc.get('FileExtension')}")
                print(f"  - Tamano: {doc.get('ContentSize')} bytes")
                print(f"  - Creado: {doc.get('CreatedDate')}")
                print(f"  - Modificado: {doc.get('LastModifiedDate')}")

    # 4. Buscar en Chatter del Case
    print("\n--- Chatter del Case ---")
    try:
        response = sf.restful(f"chatter/feeds/record/{tsi_id}/feed-elements", method="GET")
        elements = response.get("elements", [])
        print(f"Total de posts: {len(elements)}")
        
        for el in elements:
            # Buscar archivos en capabilities
            capabilities = el.get("capabilities", {})
            if "files" in capabilities:
                files = capabilities["files"].get("items", [])
                if files:
                    print(f"\n  Post de: {el.get('actor', {}).get('name')}")
                    print(f"  Fecha: {el.get('createdDate')}")
                    for f in files:
                        print(f"  - Archivo: {f.get('title')} ({f.get('description', 'Sin desc')})")
            
            # Imprimir info del post para debugging
            body_segments = el.get("body", {}).get("messageSegments", [])
            text = "".join(s.get("text", "") for s in body_segments if s.get("type") == "Text")
            if text:
                try:
                    print(f"\n  Post de: {el.get('actor', {}).get('name')} ({el.get('createdDate')})")
                    print(f"  Texto: {text[:100]}...")
                except Exception:
                    print(f"\n  Post de: {el.get('actor', {}).get('name')} ({el.get('createdDate')})")
                    print(f"  Texto: [No se pudo mostrar por encoding]")
    except Exception as e:
        print(f"Error al obtener Chatter: {e}")

    # 5. Buscar ContentVersion directamente
    print("\n--- ContentVersion del Case ---")
    query_cv = f"""
        SELECT Id, Title, FileType, ContentSize, CreatedDate
        FROM ContentVersion
        WHERE FirstPublishLocationId = '{tsi_id}'
    """
    data_cv = sf.query(query_cv)
    versions = data_cv.get("records", [])
    print(f"Total de ContentVersion: {len(versions)}")
    for v in versions:
        print(f"  - {v.get('Title')} ({v.get('FileType')}, {v.get('ContentSize')} bytes)")


def buscar_claims_con_adjuntos():
    """Busca claims con múltiples adjuntos para tener un mejor ejemplo."""
    sf = connect_salesforce()
    
    print("\n--- Buscando claims Factory Warranty con adjuntos ---\n")
    
    # Obtener claims Factory Warranty
    query = """
        SELECT Id, Name, TSINumber__c, ClaimType, Status
        FROM Claim 
        WHERE ClaimType = 'Factory Warranty'
        AND Status IN ('Submitted', 'Draft')
        LIMIT 20
    """
    data = sf.query_all(query)
    claims = data.get("records", [])
    
    for claim in claims:
        tsi_id = claim.get("TSINumber__c")
        if not tsi_id:
            continue
        
        # Contar adjuntos
        query_adj = f"""
            SELECT COUNT(Id) total
            FROM ContentDocumentLink 
            WHERE LinkedEntityId = '{tsi_id}'
        """
        data_adj = sf.query(query_adj)
        total = data_adj.get("records", [{}])[0].get("total", 0)
        
        if total > 1:
            print(f"Claim: {claim.get('Name')} | TSI: {tsi_id} | Adjuntos: {total}")
    
    print("\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--buscar":
            buscar_claims_con_adjuntos()
        else:
            claim_number = sys.argv[1]
            test_adjuntos_extendido(claim_number)
    else:
        claim_number = input("Ingrese el numero de reclamo: ").strip()
        test_adjuntos_extendido(claim_number)
