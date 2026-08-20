import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Base paths ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "Datos"
LOGS_DIR = PROJECT_ROOT / "logs"
ADJUNTOS_DIR = PROJECT_ROOT.parent / "AdjuntosSQIS"

# ── Dynamics 365 (SQIS) ────────────────────────────────────
DYNAMICS_API_URL = "https://komatsuna.api.crm.dynamics.com/api/data/v9.2"

# ── Salesforce ──────────────────────────────────────────────
SF_USERNAME = os.getenv("SF_USERNAME")
SF_PASSWORD = os.getenv("SF_PASSWORD")
SF_SECURITY_TOKEN = os.getenv("SF_SECURITY_TOKEN")
SF_CONSUMER_KEY = os.getenv("SF_CONSUMER_KEY")
SF_CONSUMER_SECRET = os.getenv("SF_CONSUMER_SECRET")
SF_AUTH_URL = "https://komatsucrm.my.salesforce.com/services/oauth2/token"

# ── SQL Server ──────────────────────────────────────────────
SQL_ENABLED = os.getenv("MRW_SQL_ENABLED", "1").strip().lower() in {"1", "true", "yes", "y"}
SQL_SERVER = os.getenv("SQL_SERVER", "").strip()
SQL_DATABASE = os.getenv("SQL_DATABASE", "").strip()
SQL_USERNAME = os.getenv("SQL_USERNAME", "").strip()
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "").strip()
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
SQL_TABLE = "mr_warranty.reclamos_procesados"

# ── Azure OpenAI ────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")

# ── Azure Mistral ───────────────────────────────────────────
AZURE_MISTRAL_ENDPOINT = os.getenv("AZURE_MISTRAL_ENDPOINT", "")
AZURE_MISTRAL_API_KEY = os.getenv("AZURE_MISTRAL_API_KEY", "")

# ── Azure Blob Storage ──────────────────────────────────────
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "imagenes-sqis")

# ── Poppler ─────────────────────────────────────────────────
POPPLER_PATH = os.getenv(
    "POPPLER_PATH",
    str(PROJECT_ROOT / "ComplementosPoppler" / "Library" / "bin"),
).strip()

# ── Warranty claim type GUIDs (Dynamics) ────────────────────
WC_TYPE_FIELD_CAMPAIGN = "774b9a34-d872-ee11-9ae7-0022480a2abf"
WC_TYPE_STANDARD = "894b9a34-d872-ee11-9ae7-0022480a2abf"
WC_TYPE_IGNORED = "814b9a34-d872-ee11-9ae7-0022480a2abf"

# ── Status codes ────────────────────────────────────────────
SQIS_STATUS_UNDER_APPLICATION = 183890003
SQIS_DETAIL_TYPE_FOC = 183890005
SQIS_JOB_STATUS_ACTIVE = 1

# ── Business thresholds ─────────────────────────────────────
REPAIR_DEADLINE_DAYS = 30
CLAIM_DEADLINE_DAYS = 30
WARRANTY_PERIOD_DAYS = 365
DEFAULT_CREATEDON_FILTER = "2025-01-01"

# ── Distributors (Salesforce) ──────────────────────────────
ALLOWED_DISTRIBUTORS = [
    "Colombia Surface DB",
    "JOY GLOBAL CHILE - CDLAMPA",
    "Joy Global Chile - CD LAMPA",
    "KLTD - Mitsui Maquinarias Perú S.       A.",
    "KMEX (225K) (225K)",
    "KOMATSU CHILE, S. - 487100 - EDT Warranty",
    "KOMATSU MAQUINARIAS MEXICO SA",
    "KOMATSU MINING PANAMA",
    "KOMATSU-MITSUI MAQUINARIAS PER",
    "KMT Mexico Surface DB",
    "Komatsu Chile  (214B)",
    "Komatsu Mitsui Maquinarias Peru  (2297)",
    "Peru Surface DB",
]
SF_CREATEDON_FILTER = "2026-02-01T00:00:00Z"
