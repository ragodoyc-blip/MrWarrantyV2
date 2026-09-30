"""
Pruebas PA - Special Policy.

- Matriz S1: within_standard_warranty siempre máximo con "No aplica.".
- SPCR informativo 0-1 (no resta peso): sin docs = 0, máximo 1.0.
- Clasificación por keywords: SPCR ruteado sin IA.
Ejecución: python tests/test_pa_special_policy.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.adapters.salesforce_client import clasificar_adjuntos
from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF
from mr_warranty.domain.validation_fc_sf import ValidacionStandard, es_pa_special_policy
from mr_warranty.services.prompts import SPCR_MAX, validar_spcr_con_ia

MAX_WARRANTY = PONDERACIONES_STD_SF.get("within_standard_warranty")
PA = "PA - Special Policy"

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


def test_detecta_pa():
    check("detecta PA exacto", es_pa_special_policy(PA))
    check("detecta PA con espacios", es_pa_special_policy("  pa - special policy  "))
    check("no confunde S1", not es_pa_special_policy("S1 - Standard Warranty"))


def test_vigencia_no_aplica():
    r_exp = ValidacionStandard(BASE_EXPIRED, claim_type__c=PA)
    check("PA expirado puntaje", r_exp["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r_exp))
    check("PA expirado razon", r_exp["within_standard_warranty_reason"] == "No aplica.", r_exp["within_standard_warranty_reason"])
    r_val = ValidacionStandard(BASE_VALID, claim_type__c=PA)
    check("PA vigente puntaje", r_val["within_standard_warranty_ponderacion"] == MAX_WARRANTY, str(r_val))
    check("PA vigente razon", r_val["within_standard_warranty_reason"] == "No aplica.", r_val["within_standard_warranty_reason"])


def test_otras_columnas_s1():
    r = ValidacionStandard(BASE_EXPIRED, claim_type__c=PA)
    check("repair deadline", r["Repair_deadline_ponderacion"] == 0.15, str(r))
    check("claim deadline", r["Claim_Deadline_ponderacion"] == 0.15, str(r))


def test_spcr_escala():
    check("SPCR_MAX es 1.0", SPCR_MAX == 1.0, str(SPCR_MAX))
    r = validar_spcr_con_ia([], "980E-5", "A50116", claim_name="002434")
    check("sin docs score 0", r["score"] == 0.0, str(r))
    check("sin docs razon", "SPCR" in r["reason"], r["reason"])


def test_keywords_spcr():
    adjuntos = [
        {"title": "SPCR Form MAN38.1-F7 002434", "file_type": "pdf", "id": "a1"},
        {"title": "Special Policy Consideration Request", "file_type": "pdf", "id": "a2"},
        {"title": "PLM report", "file_type": "pdf", "id": "a3"},
    ]
    clasif = clasificar_adjuntos(adjuntos)
    check("SPCR por keywords", "SPCR Form MAN38.1-F7 002434" in clasif["special_policy"], str(clasif))
    check("consideration por keywords", "Special Policy Consideration Request" in clasif["special_policy"], str(clasif))
    check("PLM no contamina SPCR", "PLM report" not in clasif["special_policy"], str(clasif))
    check("categoria existe", "special_policy" in clasif, str(sorted(clasif)))


if __name__ == "__main__":
    test_detecta_pa()
    test_vigencia_no_aplica()
    test_otras_columnas_s1()
    test_spcr_escala()
    test_keywords_spcr()
    print("\nTodas las pruebas PA Special Policy pasaron.")
