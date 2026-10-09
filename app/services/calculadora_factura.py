"""Calculadora pura de totales de factura.

No toca la base de datos. Recibe líneas y devuelve totales.
Usa Decimal y ROUND_HALF_UP en todos los cálculos monetarios.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Precisión interna: 4 decimales. Coincide con Numeric(14,4) del modelo.
_PRECISION = Decimal("0.0001")


def _redondear(valor: Decimal) -> Decimal:
    """Redondea a 4 decimales con ROUND_HALF_UP (comercial)."""
    return valor.quantize(_PRECISION, rounding=ROUND_HALF_UP)


@dataclass
class LineaCalculo:
    """Entrada de una línea para la calculadora.

    Los descuentos son mutuamente excluyentes por nivel:
    - Si se define `descuento_porcentaje`, no debe definirse `descuento_monto_usd`.
    - Y viceversa.

    El precio en VES ya viene calculado (precio_unitario_usd × tasa).
    La calculadora no conoce la tasa.
    """

    producto_id: int
    cantidad: Decimal
    precio_unitario_usd: Decimal
    precio_unitario_ves: Decimal
    alicuota_porcentaje: Decimal
    descuento_porcentaje: Decimal | None = None
    descuento_monto_usd: Decimal | None = None
    descuento_monto_ves: Decimal | None = None


@dataclass
class ResultadoLinea:
    """Resultado del cálculo de una línea."""

    producto_id: int
    cantidad: Decimal
    precio_unitario_usd: Decimal
    precio_unitario_ves: Decimal
    alicuota_porcentaje: Decimal
    descuento_porcentaje: Decimal | None
    descuento_monto_usd: Decimal | None
    descuento_monto_ves: Decimal | None

    subtotal_usd: Decimal
    subtotal_ves: Decimal
    descuento_aplicado_usd: Decimal
    descuento_aplicado_ves: Decimal
    base_imponible_usd: Decimal
    base_imponible_ves: Decimal
    iva_usd: Decimal
    iva_ves: Decimal
    total_usd: Decimal
    total_ves: Decimal


@dataclass
class ResultadoFactura:
    """Resultado del cálculo de una factura completa."""

    lineas: list[ResultadoLinea] = field(default_factory=list)

    subtotal_usd: Decimal = Decimal("0.0000")
    subtotal_ves: Decimal = Decimal("0.0000")

    descuento_lineas_usd: Decimal = Decimal("0.0000")
    descuento_lineas_ves: Decimal = Decimal("0.0000")

    descuento_global_porcentaje: Decimal | None = None
    descuento_global_monto_usd: Decimal | None = None
    descuento_global_monto_ves: Decimal | None = None
    descuento_global_aplicado_usd: Decimal = Decimal("0.0000")
    descuento_global_aplicado_ves: Decimal = Decimal("0.0000")

    base_imponible_usd: Decimal = Decimal("0.0000")
    base_imponible_ves: Decimal = Decimal("0.0000")
    iva_usd: Decimal = Decimal("0.0000")
    iva_ves: Decimal = Decimal("0.0000")
    total_usd: Decimal = Decimal("0.0000")
    total_ves: Decimal = Decimal("0.0000")


class CalculadoraFactura:
    """Calculadora pura de totales de factura.

    Uso:
        calc = CalculadoraFactura()
        resultado = calc.calcular(lineas, descuento_global_porcentaje=Decimal("10"))
    """

    def calcular(
        self,
        lineas: list[LineaCalculo],
        descuento_global_porcentaje: Decimal | None = None,
        descuento_global_monto_usd: Decimal | None = None,
        descuento_global_monto_ves: Decimal | None = None,
    ) -> ResultadoFactura:
        """Calcula los totales de la factura."""
        self._validar_descuento_global(
            descuento_global_porcentaje,
            descuento_global_monto_usd,
            descuento_global_monto_ves,
        )

        # 1) Calcular cada línea SIN descuento global
        lineas_calculadas = [self._calcular_linea(l) for l in lineas]

        # 2) Totales agregados antes del descuento global
        subtotal_usd = sum((l.subtotal_usd for l in lineas_calculadas), Decimal("0"))
        subtotal_ves = sum((l.subtotal_ves for l in lineas_calculadas), Decimal("0"))
        desc_lineas_usd = sum(
            (l.descuento_aplicado_usd for l in lineas_calculadas), Decimal("0")
        )
        desc_lineas_ves = sum(
            (l.descuento_aplicado_ves for l in lineas_calculadas), Decimal("0")
        )

        base_previa_usd = subtotal_usd - desc_lineas_usd
        base_previa_ves = subtotal_ves - desc_lineas_ves

        # 3) Calcular descuento global
        (
            desc_global_usd,
            desc_global_ves,
        ) = self._calcular_descuento_global(
            base_previa_usd,
            base_previa_ves,
            descuento_global_porcentaje,
            descuento_global_monto_usd,
            descuento_global_monto_ves,
        )

        # 4) Aplicar descuento global proporcionalmente a cada línea
        #    y recalcular base imponible e IVA por línea
        if desc_global_usd > 0 or desc_global_ves > 0:
            lineas_calculadas = self._aplicar_descuento_global(
                lineas_calculadas,
                base_previa_usd,
                base_previa_ves,
                desc_global_usd,
                desc_global_ves,
            )

        # 5) Sumar IVA y totales finales
        base_imponible_usd = sum(
            (l.base_imponible_usd for l in lineas_calculadas), Decimal("0")
        )
        base_imponible_ves = sum(
            (l.base_imponible_ves for l in lineas_calculadas), Decimal("0")
        )
        iva_usd = sum((l.iva_usd for l in lineas_calculadas), Decimal("0"))
        iva_ves = sum((l.iva_ves for l in lineas_calculadas), Decimal("0"))
        total_usd = base_imponible_usd + iva_usd
        total_ves = base_imponible_ves + iva_ves

        return ResultadoFactura(
            lineas=lineas_calculadas,
            subtotal_usd=_redondear(subtotal_usd),
            subtotal_ves=_redondear(subtotal_ves),
            descuento_lineas_usd=_redondear(desc_lineas_usd),
            descuento_lineas_ves=_redondear(desc_lineas_ves),
            descuento_global_porcentaje=descuento_global_porcentaje,
            descuento_global_monto_usd=descuento_global_monto_usd,
            descuento_global_monto_ves=descuento_global_monto_ves,
            descuento_global_aplicado_usd=_redondear(desc_global_usd),
            descuento_global_aplicado_ves=_redondear(desc_global_ves),
            base_imponible_usd=_redondear(base_imponible_usd),
            base_imponible_ves=_redondear(base_imponible_ves),
            iva_usd=_redondear(iva_usd),
            iva_ves=_redondear(iva_ves),
            total_usd=_redondear(total_usd),
            total_ves=_redondear(total_ves),
        )

    # --- Internos ---

    def _calcular_linea(self, linea: LineaCalculo) -> ResultadoLinea:
        """Calcula subtotal, descuento por línea, base, IVA y total."""
        self._validar_descuento_linea(linea)

        subtotal_usd = _redondear(linea.cantidad * linea.precio_unitario_usd)
        subtotal_ves = _redondear(linea.cantidad * linea.precio_unitario_ves)

        desc_usd, desc_ves = self._calcular_descuento_linea(
            subtotal_usd,
            subtotal_ves,
            linea.descuento_porcentaje,
            linea.descuento_monto_usd,
            linea.descuento_monto_ves,
        )

        base_usd = _redondear(subtotal_usd - desc_usd)
        base_ves = _redondear(subtotal_ves - desc_ves)

        iva_usd = _redondear(base_usd * linea.alicuota_porcentaje / Decimal("100"))
        iva_ves = _redondear(base_ves * linea.alicuota_porcentaje / Decimal("100"))

        return ResultadoLinea(
            producto_id=linea.producto_id,
            cantidad=linea.cantidad,
            precio_unitario_usd=linea.precio_unitario_usd,
            precio_unitario_ves=linea.precio_unitario_ves,
            alicuota_porcentaje=linea.alicuota_porcentaje,
            descuento_porcentaje=linea.descuento_porcentaje,
            descuento_monto_usd=linea.descuento_monto_usd,
            descuento_monto_ves=linea.descuento_monto_ves,
            subtotal_usd=subtotal_usd,
            subtotal_ves=subtotal_ves,
            descuento_aplicado_usd=desc_usd,
            descuento_aplicado_ves=desc_ves,
            base_imponible_usd=base_usd,
            base_imponible_ves=base_ves,
            iva_usd=iva_usd,
            iva_ves=iva_ves,
            total_usd=_redondear(base_usd + iva_usd),
            total_ves=_redondear(base_ves + iva_ves),
        )

    def _validar_descuento_linea(self, linea: LineaCalculo) -> None:
        """Los descuentos por línea son mutuamente excluyentes."""
        tiene_porcentaje = linea.descuento_porcentaje is not None
        tiene_monto = (
            linea.descuento_monto_usd is not None
            or linea.descuento_monto_ves is not None
        )
        if tiene_porcentaje and tiene_monto:
            raise ValueError(
                f"Línea del producto {linea.producto_id}: no se puede aplicar "
                "descuento por porcentaje y por monto a la vez."
            )

    def _calcular_descuento_linea(
        self,
        subtotal_usd: Decimal,
        subtotal_ves: Decimal,
        porcentaje: Decimal | None,
        monto_usd: Decimal | None,
        monto_ves: Decimal | None,
    ) -> tuple[Decimal, Decimal]:
        """Calcula el descuento aplicado a la línea, limitado al subtotal."""
        if porcentaje is not None:
            desc_usd = _redondear(subtotal_usd * porcentaje / Decimal("100"))
            desc_ves = _redondear(subtotal_ves * porcentaje / Decimal("100"))
        elif monto_usd is not None or monto_ves is not None:
            desc_usd = _redondear(monto_usd or Decimal("0"))
            desc_ves = _redondear(monto_ves or Decimal("0"))
        else:
            desc_usd = Decimal("0.0000")
            desc_ves = Decimal("0.0000")

        # Limitar al subtotal (no permitir negativos)
        desc_usd = min(desc_usd, subtotal_usd)
        desc_ves = min(desc_ves, subtotal_ves)

        return desc_usd, desc_ves

    def _validar_descuento_global(self, porcentaje, monto_usd, monto_ves):
        tiene_porcentaje = porcentaje is not None and porcentaje != 0
        tiene_monto = (monto_usd is not None and monto_usd != 0) or (
            monto_ves is not None and monto_ves != 0
        )
        if tiene_porcentaje and tiene_monto:
            raise ValueError(
                "No se puede aplicar descuento global por porcentaje y por monto a la vez."
            )

    def _calcular_descuento_global(
        self,
        base_previa_usd: Decimal,
        base_previa_ves: Decimal,
        porcentaje: Decimal | None,
        monto_usd: Decimal | None,
        monto_ves: Decimal | None,
    ) -> tuple[Decimal, Decimal]:
        """Calcula el descuento global, limitado a la base previa."""
        if porcentaje is not None:
            desc_usd = _redondear(base_previa_usd * porcentaje / Decimal("100"))
            desc_ves = _redondear(base_previa_ves * porcentaje / Decimal("100"))
        elif monto_usd is not None or monto_ves is not None:
            desc_usd = _redondear(monto_usd or Decimal("0"))
            desc_ves = _redondear(monto_ves or Decimal("0"))
        else:
            return Decimal("0.0000"), Decimal("0.0000")

        desc_usd = min(desc_usd, base_previa_usd)
        desc_ves = min(desc_ves, base_previa_ves)

        return desc_usd, desc_ves

    def _aplicar_descuento_global(
        self,
        lineas: list[ResultadoLinea],
        base_previa_usd: Decimal,
        base_previa_ves: Decimal,
        desc_global_usd: Decimal,
        desc_global_ves: Decimal,
    ) -> list[ResultadoLinea]:
        """Aplica el descuento global proporcionalmente a cada línea.

        Recalcula base imponible, IVA y total por línea con la base ajustada.
        """
        if base_previa_usd == 0 and base_previa_ves == 0:
            return lineas

        lineas_ajustadas = []
        for linea in lineas:
            # Factor proporcional por línea según su base
            if base_previa_usd > 0:
                factor_usd = linea.base_imponible_usd / base_previa_usd
                desc_linea_usd = _redondear(desc_global_usd * factor_usd)
            else:
                desc_linea_usd = Decimal("0.0000")

            if base_previa_ves > 0:
                factor_ves = linea.base_imponible_ves / base_previa_ves
                desc_linea_ves = _redondear(desc_global_ves * factor_ves)
            else:
                desc_linea_ves = Decimal("0.0000")

            nueva_base_usd = _redondear(linea.base_imponible_usd - desc_linea_usd)
            nueva_base_ves = _redondear(linea.base_imponible_ves - desc_linea_ves)

            nuevo_iva_usd = _redondear(
                nueva_base_usd * linea.alicuota_porcentaje / Decimal("100")
            )
            nuevo_iva_ves = _redondear(
                nueva_base_ves * linea.alicuota_porcentaje / Decimal("100")
            )

            lineas_ajustadas.append(
                ResultadoLinea(
                    producto_id=linea.producto_id,
                    cantidad=linea.cantidad,
                    precio_unitario_usd=linea.precio_unitario_usd,
                    precio_unitario_ves=linea.precio_unitario_ves,
                    alicuota_porcentaje=linea.alicuota_porcentaje,
                    descuento_porcentaje=linea.descuento_porcentaje,
                    descuento_monto_usd=linea.descuento_monto_usd,
                    descuento_monto_ves=linea.descuento_monto_ves,
                    subtotal_usd=linea.subtotal_usd,
                    subtotal_ves=linea.subtotal_ves,
                    descuento_aplicado_usd=linea.descuento_aplicado_usd,
                    descuento_aplicado_ves=linea.descuento_aplicado_ves,
                    base_imponible_usd=nueva_base_usd,
                    base_imponible_ves=nueva_base_ves,
                    iva_usd=nuevo_iva_usd,
                    iva_ves=nuevo_iva_ves,
                    total_usd=_redondear(nueva_base_usd + nuevo_iva_usd),
                    total_ves=_redondear(nueva_base_ves + nuevo_iva_ves),
                )
            )

        return lineas_ajustadas
