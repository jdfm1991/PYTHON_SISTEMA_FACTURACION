"""Tests unitarios de la CalculadoraFactura."""

from decimal import Decimal

import pytest

from app.services.calculadora_factura import (
    CalculadoraFactura,
    LineaCalculo,
)


@pytest.fixture
def calc() -> CalculadoraFactura:
    return CalculadoraFactura()


def _linea(
    producto_id: int = 1,
    cantidad: str = "1",
    precio_usd: str = "10",
    precio_ves: str = "400",
    alicuota: str = "16",
    descuento_porcentaje: str | None = None,
    descuento_monto_usd: str | None = None,
    descuento_monto_ves: str | None = None,
) -> LineaCalculo:
    return LineaCalculo(
        producto_id=producto_id,
        cantidad=Decimal(cantidad),
        precio_unitario_usd=Decimal(precio_usd),
        precio_unitario_ves=Decimal(precio_ves),
        alicuota_porcentaje=Decimal(alicuota),
        descuento_porcentaje=(
            Decimal(descuento_porcentaje) if descuento_porcentaje else None
        ),
        descuento_monto_usd=(
            Decimal(descuento_monto_usd) if descuento_monto_usd else None
        ),
        descuento_monto_ves=(
            Decimal(descuento_monto_ves) if descuento_monto_ves else None
        ),
    )


# --- Tests básicos ---


def test_linea_simple_sin_descuento(calc):
    """1 producto a 10 USD, IVA 16%."""
    resultado = calc.calcular([_linea()])

    assert resultado.subtotal_usd == Decimal("10.0000")
    assert resultado.base_imponible_usd == Decimal("10.0000")
    assert resultado.iva_usd == Decimal("1.6000")
    assert resultado.total_usd == Decimal("11.6000")


def test_linea_simple_en_ves(calc):
    """1 producto a 400 VES, IVA 16%."""
    resultado = calc.calcular([_linea()])

    assert resultado.subtotal_ves == Decimal("400.0000")
    assert resultado.iva_ves == Decimal("64.0000")
    assert resultado.total_ves == Decimal("464.0000")


def test_cantidad_decimal(calc):
    """2.5 kg a 10 USD."""
    resultado = calc.calcular([_linea(cantidad="2.5")])

    assert resultado.subtotal_usd == Decimal("25.0000")
    assert resultado.iva_usd == Decimal("4.0000")


def test_multiples_lineas(calc):
    """Dos líneas con la misma alícuota."""
    resultado = calc.calcular(
        [
            _linea(producto_id=1, cantidad="2", precio_usd="10", precio_ves="400"),
            _linea(producto_id=2, cantidad="1", precio_usd="5", precio_ves="200"),
        ]
    )

    assert resultado.subtotal_usd == Decimal("25.0000")
    assert resultado.iva_usd == Decimal("4.0000")
    assert resultado.total_usd == Decimal("29.0000")


def test_alicuota_exenta(calc):
    """Producto exento: no genera IVA."""
    resultado = calc.calcular([_linea(alicuota="0")])

    assert resultado.iva_usd == Decimal("0.0000")
    assert resultado.total_usd == Decimal("10.0000")


def test_multiples_alicuotas(calc):
    """Mezcla de alícuotas en la misma factura."""
    resultado = calc.calcular(
        [
            _linea(producto_id=1, precio_usd="100", precio_ves="4000", alicuota="16"),
            _linea(producto_id=2, precio_usd="100", precio_ves="4000", alicuota="8"),
            _linea(producto_id=3, precio_usd="100", precio_ves="4000", alicuota="0"),
        ]
    )

    # IVA: 16 + 8 + 0 = 24
    assert resultado.iva_usd == Decimal("24.0000")
    assert resultado.total_usd == Decimal("324.0000")


# --- Tests de descuento por línea ---


