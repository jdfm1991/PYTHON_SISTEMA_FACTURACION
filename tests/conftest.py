"""Fixtures globales de pytest.

Provee una app de Flask en modo test, una BD SQLite en memoria,
y una sesión limpia por cada test.
"""

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """App de Flask configurada para tests. Se crea una sola vez."""
    app = create_app(config_class=TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def db(app):
    """Sesión limpia por test.

    Cada test corre dentro de una transacción que se revierte al final.
    """
    with app.app_context():
        yield _db


@pytest.fixture(autouse=True)
def _limpiar_tablas(db):
    """Limpia todas las tablas antes de cada test.

    autouse=True hace que se aplique a todos los tests sin tener que pedirla.
    """
    # Borrar en orden inverso a las dependencias
    from app.models import (
        AlicuotaIVA,
        Cliente,
        CuentaPorCobrar,
        CuentaPorPagar,
        DetalleFacturaCompra,
        DetalleFacturaVenta,
        FacturaCompra,
        FacturaVenta,
        MovimientoInventario,
        PagoFacturaVenta,
        Producto,
        Proveedor,
        TasaCambio,
        Usuario,
    )

    for modelo in [
        MovimientoInventario,
        DetalleFacturaVenta,
        DetalleFacturaCompra,
        PagoFacturaVenta,
        CuentaPorCobrar,
        CuentaPorPagar,
        FacturaVenta,
        FacturaCompra,
        Producto,
        Cliente,
        Proveedor,
        AlicuotaIVA,
        TasaCambio,
        Usuario,
    ]:
        db.session.query(modelo).delete()
    db.session.commit()

    yield