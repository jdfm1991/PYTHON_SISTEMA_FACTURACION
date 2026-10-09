"""Construcción del payload para el agente fiscal.

Convierte una FacturaVenta al JSON que el agente espera.
"""

from decimal import Decimal

from app.models import FacturaVenta


def construir_payload_factura(factura: FacturaVenta) -> dict:
    """Construye el JSON para enviar al agente fiscal.

    Args:
        factura: instancia de FacturaVenta (ya confirmada, con detalles y pagos).

    Returns:
        Diccionario con la estructura esperada por el agente.
    """
    # Cliente
    cliente = factura.cliente
    cliente_data = {
        "tipo_documento": cliente.tipo_documento,
        "numero_documento": cliente.numero_documento,
        "razon_social": cliente.razon_social,
        "direccion": cliente.direccion,
    }

    # Líneas
    lineas = []
    for detalle in factura.detalles:
        lineas.append({
            "codigo": detalle.codigo_producto,
            "descripcion": detalle.nombre_producto,
            "cantidad": str(detalle.cantidad),
            "precio_unitario_ves": str(detalle.precio_unitario_ves),
            "alicuota_iva": str(detalle.alicuota_iva_porcentaje),
        })

    # Pagos (solo los que fueron en VES)
    pagos = []
    for pago in factura.pagos:
        pagos.append({
            "forma_pago": pago.forma_pago,
            "monto_ves": str(pago.monto_ves),
        })

    return {
        "cliente": cliente_data,
        "lineas": lineas,
        "pagos": pagos,
    }