def test_descuento_porcentaje_linea(calc):
    """10% de descuento en una línea."""
    resultado = calc.calcular([_linea(descuento_porcentaje="10")])

    assert resultado.subtotal_usd == Decimal("10.0000")
    assert resultado.descuento_lineas_usd == Decimal("1.0000")
    assert resultado.base_imponible_usd == Decimal("9.0000")
    assert resultado.iva_usd == Decimal("1.4400")
    assert resultado.total_usd == Decimal("10.4400")


def test_descuento_monto_linea(calc):
    """Descuento de 2 USD en una línea."""
    resultado = calc.calcular([_linea(descuento_monto_usd="2")])

    assert resultado.descuento_lineas_usd == Decimal("2.0000")
    assert resultado.base_imponible_usd == Decimal("8.0000")
    assert resultado.iva_usd == Decimal("1.2800")


def test_descuento_mayor_al_subtotal_se_limita(calc):
    """Un descuento mayor al subtotal se limita."""
    resultado = calc.calcular([_linea(descuento_monto_usd="999")])

    assert resultado.descuento_lineas_usd == Decimal("10.0000")
    assert resultado.base_imponible_usd == Decimal("0.0000")
    assert resultado.iva_usd == Decimal("0.0000")
    assert resultado.total_usd == Decimal("0.0000")


def test_descuento_porcentaje_y_monto_linea_falla(calc):
    """No se puede aplicar descuento por porcentaje y monto a la vez."""
    with pytest.raises(ValueError, match="no se puede aplicar"):
        calc.calcular([_linea(descuento_porcentaje="10", descuento_monto_usd="2")])


# --- Tests de descuento global ---


def test_descuento_global_porcentaje_recalcula_iva(calc):
    """Descuento global 10% sobre una factura simple."""
    resultado = calc.calcular(
        [_linea(precio_usd="100", precio_ves="4000")],
        descuento_global_porcentaje=Decimal("10"),
    )

    # Subtotal 100, base sin descuento 100
    # Descuento global 10% → 10
    # Base ajustada 90 → IVA 14.40 → total 104.40
    assert resultado.subtotal_usd == Decimal("100.0000")
    assert resultado.descuento_global_aplicado_usd == Decimal("10.0000")
    assert resultado.base_imponible_usd == Decimal("90.0000")
    assert resultado.iva_usd == Decimal("14.4000")
    assert resultado.total_usd == Decimal("104.4000")


def test_descuento_global_proporcional_multiples_lineas(calc):
    """El descuento global se reparte proporcionalmente entre las líneas."""
    resultado = calc.calcular(
        [
            _linea(producto_id=1, precio_usd="100", precio_ves="4000", alicuota="16"),
            _linea(producto_id=2, precio_usd="300", precio_ves="12000", alicuota="8"),
        ],
        descuento_global_porcentaje=Decimal("10"),
    )

    # Subtotal 400. Descuento global 10% = 40.
    # Línea 1: base 100 → descuento proporcional 10 → nueva base 90 → IVA 14.40
    # Línea 2: base 300 → descuento proporcional 30 → nueva base 270 → IVA 21.60
    # Total base: 360. IVA: 36.00. Total: 396.00
    assert resultado.descuento_global_aplicado_usd == Decimal("40.0000")
    assert resultado.base_imponible_usd == Decimal("360.0000")
    assert resultado.iva_usd == Decimal("36.0000")
    assert resultado.total_usd == Decimal("396.0000")


def test_descuento_global_monto(calc):
    """Descuento global de 50 USD."""
    resultado = calc.calcular(
        [_linea(precio_usd="100", precio_ves="4000")],
        descuento_global_monto_usd=Decimal("50"),
        descuento_global_monto_ves=Decimal("2000"),
    )

    assert resultado.descuento_global_aplicado_usd == Decimal("50.0000")
    assert resultado.base_imponible_usd == Decimal("50.0000")
    assert resultado.iva_usd == Decimal("8.0000")


