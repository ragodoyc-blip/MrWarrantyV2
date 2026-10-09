"""
Prueba de es_pais_cl y usa_prompt_sap (fallback por Sales_Office__c).
Ejecucion: python tests/test_pais_cl.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.core.utils import es_pais_cl, usa_prompt_sap


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


if __name__ == "__main__":
    check("CL exacto", es_pais_cl({"Claim_country__c": "CL"}) is True)
    check("cl minusculas", es_pais_cl({"Claim_country__c": "cl"}) is True)
    check("con espacios", es_pais_cl({"Claim_country__c": "  CL  "}) is True)
    check("PE falso", es_pais_cl({"Claim_country__c": "PE"}) is False)
    check("vacio falso", es_pais_cl({"Claim_country__c": ""}) is False)
    check("None falso", es_pais_cl({"Claim_country__c": None}) is False)
    check("sin clave falso", es_pais_cl({}) is False)
    check("dict None falso", es_pais_cl(None) is False)
    print("\nTodas las pruebas es_pais_cl pasaron.")

    check("SAP por pais CL", usa_prompt_sap({"Claim_country__c": "CL"}) is True)
    check("SAP pais vacio + Komatsu Chile",
          usa_prompt_sap({"Claim_country__c": "", "Sales_Office__c": "Komatsu Chile"}) is True)
    check("SAP pais None + JGI Chile",
          usa_prompt_sap({"Claim_country__c": None, "Sales_Office__c": "JGI Chile"}) is True)
    check("SAP sin pais + oficina minusculas",
          usa_prompt_sap({"Sales_Office__c": "komatsu chile"}) is True)
    check("SAP CL ignora oficina", usa_prompt_sap({"Claim_country__c": "CL", "Sales_Office__c": "Lima"}) is True)
    check("no SAP PE + oficina Chile",
          usa_prompt_sap({"Claim_country__c": "PE", "Sales_Office__c": "Komatsu Chile"}) is False)
    check("no SAP sin datos", usa_prompt_sap({}) is False)
    check("no SAP oficina otra",
          usa_prompt_sap({"Claim_country__c": "", "Sales_Office__c": "Komatsu Peru"}) is False)
    print("\nTodas las pruebas usa_prompt_sap pasaron.")
