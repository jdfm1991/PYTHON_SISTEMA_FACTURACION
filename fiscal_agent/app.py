"""Aplicación Flask del agente fiscal."""

import logging
import logging.handlers
from pathlib import Path

from flask import Flask, jsonify

from fiscal_agent.config import Config
from fiscal_agent.routes.fiscal_routes import fiscal_bp


def _configurar_logging():
    """Configura logging a archivo y consola."""
    log_file = Path(Config.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo con rotación
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(Config.LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def create_app() -> Flask:
    """Fábrica de la aplicación del agente."""
    _configurar_logging()

    app = Flask(__name__)
    app.config["DEBUG"] = Config.DEBUG

    app.register_blueprint(fiscal_bp)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Endpoint no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": "Error interno del agente"}), 500

    return app