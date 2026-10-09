"""Validación del JSON de factura recibido por el agente."""

from decimal import Decimal, InvalidOperation

from fiscal_agent.printer.base import (
    FacturaCliente,
    FacturaLinea,
    FacturaPago,
)
from fiscal_agent.printer.exceptions import PrinterCommandError


class ValidacionError(Exception):
    """Error de validación del JSON."""


def _str_requerido(data: dict, key: str) -> str:
    """Extrae un string requerido."""
    valor = data.get(key)
    if not valor or not isinstance(valor, str) or not valor.strip():
        raise ValidacionError(f"El campo '{key}' es obligatorio.")
    return valor.strip()


def _str_opcional(data: dict, key: str) -> str | None:
    """Extrae un string opcional."""
    valor = data.get(key)
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValidacionError(f"El campo '{key}' debe ser texto.")
    valor = valor.strip()
    return valor or None


def _decimal_requerido(data: dict, key: str) -> Decimal:
    """Extrae un Decimal requerido."""
    valor = data.get(key)
    if valor is None:
        raise ValidacionError(f"El campo '{key}' es obligatorio.")
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidacionError(
            f"El campo '{key}' no es un número válido: {valor!r}"
        ) from e


def parsear_cliente(data: dict) -> FacturaCliente:
    """Valida y convierte los datos del cliente."""
    return FacturaCliente(
        tipo_documento=_str_requerido(data, "tipo_documento"),
        numero_documento=_str_requerido(data, "numero_documento"),
        razon_social=_str_requerido(data, "razon_social"),
        direccion=_str_opcional(data, "direccion"),
    )


def parsear_linea(data: dict) -> FacturaLinea:
    """Valida y convierte una línea de factura."""
    return FacturaLinea(
        codigo=_str_opcional(data, "codigo") or "",
        descripcion=_str_requerido(data, "descripcion"),
        cantidad=_decimal_requerido(data, "cantidad"),
        precio_unitario_ves=_decimal_requerido(data, "precio_unitario_ves"),
        alicuota_porcentaje=_decimal_requerido(data, "alicuota_iva"),
    )


def parsear_pago(data: dict) -> FacturaPago:
    """Valida y convierte un pago."""
    return FacturaPago(
        forma_pago=_str_requerido(data, "forma_pago"),
        monto_ves=_decimal_requerido(data, "monto_ves"),
    )


def parsear_factura(data: dict) -> tuple[
    FacturaCliente, list[FacturaLinea], list[FacturaPago]
]:
    """Valida y convierte el JSON completo de la factura.

    Returns:
        Tupla (cliente, lineas, pagos).

    Raises:
        ValidacionError: si algún campo es inválido.
    """
    if not isinstance(data, dict):
        raise ValidacionError("El cuerpo debe ser un objeto JSON.")

    # Cliente
    cliente_data = data.get("cliente")
    if not isinstance(cliente_data, dict):
        raise ValidacionError("El campo 'cliente' es obligatorio.")
    cliente = parsear_cliente(cliente_data)

    # Líneas
    lineas_data = data.get("lineas")
    if not isinstance(lineas_data, list) or not lineas_data:
        raise ValidacionError(
            "El campo 'lineas' debe ser una lista no vacía."
        )
    lineas = [parsear_linea(l) for l in lineas_data]

    # Pagos (opcional)
    pagos_data = data.get("pagos") or []
    if not isinstance(pagos_data, list):
        raise ValidacionError("El campo 'pagos' debe ser una lista.")
    pagos = [parsear_pago(p) for p in pagos_data]

    return cliente, lineas, pagos