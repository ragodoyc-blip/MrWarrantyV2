"""
Prueba del medidor core/ia_cost.py (sin llamadas API).
Ejecucion: python tests/test_ia_cost.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.config.config import (
    IA_PRICE_INPUT_USD_PER_MTOK,
    IA_PRICE_OUTPUT_USD_PER_MTOK,
)
from mr_warranty.core.ia_cost import iniciar_medicion, registrar_llamada, resumen


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


if __name__ == "__main__":
    iniciar_medicion()
    r = resumen()
    check("inicio en cero", r == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}, str(r))

    registrar_llamada(1_000_000, 500_000)
    registrar_llamada(2_000_000, None)
    registrar_llamada("abc", "xyz")
    r = resumen()
    esperado = round((3_000_000 * IA_PRICE_INPUT_USD_PER_MTOK + 500_000 * IA_PRICE_OUTPUT_USD_PER_MTOK) / 1_000_000, 4)
    check("llamadas", r["calls"] == 3, str(r))
    check("tokens in", r["input_tokens"] == 3_000_000, str(r))
    check("tokens out", r["output_tokens"] == 500_000, str(r))
    check("costo", r["cost_usd"] == esperado, f"{r['cost_usd']} vs {esperado}")

    iniciar_medicion()
    r = resumen()
    check("reset", r["calls"] == 0 and r["cost_usd"] == 0.0, str(r))
    print("\nTodas las pruebas ia_cost pasaron.")
