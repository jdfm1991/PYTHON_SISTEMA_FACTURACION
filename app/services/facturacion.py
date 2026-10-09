"""Servicio de facturación.

Orquesta la creación, edición y cálculo de facturas.
No hace commit(); el llamador decide cuándo confirmar.
"""

from datetime import date, timedelta, datetime
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app

from app.constants import (
    FORMAS_PAGO,
    TIPO_DEUDOR_CLIENTE,
    TIPO_DEUDOR_FIDUCIARIO,
    TIPO_VENTA_CREDITO_DIRECTO,
    TIPO_VENTA_CREDITO_FIDUCIARIO,
    TIPOS_VENTA,
    forma_pago_aplica_igtf,
)
from app.exceptions import (
    CreditoNoHabilitadoError,
    DominioError,
    FacturaSinLineasError,
    FiduciarioNoValidoError,
    LimiteCreditoExcedidoError,
    PagoInvalidoError,
    TipoVentaInvalidoError,
    FacturaNoEditableError,
    FacturaNoAnulableError,
    CxConPagosError,
)
from app.extensions import db
from app.models import (
    Cliente,
    CuentaPorCobrar,
    DetalleFacturaVenta,
    FacturaVenta,
    Fiduciario,
    PagoFacturaVenta,
    Producto,
    TasaCambio,
)
from app.services import inventario as inventario_service
from app.services import numeracion
from app.services.calculadora_factura import CalculadoraFactura, LineaCalculo

_PRECISION = Decimal("0.0001")


def _tasa_vigente() -> TasaCambio | None:
    """Devuelve la tasa vigente o None si no hay ninguna."""
    return db.session.scalar(
        db.select(TasaCambio)
        .filter(TasaCambio.fecha <= date.today())
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )


def crear_borrador(cliente_id: int, usuario_id: int | None = None) -> FacturaVenta:
    """Crea un borrador de factura de venta con cabecera vacía.

    Raises:
        DominioError: si no hay tasa vigente o el cliente no existe.
    """
    cliente = db.session.get(Cliente, cliente_id)
    if cliente is None:
        raise DominioError("Cliente no encontrado.")
    if not cliente.activo:
        raise DominioError("El cliente está inactivo.")

    tasa = _tasa_vigente()
    if tasa is None:
        raise DominioError(
            "No hay tasa de cambio vigente. Registre una tasa antes de facturar."
        )

    # Reintentar si colisiona el numero_interno
    numero = numeracion.generar_numero_interno_venta()
    existente = db.session.scalar(
        db.select(FacturaVenta).filter_by(numero_interno=numero)
    )
    if existente is not None:
        # Colisión (raro, por concurrencia). Intentar de nuevo.
        numero = numeracion.generar_numero_interno_venta()
        existente = db.session.scalar(
            db.select(FacturaVenta).filter_by(numero_interno=numero)
        )
    if existente is not None:
        raise DominioError(
            "No se pudo generar un número interno único. Intente de nuevo."
        )

    factura = FacturaVenta(
        numero_interno=numero,
        cliente_id=cliente_id,
        tasa_cambio_id=tasa.id,
        tasa_cambio_valor=tasa.tasa_bcv,
        modalidad="fiscal",
        estado="borrador",
        fecha_emision=date.today(),
    )
    db.session.add(factura)
    db.session.flush()
    return factura


