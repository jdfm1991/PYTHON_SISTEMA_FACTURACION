import os
from urllib.parse import quote_plus
from datetime import timedelta
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()


class Config:
    """Configuración base de la aplicación."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # --- Seguridad de formularios ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # el token dura mientras dure la sesión

    # --- Base de datos MySQL ---
    DB_USER = os.getenv("DATABASE_USER", "root")
    DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DB_HOST = os.getenv("DATABASE_HOST", "localhost")
    DB_PORT = os.getenv("DATABASE_PORT", "3306")
    DB_NAME = os.getenv("DATABASE_NAME", "facturacion_inventario")

    IGTF_PORCENTAJE = Decimal(os.getenv("IGTF_PORCENTAJE", "3.00"))

    # --- Sesión ---
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # True en producción (requiere HTTPS)

    # quote_plus codifica caracteres especiales de la contraseña
    # (ej. @, #, /) para que la URI sea válida.
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # reconecta si la conexión cayó
        "pool_recycle": 280,  # recicla conexiones antes del timeout de MySQL
    }

    # --- Agente fiscal ---
    FISCAL_AGENT_URL = os.getenv("FISCAL_AGENT_URL", "http://127.0.0.1:5001")
    FISCAL_AGENT_TIMEOUT = int(os.getenv("FISCAL_AGENT_TIMEOUT", "10"))


class TestConfig(Config):
    """Configuración para tests unitarios e integración."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-no-usar-en-produccion"
    LOGIN_DISABLED = True  # deshabilita Flask-Login en tests
