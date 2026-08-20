"""
Módulo: dynamics_fc_service_news.py
Descripción:
    Consulta datos desde Dynamics 365 para:
    1. Obtener información de un FC Master.
    2. Buscar su Service News asociado.
    3. Extraer sus Type A Repair Parts (kom_psnparts).
"""

import pandas as pd

from mr_warranty.adapters.sqis_client import _get_session
from mr_warranty.config.config import DYNAMICS_API_URL
from mr_warranty.core.logger import log


def get_fc_master(fc_number: str) -> dict | None:
    """Consulta la tabla kom_fcmasters por número de FC."""
    url = f"{DYNAMICS_API_URL}/kom_fcmasters?$filter=kom_servicenewsnumbertext eq '{fc_number}'"
    response = _get_session().get(url)

    if response.status_code != 200:
        log.error("Falló consulta FC Master (%s)", response.status_code)
        return None

    data = response.json().get("value", [])
    return data[0] if data else None


def get_service_news(servicenews_number: str) -> dict | None:
    """Consulta la tabla kom_servicenewses filtrando por kom_servicenewsnumber."""
    url = f"{DYNAMICS_API_URL}/kom_servicenewses?$filter=kom_servicenewsnumber eq '{servicenews_number}'"
    response = _get_session().get(url)

    if response.status_code != 200:
        log.error("Falló consulta Service News (%s)", response.status_code)
        return None

    data = response.json().get("value", [])
    return data[0] if data else None


def get_psn_parts(servicenews_id: str) -> pd.DataFrame:
    """Consulta la tabla kom_psnparts filtrando por el ID del Service News."""
    url = f"{DYNAMICS_API_URL}/kom_psnparts?$filter=_kom_servicenewsid_value eq {servicenews_id}"
    response = _get_session().get(url)

    if response.status_code != 200:
        log.error("Falló consulta PSN Parts (%s)", response.status_code)
        return pd.DataFrame()

    data = response.json()
    return pd.DataFrame(data.get("value", []))


def Partes_presentes(service_news_number: str) -> pd.DataFrame | None:
    """Flujo completo: buscar Service News y listar Type A Repair Parts."""
    service_news = get_service_news(service_news_number)

    if not service_news:
        log.warning("No se encontró Service News '%s'", service_news_number)
        return None

    service_news_id = service_news.get("kom_servicenewsid")
    log.info("Service News ID encontrado: %s", service_news_id)

    parts = get_psn_parts(service_news_id)
    if parts.empty:
        return parts

    parts["kom_partsquantity"] = pd.to_numeric(parts["kom_partsquantity"], errors="coerce").fillna(0).astype(int)
    parts = parts[["kom_newpartname", "kom_newpartnumber", "kom_partsquantity"]]

    return parts
