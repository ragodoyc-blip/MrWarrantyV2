"""
Prueba de regla SK/S1/MA en ValidacionStandard.

Todo Factory Warranty con Claim_Type__c en SK - Repair prior to
commissioning, S1 - Standard Warranty o MA - Missing or Damaged Part
prior to commissioning: within_standard_warranty siempre puntaje maximo
con razon "No aplica.".
Resto (vacio/desconocido/PC): logica normal por fechas.
Ejecucion: python tests/test_claim_type_precommissioning.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF
from mr_warranty.domain.validation_fc_sf import ValidacionStandard

MAX_WARRANTY = PONDERACIONES_STD_SF.get("within_standard_warranty")

# Equipo con mas de 1 anio entre puesta en marcha y falla -> expirado por fechas.
BASE_EXPIRED = {
    "FailureDate__c": "2024-06-01T00:00:00.000+0000",
    "MachineRepairCompletionDate__c": "2024-06-10T00:00:00.000+0000",
    "CreatedDate": "2024-06-15T00:00:00.000+0000",
    "MachineCommissionedDate__c": "2020-01-01T00:00:00.000+0000",
}

BASE_VALID = {
    **BASE_EXPIRED,
    "MachineCommissionedDate__c": "2024-01-01T00:00:00.000+0000",
}


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


def test_sk_expirado_da_maximo():
    r = ValidacionStandard(BASE_EXPIRED, claim_type__c="SK - Repair prior to commissioning")
    check("SK expirado puntaje", r["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r))
    check("SK expirado razon", r["within_standard_warranty_reason"] == "No aplica.", r["within_standard_warranty_reason"])


def test_ma_expirado_da_maximo():
    r = ValidacionStandard(BASE_EXPIRED, claim_type__c="MA - Missing or Damaged Part prior to commissioning")
    check("MA expirado puntaje", r["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r))
    check("MA expirado razon", r["within_standard_warranty_reason"] == "No aplica.", r["within_standard_warranty_reason"])


def test_s1_expirado_da_maximo():
    r = ValidacionStandard(BASE_EXPIRED, claim_type__c="S1 - Standard Warranty")
    check("S1 expirado puntaje", r["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r))
    check("S1 expirado razon", r["within_standard_warranty_reason"] == "No aplica.", r["within_standard_warranty_reason"])


def test_s1_vigente_da_maximo():
    r = ValidacionStandard(BASE_VALID, claim_type__c="S1 - Standard Warranty")
    check("S1 vigente puntaje", r["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r))
    check("S1 vigente razon", r["within_standard_warranty_reason"] == "No aplica.", r["within_standard_warranty_reason"])


def test_sin_claim_type_fallback_fechas():
    r_none = ValidacionStandard(BASE_EXPIRED, claim_type__c=None)
    r_empty = ValidacionStandard(BASE_EXPIRED, claim_type__c="  ")
    check("None fallback", r_none["within_standard_warranty_ponderacion"] == 0, str(r_none))
    check("vacio fallback", r_empty["within_standard_warranty_ponderacion"] == 0, str(r_empty))


def test_otras_columnas_no_cambian_en_sk():
    r = ValidacionStandard(BASE_EXPIRED, claim_type__c="SK - Repair prior to commissioning")
    check("SK repair deadline", r["Repair_deadline_ponderacion"] == 0.15, str(r))
    check("SK claim deadline", r["Claim_Deadline_ponderacion"] == 0.15, str(r))


if __name__ == "__main__":
    test_sk_expirado_da_maximo()
    test_ma_expirado_da_maximo()
    test_s1_expirado_da_maximo()
    test_s1_vigente_da_maximo()
    test_sin_claim_type_fallback_fechas()
    test_otras_columnas_no_cambian_en_sk()
    print("\nTodas las pruebas SK/S1/MA pasaron.")
