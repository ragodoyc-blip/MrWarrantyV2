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
    parser.add_argument(
        "--dry-run",
        type=int,
        nargs="?",
        const=1,
        default=None,
        dest="dry_run",
        help="Dry-run: procesa N reclamos aleatorios por plataforma.",
    )
    parser.add_argument(
        "--dry-run-seed",
        type=str,
        default=None,
        help="Seed para muestreo reproducible.",
    )
    args = parser.parse_args()
    if args.dry_run_seed is not None:
        import os

        os.environ["DRY_RUN_SEED"] = str(args.dry_run_seed)
    if args.dry_run is not None:
        import os

        os.environ["DRY_RUN_LIMIT"] = str(args.dry_run)
    main(args.fuente, dry_run_limit=args.dry_run)
