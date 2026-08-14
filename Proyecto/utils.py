from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_datetime(date_string: Optional[str]) -> Optional[datetime]:
    """Parsea un string de fecha intentando múltiples formatos.

    Args:
        date_string: Fecha en formato string.

    Returns:
        datetime parseado o None si el input es None/vacío.

    Raises:
        ValueError: Si el string no coincide con ningún formato conocido.
    """
    if not date_string or not str(date_string).strip():
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_string).strip(), fmt)
        except ValueError:
            continue

    raise ValueError(f"No se pudo parsear la fecha: '{date_string}'")


def strip_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Elimina la información de zona horaria de un datetime.

    Args:
        dt: datetime con o sin tzinfo.

    Returns:
        datetime sin tzinfo, o None si el input es None.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=None)


def max_score_with_reason(score_kw: float, reason_kw: str, score_ia: float, reason_ia: str) -> tuple:
    """Retorna (score_final, razon_final) usando el max entre keywords e IA.
    Si la IA tiene un puntaje mayor, usa la razon de IA.
    Si las keywords tienen mayor o igual puntaje, usa la razon de keywords.
    """
    if score_ia > score_kw:
        return score_ia, reason_ia
    return score_kw, reason_kw


def calcular_score_adjuntos(clasif: dict, pond: dict, tr_result: dict, plm_result: dict, photo_result: dict) -> dict:
    """Calcula scores de adjuntos usando Opcion C (max entre keywords e IA).
    Retorna dict con scores y razones coherentes.
    """
    # Technical Report
    score_tr_kw = pond.get("technical_report", 0) if clasif.get("reporte_tecnico") else 0
    score_tr_ia = tr_result.get("score", 0)
    score_tr, tr_reason = max_score_with_reason(
        score_tr_kw, ", ".join(clasif.get("reporte_tecnico", [])) or "No encontrado",
        score_tr_ia, tr_result.get("reason", "Error IA")
    )

    # PLM
    score_plm_kw = pond.get("plm", 0) if clasif.get("plm") else 0
    score_plm_ia = plm_result.get("score", 0)
    score_plm, plm_reason = max_score_with_reason(
        score_plm_kw, ", ".join(clasif.get("plm", [])) or "No encontrado",
        score_plm_ia, plm_result.get("reason", "Error IA")
    )

    # Photographs
    score_photos_kw = pond.get("photographs", 0) if clasif.get("fotografias") else 0
    score_photos_ia = photo_result.get("score", 0)
    score_photos, photos_reason = max_score_with_reason(
        score_photos_kw, ", ".join(clasif.get("fotografias", [])) or "No encontrado",
        score_photos_ia, photo_result.get("reason", "Error IA")
    )

    # Oil Analysis (solo keywords)
    score_aceite = pond.get("analisis_aceite", 0) if clasif.get("analisis_aceite") else 0
    aceite_reason = ", ".join(clasif.get("analisis_aceite", [])) or "No encontrado"

    # Datapacks (solo keywords)
    score_datapacks = pond.get("datapacks", 0) if clasif.get("datapacks") else 0
    datapacks_reason = ", ".join(clasif.get("datapacks", [])) or "No encontrado"

    return {
        "score_tr": score_tr, "tr_reason": tr_reason,
        "score_plm": score_plm, "plm_reason": plm_reason,
        "score_photos": score_photos, "photos_reason": photos_reason,
        "score_aceite": score_aceite, "aceite_reason": aceite_reason,
        "score_datapacks": score_datapacks, "datapacks_reason": datapacks_reason,
    }
