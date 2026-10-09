from datetime import date
from decimal import Decimal, InvalidOperation

from app.models import Producto

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
from app.forms.factura_compra import CabeceraCompraForm
from app.models import FacturaCompra, Proveedor
from app.security.decorators import requiere_permiso
from app.services import facturacion_compras
import json
from flask import current_app
from app.constants import FORMAS_PAGO

facturas_compra_bp = Blueprint(
    "facturas_compra", __name__, url_prefix="/facturas-compra"
)

PER_PAGE = 20


@facturas_compra_bp.route("/")
@requiere_permiso("facturas_compra.ver")
def listar():
    """Listado de facturas de compra."""
    estado = request.args.get("estado", "").strip() or None
    buscar = request.args.get("q", "").strip()

    query = db.select(FacturaCompra)
    if estado:
        query = query.filter_by(estado=estado)
    if buscar:
        patron = f"%{buscar}%"
        query = query.join(Proveedor).filter(
            db.or_(
                FacturaCompra.numero_interno.ilike(patron),
                FacturaCompra.numero_factura_proveedor.ilike(patron),
                Proveedor.razon_social.ilike(patron),
            )
        )
    query = query.order_by(FacturaCompra.fecha_creacion.desc())

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
        return render_template("facturas_compra/_tabla.html", **contexto)
    return render_template("facturas_compra/listar.html", **contexto)


@facturas_compra_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("facturas_compra.crear")
def crear():
    """Crea un borrador de compra."""
    if request.method == "POST":
        proveedor_id = request.form.get("proveedor_id", type=int)
        if not proveedor_id:
            flash("Debe seleccionar un proveedor.", "error")
            return redirect(url_for("facturas_compra.crear"))

        try:
            factura = facturacion_compras.crear_borrador(proveedor_id)
            db.session.commit()
            flash(f"Borrador {factura.numero_interno} creado.", "success")
            return redirect(url_for("facturas_compra.editar", factura_id=factura.id))
        except DominioError as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("facturas_compra.crear"))

    proveedores = db.session.scalars(
        db.select(Proveedor).filter_by(activo=True).order_by(Proveedor.razon_social)
    ).all()
    return render_template("facturas_compra/crear.html", proveedores=proveedores)


@facturas_compra_bp.route("/<int:factura_id>/editar")
@requiere_permiso("facturas_compra.ver")
def editar(factura_id: int):
    """Página de edición del borrador."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "borrador":
        flash("Solo se pueden editar facturas en borrador.", "warning")
        return redirect(url_for("facturas_compra.detalle", factura_id=factura.id))

    form = CabeceraCompraForm(obj=factura)
    form.proveedor_id.choices = [
        (p.id, f"{p.tipo_documento}-{p.numero_documento} — {p.razon_social}")
        for p in db.session.scalars(
            db.select(Proveedor).filter_by(activo=True).order_by(Proveedor.razon_social)
        )
    ]

    return render_template("facturas_compra/editar.html", factura=factura, form=form)


def _get_borrador(factura_id: int) -> FacturaCompra:
    """Helper: obtiene un borrador o lanza 404."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)
    if factura.estado != "borrador":
        abort(400, "La factura no está en estado editable.")
    return factura


@facturas_compra_bp.route("/<int:factura_id>/cabecera", methods=["POST"])
@requiere_permiso("facturas_compra.crear")
def editar_cabecera(factura_id: int):
    """Actualiza la cabecera del borrador."""
    factura = _get_borrador(factura_id)

    form = CabeceraCompraForm(obj=factura)
    form.proveedor_id.choices = [
        (p.id, f"{p.tipo_documento}-{p.numero_documento} — {p.razon_social}")
        for p in db.session.scalars(
            db.select(Proveedor).filter_by(activo=True).order_by(Proveedor.razon_social)
        )
    ]

    if form.validate_on_submit():
        if form.fecha_emision.data > date.today():
            form.fecha_emision.errors.append("La fecha de emisión no puede ser futura.")
        else:
            factura.proveedor_id = form.proveedor_id.data
            factura.fecha_emision = form.fecha_emision.data
            factura.numero_factura_proveedor = (
                form.numero_factura_proveedor.data or ""
            ).strip() or None
            factura.fecha_factura_proveedor = form.fecha_factura_proveedor.data
            factura.observaciones = (form.observaciones.data or "").strip() or None
            db.session.commit()

            # Refrescar el form
            form = CabeceraCompraForm(obj=factura)
            form.proveedor_id.choices = [
                (
                    p.id,
                    f"{p.tipo_documento}-{p.numero_documento} — {p.razon_social}",
                )
                for p in db.session.scalars(
                    db.select(Proveedor)
                    .filter_by(activo=True)
                    .order_by(Proveedor.razon_social)
                )
            ]

    return render_template(
        "facturas_compra/_cabecera_editable.html",
        factura=factura,
        form=form,
    )


