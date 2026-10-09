"""Tests del InventoryService."""

from decimal import Decimal

import pytest

from app.exceptions import (
    ProductoInactivoError,
    ProductoNoEncontradoError,
    StockInsuficienteError,
)
from app.models import AlicuotaIVA, MovimientoInventario, Producto
from app.services import inventario


@pytest.fixture
def alicuota(db):
    """Alícuota GENERAL para asociar a productos."""
    a = AlicuotaIVA(
        codigo="GENERAL",
        descripcion="General 16%",
        porcentaje=Decimal("16.00"),
    )
    db.session.add(a)
    db.session.flush()
    return a


@pytest.fixture
def producto(db, alicuota):
    """Producto de prueba con stock 100."""
    p = Producto(
        codigo="P001",
        nombre="Producto de prueba",
        precio_usd=Decimal("10.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("100.000"),
        stock_minimo=Decimal("10.000"),
        activo=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


def test_registrar_entrada(producto, db):
    """Una entrada incrementa el stock y crea un movimiento."""
    mov = inventario.registrar_entrada(
        producto_id=producto.id,
        cantidad=Decimal("50"),
        referencia_tipo=inventario.REF_FACTURA_COMPRA,
        referencia_id=1,
    )

    assert producto.stock_actual == Decimal("150.000")
    assert mov.tipo == "entrada"
    assert mov.cantidad == Decimal("50")
    assert mov.stock_anterior == Decimal("100.000")
    assert mov.stock_nuevo == Decimal("150.000")
    assert mov.referencia_tipo == "factura_compra"
    assert mov.referencia_id == 1


def test_registrar_salida(producto, db):
    """Una salida decrementa el stock y crea un movimiento."""
    mov = inventario.registrar_salida(
        producto_id=producto.id,
        cantidad=Decimal("30"),
        referencia_tipo=inventario.REF_FACTURA_VENTA,
        referencia_id=42,
    )

    assert producto.stock_actual == Decimal("70.000")
    assert mov.tipo == "salida"
    assert mov.cantidad == Decimal("30")
    assert mov.stock_anterior == Decimal("100.000")
    assert mov.stock_nuevo == Decimal("70.000")
    assert mov.referencia_tipo == "factura_venta"
    assert mov.referencia_id == 42


def test_entrada_cantidad_negativa_falla(producto, db):
    """Cantidad negativa lanza ValueError."""
    with pytest.raises(ValueError, match="debe ser positiva"):
        inventario.registrar_entrada(
            producto_id=producto.id,
            cantidad=Decimal("-5"),
            referencia_tipo=inventario.REF_AJUSTE_MANUAL,
        )


def test_salida_cantidad_negativa_falla(producto, db):
    with pytest.raises(ValueError, match="debe ser positiva"):
        inventario.registrar_salida(
            producto_id=producto.id,
            cantidad=Decimal("-5"),
            referencia_tipo=inventario.REF_FACTURA_VENTA,
        )


def test_producto_inexistente_falla(db):
    """Producto inexistente lanza ProductoNoEncontradoError."""
    with pytest.raises(ProductoNoEncontradoError):
        inventario.registrar_entrada(
            producto_id=99999,
            cantidad=Decimal("10"),
            referencia_tipo=inventario.REF_FACTURA_COMPRA,
        )


def test_producto_inactivo_entrada_falla(db, alicuota):
    """Producto inactivo lanza ProductoInactivoError."""
    p = Producto(
        codigo="P999",
        nombre="Inactivo",
        precio_usd=Decimal("1.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("0.000"),
        activo=False,
    )
    db.session.add(p)
    db.session.flush()

    with pytest.raises(ProductoInactivoError):
        inventario.registrar_entrada(
            producto_id=p.id,
            cantidad=Decimal("10"),
            referencia_tipo=inventario.REF_AJUSTE_MANUAL,
        )


def test_producto_inactivo_salida_falla(db, alicuota):
    p = Producto(
        codigo="P998",
        nombre="Inactivo",
        precio_usd=Decimal("1.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("100.000"),
        activo=False,
    )
    db.session.add(p)
    db.session.flush()

    with pytest.raises(ProductoInactivoError):
        inventario.registrar_salida(
            producto_id=p.id,
            cantidad=Decimal("10"),
            referencia_tipo=inventario.REF_FACTURA_VENTA,
        )


def test_stock_insuficiente_falla(producto, db):
    """Salida mayor al stock lanza StockInsuficienteError."""
    with pytest.raises(StockInsuficienteError) as exc_info:
        inventario.registrar_salida(
            producto_id=producto.id,
            cantidad=Decimal("500"),
            referencia_tipo=inventario.REF_FACTURA_VENTA,
        )

    assert exc_info.value.disponible == Decimal("100.000")
    assert exc_info.value.solicitado == Decimal("500")


def test_salida_exacta_al_stock(producto, db):
    """Vender exactamente todo el stock es válido (stock queda en 0)."""
    mov = inventario.registrar_salida(
        producto_id=producto.id,
        cantidad=Decimal("100"),
        referencia_tipo=inventario.REF_FACTURA_VENTA,
    )

    assert producto.stock_actual == Decimal("0.000")
    assert mov.stock_nuevo == Decimal("0.000")


def test_multiples_movimientos(producto, db):
    """Varios movimientos acumulan correctamente el stock."""
    inventario.registrar_entrada(
        producto.id, Decimal("50"), inventario.REF_FACTURA_COMPRA
    )
    inventario.registrar_salida(
        producto.id, Decimal("30"), inventario.REF_FACTURA_VENTA
    )
    inventario.registrar_salida(
        producto.id, Decimal("20"), inventario.REF_FACTURA_VENTA
    )

    assert producto.stock_actual == Decimal("100.000")

    # Deben existir 3 movimientos
    movimientos = db.session.scalars(
        db.select(MovimientoInventario).filter_by(producto_id=producto.id)
    ).all()
    assert len(movimientos) == 3
    
def test_entrada_con_producto_inactivo_permitida(db, alicuota):
    """Con permitir_inactivo=True, se permite la entrada aunque el producto esté inactivo."""
    p = Producto(
        codigo="P100",
        nombre="Inactivo",
        precio_usd=Decimal("1.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("0.000"),
        activo=False,
    )
    db.session.add(p)
    db.session.flush()

    mov = inventario.registrar_entrada(
        producto_id=p.id,
        cantidad=Decimal("10"),
        referencia_tipo=inventario.REF_AJUSTE_MANUAL,
        motivo="Reverso de anulación",
        permitir_inactivo=True,
    )

    assert mov.tipo == "entrada"
    assert p.stock_actual == Decimal("10.000")