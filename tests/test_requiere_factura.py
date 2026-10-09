"""
Prueba del gate requiere_factura (Claim.PartsRequestedQuantity__c).
True solo si numerico > 0; 0/vacio/None/NaN/ilegible -> False.
Ejecucion: python tests/test_requiere_factura.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.core.utils import requiere_factura


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


if __name__ == "__main__":
    check("1 requiere", requiere_factura(1) is True)
    check("2.5 requiere", requiere_factura(2.5) is True)
    check("'3' requiere", requiere_factura("3") is True)
    check("0 no requiere", requiere_factura(0) is False)
    check("'0' no requiere", requiere_factura("0") is False)
    check("0.0 no requiere", requiere_factura(0.0) is False)
    check("None no requiere", requiere_factura(None) is False)
    check("vacio no requiere", requiere_factura("") is False)
    check("espacios no requiere", requiere_factura("   ") is False)
    check("NaN no requiere", requiere_factura(float("nan")) is False)
    check("'nan' no requiere", requiere_factura("nan") is False)
    check("texto no requiere", requiere_factura("abc") is False)
    check("negativo no requiere", requiere_factura(-2) is False)
    print("\nTodas las pruebas requiere_factura pasaron.")
