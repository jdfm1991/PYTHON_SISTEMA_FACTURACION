"""Tests del servicio confirmar_compra."""

from datetime import date
from decimal import Decimal

import pytest

from app.exceptions import (
    FacturaNoEditableError,
    FacturaSinLineasError,
    PagoExcedeTotalError,
    PagoInvalidoError,
)
from app.models import (
    AlicuotaIVA,
    CuentaPorPagar,
    FacturaCompra,
    MovimientoInventario,
    PagoFacturaCompra,
    Producto,
    Proveedor,
    TasaCambio,
)
from app.services import facturacion_compras


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


def _crear_borrador(proveedor, producto):
    """Helper: crea un borrador de compra con un detalle."""
    factura = facturacion_compras.crear_borrador(proveedor.id)
    facturacion_compras.agregar_detalle(factura, producto.id, Decimal("1"))
    return factura


# ---------- Tests ----------


def test_compra_contado_pago_exacto_ves(db, proveedor, producto, tasa):
    """Compra contado, pago exacto en VES. Estado pagada, stock aumenta."""
    factura = _crear_borrador(proveedor, producto)
    # Total: 100 + 16 = 116 USD → 116 * 40 = 4640 VES
    pagos = [
        {
            "forma_pago": "efectivo_ves",
            "moneda_pago": "VES",
            "monto": Decimal("4640.0000"),
        }
    ]
    factura = facturacion_compras.confirmar_compra(factura, pagos)

    assert factura.estado == "pagada"

    # Stock aumentó
    assert producto.stock_actual == Decimal("1.000")

    # Movimiento de entrada
    movs = db.session.scalars(
        db.select(MovimientoInventario).filter_by(
            referencia_tipo="factura_compra", referencia_id=factura.id
        )
    ).all()
    assert len(movs) == 1
    assert movs[0].tipo == "entrada"
    assert movs[0].cantidad == Decimal("1.000")

    # Sin CxP
    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    assert cxp is None


def test_compra_contado_pago_exacto_usd(db, proveedor, producto, tasa):
    """Compra contado, pago en USD."""
    factura = _crear_borrador(proveedor, producto)
    pagos = [
        {
            "forma_pago": "efectivo_usd",
            "moneda_pago": "USD",
            "monto": Decimal("116.0000"),
        }
    ]
    factura = facturacion_compras.confirmar_compra(factura, pagos)

    assert factura.estado == "pagada"
    assert producto.stock_actual == Decimal("1.000")

    pago = db.session.scalar(
        db.select(PagoFacturaCompra).filter_by(factura_compra_id=factura.id)
    )
    assert pago.moneda_pago == "USD"
    assert pago.monto_usd == Decimal("116.0000")


def test_compra_contado_pago_parcial_genera_cxp(db, proveedor, producto, tasa):
    """Compra contado, pago parcial. Genera CuentaPorPagar al proveedor."""
    factura = _crear_borrador(proveedor, producto)
    # Total 116 USD. Pagamos 50 USD (2000 VES).
    pagos = [
        {
            "forma_pago": "efectivo_ves",
            "moneda_pago": "VES",
            "monto": Decimal("2000.0000"),
        }
    ]
    factura = facturacion_compras.confirmar_compra(factura, pagos)

    assert factura.estado == "emitida"
    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    assert cxp is not None
    assert cxp.tipo_acreedor == "proveedor"
    assert cxp.saldo_usd == Decimal("66.0000")


def test_compra_credito_sin_pago(db, proveedor, producto, tasa):
    """Compra a crédito puro. CxP por el total."""
    factura = _crear_borrador(proveedor, producto)
    factura = facturacion_compras.confirmar_compra(factura, [])

    assert factura.estado == "emitida"
    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    assert cxp is not None
    assert cxp.saldo_usd == factura.total_usd


def test_compra_sin_lineas_falla(db, proveedor, tasa):
    """Compra sin líneas no se puede confirmar."""
    factura = facturacion_compras.crear_borrador(proveedor.id)
    db.session.flush()

    with pytest.raises(FacturaSinLineasError):
        facturacion_compras.confirmar_compra(factura, [])


def test_compra_pago_excede_total_falla(db, proveedor, producto, tasa):
    """Pago mayor al total no se permite en compras."""
    factura = _crear_borrador(proveedor, producto)
    pagos = [
        {
            "forma_pago": "efectivo_ves",
            "moneda_pago": "VES",
            "monto": Decimal("10000.0000"),  # más del total
        }
    ]

    with pytest.raises(PagoExcedeTotalError):
        facturacion_compras.confirmar_compra(factura, pagos)


def test_compra_ya_emitida_falla(db, proveedor, producto, tasa):
    """No se puede confirmar una compra ya emitida."""
    factura = _crear_borrador(proveedor, producto)
    factura = facturacion_compras.confirmar_compra(factura, [])

    with pytest.raises(FacturaNoEditableError):
        facturacion_compras.confirmar_compra(factura, [])


def test_compra_producto_inactivo_permitido(db, proveedor, producto, tasa):
    """Comprar un producto inactivo está permitido."""
    producto.activo = False
    db.session.flush()

    factura = _crear_borrador(proveedor, producto)
    factura = facturacion_compras.confirmar_compra(factura, [])

    assert factura.estado == "emitida"
    assert producto.stock_actual == Decimal("1.000")


def test_compra_multiples_lineas_multiples_movimientos(db, proveedor, tasa, alicuota):
    """Una compra con N líneas genera N movimientos de entrada."""
    p1 = Producto(
        codigo="P001",
        nombre="Prod 1",
        precio_usd=Decimal("100.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("0.000"),
        activo=True,
    )
    p2 = Producto(
        codigo="P002",
        nombre="Prod 2",
        precio_usd=Decimal("50.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("0.000"),
        activo=True,
    )
    db.session.add_all([p1, p2])
    db.session.flush()

    factura = facturacion_compras.crear_borrador(proveedor.id)
    facturacion_compras.agregar_detalle(factura, p1.id, Decimal("2"))
    facturacion_compras.agregar_detalle(factura, p2.id, Decimal("3"))
    facturacion_compras.confirmar_compra(factura, [])

    movs = db.session.scalars(
        db.select(MovimientoInventario).filter_by(
            referencia_tipo="factura_compra", referencia_id=factura.id
        )
    ).all()
    assert len(movs) == 2
    assert p1.stock_actual == Decimal("2.000")
    assert p2.stock_actual == Decimal("3.000")


def test_compra_pago_monto_negativo_falla(db, proveedor, producto, tasa):
    """Pago con monto negativo es inválido."""
    factura = _crear_borrador(proveedor, producto)
    pagos = [
        {
            "forma_pago": "efectivo_ves",
            "moneda_pago": "VES",
            "monto": Decimal("-100.0000"),
        }
    ]

    with pytest.raises(PagoInvalidoError):
        facturacion_compras.confirmar_compra(factura, pagos)


def test_cxp_monto_total_es_el_total_de_la_factura(db, proveedor, producto, tasa):
    """Al crear una CxP, monto_total_usd es el total de la factura."""
    factura = _crear_borrador(proveedor, producto)
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("2000.0000"),
    }]
    facturacion_compras.confirmar_compra(factura, pagos)

    cxp = db.session.scalar(
        db.select(CuentaPorPagar).filter_by(factura_compra_id=factura.id)
    )
    assert cxp is not None
    assert cxp.monto_total_usd == factura.total_usd  # 116
    assert cxp.saldo_usd == Decimal("66.0000")        # 66