@facturas_compra_bp.route("/<int:factura_id>/cancelar", methods=["POST"])
@requiere_permiso("facturas_compra.crear")
def cancelar(factura_id: int):
    """Cancela y elimina un borrador."""
    factura = _get_borrador(factura_id)
    numero = factura.numero_interno
    db.session.delete(factura)
    db.session.commit()
    flash(f"Borrador {numero} cancelado.", "info")
    return redirect(url_for("facturas_compra.listar"))


@facturas_compra_bp.route("/<int:factura_id>/detalle")
@requiere_permiso("facturas_compra.ver")
def detalle(factura_id: int):
    """Vista de detalle (solo lectura) de una compra."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    return render_template("facturas_compra/detalle.html", factura=factura)


def _render_fragmento(factura, errores_descuento=None):
    """Renderiza el fragmento de detalles + totales para HTMX."""
    return render_template(
        "facturas_compra/_fragmento_actualizable.html",
        factura=factura,
        errores_descuento=errores_descuento or {},
    )


@facturas_compra_bp.route("/buscar-productos")
@requiere_permiso("facturas_compra.crear")
def buscar_productos():
    """Búsqueda de productos para el dropdown."""
    q = request.args.get("q", "").strip()
    factura_id = request.args.get("factura_id", type=int)
    if len(q) < 2 or not factura_id:
        return "", 204

    patron = f"%{q}%"
    productos = db.session.scalars(
        db.select(Producto)
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
        "facturas_compra/_resultados_busqueda.html",
        productos=productos,
        factura_id=factura_id,
    )


@facturas_compra_bp.route("/<int:factura_id>/detalles", methods=["POST"])
@requiere_permiso("facturas_compra.crear")
def agregar_detalle(factura_id: int):
    """Agrega un producto al borrador."""
    factura = _get_borrador(factura_id)
    producto_id = request.form.get("producto_id", type=int)
    if not producto_id:
        return "Producto inválido", 400

    try:
        facturacion_compras.agregar_detalle(factura, producto_id)
        db.session.commit()
    except DominioError as e:
        db.session.rollback()
        return f'<div class="bg-red-100 text-red-800 p-3 rounded">{e}</div>', 200

    return _render_fragmento(factura)


@facturas_compra_bp.route(
    "/<int:factura_id>/detalles/<int:detalle_id>/cantidad", methods=["POST"]
)
@requiere_permiso("facturas_compra.crear")
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
    facturacion_compras.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_compra_bp.route(
    "/<int:factura_id>/detalles/<int:detalle_id>/precio", methods=["POST"]
)
@requiere_permiso("facturas_compra.crear")
def cambiar_precio(factura_id: int, detalle_id: int):
    """Cambia el precio unitario de un detalle (solo en compras)."""
    factura = _get_borrador(factura_id)

    detalle = next((d for d in factura.detalles if d.id == detalle_id), None)
    if detalle is None:
        abort(404)

    try:
        nuevo = Decimal(request.form.get("precio", "0"))
        if nuevo <= 0:
            raise ValueError("El precio debe ser mayor a cero.")
    except (InvalidOperation, ValueError) as e:
        return f'<div class="bg-red-100 text-red-800 p-3 rounded">{e}</div>', 200

    detalle.precio_unitario_usd = nuevo
    detalle.precio_unitario_ves = (nuevo * factura.tasa_cambio_valor).quantize(
        Decimal("0.0001")
    )
    facturacion_compras.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_compra_bp.route(
    "/<int:factura_id>/detalles/<int:detalle_id>/eliminar", methods=["POST"]
)
@requiere_permiso("facturas_compra.crear")
def eliminar_detalle(factura_id: int, detalle_id: int):
    """Elimina un detalle del borrador."""
    factura = _get_borrador(factura_id)

    detalle = next((d for d in factura.detalles if d.id == detalle_id), None)
    if detalle is None:
        abort(404)

    db.session.delete(detalle)
    db.session.flush()
    db.session.refresh(factura)
    facturacion_compras.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_compra_bp.route("/<int:factura_id>/descuento-global", methods=["POST"])
@requiere_permiso("facturas_compra.crear")
def descuento_global(factura_id: int):
    """Aplica o quita el descuento global del borrador."""
    factura = _get_borrador(factura_id)
    accion = request.form.get("accion", "aplicar")

    if accion == "quitar":
        factura.descuento_global_porcentaje = None
        factura.descuento_global_monto_usd = None
        factura.descuento_global_monto_ves = None
        facturacion_compras.recalcular(factura)
        db.session.commit()
        return _render_fragmento(factura)

    # Reutilizamos el form de descuento de ventas (mismo formato)
    from app.forms.factura_venta import DescuentoGlobalForm

    form = DescuentoGlobalForm()
    if not form.validate_on_submit():
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

    facturacion_compras.recalcular(factura)
    db.session.commit()
    return _render_fragmento(factura)


@facturas_compra_bp.route("/<int:factura_id>/confirmar", methods=["GET"])
@requiere_permiso("facturas_compra.crear")
def confirmar_get(factura_id: int):
    """Pantalla de confirmación de compra."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "borrador":
        flash("Solo se pueden confirmar compras en borrador.", "warning")
        return redirect(url_for("facturas_compra.listar"))

    if not factura.detalles:
        flash(
            "La compra no tiene productos. Agregue al menos uno antes de confirmar.",
            "warning",
        )
        return redirect(url_for("facturas_compra.editar", factura_id=factura.id))

    formas_pago_json = [
        {
            "valor": k,
            "nombre": v["nombre"],
            "moneda": v["moneda"],
        }
        for k, v in FORMAS_PAGO.items()
    ]

    return render_template(
        "facturas_compra/confirmar.html",
        factura=factura,
        formas_pago=formas_pago_json,
        formas_pago_json=json.dumps(formas_pago_json),
        total_usd_str=str(factura.total_usd),
        total_ves_str=str(factura.total_ves),
    )