def recalcular(factura: FacturaVenta) -> None:
    """Recalcula totales de la factura a partir de sus detalles.

    Actualiza los campos de totales en la factura (subtotal, iva, total)
    en USD y VES. No hace commit.
    """
    # Si no hay tasa vigente para el pago, usamos la que ya tiene la factura
    # (la tasa de la factura es un snapshot, no se recalcula).

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

    # Actualizar cada detalle con los valores recalculados
    for detalle, linea in zip(factura.detalles, resultado.lineas):
        detalle.subtotal_usd = linea.subtotal_usd
        detalle.subtotal_ves = linea.subtotal_ves
        detalle.descuento_monto_usd = (
            linea.descuento_aplicado_usd or detalle.descuento_monto_usd
        )
        detalle.descuento_monto_ves = (
            linea.descuento_aplicado_ves or detalle.descuento_monto_ves
        )
        detalle.base_imponible_usd = linea.base_imponible_usd
        detalle.base_imponible_ves = linea.base_imponible_ves
        detalle.iva_usd = linea.iva_usd
        detalle.iva_ves = linea.iva_ves
        detalle.total_usd = linea.total_usd
        detalle.total_ves = linea.total_ves

    # Actualizar totales de la factura
    factura.subtotal_usd = resultado.subtotal_usd
    factura.subtotal_ves = resultado.subtotal_ves
    factura.base_imponible_usd = resultado.base_imponible_usd
    factura.base_imponible_ves = resultado.base_imponible_ves
    factura.iva_usd = resultado.iva_usd
    factura.iva_ves = resultado.iva_ves
    factura.total_usd = resultado.total_usd
    factura.total_ves = resultado.total_ves

    db.session.flush()


def agregar_detalle(
    factura: FacturaVenta,
    producto_id: int,
    cantidad: Decimal = Decimal("1"),
) -> DetalleFacturaVenta:
    """Agrega un detalle al borrador con cantidad por defecto.

    Si el producto ya está en la factura, incrementa la cantidad.
    """
    if factura.estado != "borrador":
        raise FacturaNoEditableError(
            "Solo se pueden editar facturas en estado borrador."
        )

    producto = db.session.get(Producto, producto_id)
    if producto is None:
        raise DominioError("Producto no encontrado.")
    if not producto.activo:
        raise DominioError(f"El producto '{producto.codigo}' está inactivo.")

    # Si ya existe, incrementar cantidad
    for detalle in factura.detalles:
        if detalle.producto_id == producto_id:
            detalle.cantidad += cantidad
            recalcular(factura)
            return detalle

    # Si no existe, crear
    precio_unitario_ves = (producto.precio_usd * factura.tasa_cambio_valor).quantize(
        Decimal("0.0001")
    )

    detalle = DetalleFacturaVenta(
        factura_venta_id=factura.id,
        producto_id=producto.id,
        codigo_producto=producto.codigo,
        nombre_producto=producto.nombre,
        cantidad=cantidad,
        precio_unitario_usd=producto.precio_usd,
        precio_unitario_ves=precio_unitario_ves,
        alicuota_iva_id=producto.alicuota_iva_id,
        alicuota_iva_porcentaje=producto.alicuota_iva.porcentaje,
    )
    db.session.add(detalle)
    factura.detalles.append(detalle)  # para que recalcular lo vea
    recalcular(factura)
    return detalle


def _redondear(v: Decimal) -> Decimal:
    """Redondea a 4 decimales con ROUND_HALF_UP."""
    return v.quantize(_PRECISION, rounding=ROUND_HALF_UP)


def _saldo_actual_cliente(cliente_id: int) -> Decimal:
    """Suma de saldos pendientes del cliente en cuentas por cobrar propias.

    Excluye cuentas contra fiduciarios (esas no son deuda del cliente).
    """
    resultado = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(CuentaPorCobrar.saldo_usd), 0))
        .filter(CuentaPorCobrar.fiduciario_id.is_(None))
        .join(CuentaPorCobrar.factura)
        .filter(FacturaVenta.cliente_id == cliente_id)
        .filter(CuentaPorCobrar.estado.in_(["pendiente", "parcial", "vencida"]))
    )
    return Decimal(resultado or 0)


