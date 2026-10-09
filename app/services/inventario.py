"""Servicio de inventario.

Único punto del sistema que modifica Producto.stock_actual.
Cada cambio de stock genera un MovimientoInventario.

Los métodos usan flush() pero NO commit(). El llamador decide cuándo
confirmar la transacción, para permitir operaciones atómicas compuestas
(factura + movimiento, por ejemplo).

En producción (MySQL), las lecturas de producto usan SELECT ... FOR UPDATE
para evitar race conditions entre transacciones concurrentes.
En SQLite (tests), el bloqueo se omite porque el motor no lo soporta.
"""

from decimal import Decimal

from app.exceptions import (
    ProductoInactivoError,
    ProductoNoEncontradoError,
    StockInsuficienteError,
)
from app.extensions import db
from app.models import MovimientoInventario, Producto

TIPO_ENTRADA = "entrada"
TIPO_SALIDA = "salida"

REF_FACTURA_VENTA = "factura_venta"
REF_FACTURA_COMPRA = "factura_compra"
REF_AJUSTE_MANUAL = "ajuste_manual"

# Motores que soportan SELECT ... FOR UPDATE
_MOTORES_CON_BLOQUEO = ("mysql", "postgresql")


def _get_producto_bloqueado(producto_id: int) -> Producto | None:
    """Obtiene un producto con bloqueo de fila si el motor lo soporta.

    En MySQL/PostgreSQL, usa SELECT ... FOR UPDATE para que la fila quede
    bloqueada durante la transacción. Esto evita que dos transacciones
    lean y modifiquen el stock concurrentemente produciendo inconsistencias.

    En SQLite (tests), hace un get normal porque el motor no soporta
    FOR UPDATE y lo ignoraría silenciosamente.
    """
    motor = db.session.get_bind().dialect.name
    if motor in _MOTORES_CON_BLOQUEO:
        return db.session.get(Producto, producto_id, with_for_update=True)
    return db.session.get(Producto, producto_id)


def registrar_entrada(
    producto_id: int,
    cantidad: Decimal,
    referencia_tipo: str,
    referencia_id: int | None = None,
    motivo: str | None = None,
) -> MovimientoInventario:
    """Registra una entrada de stock (compra o ajuste positivo).

    Raises:
        ProductoNoEncontradoError: si el producto no existe.
        ProductoInactivoError: si el producto está inactivo.
        ValueError: si la cantidad no es positiva.
    """
    if cantidad <= 0:
        raise ValueError(f"La cantidad debe ser positiva, recibida: {cantidad}")

    producto = _get_producto_bloqueado(producto_id)
    if producto is None:
        raise ProductoNoEncontradoError(
            f"Producto con ID {producto_id} no encontrado."
        )
    if not producto.activo:
        raise ProductoInactivoError(
            f"El producto '{producto.codigo}' está inactivo."
        )

    stock_anterior = producto.stock_actual
    stock_nuevo = stock_anterior + cantidad

    producto.stock_actual = stock_nuevo

    movimiento = MovimientoInventario(
        producto_id=producto_id,
        tipo=TIPO_ENTRADA,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
    )
    db.session.add(movimiento)
    db.session.flush()  # NO commit

    return movimiento


def registrar_salida(
    producto_id: int,
    cantidad: Decimal,
    referencia_tipo: str,
    referencia_id: int | None = None,
    motivo: str | None = None,
) -> MovimientoInventario:
    """Registra una salida de stock (venta o ajuste negativo).

    Raises:
        ProductoNoEncontradoError: si el producto no existe.
        ProductoInactivoError: si el producto está inactivo.
        StockInsuficienteError: si no hay stock suficiente.
        ValueError: si la cantidad no es positiva.
    """
    if cantidad <= 0:
        raise ValueError(f"La cantidad debe ser positiva, recibida: {cantidad}")

    producto = _get_producto_bloqueado(producto_id)
    if producto is None:
        raise ProductoNoEncontradoError(
            f"Producto con ID {producto_id} no encontrado."
        )
    if not producto.activo:
        raise ProductoInactivoError(
            f"El producto '{producto.codigo}' está inactivo."
        )

    stock_anterior = producto.stock_actual
    if stock_anterior < cantidad:
        raise StockInsuficienteError(
            producto_codigo=producto.codigo,
            disponible=stock_anterior,
            solicitado=cantidad,
        )

    stock_nuevo = stock_anterior - cantidad
    producto.stock_actual = stock_nuevo

    movimiento = MovimientoInventario(
        producto_id=producto_id,
        tipo=TIPO_SALIDA,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
    )
    db.session.add(movimiento)
    db.session.flush()  # NO commit

    return movimiento

def registrar_entrada(
    producto_id: int,
    cantidad: Decimal,
    referencia_tipo: str,
    referencia_id: int | None = None,
    motivo: str | None = None,
    permitir_inactivo: bool = False,
) -> MovimientoInventario:
    """Registra una entrada de stock (compra, ajuste positivo o reverso).

    Args:
        ...
        permitir_inactivo: si True, no rechaza productos inactivos.
            Se usa en reversos (por ejemplo, al anular una factura)
            para permitir la devolución aunque el producto se haya
            desactivado después.

    Raises:
        ProductoNoEncontradoError: si el producto no existe.
        ProductoInactivoError: si el producto está inactivo y no se permite.
        ValueError: si la cantidad no es positiva.
    """
    if cantidad <= 0:
        raise ValueError(f"La cantidad debe ser positiva, recibida: {cantidad}")

    producto = _get_producto_bloqueado(producto_id)
    if producto is None:
        raise ProductoNoEncontradoError(
            f"Producto con ID {producto_id} no encontrado."
        )
    if not producto.activo and not permitir_inactivo:
        raise ProductoInactivoError(
            f"El producto '{producto.codigo}' está inactivo."
        )

    stock_anterior = producto.stock_actual
    stock_nuevo = stock_anterior + cantidad
    producto.stock_actual = stock_nuevo

    movimiento = MovimientoInventario(
        producto_id=producto_id,
        tipo=TIPO_ENTRADA,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
    )
    db.session.add(movimiento)
    db.session.flush()
    return movimiento