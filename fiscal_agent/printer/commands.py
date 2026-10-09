"""Constructor de comandos para la impresora fiscal HKA.

Encapsula la lógica de formateo de cada tipo de comando.
Los comandos se devuelven como strings listos para enviar con SendCmd.
"""

from decimal import ROUND_HALF_UP, Decimal

from fiscal_agent.constants import (
    ALICUOTA_A_COMANDO,
    CANTIDAD_DECIMALES,
    CANTIDAD_ENTERO_DIGITOS,
    CMD_CLIENTE_LINEA,
    CMD_CLIENTE_NOMBRE,
    CMD_CLIENTE_RIF,
    CMD_CERRAR_FACTURA,
    CMD_PAGO,
    CMD_SUBTOTAL,
    FORMA_PAGO_A_CODIGO,
    MONTO_DECIMALES,
    MONTO_ENTERO_DIGITOS,
    PRECIO_DECIMALES,
    PRECIO_ENTERO_DIGITOS,
)
from fiscal_agent.printer.exceptions import PrinterCommandError


# --- Utilidades de formateo ---

def _formatear_precio(precio_ves: Decimal) -> str:
    """Formatea un precio en VES al formato de la impresora.

    Formato: 8 dígitos enteros + 2 decimales = 10 dígitos.
    Ejemplo: Bs 50.63 → "0000005063"
    """
    precio = precio_ves.quantize(
        Decimal(f"0.{'0' * PRECIO_DECIMALES}"), rounding=ROUND_HALF_UP
    )
    entero = int(precio)
    decimales = int(
        (precio - entero) * (10 ** PRECIO_DECIMALES)
    )
    return f"{entero:0{PRECIO_ENTERO_DIGITOS}d}{decimales:0{PRECIO_DECIMALES}d}"


def _formatear_cantidad(cantidad: Decimal) -> str:
    """Formatea una cantidad al formato de la impresora.

    Formato: 5 dígitos enteros + 3 decimales = 8 dígitos.
    Ejemplo: 2.000 → "00002000"
    """
    cantidad = cantidad.quantize(
        Decimal(f"0.{'0' * CANTIDAD_DECIMALES}"), rounding=ROUND_HALF_UP
    )
    entero = int(cantidad)
    decimales = int(
        (cantidad - entero) * (10 ** CANTIDAD_DECIMALES)
    )
    return f"{entero:0{CANTIDAD_ENTERO_DIGITOS}d}{decimales:0{CANTIDAD_DECIMALES}d}"


def _formatear_monto(monto_ves: Decimal) -> str:
    """Formatea un monto de pago al formato de la impresora.

    Formato: 10 dígitos enteros + 2 decimales = 12 dígitos.
    Ejemplo: Bs 117.45 → "000000011745"
    """
    monto = monto_ves.quantize(
        Decimal(f"0.{'0' * MONTO_DECIMALES}"), rounding=ROUND_HALF_UP
    )
    entero = int(monto)
    decimales = int((monto - entero) * 100) 
    return f"{entero:010d}{decimales:02d}"


# --- Constructores de comandos ---

def comando_cliente_rif(tipo_documento: str, numero_documento: str) -> str:
    """Construye el comando de RIF del cliente.

    Formato: iR* + tipo + numero
    Ejemplo: iR*V12345678
    """
    tipo = (tipo_documento or "").strip().upper()
    numero = (numero_documento or "").strip()
    if not tipo or not numero:
        raise PrinterCommandError(
            "El tipo y número de documento del cliente son obligatorios."
        )
    return f"{CMD_CLIENTE_RIF}{tipo}{numero}"


def comando_cliente_nombre(razon_social: str) -> str:
    """Construye el comando de razón social del cliente.

    Formato: iS* + razón social
    Ejemplo: iS*JUAN PEREZ
    """
    nombre = (razon_social or "").strip().upper()
    if not nombre:
        raise PrinterCommandError(
            "La razón social del cliente es obligatoria."
        )
    return f"{CMD_CLIENTE_NOMBRE}{nombre}"


def comando_cliente_linea(numero: int, texto: str) -> str:
    """Construye un comando de línea adicional del cliente (i01..i09).

    Args:
        numero: 1..9
        texto: contenido de la línea.
    """
    if not 1 <= numero <= 9:
        raise PrinterCommandError(
            f"Número de línea inválido: {numero}. Debe ser 1..9."
        )
    texto = (texto or "").strip()
    if not texto:
        return ""  # línea vacía → no enviar
    return f"{CMD_CLIENTE_LINEA.format(numero)}{texto}"


def comando_producto(
    codigo: str,
    descripcion: str,
    cantidad: Decimal,
    precio_unitario_ves: Decimal,
    alicuota_porcentaje: Decimal,
) -> str:
    """Construye el comando de una línea de producto.

    Formato: CMD_IVA + PRECIO + CANTIDAD + CÓDIGO(4) + DESCRIPCIÓN
    """
    alicuota_str = str(alicuota_porcentaje.quantize(Decimal("0.00")))
    if alicuota_str not in ALICUOTA_A_COMANDO:
        raise PrinterCommandError(
            f"Alícuota no soportada: {alicuota_str}%. "
            f"Válidas: {list(ALICUOTA_A_COMANDO.keys())}"
        )
    cmd_iva = ALICUOTA_A_COMANDO[alicuota_str]

    precio_str = _formatear_precio(precio_unitario_ves)
    cantidad_str = _formatear_cantidad(cantidad)

    # Código: hasta 4 dígitos. Si es más largo, se trunca.
    codigo_str = str(codigo or "").strip()[:4]
    codigo_str = codigo_str.ljust(4, " ")

    desc = (descripcion or "").strip().upper()[:40]

    return f"{cmd_iva}{precio_str}{cantidad_str}{codigo_str}{desc}"


def comando_pago(forma_pago: str, monto_ves: Decimal) -> str:
    """Construye el comando de un pago.

    Formato: 2 + CODIGO_MEDIO(2) + MONTO(12)
    """
    if forma_pago not in FORMA_PAGO_A_CODIGO:
        raise PrinterCommandError(
            f"Forma de pago no soportada: {forma_pago}. "
            f"Válidas: {list(FORMA_PAGO_A_CODIGO.keys())}"
        )
    codigo = FORMA_PAGO_A_CODIGO[forma_pago]
    monto_str = _formatear_monto(monto_ves)
    return f"{CMD_PAGO}{codigo}{monto_str}"


def comando_cerrar_factura() -> str:
    """Devuelve el comando de cierre fiscal."""
    return CMD_CERRAR_FACTURA


def comando_subtotal() -> str:
    """Devuelve el comando de impresión de subtotal."""
    return CMD_SUBTOTAL