def _validar_credito_directo(factura: FacturaVenta) -> None:
    """Valida que el cliente pueda facturarse a crédito directo."""
    cliente = factura.cliente
    if not cliente.tiene_credito:
        raise CreditoNoHabilitadoError(cliente.razon_social)

    if cliente.limite_credito_usd is None:
        return  # sin límite definido

    saldo = _saldo_actual_cliente(cliente.id)
    if saldo + factura.total_usd > cliente.limite_credito_usd:
        raise LimiteCreditoExcedidoError(
            cliente_nombre=cliente.razon_social,
            saldo_actual=saldo,
            limite=cliente.limite_credito_usd,
            monto_nuevo=factura.total_usd,
        )


def _validar_fiduciario(fiduciario_id: int | None) -> Fiduciario:
    """Valida que el fiduciario exista y esté activo."""
    if fiduciario_id is None:
        raise FiduciarioNoValidoError(
            "Debe indicar un fiduciario para el crédito con fiduciario."
        )
    fiduciario = db.session.get(Fiduciario, fiduciario_id)
    if fiduciario is None or not fiduciario.activo:
        raise FiduciarioNoValidoError(
            "El fiduciario indicado no existe o está inactivo."
        )
    return fiduciario


def _validar_pago(pago: dict, tasa_cambio: Decimal) -> None:
    """Valida los datos básicos de un pago (antes de procesarlo)."""
    forma = pago.get("forma_pago")
    moneda = pago.get("moneda_pago")
    monto = pago.get("monto")

    if forma not in FORMAS_PAGO:
        raise PagoInvalidoError(f"Forma de pago '{forma}' no reconocida.")
    if moneda not in ("VES", "USD"):
        raise PagoInvalidoError(f"Moneda '{moneda}' no válida.")
    if monto is None or monto <= 0:
        raise PagoInvalidoError("El monto del pago debe ser mayor a cero.")


def confirmar_factura(
    factura: FacturaVenta,
    tipo_venta: str,
    pagos: list[dict],
    fiduciario_id: int | None = None,
) -> FacturaVenta:
    """Confirma una factura de venta en borrador.

    Args:
        factura: la factura en borrador.
        tipo_venta: "contado" | "credito_directo" | "credito_fiduciario".
        pagos: lista de dicts con forma_pago, moneda_pago, monto,
               referencia (opt), observaciones (opt), aplica_igtf (opt).
        fiduciario_id: id del fiduciario si tipo_venta="credito_fiduciario".

    Returns:
        La factura confirmada (flush, sin commit).

    Raises:
        DominioError y subclases: cualquier violación de reglas de negocio.
    """
    # ---------- 1) Validaciones previas ----------
    if factura.estado != "borrador":
        raise FacturaNoEditableError(
            f"La factura no está en estado borrador (estado actual: {factura.estado})."
        )

    if not factura.detalles:
        raise FacturaSinLineasError(
            "La factura no tiene líneas. Agregue al menos un producto."
        )

    if tipo_venta not in TIPOS_VENTA:
        raise TipoVentaInvalidoError(f"Tipo de venta '{tipo_venta}' no reconocido.")

    # Recalcular por si los totales no están actualizados
    recalcular(factura)

    # Validar según el tipo de venta
    fiduciario = None
    if tipo_venta == TIPO_VENTA_CREDITO_DIRECTO:
        _validar_credito_directo(factura)
    elif tipo_venta == TIPO_VENTA_CREDITO_FIDUCIARIO:
        fiduciario = _validar_fiduciario(fiduciario_id)

    # Validar los pagos estructuralmente
    for pago in pagos:
        _validar_pago(pago, factura.tasa_cambio_valor)

    # ---------- 2) Registrar pagos ----------
    total_pagado_usd = Decimal("0.0000")
    total_pagado_ves = Decimal("0.0000")
    igtf_total_usd = Decimal("0.0000")
    igtf_total_ves = Decimal("0.0000")

    for pago in pagos:
        pago_obj = _registrar_pago(factura, pago)
        total_pagado_usd += pago_obj.monto_usd
        total_pagado_ves += pago_obj.monto_ves
        igtf_total_usd += pago_obj.monto_igtf_usd
        igtf_total_ves += pago_obj.monto_igtf_ves

    total_pagado_usd = _redondear(total_pagado_usd)
    total_pagado_ves = _redondear(total_pagado_ves)
    igtf_total_usd = _redondear(igtf_total_usd)
    igtf_total_ves = _redondear(igtf_total_ves)

    # ---------- 3) Calcular vuelto ----------
    vuelto_usd = _redondear(max(Decimal("0"), total_pagado_usd - factura.total_usd))
    vuelto_ves = _redondear(max(Decimal("0"), total_pagado_ves - factura.total_ves))

    factura.vuelto_usd = vuelto_usd
    factura.vuelto_ves = vuelto_ves
    factura.igtf_total_usd = igtf_total_usd
    factura.igtf_total_ves = igtf_total_ves

    # ---------- 4) Registrar movimientos de inventario ----------
    for detalle in factura.detalles:
        inventario_service.registrar_salida(
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            referencia_tipo=inventario_service.REF_FACTURA_VENTA,
            referencia_id=factura.id,
        )

    # ---------- 5) Generar CuentaPorCobrar si aplica ----------
    saldo_pendiente_usd = _redondear(
        max(Decimal("0"), factura.total_usd - total_pagado_usd)
    )
    if saldo_pendiente_usd > 0:
        _crear_cuenta_por_cobrar(
            factura=factura,
            tipo_venta=tipo_venta,
            fiduciario=fiduciario,
            saldo_usd=saldo_pendiente_usd,
        )

    # ---------- 6) Actualizar estado y clasificación ----------
    factura.tipo_venta = tipo_venta
    factura.fiduciario_id = fiduciario.id if fiduciario else None

    if saldo_pendiente_usd > 0:
        factura.estado = "emitida"
    else:
        factura.estado = "pagada"

    db.session.flush()
    return factura


