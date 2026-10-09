"""Tests del servicio de anulación de facturas."""

from datetime import date
from decimal import Decimal

import pytest

from app.constants import TIPO_VENTA_CONTADO, TIPO_VENTA_CREDITO_DIRECTO
from app.exceptions import DominioError
from app.extensions import db
from app.models import (
    AlicuotaIVA,
    Cliente,
    CuentaPorCobrar,
    FacturaVenta,
    MovimientoInventario,
    Producto,
    TasaCambio,
    Usuario,
)
from app.services import facturacion
from app.services.facturacion import (
    CxConPagosError,
    FacturaNoAnulableError,
)


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
def cliente(db):
    c = Cliente(
        tipo_documento="V",
        numero_documento="12345678",
        razon_social="Cliente Test",
        activo=True,
    )
    db.session.add(c)
    db.session.flush()
    return c

@pytest.fixture
def cliente_con_credito(db):
    c = Cliente(
        tipo_documento="V",
        numero_documento="87654321",
        razon_social="Cliente Crédito",
        activo=True,
        tiene_credito=True,
        limite_credito_usd=Decimal("5000.0000"),
        dias_credito=30,
    )
    db.session.add(c)
    db.session.flush()
    return c


@pytest.fixture
def producto(db, alicuota):
    p = Producto(
        codigo="P001",
        nombre="Producto Test",
        precio_usd=Decimal("100.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("50.000"),
        activo=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


@pytest.fixture
def usuario(db):
    u = Usuario(
        username="testuser",
        rol="admin",
        activo=True,
    )
    u.set_password("testpass123")
    db.session.add(u)
    db.session.flush()
    return u


def _crear_y_confirmar_factura(cliente, producto, tasa, tipo_venta=TIPO_VENTA_CONTADO, pagos=None):
    """Helper: crea factura, agrega detalle y confirma."""
    factura = facturacion.crear_borrador(cliente.id)
    facturacion.agregar_detalle(factura, producto.id, Decimal("1"))
    db.session.flush()

    if pagos is None:
        pagos = []
    facturacion.confirmar_factura(
        factura, tipo_venta=tipo_venta, pagos=pagos
    )
    db.session.flush()
    return factura


# ---------- Tests ----------


def test_anular_factura_sin_cxc(db, cliente, producto, tasa, usuario):
    """Anular factura contado pagada (sin CxC). Verifica movimiento de entrada."""
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("4640.0000"),
    }]
    factura = _crear_y_confirmar_factura(
        cliente, producto, tasa, TIPO_VENTA_CONTADO, pagos
    )
    assert factura.estado == "pagada"

    # Forzar a emitida para poder anular (regla: solo emitida)
    factura.estado = "emitida"
    db.session.flush()

    stock_antes = producto.stock_actual  # 49
    factura = facturacion.anular_factura(
        factura,
        motivo="Anulación por error en el cliente",
        usuario_id=usuario.id,
    )

    assert factura.estado == "anulada"
    assert factura.motivo_anulacion == "Anulación por error en el cliente"
    assert factura.fecha_anulacion is not None
    assert factura.anulada_por_id == usuario.id

    # Stock restaurado
    assert producto.stock_actual == stock_antes + Decimal("1.000")

    # Movimientos: 1 salida (confirmación) + 1 entrada (anulación)
    movs = db.session.scalars(
        db.select(MovimientoInventario).filter_by(
            referencia_tipo="factura_venta",
            referencia_id=factura.id,
        )
    ).all()
    assert len(movs) == 2
    tipos = sorted(m.tipo for m in movs)
    assert tipos == ["entrada", "salida"]


def test_anular_factura_con_cxc_pendiente(db, cliente_con_credito, producto, tasa, usuario):
    """Anular factura a crédito con CxC pendiente."""
    factura = _crear_y_confirmar_factura(
        cliente_con_credito, producto, tasa, TIPO_VENTA_CREDITO_DIRECTO
    )
    assert factura.estado == "emitida"

    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is not None
    assert cxc.estado == "pendiente"

    facturacion.anular_factura(
        factura,
        motivo="Anulación por error en el cliente",
        usuario_id=usuario.id,
    )

    assert factura.estado == "anulada"
    assert cxc.estado == "anulada"
    assert cxc.saldo_usd == Decimal("0.0000")


def test_anular_factura_con_cxc_con_pagos_falla(db, cliente_con_credito, producto, tasa, usuario):
    """No se puede anular si la CxC tiene pagos parciales."""
    factura = _crear_y_confirmar_factura(
        cliente_con_credito, producto, tasa, TIPO_VENTA_CREDITO_DIRECTO
    )
    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    cxc.saldo_usd = cxc.monto_total_usd - Decimal("20.0000")
    db.session.flush()

    with pytest.raises(CxConPagosError):
        facturacion.anular_factura(
            factura,
            motivo="Anulación por error en el cliente",
            usuario_id=usuario.id,
        )


def test_anular_factura_ya_anulada_falla(db, cliente_con_credito, producto, tasa, usuario):
    """No se puede anular una factura ya anulada."""
    factura = _crear_y_confirmar_factura(
        cliente_con_credito, producto, tasa, TIPO_VENTA_CREDITO_DIRECTO
    )
    facturacion.anular_factura(
        factura,
        motivo="Anulación por error en el cliente",
        usuario_id=usuario.id,
    )
    db.session.flush()

    with pytest.raises(FacturaNoAnulableError):
        facturacion.anular_factura(
            factura,
            motivo="Segunda anulación",
            usuario_id=usuario.id,
        )


def test_anular_factura_con_producto_inactivo(db, cliente_con_credito, producto, tasa, usuario):
    """Anular funciona aunque el producto esté desactivado."""
    factura = _crear_y_confirmar_factura(
        cliente_con_credito, producto, tasa, TIPO_VENTA_CREDITO_DIRECTO
    )
    producto.activo = False
    db.session.flush()

    stock_antes = producto.stock_actual
    facturacion.anular_factura(
        factura,
        motivo="Anulación por error en el cliente",
        usuario_id=usuario.id,
    )

    assert factura.estado == "anulada"
    assert producto.stock_actual == stock_antes + Decimal("1.000")


def test_motivo_corto_falla(db, cliente_con_credito, producto, tasa, usuario):
    """El motivo debe tener al menos 10 caracteres."""
    factura = _crear_y_confirmar_factura(
        cliente_con_credito, producto, tasa, TIPO_VENTA_CREDITO_DIRECTO
    )

    with pytest.raises(DominioError):
        facturacion.anular_factura(
            factura,
            motivo="corto",
            usuario_id=usuario.id,
        )
        
def test_anular_factura_borrador_falla(db, cliente, producto, tasa, usuario):
    """No se puede anular una factura en borrador."""
    factura = facturacion.crear_borrador(cliente.id)
    facturacion.agregar_detalle(factura, producto.id, Decimal("1"))
    db.session.flush()

    with pytest.raises(FacturaNoAnulableError):
        facturacion.anular_factura(
            factura,
            motivo="Anulación por error en el cliente",
            usuario_id=usuario.id,
        )


def test_anular_factura_pagada_falla(db, cliente, producto, tasa, usuario):
    """No se puede anular una factura pagada."""
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("4640.0000"),
    }]
    factura = _crear_y_confirmar_factura(
        cliente, producto, tasa, TIPO_VENTA_CONTADO, pagos
    )
    assert factura.estado == "pagada"

    with pytest.raises(FacturaNoAnulableError):
        facturacion.anular_factura(
            factura,
            motivo="Anulación por error en el cliente",
            usuario_id=usuario.id,
        )