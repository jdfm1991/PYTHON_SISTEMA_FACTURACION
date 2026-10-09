"""Tests de anulación de compras."""

from datetime import date
from decimal import Decimal

import pytest

from app.exceptions import (
    CxConPagosError,
    DominioError,
    FacturaNoAnulableError,
    StockNegativoError,
)
from app.models import (
    AlicuotaIVA,
    CuentaPorPagar,
    FacturaCompra,
    MovimientoInventario,
    Producto,
    Proveedor,
    TasaCambio,
    Usuario,
)
from app.services import facturacion_compras


# ---------- Fixtures ----------


@pytest.fixture
def alicuota(db):
    a = AlicuotaIVA(codigo="GENERAL", descripcion="16%", porcentaje=Decimal("16.00"))
    db.session.add(a)
    db.session.flush()
    return a


@pytest.fixture
def tasa(db):
    t = TasaCambio(
        fecha=date.today(),
        tasa_bcv=Decimal("40.00000000"),
        fuente="BCV",
    )
    db.session.add(t)
    db.session.flush()
    return t


@pytest.fixture
def proveedor(db):
    p = Proveedor(
        tipo_documento="J",
        numero_documento="J-12345678",
        razon_social="Proveedor Test",
        activo=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def producto(db, alicuota):
    p = Producto(
        codigo="P001",
        nombre="Producto Test",
        precio_usd=Decimal("100.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("0.000"),
        activo=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def usuario(db):
    u = Usuario(username="testuser", rol="admin", activo=True)
    u.set_password("testpass123")
    db.session.add(u)
    db.session.flush()
    return u


def _crear_y_confirmar_compra(proveedor, producto, cantidad="1", pagos=None):
    """Helper: crea borrador, agrega detalle y confirma."""
    factura = facturacion_compras.crear_borrador(proveedor.id)
    facturacion_compras.agregar_detalle(factura, producto.id, Decimal(cantidad))
    if pagos is None:
        pagos = []
    facturacion_compras.confirmar_compra(factura, pagos)
    return factura


# ---------- Tests ----------


def test_anular_compra_sin_cxp(db, proveedor, producto, tasa, usuario):
    """Anular compra con pago completo (sin CxP)."""
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("4640.0000"),
    }]
    factura = _crear_y_confirmar_compra(proveedor, producto, "1", pagos)
    assert factura.estado == "pagada"

    # Forzar a emitida para poder anular
    factura.estado = "emitida"
    db.session.flush()

    stock_antes = producto.stock_actual  # 1
    facturacion_compras.anular_compra(
        factura,
        motivo="Anulación por error en la compra",
        usuario_id=usuario.id,
    )

    assert factura.estado == "anulada"
    assert factura.motivo_anulacion == "Anulación por error en la compra"
    assert factura.fecha_anulacion is not None
    assert factura.anulada_por_id == usuario.id

    # Stock disminuye
    assert producto.stock_actual == stock_antes - Decimal("1.000")

    # Movimientos: 1 entrada + 1 salida
    movs = db.session.scalars(
        db.select(MovimientoInventario).filter_by(
            referencia_tipo="factura_compra",
            referencia_id=factura.id,
        )
    ).all()
    assert len(movs) == 2
    tipos = sorted(m.tipo for m in movs)
    assert tipos == ["entrada", "salida"]


def test_anular_compra_con_cxp_pendiente(db, proveedor, producto, tasa, usuario):
    """Anular compra con CxP pendiente."""
    factura = _crear_y_confirmar_compra(proveedor, producto)
    assert factura.estado == "emitida"

    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    assert cxp is not None

    facturacion_compras.anular_compra(
        factura,
        motivo="Anulación por error en la compra",
        usuario_id=usuario.id,
    )

    assert factura.estado == "anulada"
    assert cxp.estado == "anulada"
    assert cxp.saldo_usd == Decimal("0.0000")


def test_anular_compra_con_cxp_con_pagos_falla(db, proveedor, producto, tasa, usuario):
    """No se puede anular si la CxP tiene pagos parciales."""
    factura = _crear_y_confirmar_compra(proveedor, producto)
    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    cxp.saldo_usd = cxp.monto_total_usd - Decimal("20.0000")
    db.session.flush()

    with pytest.raises(CxConPagosError):
        facturacion_compras.anular_compra(
            factura,
            motivo="Anulación por error en la compra",
            usuario_id=usuario.id,
        )


def test_anular_compra_borrador_falla(db, proveedor, producto, tasa, usuario):
    """No se puede anular una compra en borrador."""
    factura = facturacion_compras.crear_borrador(proveedor.id)
    facturacion_compras.agregar_detalle(factura, producto.id, Decimal("1"))
    db.session.flush()

    with pytest.raises(FacturaNoAnulableError):
        facturacion_compras.anular_compra(
            factura,
            motivo="Anulación por error en la compra",
            usuario_id=usuario.id,
        )


def test_anular_compra_pagada_falla(db, proveedor, producto, tasa, usuario):
    """No se puede anular una compra pagada."""
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("4640.0000"),
    }]
    factura = _crear_y_confirmar_compra(proveedor, producto, "1", pagos)
    assert factura.estado == "pagada"

    with pytest.raises(FacturaNoAnulableError):
        facturacion_compras.anular_compra(
            factura,
            motivo="Anulación por error en la compra",
            usuario_id=usuario.id,
        )


def test_anular_compra_ya_anulada_falla(db, proveedor, producto, tasa, usuario):
    """No se puede anular una compra ya anulada."""
    factura = _crear_y_confirmar_compra(proveedor, producto)
    facturacion_compras.anular_compra(
        factura,
        motivo="Anulación por error en la compra",
        usuario_id=usuario.id,
    )
    db.session.flush()

    with pytest.raises(FacturaNoAnulableError):
        facturacion_compras.anular_compra(
            factura,
            motivo="Segunda anulación",
            usuario_id=usuario.id,
        )


def test_anular_compra_stock_negativo_falla(db, proveedor, producto, tasa, usuario):
    """No se puede anular si el stock resultante sería negativo."""
    factura = _crear_y_confirmar_compra(proveedor, producto, "10")

    # Simular que se vendió todo (stock = 0)
    producto.stock_actual = Decimal("0.000")
    db.session.flush()

    with pytest.raises(StockNegativoError):
        facturacion_compras.anular_compra(
            factura,
            motivo="Anulación por error en la compra",
            usuario_id=usuario.id,
        )


def test_motivo_corto_falla(db, proveedor, producto, tasa, usuario):
    """El motivo debe tener al menos 10 caracteres."""
    factura = _crear_y_confirmar_compra(proveedor, producto)

    with pytest.raises(DominioError):
        facturacion_compras.anular_compra(
            factura,
            motivo="corto",
            usuario_id=usuario.id,
        )