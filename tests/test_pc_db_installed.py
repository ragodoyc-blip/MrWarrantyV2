"""
Pruebas PC - Part DB Installed.

- Within standard warranty INVERTIDO sobre el equipo:
  dentro de 1 año = 0, sobre 1 año = puntaje máximo.
- Extracción de partes failing/installed desde texto libre
  (pueden no estar en campos estructurados).
- Doble factura: <2 documentos = 0 sin llamar IA.
Ejecución: python tests/test_pc_db_installed.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF
from mr_warranty.domain.validation_fc_sf import ValidacionStandard, es_pc_db_installed
from mr_warranty.services.prompts import (
    extraer_partes_db_installed,
    validar_purchase_invoice_db_installed_con_ia,
)

MAX_WARRANTY = PONDERACIONES_STD_SF.get("within_standard_warranty")
DB = "PC - Part DB Installed"

BASE_FUERA = {
    "FailureDate__c": "2024-06-01T00:00:00.000+0000",
    "MachineRepairCompletionDate__c": "2024-06-10T00:00:00.000+0000",
    "CreatedDate": "2024-06-15T00:00:00.000+0000",
    "MachineCommissionedDate__c": "2020-01-01T00:00:00.000+0000",
}
BASE_DENTRO = {
    **BASE_FUERA,
    "MachineCommissionedDate__c": "2024-01-01T00:00:00.000+0000",
}


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


def test_detecta_db():
    check("detecta DB exacto", es_pc_db_installed(DB))
    check("detecta DB con espacios", es_pc_db_installed("  pc - part db installed  "))
    check("no confunde PC normal", not es_pc_db_installed("PC - Other"))


def test_vigencia_invertida():
    r_fuera = ValidacionStandard(BASE_FUERA, es_pc=True, claim_type__c=DB)
    check("fuera puntaje max", r_fuera["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r_fuera))
    r_dentro = ValidacionStandard(BASE_DENTRO, es_pc=True, claim_type__c=DB)
    check("dentro puntaje 0", r_dentro["within_standard_warranty_ponderacion"] == 0, str(r_dentro))
    check("dentro menciona fuera de garantia", "fuera de garant" in r_dentro["within_standard_warranty_reason"].lower(), r_dentro["within_standard_warranty_reason"])


def test_otras_columnas_no_cambian():
    r = ValidacionStandard(BASE_FUERA, es_pc=True, claim_type__c=DB)
    check("repair deadline", r["Repair_deadline_ponderacion"] == 0.15, str(r))
    check("claim deadline", r["Claim_Deadline_ponderacion"] == 0.15, str(r))


def test_extrae_partes_solo_texto():
    claim = {
        "CausalPart__c": "",
        "Product_Code__c": "",
        "Complaint__c": "Falla componente 7826-77-7000",
        "Correction__c": "Se instala el componente 7826-47-1007",
        "Cause__c": "", "Summary": "", "Description": "",
    }
    tsi = {"Subject": "", "Description": "", "Resolution_Details__c": "reemplazo 7826-47-1007 por 7826-77-7000"}
    p = extraer_partes_db_installed(claim, tsi)
    check("failing texto", p["failing"] == "7826-77-7000", str(p))
    check("installed texto", p["installed"] == "7826-47-1007", str(p))


def test_extrae_con_estructurado_como_pista():
    claim = {
        "Complaint__c": "ruido",
        "Correction__c": "se instala R107235D1 nuevo",
        "Cause__c": "", "Summary": "", "Description": "",
    }
    p = extraer_partes_db_installed(claim, {}, causal_part="58F-98-40240")
    check("failing estructurado", p["failing"] == "58F-98-40240", str(p))
    check("installed texto", p["installed"] == "R107235D1", str(p))


def test_doble_factura_sin_docs():
    r = validar_purchase_invoice_db_installed_con_ia([], {"Name": "X"})
    check("sin urls 0", r["score"] == 0, str(r))
    r2 = validar_purchase_invoice_db_installed_con_ia(
        ["http://x/1.png"], {"Name": "X"}, num_docs=1
    )
    check(
        "1 doc exige dos facturas",
        r2["score"] == 0 and "1 respaldo" in r2["reason"],
        str(r2),
    )


if __name__ == "__main__":
    test_detecta_db()
    test_vigencia_invertida()
    test_otras_columnas_no_cambian()
    test_extrae_partes_solo_texto()
    test_extrae_con_estructurado_como_pista()
    test_doble_factura_sin_docs()
    print("\nTodas las pruebas PC DB Installed pasaron.")
