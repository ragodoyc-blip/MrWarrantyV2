"""
Prueba del puntaje parcial de PLM por presencia y de plm_no_requerido.

PLM con archivos detectados por nombre pero sin URLs legibles
para la IA (ej. ZIPs): mitad de la ponderacion (0.025).
SK/MA: PLM no requerido (exento).
Ejecucion: python tests/test_plm_presencia.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF
from mr_warranty.core.utils import plm_no_requerido, puntaje_plm_presencia

POND_PLM = PONDERACIONES_STD_SF.get("plm")


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


def test_presencia_da_mitad():
    r = puntaje_plm_presencia(["DATA PLM IV", "Data PLM IV"], POND_PLM)
    check("presencia puntaje", r["score"] == round(POND_PLM * 0.5, 4), str(r))
    check("presencia nombres", "DATA PLM IV" in r["reason"] and "Data PLM IV" in r["reason"], r["reason"])


def test_titulos_vacios():
    r = puntaje_plm_presencia([], POND_PLM)
    check("vacio puntaje", r["score"] == round(POND_PLM * 0.5, 4), str(r))
    check("vacio razon", "sin detalle" in r["reason"], r["reason"])


if __name__ == "__main__":
    test_presencia_da_mitad()
    test_titulos_vacios()
    print("\nTodas las pruebas PLM presencia pasaron.")

    check("SK exento", plm_no_requerido("SK - Repair prior to commissioning") is True)
    check("MA exento", plm_no_requerido("MA - Missing or Damaged Part prior to commissioning") is True)
    check("minusculas/espacios", plm_no_requerido("  sk - repair prior to commissioning  ") is True)
    check("S1 no exento", plm_no_requerido("S1 - Standard Warranty") is False)
    check("vacio no exento", plm_no_requerido("") is False)
    check("None no exento", plm_no_requerido(None) is False)
    check("PC no exento", plm_no_requerido("PC - Part DB Installed") is False)
    print("\nTodas las pruebas plm_no_requerido pasaron.")
