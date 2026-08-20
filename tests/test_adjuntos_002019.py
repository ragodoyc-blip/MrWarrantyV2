"""
Busqueda completa de adjuntos para caso 002019.
Busca en Claim, Case (TSI) y Chatter.
"""

from mr_warranty.adapters.salesforce_client import connect_salesforce


def buscar_adjuntos_completo(claim_number: str):
    sf = connect_salesforce()
    print(f"\n{'='*60}")
    print(f"BUSQUEDA COMPLETA - Claim: {claim_number}")
    print(f"{'='*60}\n")

    # 1. Obtener el Claim
    query_claim = f"""
        SELECT Id, Name, TSINumber__c, ClaimType, Status, 
               Complaint__c, Cause__c, Correction__c,
               Servicing_Distributor__c, Account__c
        FROM Claim 
        WHERE Name = '{claim_number}'
    """
    data = sf.query_all(query_claim)
    claims = data.get("records", [])

    if not claims:
        print(f"Claim {claim_number} no encontrado")
        return

    claim = claims[0]
    claim_id = claim.get("Id")
    tsi_id = claim.get("TSINumber__c")
    
    print(f"CLAIM:")
    print(f"  ID: {claim_id}")
    print(f"  Name: {claim.get('Name')}")
    print(f"  ClaimType: {claim.get('ClaimType')}")
    print(f"  Status: {claim.get('Status')}")
    print(f"  Complaint: {claim.get('Complaint__c')}")
    print(f"  Cause: {claim.get('Cause__c')}")
    print(f"  Correction: {claim.get('Correction__c')}")
    print(f"  Distributor: {claim.get('Servicing_Distributor__c')}")
    print(f"  Account: {claim.get('Account__c')}")
    print(f"\n  TSI (Case ID): {tsi_id}\n")

    # 2. Buscar adjuntos en el CLAIM
    print("--- ADJUNTOS EN CLAIM ---")
    query_claim_adj = f"""
        SELECT ContentDocumentId, ContentDocument.Title, 
               ContentDocument.FileType, ContentDocument.ContentSize
        FROM ContentDocumentLink 
        WHERE LinkedEntityId = '{claim_id}'
    """
    data_claim_adj = sf.query(query_claim_adj)
    claim_adj = data_claim_adj.get("records", [])
    print(f"Total adjuntos en Claim: {len(claim_adj)}")
    for adj in claim_adj:
        doc = adj.get("ContentDocument", {})
        print(f"  - {doc.get('Title')} ({doc.get('FileType')}, {doc.get('ContentSize')} bytes)")

    # 3. Buscar adjuntos en el CASE (TSI)
    print(f"\n--- ADJUNTOS EN CASE (TSI) ---")
    if tsi_id:
        query_case_adj = f"""
            SELECT ContentDocumentId, ContentDocument.Title, 
                   ContentDocument.FileType, ContentDocument.ContentSize
            FROM ContentDocumentLink 
            WHERE LinkedEntityId = '{tsi_id}'
        """
        data_case_adj = sf.query(query_case_adj)
        case_adj = data_case_adj.get("records", [])
        print(f"Total adjuntos en Case: {len(case_adj)}")
        for adj in case_adj:
            doc = adj.get("ContentDocument", {})
            print(f"  - {doc.get('Title')} ({doc.get('FileType')}, {doc.get('ContentSize')} bytes)")
    else:
        print("No hay TSI asociado")

    # 4. Buscar en Chatter del Case
    print(f"\n--- CHATTER DEL CASE ---")
    if tsi_id:
        try:
            response = sf.restful(f"chatter/feeds/record/{tsi_id}/feed-elements", method="GET")
            elements = response.get("elements", [])
            print(f"Total posts: {len(elements)}")
            
            for idx, el in enumerate(elements, 1):
                actor = el.get("actor", {}).get("name", "Unknown")
                fecha = el.get("createdDate", "")
                
                # Obtener texto del post
                body_segments = el.get("body", {}).get("messageSegments", [])
                text = "".join(s.get("text", "") for s in body_segments if s.get("type") == "Text")
                
                # Buscar archivos
                capabilities = el.get("capabilities", {})
                files = capabilities.get("files", {}).get("items", [])
                comments = capabilities.get("comments", {}).get("items", [])
                
                print(f"\n  Post #{idx}:")
                print(f"    Autor: {actor}")
                print(f"    Fecha: {fecha}")
                if text:
                    try:
                        print(f"    Texto: {text[:150]}...")
                    except:
                        print(f"    Texto: [encoding issue]")
                
                if files:
                    print(f"    Archivos:")
                    for f in files:
                        print(f"      - {f.get('title')} ({f.get('description', '')})")
                
                if comments:
                    print(f"    Comentarios: {len(comments)}")
                    for c in comments[:3]:
                        c_actor = c.get("actor", {}).get("name", "")
                        c_body = "".join(s.get("text", "") for s in c.get("body", {}).get("messageSegments", []) if s.get("type") == "Text")
                        try:
                            print(f"      - {c_actor}: {c_body[:80]}...")
                        except:
                            print(f"      - {c_actor}: [encoding issue]")
        except Exception as e:
            print(f"Error al obtener Chatter: {e}")
    else:
        print("No hay TSI para buscar Chatter")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    buscar_adjuntos_completo("002019")
