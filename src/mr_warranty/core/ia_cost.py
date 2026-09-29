"""Medidor de consumo IA por reclamo.

El pipeline es secuencial: se reinicia al inicio de cada reclamo y se lee
al armar el registro. Cada intento de API cuenta (es gasto real); los
aciertos de cache no pasan por aqui y cuestan 0.
"""
from __future__ import annotations

from mr_warranty.config.config import (
    IA_PRICE_INPUT_USD_PER_MTOK,
    IA_PRICE_OUTPUT_USD_PER_MTOK,
)

_medicion = {"calls": 0, "input_tokens": 0, "output_tokens": 0}


def iniciar_medicion() -> None:
    """Reinicia el medidor para un nuevo reclamo."""
    _medicion["calls"] = 0
    _medicion["input_tokens"] = 0
    _medicion["output_tokens"] = 0


def registrar_llamada(input_tokens: int | None, output_tokens: int | None) -> None:
    """Suma un intento de API con sus tokens (None/ilegible = 0)."""
    try:
        in_tok = int(input_tokens or 0)
    except (TypeError, ValueError):
        in_tok = 0
    try:
        out_tok = int(output_tokens or 0)
    except (TypeError, ValueError):
        out_tok = 0
    _medicion["calls"] += 1
    _medicion["input_tokens"] += max(in_tok, 0)
    _medicion["output_tokens"] += max(out_tok, 0)


def resumen() -> dict:
    """Retorna llamadas, tokens y costo estimado USD del reclamo actual."""
    calls = _medicion["calls"]
    in_tok = _medicion["input_tokens"]
    out_tok = _medicion["output_tokens"]
    cost = (in_tok * IA_PRICE_INPUT_USD_PER_MTOK + out_tok * IA_PRICE_OUTPUT_USD_PER_MTOK) / 1_000_000
    return {
        "calls": calls,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": round(cost, 4),
    }
