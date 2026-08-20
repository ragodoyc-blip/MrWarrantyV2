"""
Consulta un documento específico de ContentDocument.
"""

from mr_warranty.adapters.salesforce_client import connect_salesforce


def consultar_documento(doc_id: str):
    sf = connect_salesforce()
    
    query = f"""
        SELECT Id, Title, FileType, ContentSize, CreatedDate
        FROM ContentDocument 
        WHERE Id = '{doc_id}'
    """
    data = sf.query(query)
    docs = data.get("records", [])
    
    if docs:
        doc = docs[0]
        print(f"\nDocumento: {doc.get('Title')}")
        print(f"  ID: {doc.get('Id')}")
        print(f"  Tipo: {doc.get('FileType')}")
        print(f"  Tamano: {doc.get('ContentSize')} bytes")
        print(f"  Creado: {doc.get('CreatedDate')}")
        
        # Verificar a qué claims está vinculado
        query_link = f"""
            SELECT LinkedEntityId, LinkedEntity.Name
            FROM ContentDocumentLink 
            WHERE ContentDocumentId = '{doc_id}'
        """
        data_link = sf.query(query_link)
        links = data_link.get("records", [])
        print(f"\n  Vinculado a:")
        for link in links:
            print(f"    - {link.get('LinkedEntityId')} ({link.get('LinkedEntity', {}).get('Name', 'N/A')})")
    else:
        print(f"Documento {doc_id} no encontrado")


if __name__ == "__main__":
    consultar_documento("069Nr00000lhjzjIAA")
