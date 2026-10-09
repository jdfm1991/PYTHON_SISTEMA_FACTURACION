"""Excepciones de dominio del sistema.

Errores esperados de negocio. No son errores técnicos (TypeError, ValueError),
sino violaciones de reglas de negocio que el llamador debe manejar.
"""


class DominioError(Exception):
    """Base para todas las excepciones de dominio.

    Permite capturar cualquier error de negocio con:
        try:
            ...
        except DominioError as e:
            flash(str(e), "error")
    """


class ProductoNoEncontradoError(DominioError):
    """El producto solicitado no existe."""


class ProductoInactivoError(DominioError):
    """El producto está inactivo y no puede operarse."""


class StockInsuficienteError(DominioError):
    """No hay stock suficiente para la operación."""

    def __init__(self, producto_codigo: str, disponible, solicitado):
        self.producto_codigo = producto_codigo
        self.disponible = disponible
        self.solicitado = solicitado
        super().__init__(
            f"Stock insuficiente para '{producto_codigo}'. "
            f"Disponible: {disponible}, solicitado: {solicitado}."
        )


class CreditoNoHabilitadoError(DominioError):
    """El cliente no tiene crédito habilitado."""

    def __init__(self, cliente_nombre: str):
        self.cliente_nombre = cliente_nombre
        super().__init__(f"El cliente '{cliente_nombre}' no tiene crédito habilitado.")


class LimiteCreditoExcedidoError(DominioError):
    """El cliente excede su límite de crédito."""

    def __init__(self, cliente_nombre: str, saldo_actual, limite, monto_nuevo):
        self.cliente_nombre = cliente_nombre
        self.saldo_actual = saldo_actual
        self.limite = limite
        self.monto_nuevo = monto_nuevo
        super().__init__(
            f"El cliente '{cliente_nombre}' excede su límite de crédito. "
            f"Saldo actual: {saldo_actual}, "
            f"nuevo cargo: {monto_nuevo}, "
            f"límite: {limite}."
        )


class PagoInvalidoError(DominioError):
    """Un pago tiene datos inválidos."""


class FiduciarioNoValidoError(DominioError):
    """El fiduciario indicado no es válido o está inactivo."""


class TipoVentaInvalidoError(DominioError):
    """El tipo de venta indicado no es válido."""


class FacturaSinLineasError(DominioError):
    """La factura no tiene líneas para confirmar."""
    
class FacturaNoEditableError(DominioError):
    """La factura no está en estado editable."""
    
class FacturaNoAnulableError(DominioError):
    """La factura no puede anularse en su estado actual."""

class CxConPagosError(DominioError):
    """La CuentaPorCobrar tiene pagos parciales; no se puede anular."""

class PagoExcedeTotalError(DominioError):
    """El monto total de los pagos excede el total de la factura."""

    def __init__(self, total_pagado, total_factura):
        self.total_pagado = total_pagado
        self.total_factura = total_factura
        super().__init__(
            f"El total pagado ({total_pagado}) excede el total de la factura "
            f"({total_factura}). En compras no se permite pago mayor al total."
        )

class StockNegativoError(DominioError):
    """La operación dejaría el stock en negativo."""

    def __init__(self, producto_codigo: str, stock_actual, a_descontar, resultante):
        self.producto_codigo = producto_codigo
        self.stock_actual = stock_actual
        self.a_descontar = a_descontar
        self.resultante = resultante
        super().__init__(
            f"No se puede anular: el stock de '{producto_codigo}' "
            f"quedaría en {resultante}. "
            f"Stock actual: {stock_actual}, a descontar: {a_descontar}. "
            "Ajuste el inventario antes de anular."
        )