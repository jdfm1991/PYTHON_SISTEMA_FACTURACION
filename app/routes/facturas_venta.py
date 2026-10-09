from datetime import date
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.exceptions import DominioError
from app.extensions import db
from app.models import Cliente, FacturaVenta, Producto
from app.security.decorators import requiere_permiso
from app.services import facturacion
from app.forms.factura_venta import CabeceraFacturaForm, DescuentoGlobalForm
from app.services.fiscal_client import EstadoImpresion, fiscal_client

from app.constants import (
    TIPO_VENTA_CONTADO,
    TIPO_VENTA_CREDITO_DIRECTO,
    TIPO_VENTA_CREDITO_FIDUCIARIO,
    tipo_venta_choices,
)
from app.models import Fiduciario
from app.services.fiscal_client import fiscal_client
from app.services.fiscal_payload import construir_payload_factura

facturas_venta_bp = Blueprint("facturas_venta", __name__, url_prefix="/facturas-venta")

PER_PAGE = 20


# --- Listado ---
@facturas_venta_bp.route("/")
@requiere_permiso("facturas_venta.ver")
def listar():
    """Listado de facturas de venta."""
    estado = request.args.get("estado", "").strip() or None
    buscar = request.args.get("q", "").strip()

    query = db.select(FacturaVenta)
    if estado:
        query = query.filter_by(estado=estado)
    if buscar:
        patron = f"%{buscar}%"
        query = query.join(Cliente).filter(
            db.or_(
                FacturaVenta.numero_interno.ilike(patron),
                FacturaVenta.numero_fiscal.ilike(patron),
                Cliente.razon_social.ilike(patron),
            )
        )
    query = query.order_by(FacturaVenta.fecha_creacion.desc())

    paginacion = db.paginate(
        query,
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )

    contexto = {
        "paginacion": paginacion,
        "estado": estado,
        "buscar": buscar,
    }

    if request.headers.get("HX-Request") == "true":
        return render_template("facturas_venta/_tabla.html", **contexto)
    return render_template("facturas_venta/listar.html", **contexto)


@facturas_venta_bp.route("/<int:factura_id>/detalle")
@requiere_permiso("facturas_venta.ver")
def detalle(factura_id: int):
    """Vista de detalle (solo lectura) de una factura."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    return render_template(
        "facturas_venta/detalle.html",
        factura=factura,
    )


# --- Crear borrador ---
@facturas_venta_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("facturas_venta.crear")
def crear():
    """Crea un borrador y redirige a su edición.

    GET: muestra formulario para elegir cliente.
    POST: crea borrador con el cliente elegido.
    """
    if request.method == "POST":
        cliente_id = request.form.get("cliente_id", type=int)
        if not cliente_id:
            flash("Debe seleccionar un cliente.", "error")
            return redirect(url_for("facturas_venta.crear"))

        try:
            factura = facturacion.crear_borrador(cliente_id)
            db.session.commit()
            flash(f"Borrador {factura.numero_interno} creado.", "success")
            return redirect(url_for("facturas_venta.editar", factura_id=factura.id))
        except DominioError as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("facturas_venta.crear"))

    # GET: mostrar formulario
    clientes = db.session.scalars(
        db.select(Cliente).filter_by(activo=True).order_by(Cliente.razon_social)
    ).all()
    return render_template("facturas_venta/crear.html", clientes=clientes)


# --- Editar borrador ---
@facturas_venta_bp.route("/<int:factura_id>/editar")
@requiere_permiso("facturas_venta.ver")
def editar(factura_id: int):
    """Página de edición del borrador."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "borrador":
        flash("Solo se pueden editar facturas en borrador.", "warning")
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    # Construir el form de cabecera con las choices cargadas
    form = CabeceraFacturaForm(obj=factura)
    form.cliente_id.choices = [
        (c.id, f"{c.tipo_documento}-{c.numero_documento} — {c.razon_social}")
        for c in db.session.scalars(
            db.select(Cliente).filter_by(activo=True).order_by(Cliente.razon_social)
        )
    ]

    return render_template(
        "facturas_venta/editar.html",
        factura=factura,
        form=form,
    )


