"""
Prueba para verificar campos disponibles en el diccionario.
"""

from mr_warranty.adapters.salesforce_client import process_salesforce_data


def test_campos(claim_number: str):
    print(f"\nCampos disponibles en el diccionario para claim {claim_number}:\n")
    
    diccionario = process_salesforce_data(claim_number)
    
    print("Keys del diccionario:")
    for key in sorted(diccionario.keys()):
        value = diccionario[key]
        print(f"  {key}: {type(value).__name__} = {str(value)[:80]}...")


if __name__ == "__main__":
    test_campos("002019")
