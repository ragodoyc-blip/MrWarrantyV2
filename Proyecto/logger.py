import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = "mrwarranty", log_dir: str | None = None) -> logging.Logger:
    """Configura y retorna un logger con handlers de archivo y consola.

    Args:
        name: Nombre del logger.
        log_dir: Directorio de logs. Si es None, usa 'logs/' junto al caller.

    Returns:
        Logger configurado.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    if log_dir is None:
        log_dir = Path(__file__).resolve().parent / "logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(module)s:%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_dir / "mrwarranty.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Logger global reutilizable
log = setup_logger()
