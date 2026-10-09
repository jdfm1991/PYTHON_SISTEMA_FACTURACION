"""Configuración del agente fiscal.

Lee variables de entorno desde .env. Los valores sensibles
(puerto COM, baudrate) se configuran ahí.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde el directorio del agente
_agent_dir = Path(__file__).resolve().parent
load_dotenv(_agent_dir / ".env")


class Config:
    """Configuración base del agente."""

    # --- Servidor HTTP ---
    HOST = os.getenv("AGENT_HOST", "127.0.0.1")
    PORT = int(os.getenv("AGENT_PORT", "5001"))
    DEBUG = os.getenv("AGENT_DEBUG", "False").lower() == "true"

    # --- Impresora fiscal ---
    PRINTER_PORT = os.getenv("PRINTER_PORT", "COM99")
    PRINTER_BAUDRATE = int(os.getenv("PRINTER_BAUDRATE", "9600"))
    PRINTER_TIMEOUT = float(os.getenv("PRINTER_TIMEOUT", "5.0"))

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv(
        "LOG_FILE", str(_agent_dir / "logs" / "fiscal_agent.log")
    )

    # --- SDK ---
    VENDOR_DIR = _agent_dir / "vendor"