# --- Mutaciones sobre el borrador ---
def _get_borrador(factura_id: int) -> FacturaVenta:
    """Helper: obtiene un borrador o lanza 404."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)
    if factura.estado != "borrador":
        abort(400, "La factura no está en estado editable.")
    return factura


def _render_fragmento(factura, errores_descuento=None):
    """Renderiza el fragmento de detalles + totales para HTMX."""
    return render_template(
        "facturas_venta/_fragmento_actualizable.html",
        factura=factura,
        errores_descuento=errores_descuento or {},
    )


@facturas_venta_bp.route("/<int:factura_id>/detalles", methods=["POST"])
@requiere_permiso("facturas_venta.crear")
def agregar_detalle(factura_id: int):
    """Agrega un producto al borrador."""
    factura = _get_borrador(factura_id)
    producto_id = request.form.get("producto_id", type=int)
    if not producto_id:
        return "Producto inválido", 400

    try:
        facturacion.agregar_detalle(factura, producto_id)
        db.session.commit()
    except DominioError as e:
        db.session.rollback()
        return f'<div class="bg-red-100 text-red-800 p-3 rounded">{e}</div>', 200

    return _render_fragmento(factura)


@facturas_venta_bp.route(
    "/<int:factura_id>/detalles/<int:detalle_id>/cantidad", methods=["POST"]
)
@requiere_permiso("facturas_venta.crear")
def cambiar_cantidad(factura_id: int, detalle_id: int):
    """Cambia la cantidad de un detalle."""
    factura = _get_borrador(factura_id)

    detalle = next((d for d in factura.detalles if d.id == detalle_id), None)
    if detalle is None:
        abort(404)

    try:
        nueva = Decimal(request.form.get("cantidad", "1"))
        if nueva <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
    except (InvalidOperation, ValueError) as e:
        return f'<div class="bg-red-100 text-red-800 p-3 rounded">{e}</div>', 200

    detalle.cantidad = nueva
    facturacion.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_venta_bp.route(
    "/<int:factura_id>/detalles/<int:detalle_id>/eliminar", methods=["POST"]
)
@requiere_permiso("facturas_venta.crear")
def eliminar_detalle(factura_id: int, detalle_id: int):
    """Elimina un detalle del borrador."""
    factura = _get_borrador(factura_id)

    detalle = next((d for d in factura.detalles if d.id == detalle_id), None)
    if detalle is None:
        abort(404)

    db.session.delete(detalle)
    db.session.flush()
    # Refrescar factura para recalcular
    db.session.refresh(factura)
    facturacion.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_venta_bp.route("/<int:factura_id>/descuento-global", methods=["POST"])
@requiere_permiso("facturas_venta.crear")
def descuento_global(factura_id: int):
    """Aplica o quita el descuento global del borrador."""
    factura = _get_borrador(factura_id)

    accion = request.form.get("accion", "aplicar")

    if accion == "quitar":
        factura.descuento_global_porcentaje = None
        factura.descuento_global_monto_usd = None
        factura.descuento_global_monto_ves = None
        facturacion.recalcular(factura)
        db.session.commit()
        return _render_fragmento(factura)

    form = DescuentoGlobalForm()
    if not form.validate_on_submit():
        # Devolver el fragmento con errores en el descuento
        return _render_fragmento(factura, errores_descuento=form.errors)

    tipo = form.tipo.data
    valor = form.valor.data

    if tipo == "porcentaje":
        if valor > 100:
            return _render_fragmento(
                factura,
                errores_descuento={"valor": ["El porcentaje no puede exceder 100."]},
            )
        factura.descuento_global_porcentaje = valor
        factura.descuento_global_monto_usd = None
        factura.descuento_global_monto_ves = None
    elif tipo == "monto_usd":
        factura.descuento_global_porcentaje = None
        factura.descuento_global_monto_usd = valor
        factura.descuento_global_monto_ves = (
            valor * factura.tasa_cambio_valor
        ).quantize(Decimal("0.0001"))

    facturacion.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_venta_bp.route("/<int:factura_id>/cabecera", methods=["POST"])
@requiere_permiso("facturas_venta.crear")
def editar_cabecera(factura_id: int):
    """Actualiza la cabecera del borrador."""
    factura = _get_borrador(factura_id)

    form = CabeceraFacturaForm(obj=factura)
    form.cliente_id.choices = [
        (c.id, f"{c.tipo_documento}-{c.numero_documento} — {c.razon_social}")
        for c in db.session.scalars(
            db.select(Cliente).filter_by(activo=True).order_by(Cliente.razon_social)
        )
    ]

    if form.validate_on_submit():
        if form.fecha_emision.data > date.today():
            form.fecha_emision.errors.append("La fecha de emisión no puede ser futura.")
        else:
            factura.cliente_id = form.cliente_id.data
            factura.fecha_emision = form.fecha_emision.data
            factura.modalidad = form.modalidad.data
            factura.observaciones = (form.observaciones.data or "").strip() or None
            db.session.commit()
            # Refrescar con datos actualizados
            form = CabeceraFacturaForm(obj=factura)
            form.cliente_id.choices = [
                (c.id, f"{c.tipo_documento}-{c.numero_documento} — {c.razon_social}")
                for c in db.session.scalars(
                    db.select(Cliente)
                    .filter_by(activo=True)
                    .order_by(Cliente.razon_social)
                )
            ]

    return render_template(
        "facturas_venta/_cabecera_editable.html",
        factura=factura,
        form=form,
    )


@facturas_venta_bp.route("/<int:factura_id>/cancelar", methods=["POST"])
@requiere_permiso("facturas_venta.crear")
def cancelar(factura_id: int):
    """Cancela y elimina un borrador."""
    factura = _get_borrador(factura_id)
    numero = factura.numero_interno
    db.session.delete(factura)
    db.session.commit()
    flash(f"Borrador {numero} cancelado.", "info")
    return redirect(url_for("facturas_venta.listar"))


# --- Búsqueda de productos (HTMX) ---
@facturas_venta_bp.route("/buscar-productos")
@requiere_permiso("facturas_venta.crear")
def buscar_productos():
    """Búsqueda de productos para el dropdown."""
    q = request.args.get("q", "").strip()
    factura_id = request.args.get("factura_id", type=int)
    if len(q) < 2 or not factura_id:
        return "", 204

    patron = f"%{q}%"
    productos = db.session.scalars(
        db.select(Producto)
        .filter(Producto.activo.is_(True))
        .filter(
            db.or_(
                Producto.codigo.ilike(patron),
                Producto.nombre.ilike(patron),
            )
        )
        .order_by(Producto.codigo)
        .limit(10)
    ).all()

    return render_template(
        "facturas_venta/_resultados_busqueda.html",
        productos=productos,
        factura_id=factura_id,  # ← ESTA LÍNEA
    )


import json
from flask import current_app

from app.constants import FORMAS_PAGO


@facturas_venta_bp.route("/<int:factura_id>/confirmar", methods=["GET"])
@requiere_permiso("facturas_venta.crear")
def confirmar_get(factura_id: int):
    """Pantalla de confirmación de factura."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "borrador":
        flash("Solo se pueden confirmar facturas en borrador.", "warning")
        return redirect(url_for("facturas_venta.listar"))

    if not factura.detalles:
        flash(
            "La factura no tiene productos. Agregue al menos uno antes de confirmar.",
            "warning",
        )
        return redirect(url_for("facturas_venta.editar", factura_id=factura.id))

    # Catálogos para los selectores
    fiduciarios = db.session.scalars(
        db.select(Fiduciario).filter_by(activo=True).order_by(Fiduciario.nombre)
    ).all()

    # Datos serializables para el JS
    formas_pago_json = [
        {
            "valor": k,
            "nombre": v["nombre"],
            "moneda": v["moneda"],
            "aplica_igtf": v["aplica_igtf"],
        }
        for k, v in FORMAS_PAGO.items()
    ]

    return render_template(
        "facturas_venta/confirmar.html",
        factura=factura,
        fiduciarios=fiduciarios,
        tipos_venta=tipo_venta_choices(),
        formas_pago=formas_pago_json,
        formas_pago_json=json.dumps(formas_pago_json),
        igtf_porcentaje=str(current_app.config["IGTF_PORCENTAJE"]),
        total_usd_str=str(factura.total_usd),
        total_ves_str=str(factura.total_ves),
    )


