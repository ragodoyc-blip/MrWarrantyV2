import json
from pathlib import Path

from logger import log
from sql_storage import (
    bulk_update_status_sql,
    bulk_upsert_reclamos,
    is_sql_enabled,
)

RUTA_PENDIENTES = Path(__file__).resolve().parent.parent / "Reclamos_Procesados_pendientes.jsonl"


def _serializar_para_json(valor):
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        try:
            return valor.isoformat()
        except Exception:
            return str(valor)
    return valor


def _guardar_en_pendientes(datos_dict):
    datos_serializables = {k: _serializar_para_json(v) for k, v in datos_dict.items()}
    with open(RUTA_PENDIENTES, "a", encoding="utf-8") as f:
        f.write(json.dumps(datos_serializables, ensure_ascii=False) + "\n")


def _leer_pendientes():
    if not RUTA_PENDIENTES.exists():
        return []

    pendientes = []
    with open(RUTA_PENDIENTES, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pendientes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pendientes


def _escribir_pendientes(pendientes):
    if not pendientes:
        RUTA_PENDIENTES.unlink(missing_ok=True)
        return

    with open(RUTA_PENDIENTES, "w", encoding="utf-8") as f:
        for item in pendientes:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _clave_reclamo(datos_dict):
    claim = str(datos_dict.get("ClaimNumber", "")).strip()
    plataforma = str(datos_dict.get("Plataforma", "")).strip()
    return claim, plataforma


def encolar_registro(datos_dict):
    """Guarda un reclamo en SQL y usa JSONL solo como respaldo transitorio."""
    if not is_sql_enabled():
        log.info("SQL deshabilitado. Encolando en JSON.")
        _guardar_en_pendientes(datos_dict)
        return False

    try:
        bulk_upsert_reclamos([datos_dict])
        return True
    except Exception as e:
        _guardar_en_pendientes(datos_dict)
        log.error("Error al guardar en SQL, se encola en JSON: %s", e)
        return False


def sincronizar_pendientes_excel():
    """Sincroniza pendientes JSONL hacia SQL."""
    pendientes = _leer_pendientes()
    if not pendientes:
        return 0

    if not is_sql_enabled():
        log.info("SQL deshabilitado. Pendientes conservados en JSON: %d", len(pendientes))
        return 0

    dedup = {}
    pendientes_sin_clave = []
    for item in pendientes:
        claim, plataforma = _clave_reclamo(item)
        if claim:
            dedup[(claim, plataforma)] = item
        else:
            pendientes_sin_clave.append(item)

    pendientes_lote = list(dedup.values()) + pendientes_sin_clave

    try:
        sincronizados = bulk_upsert_reclamos(pendientes_lote)
        _escribir_pendientes([])
        log.info("Pendientes sincronizados a SQL: %d", sincronizados)
        return sincronizados
    except Exception as e:
        log.error("Error al sincronizar pendientes a SQL: %s (pendientes: %d)", e, len(pendientes_lote))
        return 0


def actualizar_status_masivo(status_por_reclamo):
    """Actualiza status en SQL por clave (ClaimNumber, Plataforma)."""
    if not status_por_reclamo:
        return 0

    if not is_sql_enabled():
        log.info("SQL deshabilitado. No se actualiza status.")
        return 0

    try:
        actualizados = bulk_update_status_sql(status_por_reclamo)
        log.info("Status actualizados en SQL: %d", actualizados)
        return actualizados
    except Exception as e:
        log.error("Error al actualizar status en SQL: %s", e)
        return 0


# Funciones legado para no romper imports externos.
def agregar_fila(datos_dict):
    return encolar_registro(datos_dict)


def obtener_tabla_case():
    return None, None
