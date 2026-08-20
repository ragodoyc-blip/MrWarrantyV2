"""
Búsqueda completa de adjuntos para claim 001972.
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
               Complaint__c, Cause__c, Correction__c
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
    
    print(f"CLAIM: {claim.get('Name')}")
    print(f"  Claim ID: {claim_id}")
    print(f"  TSI (Case ID): {tsi_id}")
    print(f"  Complaint: {claim.get('Complaint__c')}")
    print(f"  Cause: {claim.get('Cause__c')}\n")

    # 2. Buscar adjuntos en el CLAIM
    print("--- ADJUNTOS EN CLAIM ---")
    query_claim_adj = f"""
        SELECT ContentDocumentId
        FROM ContentDocumentLink 
        WHERE LinkedEntityId = '{claim_id}'
    """
    data_claim_adj = sf.query(query_claim_adj)
    claim_links = data_claim_adj.get("records", [])
    
    for link in claim_links:
        doc_id = link.get("ContentDocumentId")
        query_doc = f"""
            SELECT Title, FileType, ContentSize
            FROM ContentDocument WHERE Id = '{doc_id}'
        """
        data_doc = sf.query(query_doc)
        docs = data_doc.get("records", [])
        if docs:
            doc = docs[0]
            print(f"  - {doc.get('Title')} ({doc.get('FileType')}, {doc.get('ContentSize')} bytes)")

    # 3. Buscar adjuntos en el CASE (TSI)
    print(f"\n--- ADJUNTOS EN CASE (TSI) ---")
    if tsi_id:
        query_case_adj = f"""
            SELECT ContentDocumentId
            FROM ContentDocumentLink 
            WHERE LinkedEntityId = '{tsi_id}'
        """
        data_case_adj = sf.query(query_case_adj)
        case_links = data_case_adj.get("records", [])
        
        for link in case_links:
            doc_id = link.get("ContentDocumentId")
            query_doc = f"""
                SELECT Title, FileType, ContentSize
                FROM ContentDocument WHERE Id = '{doc_id}'
            """
            data_doc = sf.query(query_doc)
            docs = data_doc.get("records", [])
            if docs:
                doc = docs[0]
                print(f"  - {doc.get('Title')} ({doc.get('FileType')}, {doc.get('ContentSize')} bytes)")

    # 4. Clasificar adjuntos
    print(f"\n--- CLASIFICACION POR NOMBRE ---")
    classifications = {
        "plm": [],
        "analisis_aceite": [],
        "datapacks": [],
        "reporte_tecnico": [],
        "fotografias": [],
    }

    keywords = {
        "plm": ["plm"],
        "analisis_aceite": ["oil analysis", "analisis de aceite", "oil leakage", "oil sample"],
        "datapacks": ["dsc_", "datapack", "dsc"],
        "reporte_tecnico": ["technical report", "reporte tecnico", "failure analysis", "repair"],
        "fotografias": ["foto", "photo", "imagen", "image", "picture", "img_", "dsc_", "screenshot"],
    }

    # Recopilar todos los adjuntos
    all_docs = []
    for link in claim_links + (case_links if tsi_id else []):
        doc_id = link.get("ContentDocumentId")
        query_doc = f"""
            SELECT Title, FileType
            FROM ContentDocument WHERE Id = '{doc_id}'
        """
        data_doc = sf.query(query_doc)
        docs = data_doc.get("records", [])
        if docs:
            all_docs.append(docs[0])

    for doc in all_docs:
        title_lower = doc.get("Title", "").lower()
        for tipo, kw_list in keywords.items():
            if any(kw in title_lower for kw in kw_list):
                classifications[tipo].append(doc.get("Title"))
                break

    for tipo, docs in classifications.items():
        estado = "ENCONTRADO" if docs else "NO ENCONTRADO"
        print(f"\n  {tipo.upper()}: {estado}")
        for doc in docs:
            print(f"    - {doc}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import sys
    claim = sys.argv[1] if len(sys.argv) > 1 else "001972"
    buscar_adjuntos_completo(claim)
