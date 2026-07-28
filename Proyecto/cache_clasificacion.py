"""
Cache local de clasificaciones de adjuntos para evitar re-clasificar.
Almacena en AdjuntosSF/clasificaciones/cache.json
"""
import json
from pathlib import Path

CACHE_DIR = Path("AdjuntosSF/clasificaciones")
CACHE_FILE = CACHE_DIR / "cache.json"


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_cache() -> dict:
    _ensure_cache_dir()
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict):
    _ensure_cache_dir()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_clasificacion_cache(content_doc_id: str) -> dict | None:
    """Obtiene clasificacion cacheada por ContentDocumentId."""
    cache = _load_cache()
    return cache.get(content_doc_id)


def save_clasificacion_cache(content_doc_id: str, resultado: dict):
    """Guarda clasificacion en cache."""
    cache = _load_cache()
    cache[content_doc_id] = resultado
    _save_cache(cache)
