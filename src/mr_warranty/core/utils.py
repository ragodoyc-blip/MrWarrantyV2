from __future__ import annotations

from datetime import datetime, timedelta
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


def calcular_periodo_plm(fecha_falla: Optional[str], fecha_puesta_marcha: Optional[str]) -> tuple[str, str]:
    """Calcula el período PLM válido para un reclamo Salesforce."""
    failure = strip_tz(parse_datetime(fecha_falla))
    commissioned = strip_tz(parse_datetime(fecha_puesta_marcha))
    if failure is None:
        return "", ""

    if commissioned is not None and (failure - commissioned).days < 365:
        start = commissioned
    else:
        start = failure - timedelta(days=365)

    return start.strftime("%Y-%m-%d"), failure.strftime("%Y-%m-%d")


def componente_usa_aceite_hidraulico(componente: str, contexto: str = "") -> bool:
    """Determina si el componente pertenece a un sistema hidráulico conocido."""
    texto = f"{componente} {contexto}".lower()
    hydraulic_terms = (
        "hydraulic",
        "hidraulic",
        "hidrául",
        "hydraulic pump",
        "hydraulic motor",
        "hydraulic cylinder",
        "hydraulic valve",
        "hydraulic hose",
        "bomba hidráulica",
        "cilindro hidráulico",
        "válvula hidráulica",
        "manguera hidráulica",
    )
    return any(term in texto for term in hydraulic_terms)


def seleccionar_imagenes_para_ia(urls_sas: list[str], max_images: int = 10) -> list[str]:
    """Selecciona imágenes para IA: portada + distribución uniforme (extraído de API_Salesforce)."""
    if not urls_sas:
        return []
    if len(urls_sas) <= max_images:
        return urls_sas
    seleccionadas = [urls_sas[0]]
    restantes = urls_sas[1:]
    step = max(1, len(restantes) // (max_images - 1))
    for i in range(0, len(restantes), step):
        if len(seleccionadas) >= max_images:
            break
        seleccionadas.append(restantes[i])
    return seleccionadas[:max_images]


def puntaje_plm_presencia(titulos: list[str], ponderacion: float) -> dict:
    """Puntaje parcial de PLM por presencia solo por nombre.

    Se usa cuando hay archivos clasificados como PLM pero ninguno dejo
    URLs legibles para la IA (ej. ZIPs). Otorga la mitad de la ponderacion.
    """
    nombres = ", ".join(t for t in (titulos or []) if t) or "sin detalle"
    return {
        "score": round((ponderacion or 0) * 0.5, 4),
        "reason": f"PLM presente solo por nombre ({nombres}); formato no legible por IA; puntaje parcial por presencia",
    }


# Claim_Type__c exentos de PLM: puntaje maximo sin validacion.
CLAIM_TYPES_SIN_PLM = frozenset({
    "sk - repair prior to commissioning",
    "ma - missing or damaged part prior to commissioning",
})


def plm_no_requerido(claim_type__c: str | None) -> bool:
    """Indica si el PLM no es requerido (SK/MA: puntaje maximo directo)."""
    return str(claim_type__c or "").strip().lower() in CLAIM_TYPES_SIN_PLM


def es_pais_cl(claim_data: dict | None) -> bool:
    """Indica si el reclamo es de Chile (Claim_country__c = CL).

    Normaliza mayusculas y espacios. Retorna False si falta el dato.
    """
    pais = ((claim_data or {}).get("Claim_country__c") or "")
    return str(pais).strip().upper() == "CL"


# Oficinas de Chile para el fallback SAP cuando Claim_country__c viene vacio.
OFICINAS_CHILE = frozenset({"komatsu chile", "jgi chile"})


def usa_prompt_sap(claim_data: dict | None) -> bool:
    """Indica si el invoice debe evaluarse con la variante SAP.

    True si Claim_country__c = CL, o si el pais viene vacio y el
    Case trae Sales_Office__c de Chile (Komatsu Chile / JGI Chile).
    """
    if es_pais_cl(claim_data):
        return True
    pais = str(((claim_data or {}).get("Claim_country__c") or "")).strip()
    if pais:
        return False
    oficina = str(((claim_data or {}).get("Sales_Office__c") or "")).strip().lower()
    return oficina in OFICINAS_CHILE


def requiere_factura(cantidad) -> bool:
    """Indica si corresponde analizar facturas según Claim.PartsRequestedQuantity__c.

    True solo si es numérico > 0. Cero, vacío, None, NaN o ilegible → False.
    """
    if cantidad is None or isinstance(cantidad, bool):
        return False
    try:
        valor = float(str(cantidad).strip())
    except (TypeError, ValueError):
        return False
    if valor != valor:  # NaN
        return False
    return valor > 0


def calcular_score_adjuntos(
    clasif: dict,
    pond: dict,
    tr_result: dict,
    plm_result: dict,
    photo_result: dict,
    oil_result: dict | None = None,
) -> dict:
    """Calcula scores de adjuntos usando validación IA y presencia de Datapacks.
    Retorna dict con scores y razones coherentes.
    """
    # Technical Report
    score_tr_kw = pond.get("technical_report", 0) if clasif.get("reporte_tecnico") else 0
    if "score" in tr_result:
        score_tr, tr_reason = tr_result.get("score", 0), tr_result.get("reason", "Error IA")
    else:
        score_tr, tr_reason = score_tr_kw, ", ".join(clasif.get("reporte_tecnico", [])) or "No encontrado"

    # PLM
    score_plm_kw = pond.get("plm", 0) if clasif.get("plm") else 0
    if "score" in plm_result:
        score_plm, plm_reason = plm_result.get("score", 0), plm_result.get("reason", "Error IA")
    else:
        score_plm, plm_reason = score_plm_kw, ", ".join(clasif.get("plm", [])) or "No encontrado"

    # Photographs
    score_photos_kw = pond.get("photographs", 0) if clasif.get("fotografias") else 0
    if "score" in photo_result:
        score_photos, photos_reason = photo_result.get("score", 0), photo_result.get("reason", "Error IA")
    else:
        score_photos, photos_reason = score_photos_kw, ", ".join(clasif.get("fotografias", [])) or "No encontrado"

    # Oil Analysis: validación IA de máquina, serial y componente.
    if oil_result is not None:
        score_aceite = oil_result.get("score", 0)
        aceite_reason = oil_result.get("reason", "Error IA")
    else:
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
