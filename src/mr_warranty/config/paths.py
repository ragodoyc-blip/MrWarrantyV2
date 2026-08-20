from pathlib import Path

# Repo root = 3 niveles arriba de src/mr_warranty/config -> 002 Mr. Warranty
REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
PROJECT_SHIM_DIR = REPO_ROOT / "Proyecto"

# Rutas estables - src/ es autónomo, Proyecto/ queda como legado para shim
ADJUNTOS_DIR = REPO_ROOT / "AdjuntosSQIS"
LOGS_DIR = REPO_ROOT / "logs"
DATA_DIR = REPO_ROOT / "data"
POPPLER_DEFAULT = REPO_ROOT / "Proyecto" / "ComplementosPoppler" / "Library" / "bin"
# Fallbacks legados (si data/logs no existen en root, usar Proyecto/)
LOGS_DIR = LOGS_DIR if LOGS_DIR.exists() or not (REPO_ROOT / "Proyecto" / "logs").exists() else REPO_ROOT / "Proyecto" / "logs"
DATA_DIR = DATA_DIR if DATA_DIR.exists() or not (REPO_ROOT / "Proyecto" / "Datos").exists() else REPO_ROOT / "Proyecto" / "Datos"