def _registrar_pago(factura: FacturaVenta, pago: dict) -> PagoFacturaVenta:
    """Registra un pago individual y calcula su IGTF.

    El IGTF se calcula sobre el monto pagado en USD si la forma
    lo requiere. Nunca sobre el total de la factura.
    """
    forma = pago["forma_pago"]
    moneda = pago["moneda_pago"]
    monto = _redondear(Decimal(pago["monto"]))
    tasa = factura.tasa_cambio_valor
    # Dentro de _registrar_pago:
    IGTF_PORCENTAJE = current_app.config["IGTF_PORCENTAJE"]

    # Resolver montos en ambas monedas
    if moneda == "USD":
        monto_usd = monto
        monto_ves = _redondear(monto * tasa)
    else:  # VES
        monto_ves = monto
        monto_usd = _redondear(monto / tasa)

    # Determinar si aplica IGTF
    aplica = pago.get("aplica_igtf")
    if aplica is None:
        aplica = forma_pago_aplica_igtf(forma, moneda)

    if aplica:
        igtf_usd = _redondear(monto_usd * IGTF_PORCENTAJE / Decimal("100"))
        igtf_ves = _redondear(igtf_usd * tasa)
    else:
        igtf_usd = Decimal("0.0000")
        igtf_ves = Decimal("0.0000")

    pago_obj = PagoFacturaVenta(
        factura_venta_id=factura.id,
        forma_pago=forma,
        moneda_pago=moneda,
        monto_usd=monto_usd,
        monto_ves=monto_ves,
        tasa_cambio_valor=tasa,
        aplica_igtf=aplica,
        monto_igtf_usd=igtf_usd,
        monto_igtf_ves=igtf_ves,
        referencia=(pago.get("referencia") or "").strip() or None,
        observaciones=(pago.get("observaciones") or "").strip() or None,
        fecha_pago=date.today(),
    )
    db.session.add(pago_obj)
    db.session.flush()
    return pago_obj