from app.services.fiscal_client import fiscal_client
from app.services.fiscal_payload import construir_payload_factura


@facturas_venta_bp.route("/<int:factura_id>/confirmar", methods=["POST"])
@requiere_permiso("facturas_venta.crear")
def confirmar_post(factura_id: int):
    """Procesa la confirmación de la factura."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    tipo_venta = request.form.get("tipo_venta", "").strip()
    fiduciario_id = request.form.get("fiduciario_id", type=int)

    # Parsear pagos (existente)
    pagos_json = request.form.get("pagos_json", "").strip()
    pagos = []
    if pagos_json:
        try:
            pagos_raw = json.loads(pagos_json)
            for p in pagos_raw:
                pagos.append(
                    {
                        "forma_pago": p["forma_pago"],
                        "moneda_pago": p["moneda_pago"],
                        "monto": Decimal(str(p["monto"])),
                        "referencia": p.get("referencia") or None,
                        "observaciones": p.get("observaciones") or None,
                    }
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            flash(f"Error al interpretar los pagos: {e}", "error")
            return redirect(
                url_for("facturas_venta.confirmar_get", factura_id=factura.id)
            )

    # --- Confirmar la factura (transacción BD) ---
    try:
        facturacion.confirmar_factura(
            factura=factura,
            tipo_venta=tipo_venta,
            pagos=pagos,
            fiduciario_id=fiduciario_id,
        )
        db.session.commit()
    except DominioError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("facturas_venta.confirmar_get", factura_id=factura.id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error inesperado al confirmar factura")
        if current_app.config.get("DEBUG"):
            flash(f"Error interno: {e}", "error")
        else:
            flash(
                "Ocurrió un error inesperado. Contacte al administrador.",
                "error",
            )
        return redirect(url_for("facturas_venta.confirmar_get", factura_id=factura.id))

    # --- Factura confirmada en BD. Ahora intentar imprimir en el agente fiscal. ---
    _intentar_impresion_fiscal(factura)

    flash(
        f"Factura {factura.numero_interno} confirmada.",
        "success",
    )
    return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))


def _intentar_impresion_fiscal(factura: FacturaVenta) -> bool:
    """Intenta imprimir la factura en el agente fiscal.

    Returns:
        True si la factura fue emitida (con o sin número leído).
        False si no se pudo emitir.
    """
    if factura.modalidad != "fiscal":
        current_app.logger.info(
            f"Factura {factura.numero_interno} no es fiscal, no se envía al agente."
        )
        return False

    payload = construir_payload_factura(factura)
    resultado = fiscal_client.imprimir_factura(payload)

    if resultado.estado == EstadoImpresion.EXITOSA_CON_NUMERO:
        # Caso 1: éxito completo
        factura.numero_fiscal = str(resultado.numero_fiscal)
        factura.numero_maquina = resultado.numero_maquina
        db.session.commit()
        current_app.logger.info(
            f"Factura {factura.numero_interno} impresa: "
            f"numero={resultado.numero_fiscal} "
            f"maquina={resultado.numero_maquina}"
        )
        flash(
            f"Factura impresa en la impresora fiscal "
            f"(N° {resultado.numero_fiscal}).",
            "success",
        )
        return True

    elif resultado.estado == EstadoImpresion.EXITOSA_SIN_NUMERO:
        # Caso 2 (DT-001): factura emitida pero número no leído
        factura.numero_maquina = resultado.numero_maquina
        db.session.commit()
        current_app.logger.warning(
            f"Factura {factura.numero_interno} emitida pero número fiscal "
            f"no leído: {resultado.mensaje}"
        )
        flash(
            "Factura emitida en la impresora fiscal, PERO no se pudo leer "
            "el número fiscal automáticamente. "
            "Verifique el ticket impreso e ingrese el número manualmente "
            "desde el detalle de la factura.",
            "warning",
        )
        return True

    elif resultado.estado == EstadoImpresion.AGENTE_NO_DISPONIBLE:
        # Caso 3: agente apagado o timeout
        current_app.logger.warning(
            f"Agente fiscal no disponible al imprimir "
            f"{factura.numero_interno}: {resultado.mensaje}"
        )
        flash(
            "Factura emitida pero NO impresa en la impresora fiscal. "
            "El agente fiscal no está disponible. "
            "Puede reintentar la impresión desde el detalle de la factura.",
            "warning",
        )
        return False

    else:  # ERROR_AGENTE
        # Caso 4: agente devolvió error
        current_app.logger.error(
            f"Error del agente al imprimir {factura.numero_interno}: "
            f"{resultado.mensaje} - {resultado.error}"
        )
        flash(
            f"Factura emitida pero NO impresa. Motivo: {resultado.mensaje}. "
            "Puede reintentar la impresión desde el detalle de la factura.",
            "warning",
        )
        return False


@facturas_venta_bp.route("/<int:factura_id>/anular", methods=["GET"])
@requiere_permiso("facturas_venta.anular")
def anular_get(factura_id: int):
    """Pantalla de anulación de factura."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "emitida":
        flash(
            f"Solo se pueden anular facturas emitidas. "
            f"Estado actual: {factura.estado}.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    return render_template("facturas_venta/anular.html", factura=factura)


@facturas_venta_bp.route("/<int:factura_id>/anular", methods=["POST"])
@requiere_permiso("facturas_venta.anular")
def anular_post(factura_id: int):
    """Procesa la anulación de la factura."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    motivo = request.form.get("motivo", "").strip()

    try:
        facturacion.anular_factura(
            factura=factura,
            motivo=motivo,
            usuario_id=current_user.id,
        )
        db.session.commit()
        flash(
            f"Factura {factura.numero_interno} anulada correctamente.",
            "success",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))
    except DominioError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("facturas_venta.anular_get", factura_id=factura.id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error inesperado al anular factura")
        if current_app.config.get("DEBUG"):
            flash(f"Error interno: {e}", "error")
        else:
            flash(
                "Ocurrió un error inesperado. Contacte al administrador.",
                "error",
            )
        return redirect(url_for("facturas_venta.anular_get", factura_id=factura.id))


@facturas_venta_bp.route("/<int:factura_id>/numero-fiscal", methods=["POST"])
@requiere_permiso("facturas_venta.anular")
def ingresar_numero_fiscal(factura_id: int):
    """Permite ingresar manualmente el número fiscal (caso DT-001)."""
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    if factura.estado not in ("emitida", "pagada"):
        flash(
            "Solo se puede ingresar el número fiscal en facturas emitidas.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    if factura.numero_fiscal:
        flash(
            f"Esta factura ya tiene número fiscal: {factura.numero_fiscal}.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    numero = request.form.get("numero_fiscal", "").strip()
    if not numero:
        flash("Debe ingresar un número fiscal.", "error")
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    if not numero.isdigit():
        flash("El número fiscal debe ser numérico.", "error")
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    # --- NUEVO: Validar unicidad ---
    numero_maquina = factura.numero_maquina or ""
    existente = db.session.scalar(
        db.select(FacturaVenta).filter(
            FacturaVenta.numero_fiscal == numero,
            FacturaVenta.numero_maquina == numero_maquina,
            FacturaVenta.id != factura.id,
        )
    )
    if existente is not None:
        flash(
            f"El número fiscal {numero} ya está registrado en la factura "
            f"{existente.numero_interno}. "
            "El número fiscal debe ser único por equipo fiscal.",
            "error",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    factura.numero_fiscal = numero
    db.session.commit()
    current_app.logger.info(
        f"Número fiscal ingresado manualmente para "
        f"{factura.numero_interno}: {numero}"
    )
    flash(f"Número fiscal {numero} registrado.", "success")
    return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))


@facturas_venta_bp.route("/<int:factura_id>/reimprimir", methods=["POST"])
@requiere_permiso("facturas_venta.anular")
def reimprimir(factura_id: int):
    """Reintenta imprimir una factura fiscal pendiente.

    Solo para facturas emitidas sin número fiscal.
    Solo admin/contador (permiso facturas_venta.anular).
    """
    factura = db.session.get(FacturaVenta, factura_id)
    if factura is None:
        abort(404)

    if factura.estado not in ("emitida", "pagada"):
        flash(
            "Solo se pueden reimprimir facturas emitidas o pagadas.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    if factura.modalidad != "fiscal":
        flash(
            "Esta factura no es de modalidad fiscal. No se imprime.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    if factura.numero_fiscal:
        flash(
            f"Esta factura ya tiene número fiscal "
            f"({factura.serie}-{factura.numero_fiscal}). "
            "No se reimprime para evitar duplicar el documento.",
            "warning",
        )
        return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))

    _intentar_impresion_fiscal(factura)
    return redirect(url_for("facturas_venta.detalle", factura_id=factura.id))