@facturas_compra_bp.route("/<int:factura_id>/confirmar", methods=["POST"])
@requiere_permiso("facturas_compra.crear")
def confirmar_post(factura_id: int):
    """Procesa la confirmación de la compra."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    # Parsear pagos
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
                url_for("facturas_compra.confirmar_get", factura_id=factura.id)
            )

    try:
        facturacion_compras.confirmar_compra(factura, pagos=pagos)
        db.session.commit()
        flash(
            f"Compra {factura.numero_interno} confirmada "
            f"(estado: {factura.estado}).",
            "success",
        )
        return redirect(url_for("facturas_compra.listar"))
    except DominioError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("facturas_compra.confirmar_get", factura_id=factura.id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error inesperado al confirmar compra")
        if current_app.config.get("DEBUG"):
            flash(f"Error interno: {e}", "error")
        else:
            flash(
                "Ocurrió un error inesperado. Contacte al administrador.",
                "error",
            )
        return redirect(url_for("facturas_compra.confirmar_get", factura_id=factura.id))


@facturas_compra_bp.route("/<int:factura_id>/anular", methods=["GET"])
@requiere_permiso("facturas_compra.anular")
def anular_get(factura_id: int):
    """Pantalla de anulación de compra."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    if factura.estado != "emitida":
        flash(
            f"Solo se pueden anular compras emitidas. "
            f"Estado actual: {factura.estado}.",
            "warning",
        )
        return redirect(
            url_for("facturas_compra.detalle", factura_id=factura.id)
        )

    return render_template("facturas_compra/anular.html", factura=factura)


@facturas_compra_bp.route("/<int:factura_id>/anular", methods=["POST"])
@requiere_permiso("facturas_compra.anular")
def anular_post(factura_id: int):
    """Procesa la anulación de la compra."""
    factura = db.session.get(FacturaCompra, factura_id)
    if factura is None:
        abort(404)

    motivo = request.form.get("motivo", "").strip()

    try:
        facturacion_compras.anular_compra(
            factura=factura,
            motivo=motivo,
            usuario_id=current_user.id,
        )
        db.session.commit()
        flash(
            f"Compra {factura.numero_interno} anulada correctamente.",
            "success",
        )
        return redirect(
            url_for("facturas_compra.detalle", factura_id=factura.id)
        )
    except DominioError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(
            url_for("facturas_compra.anular_get", factura_id=factura.id)
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error inesperado al anular compra")
        if current_app.config.get("DEBUG"):
            flash(f"Error interno: {e}", "error")
        else:
            flash(
                "Ocurrió un error inesperado. Contacte al administrador.",
                "error",
            )
        return redirect(
            url_for("facturas_compra.anular_get", factura_id=factura.id)
        )