def _crear_cuenta_por_cobrar(
    factura: FacturaVenta,
    tipo_venta: str,
    fiduciario: Fiduciario | None,
    saldo_usd: Decimal,
) -> CuentaPorCobrar:
    """Crea la CuentaPorCobrar para la factura con saldo pendiente.

    - monto_total_usd: total de la factura (cuánto se debía).
    - saldo_usd: saldo pendiente (total - pagos).
    """
    saldo_ves = _redondear(saldo_usd * factura.tasa_cambio_valor)

    if tipo_venta == TIPO_VENTA_CREDITO_FIDUCIARIO:
        tipo_deudor = TIPO_DEUDOR_FIDUCIARIO
        fiduciario_id = fiduciario.id if fiduciario else None
        fecha_vencimiento = None
    else:
        tipo_deudor = TIPO_DEUDOR_CLIENTE
        fiduciario_id = None
        dias = factura.cliente.dias_credito
        fecha_vencimiento = (
            factura.fecha_emision + timedelta(days=dias) if dias else None
        )

    cuenta = CuentaPorCobrar(
        factura_venta_id=factura.id,
        tipo_deudor=tipo_deudor,
        fiduciario_id=fiduciario_id,
        monto_total_usd=factura.total_usd,  # ← total factura
        monto_total_ves=factura.total_ves,  # ← total factura
        saldo_usd=saldo_usd,  # ← saldo pendiente
        saldo_ves=saldo_ves,
        estado="pendiente",
        fecha_vencimiento=fecha_vencimiento,
    )
    db.session.add(cuenta)
    db.session.flush()
    return cuenta

def anular_factura(
    factura: FacturaVenta,
    motivo: str,
    usuario_id: int,
) -> FacturaVenta:
    """Anula una factura de venta emitida.

    Revierte:
    - Inventario: crea movimientos de entrada por cada detalle.
    - CuentaPorCobrar: si existe, se marca como 'anulada' con saldo 0.
    - Estado de la factura: pasa a 'anulada'.

    Args:
        factura: la factura a anular.
        motivo: razón de la anulación (mínimo 10 caracteres).
        usuario_id: id del usuario que anula.

    Returns:
        La factura anulada (flush, sin commit).

    Raises:
        FacturaNoAnulableError: si el estado no es 'emitida'.
        CxConPagosError: si la CxC tiene pagos parciales.
        ValueError: si el motivo es demasiado corto.
    """
    # Validaciones
    if factura.estado != "emitida":
        raise FacturaNoAnulableError(
            f"Solo se pueden anular facturas emitidas. "
            f"Estado actual: {factura.estado}."
        )

    motivo_limpio = (motivo or "").strip()
    if len(motivo_limpio) < 10:
        raise DominioError("El motivo de anulación debe tener al menos 10 caracteres.")

    # Validar CxC sin pagos parciales
    cxc = factura.cuenta_por_cobrar
    if cxc is not None:
        if cxc.saldo_usd < cxc.monto_total_usd:
            raise CxConPagosError(
                "La cuenta por cobrar tiene pagos parciales. "
                "Revierta primero los pagos antes de anular."
            )

    # 1) Reversar inventario: movimiento de entrada por cada detalle
    for detalle in factura.detalles:
        inventario_service.registrar_entrada(
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            referencia_tipo=inventario_service.REF_FACTURA_VENTA,
            referencia_id=factura.id,
            motivo=f"Anulación de {factura.numero_interno}",
            permitir_inactivo=True,
        )

    # 2) Marcar la CxC como anulada
    if cxc is not None:
        cxc.estado = "anulada"
        cxc.saldo_usd = Decimal("0.0000")
        cxc.saldo_ves = Decimal("0.0000")

    # 3) Cambiar el estado de la factura y registrar auditoría
    factura.estado = "anulada"
    factura.motivo_anulacion = motivo_limpio
    factura.fecha_anulacion = datetime.now()
    factura.anulada_por_id = usuario_id

    db.session.flush()
    return factura
