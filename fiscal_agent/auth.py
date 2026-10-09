"""Autenticación simple por token para el agente fiscal.

El sistema web envía el token en el header X-Agent-Token.
El agente verifica que coincida con AGENT_TOKEN de configuración.
"""

from functools import wraps

from flask import jsonify, request

from fiscal_agent.config import Config

# Endpoints públicos (no requieren token)
_PUBLIC_ENDPOINTS = {"/health"}


def requiere_token(f):
    """Decorador que verifica el token del header X-Agent-Token.

    Excepciones:
    - Endpoints en _PUBLIC_ENDPOINTS.
    - Si AGENT_TOKEN está vacío, no se verifica (modo desarrollo).
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Health check no requiere token
        if request.path in _PUBLIC_ENDPOINTS:
            return f(*args, **kwargs)

        # Si no hay token configurado, permitir (modo desarrollo)
        if not Config.AGENT_TOKEN:
            return f(*args, **kwargs)

        token_recibido = request.headers.get("X-Agent-Token", "").strip()

        if not token_recibido:
            return jsonify({
                "success": False,
                "error": "Token de autenticación requerido.",
            }), 401

        if token_recibido != Config.AGENT_TOKEN:
            return jsonify({
                "success": False,
                "error": "Token de autenticación inválido.",
            }), 403

        return f(*args, **kwargs)

    return wrapper