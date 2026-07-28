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
