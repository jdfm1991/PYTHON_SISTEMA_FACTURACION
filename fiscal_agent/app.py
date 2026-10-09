"""Aplicación Flask del agente fiscal."""

import logging
import logging.handlers
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, g

from fiscal_agent.config import Config
from fiscal_agent.routes.fiscal_routes import fiscal_bp


class _RequestIdFilter(logging.Filter):
    """Filtro que inyecta el request_id en cada registro de log."""

    def filter(self, record):
        from flask import g, has_request_context

        if has_request_context() and hasattr(g, "request_id"):
            record.request_id = g.request_id
        else:
            record.request_id = "-"
        return True


def _configurar_logging():
    """Configura logging a archivo y consola con request_id."""
    log_file = Path(Config.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    request_id_filter = _RequestIdFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_id_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(Config.LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def _configurar_request_id(app):
    """Agrega request_id a cada petición para trazabilidad."""

    @app.before_request
    def _asignar_request_id():
        g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]

    @app.after_request
    def _agregar_request_id_header(response):
        if hasattr(g, "request_id"):
            response.headers["X-Request-Id"] = g.request_id
        return response


def create_app() -> Flask:
    """Fábrica de la aplicación del agente."""
    _configurar_logging()

    app = Flask(__name__)
    app.config["DEBUG"] = Config.DEBUG

    _configurar_request_id(app)

    app.register_blueprint(fiscal_bp)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Endpoint no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": "Error interno del agente"}), 500

    return app