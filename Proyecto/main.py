"""Shim de compatibilidad - delega a src/mr_warranty. Será eliminado en v2."""
import warnings
import sys
from pathlib import Path

warnings.warn(
    "Proyecto/main.py está deprecado. Usa: python -m mr_warranty.pipelines.main [sqis|salesforce|ambos]",
    DeprecationWarning,
    stacklevel=2,
)

# Fallback: asegura que src esté en PYTHONPATH aunque no se haya hecho pip install -e .
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from mr_warranty.pipelines.main import main  # noqa: E402

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Procesa reclamos de garantía de SQIS, Salesforce o ambas plataformas. (Shim deprecated)"
    )
    parser.add_argument(
        "fuente",
        nargs="?",
        choices=("sqis", "salesforce", "ambos"),
        default="ambos",
        help="Fuente a procesar (por defecto: ambos).",
    )
    args = parser.parse_args()
    main(args.fuente)
