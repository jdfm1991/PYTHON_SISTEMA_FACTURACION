"""Servicio de numeración interna de facturas.

Genera números internos únicos con formato:
    WEB-V-2026-00001   (venta)
    WEB-C-2026-00001   (compra)

El número fiscal definitivo lo asigna la impresora fiscal (FASE 5).
"""

from datetime import date

from sqlalchemy import func

from app.extensions import db
from app.models import FacturaCompra, FacturaVenta


def _siguiente_correlativo(modelo, anio: int, prefijo: str) -> int:
    """Devuelve el siguiente correlativo del año para el modelo dado."""
    patron = f"{prefijo}-%"
    ultimo = db.session.scalar(
        db.select(func.max(modelo.numero_interno)).filter(
            modelo.numero_interno.like(patron)
        )
    )
    if ultimo is None:
        return 1
    try:
        return int(ultimo.split("-")[-1]) + 1
    except (ValueError, IndexError):
        return 1


def generar_numero_interno_venta() -> str:
    """Genera un número interno para una factura de venta."""
    anio = date.today().year
    prefijo = f"WEB-V-{anio}"
    correlativo = _siguiente_correlativo(FacturaVenta, anio, prefijo)
    return f"{prefijo}-{correlativo:05d}"


def generar_numero_interno_compra() -> str:
    """Genera un número interno para una factura de compra."""
    anio = date.today().year
    prefijo = f"WEB-C-{anio}"
    correlativo = _siguiente_correlativo(FacturaCompra, anio, prefijo)
    return f"{prefijo}-{correlativo:05d}"