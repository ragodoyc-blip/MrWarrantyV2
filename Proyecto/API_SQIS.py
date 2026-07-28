import pandas as pd
import requests

from config import DYNAMICS_API_URL
from cookies import COOKIES
from logger import log

# ── Sesión HTTP reutilizable para Dynamics 365 ──────────────
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    """Retorna una sesión HTTP reutilizable con headers de Dynamics."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Accept": "application/json",
            "Cookie": COOKIES.get("session"),
        })
    return _session


def getWarrantyclaimid(RFnumber: str) -> str | None:
    """Obtiene el GUID de un warrantyclaim por número de reclamo."""
    url = (
        f"{DYNAMICS_API_URL}/kom_warrantyclaims?"
        f"$filter=kom_claimnumber%20eq%20%27{RFnumber}%27&$select=kom_warrantyclaimid"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        data = response.json().get("value", [])
        if data:
            return data[0].get("kom_warrantyclaimid")

    log.error("No se pudo obtener ID para reclamo %s (HTTP %s)", RFnumber, response.status_code)
    return None


def get_offerstatus_labels() -> dict[int, str]:
    """Obtiene el mapa {codigo_int: etiqueta_texto} del campo kom_offerstatus."""
    url = (
        f"{DYNAMICS_API_URL}/"
        "EntityDefinitions(LogicalName='kom_warrantyclaim')/"
        "Attributes(LogicalName='kom_offerstatus')/"
        "Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=OptionSet"
    )
    try:
        response = _get_session().get(url)
        if response.status_code == 200:
            options = response.json().get("OptionSet", {}).get("Options", [])
            return {opt["Value"]: opt["Label"]["UserLocalizedLabel"]["Label"] for opt in options}
    except Exception as e:
        log.warning("Error obteniendo labels de offerstatus: %s", e)

    return {183890003: "Under Application"}


def Allgetwarrantyclaim() -> pd.DataFrame:
    """Obtiene todos los warrantyclaims desde Dynamics."""
    url = (
        f"{DYNAMICS_API_URL}/kom_warrantyclaims?"
        "$select=createdon,kom_claimnumber,_kom_offerclaimtype_value,kom_offerstatus"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        data = response.json()
        return pd.DataFrame(data["value"])

    log.error("Error al obtener warrantyclaims: HTTP %s", response.status_code)
    return pd.DataFrame()


def getwarrantyclaim(RfNumber: str) -> dict | None:
    """Obtiene los datos de un warrantyclaim específico."""
    url = (
        f"{DYNAMICS_API_URL}/kom_warrantyclaims?"
        f"$filter=kom_claimnumber%20eq%20%27{RfNumber}%27"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        data = response.json()
        value = data.get("value", [])
        if value:
            return value[0]

    log.error("No se pudo obtener warrantyclaim %s", RfNumber)
    return None


def getwarrantyclaimdetails(kom_clainnumber_value: str) -> pd.DataFrame:
    """Obtiene los detalles de un warrantyclaim."""
    url = (
        f"{DYNAMICS_API_URL}/kom_warrantyclaimdetails?"
        f"$filter=_kom_claimnumber_value%20eq%20{kom_clainnumber_value}"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        data = response.json()
        return pd.DataFrame(data.get("value", []))

    log.error("Error al obtener detalles del reclamo %s", kom_clainnumber_value)
    return pd.DataFrame()


def getkom_fcmachinedetails(WarramtyID: str) -> str | None:
    """Obtiene el nombre del FC machine detail."""
    url = (
        f"{DYNAMICS_API_URL}/kom_fcmachinedetails?"
        f"$filter=%20_kom_claimnumber_value%20eq%20{WarramtyID}"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        try:
            data = response.json().get("value", [])
            return data[0].get("kom_name")
        except (IndexError, AttributeError, TypeError):
            return None
    return None


def getkom_warrantyclaimworks(WarramtyID: str) -> pd.DataFrame | None:
    """Obtiene los claim works asociados a un warrantyclaim."""
    url = (
        f"{DYNAMICS_API_URL}/kom_warrantyclaimworks?"
        f"filter=_kom_claimnumber_value%20eq%20{WarramtyID}"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        try:
            data = response.json()
            return pd.DataFrame(data["value"])
        except (IndexError, AttributeError, TypeError):
            return None
    return None


def URL_Adjuntos(RfNumber: str) -> list[dict] | None:
    """Obtiene las URLs de los adjuntos asociados a un reclamo."""
    kom_id = getWarrantyclaimid(RfNumber)
    if kom_id is None:
        log.warning("No se encontró ID para reclamo %s", RfNumber)
        return None

    url = (
        f"{DYNAMICS_API_URL}/adx_portalcomments%20?"
        f"$filter=_regardingobjectid_value%20eq%20{kom_id}"
    )
    response = _get_session().get(url)
    if response.status_code != 200:
        log.error("Falló consulta adjuntos (%s) para reclamo %s", response.status_code, RfNumber)
        return None

    data = response.json().get("value", [])
    activityidlist = [item.get("activityid") for item in data]

    adjuntos = []
    for activityid in activityidlist:
        url_annotations = (
            f"{DYNAMICS_API_URL}/annotations%20?"
            f"$select=filename,notetext,createdon%20&$filter=_objectid_value%20eq%20{activityid}"
        )
        response = _get_session().get(url_annotations)
        if response.status_code == 200:
            values = response.json().get("value", [])
            if not values:
                continue
            entry = values[0]
            adjuntos.append({
                "filename": entry.get("filename"),
                "url": entry.get("notetext"),
            })

    return adjuntos


def AllServiceNews() -> pd.DataFrame:
    """Obtiene todos los service news desde Dynamics."""
    url = (
        f"{DYNAMICS_API_URL}/kom_servicenewses?"
        "$select=kom_servicenewsnumber,_kom_componentname1_new_value,_kom_phenomenonname1_new_value"
    )
    response = _get_session().get(url)

    if response.status_code == 200:
        data = response.json()
        return pd.DataFrame(data["value"])

    log.error("Error al obtener Service News: HTTP %s", response.status_code)
    return pd.DataFrame()
