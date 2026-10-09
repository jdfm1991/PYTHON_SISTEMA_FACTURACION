"""Constantes del sistema: enums, mapas de configuración.

Viven en código, no en BD, porque cambian raramente y necesitan
estar disponibles sin consultar la base de datos.
"""

# --- Formas de pago ---
# Cada forma tiene: nombre para mostrar, moneda por defecto, y si aplica IGTF.
# El IGTF solo aplica cuando la moneda es USD (o divisa).

FORMAS_PAGO: dict[str, dict] = {
    "efectivo_ves": {
        "nombre": "Efectivo (Bs)",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "efectivo_usd": {
        "nombre": "Efectivo (USD)",
        "moneda": "USD",
        "aplica_igtf": True,
    },
    "transferencia_ves": {
        "nombre": "Transferencia (Bs)",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "transferencia_usd": {
        "nombre": "Transferencia (USD)",
        "moneda": "USD",
        "aplica_igtf": True,
    },
    "tarjeta_debito_ves": {
        "nombre": "Tarjeta de débito (Bs)",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "tarjeta_credito_ves": {
        "nombre": "Tarjeta de crédito (Bs)",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "tarjeta_internacional": {
        "nombre": "Tarjeta internacional",
        "moneda": "USD",
        "aplica_igtf": True,
    },
    "pago_movil": {
        "nombre": "Pago Móvil",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "cashea": {
        "nombre": "Cashea",
        "moneda": "VES",
        "aplica_igtf": False,
    },
    "cripto": {
        "nombre": "Criptomonedas",
        "moneda": "USD",
        "aplica_igtf": True,
    },
}


def forma_pago_choices() -> list[tuple[str, str]]:
    """Lista de tuplas (valor, nombre) para usar en un SelectField."""
    return [(k, v["nombre"]) for k, v in FORMAS_PAGO.items()]


def forma_pago_nombre(forma: str) -> str:
    """Devuelve el nombre legible de una forma de pago."""
    return FORMAS_PAGO.get(forma, {}).get("nombre", forma)


def forma_pago_aplica_igtf(forma: str, moneda: str) -> bool:
    """Determina si un pago aplica IGTF.

    Regla: aplica IGTF solo si la forma lo declara Y la moneda es USD.
    """
    if forma not in FORMAS_PAGO:
        return False
    return FORMAS_PAGO[forma]["aplica_igtf"] and moneda == "USD"


# --- Tipos de venta ---
TIPO_VENTA_CONTADO = "contado"
TIPO_VENTA_CREDITO_DIRECTO = "credito_directo"
TIPO_VENTA_CREDITO_FIDUCIARIO = "credito_fiduciario"

TIPOS_VENTA: dict[str, str] = {
    TIPO_VENTA_CONTADO: "Contado",
    TIPO_VENTA_CREDITO_DIRECTO: "Crédito directo",
    TIPO_VENTA_CREDITO_FIDUCIARIO: "Crédito con fiduciario",
}


def tipo_venta_choices() -> list[tuple[str, str]]:
    return [(k, v) for k, v in TIPOS_VENTA.items()]


def tipo_venta_nombre(tipo: str) -> str:
    return TIPOS_VENTA.get(tipo, tipo)


# --- Tipos de deudor en CuentaPorCobrar ---
TIPO_DEUDOR_CLIENTE = "cliente"
TIPO_DEUDOR_FIDUCIARIO = "fiduciario"