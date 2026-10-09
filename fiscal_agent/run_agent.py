"""Punto de entrada del agente fiscal.

IMPORTANTE: ejecutar SIEMPRE desde la raíz del proyecto con:
    python -m fiscal_agent.run_agent

NO ejecutar con `python fiscal_agent/run_agent.py` ni desde dentro
de `fiscal_agent/`. Eso rompe los imports.
"""

import logging

from fiscal_agent.app import create_app
from fiscal_agent.config import Config

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

logger = logging.getLogger(__name__)


def main():
    app = create_app()
    logger.info(f"Agente fiscal iniciando en http://{Config.HOST}:{Config.PORT}")
    logger.info(f"Impresora: {Config.PRINTER_PORT} a {Config.PRINTER_BAUDRATE} baudios")
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        use_reloader=False,  # evitar doble inicialización
    )


if __name__ == "__main__":
    main()
