"""Servicio de facturación de compras.

Análogo a `facturacion.py` pero para compras. Menos complejo (sin
fiduciario, sin modalidad fiscal, sin IGTF separado).
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.models import CuentaPorPagar

from app.constants import FORMAS_PAGO
from app.exceptions import (
    DominioError,
    FacturaNoEditableError,
    FacturaSinLineasError,
    PagoExcedeTotalError,
    PagoInvalidoError,
    CxConPagosError,
    FacturaNoAnulableError,
    StockNegativoError,
)
from app.extensions import db
from app.models import (
    CuentaPorPagar,
    DetalleFacturaCompra,
    FacturaCompra,
    PagoFacturaCompra,
    Producto,
    Proveedor,
    TasaCambio,
)
from app.services import inventario as inventario_service
from app.services import numeracion
from app.services.calculadora_factura import CalculadoraFactura, LineaCalculo


def _tasa_vigente() -> TasaCambio | None:
    """Devuelve la tasa vigente o None si no hay ninguna."""
    return db.session.scalar(
        db.select(TasaCambio)
        .filter(TasaCambio.fecha <= date.today())
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )


def crear_borrador(proveedor_id: int) -> FacturaCompra:
    """Crea un borrador de factura de compra.

    Raises:
        DominioError: si no hay tasa vigente o el proveedor no existe.
    """
    proveedor = db.session.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise DominioError("Proveedor no encontrado.")
    if not proveedor.activo:
        raise DominioError("El proveedor está inactivo.")

    tasa = _tasa_vigente()
    if tasa is None:
        raise DominioError(
            "No hay tasa de cambio vigente. Registre una tasa antes de continuar."
        )

    # Reintentar si colisiona el numero_interno
    for _ in range(3):
        numero = numeracion.generar_numero_interno_compra()
        existente = db.session.scalar(
            db.select(FacturaCompra).filter_by(numero_interno=numero)
        )
        if existente is None:
            break
    else:
        raise DominioError(
            "No se pudo generar un número interno único. Intente de nuevo."
        )

    factura = FacturaCompra(
        numero_interno=numero,
        proveedor_id=proveedor_id,
        tasa_cambio_id=tasa.id,
        tasa_cambio_valor=tasa.tasa_bcv,
        estado="borrador",
        fecha_emision=date.today(),
    )
    db.session.add(factura)
    db.session.flush()
    return factura


"""Servicio de facturación de compras."""

from datetime import date
from decimal import Decimal

from app.exceptions import DominioError
from app.extensions import db
from app.models import (
    DetalleFacturaCompra,
    FacturaCompra,
    Producto,
    Proveedor,
    TasaCambio,
)
from app.services import numeracion
from app.services.calculadora_factura import CalculadoraFactura, LineaCalculo


def _tasa_vigente() -> TasaCambio | None:
    """Devuelve la tasa vigente o None si no hay ninguna."""
    return db.session.scalar(
        db.select(TasaCambio)
        .filter(TasaCambio.fecha <= date.today())
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )


def crear_borrador(proveedor_id: int) -> FacturaCompra:
    """Crea un borrador de factura de compra."""
    proveedor = db.session.get(Proveedor, proveedor_id)
    if proveedor is None:
        raise DominioError("Proveedor no encontrado.")
    if not proveedor.activo:
        raise DominioError("El proveedor está inactivo.")

    tasa = _tasa_vigente()
    if tasa is None:
        raise DominioError(
            "No hay tasa de cambio vigente. Registre una tasa antes de continuar."
        )

    for _ in range(3):
        numero = numeracion.generar_numero_interno_compra()
        existente = db.session.scalar(
            db.select(FacturaCompra).filter_by(numero_interno=numero)
        )
        if existente is None:
            break
    else:
        raise DominioError(
            "No se pudo generar un número interno único. Intente de nuevo."
        )

    factura = FacturaCompra(
        numero_interno=numero,
        proveedor_id=proveedor_id,
        tasa_cambio_id=tasa.id,
        tasa_cambio_valor=tasa.tasa_bcv,
        estado="borrador",
        fecha_emision=date.today(),
    )
    db.session.add(factura)
    db.session.flush()
    return factura


def agregar_detalle(
    factura: FacturaCompra,
    producto_id: int,
    cantidad: Decimal = Decimal("1"),
    precio_usd: Decimal | None = None,
) -> DetalleFacturaCompra:
    """Agrega un producto al borrador de compra.

    Args:
        factura: la factura en borrador.
        producto_id: id del producto.
        cantidad: cantidad a comprar.
        precio_usd: precio unitario en USD. Si no se especifica,
            se usa el precio del catálogo.

    Si el producto ya está en la factura, incrementa la cantidad
    (y actualiza el precio si se especifica uno nuevo).
    """
    if factura.estado != "borrador":
        raise DominioError("Solo se pueden editar facturas en borrador.")

    producto = db.session.get(Producto, producto_id)
    if producto is None:
        raise DominioError("Producto no encontrado.")

    # En compras NO validamos que el producto esté activo.
    # Puedes comprar a un producto descontinuado para liquidar stock.

    precio_final = precio_usd if precio_usd is not None else producto.precio_usd
    if precio_final <= 0:
        raise DominioError("El precio debe ser mayor que cero.")

    # Si ya existe, incrementar cantidad y actualizar precio
    for detalle in factura.detalles:
        if detalle.producto_id == producto_id:
            detalle.cantidad += cantidad
            if precio_usd is not None:
                detalle.precio_unitario_usd = precio_usd
                detalle.precio_unitario_ves = (
                    precio_usd * factura.tasa_cambio_valor
                ).quantize(Decimal("0.0001"))
            recalcular(factura)
            return detalle

    # Si no existe, crear
    precio_unitario_ves = (precio_final * factura.tasa_cambio_valor).quantize(
        Decimal("0.0001")
    )

    detalle = DetalleFacturaCompra(
        factura_compra_id=factura.id,
        producto_id=producto.id,
        codigo_producto=producto.codigo,
        nombre_producto=producto.nombre,
        cantidad=cantidad,
        precio_unitario_usd=precio_final,
        precio_unitario_ves=precio_unitario_ves,
        alicuota_iva_id=producto.alicuota_iva_id,
        alicuota_iva_porcentaje=producto.alicuota_iva.porcentaje,
    )
    db.session.add(detalle)
    factura.detalles.append(detalle)
    recalcular(factura)
    return detalle


def recalcular(factura: FacturaCompra) -> None:
    """Recalcula totales de la compra a partir de sus detalles.

    IMPORTANTE: los campos descuento_global_* de la factura
    representan la CONFIGURACIÓN del usuario. NO se sobreescriben
    con los valores calculados.
    """
    lineas: list[LineaCalculo] = []
    for detalle in factura.detalles:
        lineas.append(
            LineaCalculo(
                producto_id=detalle.producto_id,
                cantidad=detalle.cantidad,
                precio_unitario_usd=detalle.precio_unitario_usd,
                precio_unitario_ves=detalle.precio_unitario_ves,
                alicuota_porcentaje=detalle.alicuota_iva_porcentaje,
                descuento_porcentaje=detalle.descuento_porcentaje,
                descuento_monto_usd=detalle.descuento_monto_usd,
                descuento_monto_ves=detalle.descuento_monto_ves,
            )
        )

    calculadora = CalculadoraFactura()
    resultado = calculadora.calcular(
        lineas,
        descuento_global_porcentaje=factura.descuento_global_porcentaje,
        descuento_global_monto_usd=factura.descuento_global_monto_usd,
        descuento_global_monto_ves=factura.descuento_global_monto_ves,
    )

    for detalle, linea in zip(factura.detalles, resultado.lineas):
        detalle.subtotal_usd = linea.subtotal_usd
        detalle.subtotal_ves = linea.subtotal_ves
        detalle.base_imponible_usd = linea.base_imponible_usd
        detalle.base_imponible_ves = linea.base_imponible_ves
        detalle.iva_usd = linea.iva_usd
        detalle.iva_ves = linea.iva_ves
        detalle.total_usd = linea.total_usd
        detalle.total_ves = linea.total_ves

    factura.subtotal_usd = resultado.subtotal_usd
    factura.subtotal_ves = resultado.subtotal_ves
    factura.base_imponible_usd = resultado.base_imponible_usd
    factura.base_imponible_ves = resultado.base_imponible_ves
    factura.iva_usd = resultado.iva_usd
    factura.iva_ves = resultado.iva_ves
    factura.total_usd = resultado.total_usd
    factura.total_ves = resultado.total_ves

    db.session.flush()


def confirmar_compra(
    factura: FacturaCompra,
    pagos: list[dict],
) -> FacturaCompra:
    """Confirma una factura de compra en borrador.

    Args:
        factura: la factura en borrador.
        pagos: lista de dicts con:
            - forma_pago: str (clave de FORMAS_PAGO)
            - moneda_pago: "VES" | "USD"
            - monto: Decimal (monto total, incluye IGTF si aplica)
            - referencia: str | None
            - observaciones: str | None

    Returns:
        La factura confirmada (flush, sin commit).

    Raises:
        FacturaNoEditableError: si no está en borrador.
        FacturaSinLineasError: si no tiene líneas.
        PagoInvalidoError: si un pago tiene datos inválidos.
        PagoExcedeTotalError: si la suma de pagos excede el total.
    """
    # ---------- 1) Validaciones previas ----------
    if factura.estado != "borrador":
        raise FacturaNoEditableError(
            f"La factura no está en estado borrador "
            f"(estado actual: {factura.estado})."
        )

    if not factura.detalles:
        raise FacturaSinLineasError(
            "La factura no tiene líneas. Agregue al menos un producto."
        )

    # Recalcular por si los totales no están actualizados
    recalcular(factura)

    # Validar pagos
    for pago in pagos:
        _validar_pago_compra(pago)

    # ---------- 2) Registrar pagos ----------
    total_pagado_usd = Decimal("0.0000")
    total_pagado_ves = Decimal("0.0000")

    for pago in pagos:
        pago_obj = _registrar_pago_compra(factura, pago)
        total_pagado_usd += pago_obj.monto_usd
        total_pagado_ves += pago_obj.monto_ves

    total_pagado_usd = _redondear(total_pagado_usd)
    total_pagado_ves = _redondear(total_pagado_ves)

    # Validar que no exceda el total
    if total_pagado_usd > factura.total_usd:
        raise PagoExcedeTotalError(
            total_pagado=total_pagado_usd,
            total_factura=factura.total_usd,
        )

    # ---------- 3) Registrar movimientos de inventario (entrada) ----------
    for detalle in factura.detalles:
        inventario_service.registrar_entrada(
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            referencia_tipo=inventario_service.REF_FACTURA_COMPRA,
            referencia_id=factura.id,
            permitir_inactivo=True,  # compras permiten producto inactivo
        )

    # ---------- 4) Generar CuentaPorPagar si aplica ----------
    saldo_pendiente_usd = _redondear(
        max(Decimal("0"), factura.total_usd - total_pagado_usd)
    )
    if saldo_pendiente_usd > 0:
        _crear_cuenta_por_pagar(factura, saldo_pendiente_usd)

    # ---------- 5) Actualizar estado ----------
    if saldo_pendiente_usd > 0:
        factura.estado = "emitida"
    else:
        factura.estado = "pagada"

    db.session.flush()
    return factura


_PRECISION = Decimal("0.0001")


def _redondear(v: Decimal) -> Decimal:
    """Redondea a 4 decimales con ROUND_HALF_UP."""
    from decimal import ROUND_HALF_UP

    return v.quantize(_PRECISION, rounding=ROUND_HALF_UP)


def _validar_pago_compra(pago: dict) -> None:
    """Valida los datos básicos de un pago de compra."""
    forma = pago.get("forma_pago")
    moneda = pago.get("moneda_pago")
    monto = pago.get("monto")

    if forma not in FORMAS_PAGO:
        raise PagoInvalidoError(f"Forma de pago '{forma}' no reconocida.")
    if moneda not in ("VES", "USD"):
        raise PagoInvalidoError(f"Moneda '{moneda}' no válida.")
    if monto is None or monto <= 0:
        raise PagoInvalidoError("El monto del pago debe ser mayor a cero.")


def _registrar_pago_compra(factura: FacturaCompra, pago: dict) -> PagoFacturaCompra:
    """Registra un pago individual de compra.

    NO calcula IGTF. El monto ingresado es el total pagado al proveedor,
    que puede o no incluir IGTF según la negociación.
    """
    forma = pago["forma_pago"]
    moneda = pago["moneda_pago"]
    monto = _redondear(Decimal(pago["monto"]))
    tasa = factura.tasa_cambio_valor

    if moneda == "USD":
        monto_usd = monto
        monto_ves = _redondear(monto * tasa)
    else:  # VES
        monto_ves = monto
        monto_usd = _redondear(monto / tasa)

    pago_obj = PagoFacturaCompra(
        factura_compra_id=factura.id,
        forma_pago=forma,
        moneda_pago=moneda,
        monto_usd=monto_usd,
        monto_ves=monto_ves,
        tasa_cambio_valor=tasa,
        referencia=(pago.get("referencia") or "").strip() or None,
        observaciones=(pago.get("observaciones") or "").strip() or None,
        fecha_pago=date.today(),
    )
    db.session.add(pago_obj)
    db.session.flush()
    return pago_obj


def _crear_cuenta_por_pagar(
    factura: FacturaCompra,
    saldo_usd: Decimal,
) -> CuentaPorPagar:
    """Crea la CuentaPorPagar para la factura con saldo pendiente.

    - monto_total_usd: total de la factura (cuánto se debía).
    - saldo_usd: saldo pendiente (total - pagos).
    """
    saldo_ves = _redondear(saldo_usd * factura.tasa_cambio_valor)

    cuenta = CuentaPorPagar(
        factura_compra_id=factura.id,
        tipo_acreedor="proveedor",
        monto_total_usd=factura.total_usd,  # ← total factura
        monto_total_ves=factura.total_ves,  # ← total factura
        saldo_usd=saldo_usd,  # ← saldo pendiente
        saldo_ves=saldo_ves,
        estado="pendiente",
        fecha_vencimiento=None,
    )
    db.session.add(cuenta)
    db.session.flush()
    return cuenta


def anular_compra(
    factura: FacturaCompra,
    motivo: str,
    usuario_id: int,
) -> FacturaCompra:
    """Anula una factura de compra emitida.

    Revierte:
    - Inventario: crea movimientos de salida por cada detalle.
      Valida que el stock resultante no sea negativo.
    - CuentaPorPagar: si existe, se marca como 'anulada' con saldo 0.
    - Estado de la factura: pasa a 'anulada'.

    Args:
        factura: la factura a anular.
        motivo: razón de la anulación (mínimo 10 caracteres).
        usuario_id: id del usuario que anula.

    Returns:
        La factura anulada (flush, sin commit).

    Raises:
        FacturaNoAnulableError: si el estado no es 'emitida'.
        CxConPagosError: si la CxP tiene pagos parciales.
        StockNegativoError: si el stock resultante sería negativo.
        DominioError: si el motivo es demasiado corto.
    """
    # Validaciones
    if factura.estado != "emitida":
        raise FacturaNoAnulableError(
            f"Solo se pueden anular compras emitidas. "
            f"Estado actual: {factura.estado}."
        )

    motivo_limpio = (motivo or "").strip()
    if len(motivo_limpio) < 10:
        raise DominioError("El motivo de anulación debe tener al menos 10 caracteres.")

    # Validar CxP sin pagos parciales
    cxp = factura.cuenta_por_pagar
    if cxp is not None:
        if cxp.saldo_usd < cxp.monto_total_usd:
            raise CxConPagosError(
                "La cuenta por pagar tiene pagos parciales. "
                "Revierta primero los pagos antes de anular."
            )

    # Validar que el stock resultante no sea negativo (antes de tocar nada)
    for detalle in factura.detalles:
        producto = db.session.get(Producto, detalle.producto_id)
        if producto is None:
            raise DominioError(f"Producto {detalle.codigo_producto} no encontrado.")
        stock_resultante = producto.stock_actual - detalle.cantidad
        if stock_resultante < 0:
            raise StockNegativoError(
                producto_codigo=producto.codigo,
                stock_actual=producto.stock_actual,
                a_descontar=detalle.cantidad,
                resultante=stock_resultante,
            )

    # 1) Reversar inventario: movimiento de salida por cada detalle
    for detalle in factura.detalles:
        inventario_service.registrar_salida(
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            referencia_tipo=inventario_service.REF_FACTURA_COMPRA,
            referencia_id=factura.id,
            motivo=f"Anulación de {factura.numero_interno}",
        )

    # 2) Marcar la CxP como anulada
    if cxp is not None:
        cxp.estado = "anulada"
        cxp.saldo_usd = Decimal("0.0000")
        cxp.saldo_ves = Decimal("0.0000")

    # 3) Cambiar estado y registrar auditoría
    factura.estado = "anulada"
    factura.motivo_anulacion = motivo_limpio
    factura.fecha_anulacion = datetime.now()
    factura.anulada_por_id = usuario_id

    db.session.flush()
    return factura
