from pathlib import Path

# Repo root = 3 niveles arriba de src/mr_warranty/config -> 002 Mr. Warranty
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
PROJECT_SHIM_DIR = REPO_ROOT / "Proyecto"

# Rutas estables independientes de dónde se ejecute python -m
ADJUNTOS_DIR = REPO_ROOT / "AdjuntosSQIS"
LOGS_DIR = REPO_ROOT / "Proyecto" / "logs"
DATA_DIR = REPO_ROOT / "Proyecto" / "Datos"
POPPLER_DEFAULT = REPO_ROOT / "Proyecto" / "ComplementosPoppler" / "Library" / "bin"