def test_descuento_global_mayor_a_base_se_limita(calc):
    """Un descuento global mayor a la base se limita."""
    resultado = calc.calcular(
        [_linea(precio_usd="100", precio_ves="4000")],
        descuento_global_monto_usd=Decimal("999"),
        descuento_global_monto_ves=Decimal("39996"),
    )

    assert resultado.descuento_global_aplicado_usd == Decimal("100.0000")
    assert resultado.base_imponible_usd == Decimal("0.0000")
    assert resultado.total_usd == Decimal("0.0000")


def test_descuento_global_porcentaje_y_monto_falla(calc):
    """No se puede aplicar descuento global por porcentaje y monto a la vez."""
    with pytest.raises(ValueError, match="No se puede aplicar"):
        calc.calcular(
            [_linea()],
            descuento_global_porcentaje=Decimal("10"),
            descuento_global_monto_usd=Decimal("5"),
        )


# --- Tests de redondeo ---


def test_redondeo_comercial(calc):
    """El redondeo de 0.5 va hacia arriba (ROUND_HALF_UP)."""
    # 1 unidad a 1.0050 USD → subtotal 1.0050. Base 1.0050. IVA 16% = 0.1608
    resultado = calc.calcular(
        [_linea(precio_usd="1.0050", precio_ves="40.20", cantidad="1")]
    )

    # Base 1.0050, IVA 16% = 0.1608, total 1.1658
    assert resultado.iva_usd == Decimal("0.1608")


def test_precio_con_cuatro_decimales(calc):
    """Precios con 4 decimales (fracciones de centavo)."""
    resultado = calc.calcular(
        [_linea(precio_usd="0.1234", precio_ves="4.9360", cantidad="1", alicuota="16")]
    )

    assert resultado.subtotal_usd == Decimal("0.1234")
    assert resultado.iva_usd == Decimal("0.0197")


# --- Tests combinados ---


def test_descuento_linea_y_global_combinados(calc):
    """Descuento por línea + descuento global."""
    resultado = calc.calcular(
        [_linea(precio_usd="100", precio_ves="4000", descuento_porcentaje="10")],
        descuento_global_porcentaje=Decimal("5"),
    )

    # Subtotal 100. Descuento línea 10% = 10. Base previa = 90.
    # Descuento global 5% sobre 90 = 4.50. Base final = 85.50. IVA 16% = 13.68.
    assert resultado.subtotal_usd == Decimal("100.0000")
    assert resultado.descuento_lineas_usd == Decimal("10.0000")
    assert resultado.descuento_global_aplicado_usd == Decimal("4.5000")
    assert resultado.base_imponible_usd == Decimal("85.5000")
    assert resultado.iva_usd == Decimal("13.6800")
    assert resultado.total_usd == Decimal("99.1800")


def test_factura_vacia(calc):
    """Sin líneas, todos los totales son 0."""
    resultado = calc.calcular([])

    assert resultado.subtotal_usd == Decimal("0.0000")
    assert resultado.iva_usd == Decimal("0.0000")
    assert resultado.total_usd == Decimal("0.0000")
    assert resultado.lineas == []


def test_factura_con_todas_lineas_en_cero(calc):
    """Factura con todas las líneas en 0 no divide por cero.

    Verifica que _aplicar_descuento_global maneje correctamente el caso
    donde base_previa_usd y base_previa_ves son 0.
    """
    resultado = calc.calcular(
        [
            _linea(producto_id=1, precio_usd="0", precio_ves="0"),
            _linea(producto_id=2, precio_usd="0", precio_ves="0"),
        ],
        descuento_global_porcentaje=Decimal("10"),
    )

    assert resultado.subtotal_usd == Decimal("0.0000")
    assert resultado.subtotal_ves == Decimal("0.0000")
    assert resultado.descuento_global_aplicado_usd == Decimal("0.0000")
    assert resultado.descuento_global_aplicado_ves == Decimal("0.0000")
    assert resultado.base_imponible_usd == Decimal("0.0000")
    assert resultado.iva_usd == Decimal("0.0000")
    assert resultado.total_usd == Decimal("0.0000")
