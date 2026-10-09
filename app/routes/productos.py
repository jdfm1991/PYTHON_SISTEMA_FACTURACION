from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.extensions import db
from app.forms.producto import ProductoForm
from app.models import AlicuotaIVA, Producto
from app.security.decorators import requiere_permiso

productos_bp = Blueprint("productos", __name__, url_prefix="/productos")

PER_PAGE = 20


def _query_filtrada():
    """Construye la consulta aplicando los filtros del request."""
    buscar = request.args.get("q", "").strip()
    mostrar_inactivos = request.args.get("inactivos", "0") == "1"
    alicuota_id = request.args.get("alicuota", type=int)

    query = db.select(Producto)
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)
    if alicuota_id:
        query = query.filter_by(alicuota_iva_id=alicuota_id)
    if buscar:
        patron = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(patron),
                Producto.nombre.ilike(patron),
            )
        )
    query = query.order_by(Producto.codigo)

    return query, buscar, mostrar_inactivos, alicuota_id


def _contexto_comun():
    """Contexto que necesita la plantilla en cualquier vista del listado."""
    query, buscar, mostrar_inactivos, alicuota_id = _query_filtrada()

    paginacion = db.paginate(
        query,
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )

    alicuotas = db.session.scalars(
        db.select(AlicuotaIVA).order_by(AlicuotaIVA.porcentaje)
    ).all()

    return {
        "paginacion": paginacion,
        "alicuotas": alicuotas,
        "buscar": buscar,
        "mostrar_inactivos": mostrar_inactivos,
        "alicuota_id": alicuota_id,
    }


@productos_bp.route("/")
@requiere_permiso("productos.ver")
def listar():
    """Listado paginado de productos."""
    contexto = _contexto_comun()

    if request.headers.get("HX-Request") == "true":
        return render_template("productos/_tabla.html", **contexto)

    return render_template("productos/listar.html", **contexto)


@productos_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("productos.crear")
def crear():
    """Alta de producto."""
    form = ProductoForm()
    if form.validate_on_submit():
        codigo = form.codigo.data.strip()

        existente = db.session.scalar(
            db.select(Producto).filter_by(codigo=codigo)
        )
        if existente:
            form.codigo.errors.append(
                "Ya existe un producto con ese código."
            )
            return render_template(
                "productos/form.html", form=form, producto=None
            )

        producto = Producto(
            codigo=codigo,
            nombre=form.nombre.data.strip(),
            descripcion=(form.descripcion.data or "").strip() or None,
            precio_usd=form.precio_usd.data,
            alicuota_iva_id=form.alicuota_iva_id.data,
            stock_minimo=form.stock_minimo.data,
            activo=form.activo.data,
            # stock_actual se inicializa en el default del modelo (0)
        )
        db.session.add(producto)
        db.session.commit()
        flash(f"Producto '{producto.nombre}' creado.", "success")
        return redirect(url_for("productos.listar"))

    return render_template("productos/form.html", form=form, producto=None)


@productos_bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
@requiere_permiso("productos.editar")
def editar(producto_id: int):
    """Edición de producto."""
    producto = db.session.get(Producto, producto_id)
    if producto is None:
        flash("Producto no encontrado.", "error")
        return redirect(url_for("productos.listar"))

    form = ProductoForm(obj=producto)
    if form.validate_on_submit():
        codigo = form.codigo.data.strip()

        # Unicidad (excluyendo al propio producto)
        if codigo != producto.codigo:
            existente = db.session.scalar(
                db.select(Producto).filter(
                    Producto.codigo == codigo,
                    Producto.id != producto.id,
                )
            )
            if existente:
                form.codigo.errors.append(
                    "Ya existe otro producto con ese código."
                )
                return render_template(
                    "productos/form.html", form=form, producto=producto
                )

        producto.codigo = codigo
        producto.nombre = form.nombre.data.strip()
        producto.descripcion = (form.descripcion.data or "").strip() or None
        producto.precio_usd = form.precio_usd.data
        producto.alicuota_iva_id = form.alicuota_iva_id.data
        producto.stock_minimo = form.stock_minimo.data
        producto.activo = form.activo.data

        db.session.commit()
        flash(f"Producto '{producto.nombre}' actualizado.", "success")
        return redirect(url_for("productos.listar"))

    return render_template(
        "productos/form.html", form=form, producto=producto
    )


@productos_bp.route("/<int:producto_id>/desactivar", methods=["POST"])
@requiere_permiso("productos.editar")
def desactivar(producto_id: int):
    """Desactiva un producto (HTMX)."""
    producto = db.session.get(Producto, producto_id)
    if producto is None:
        return "Producto no encontrado", 404

    producto.activo = False
    db.session.commit()
    return render_template("productos/_fila.html", producto=producto)


@productos_bp.route("/<int:producto_id>/activar", methods=["POST"])
@requiere_permiso("productos.editar")
def activar(producto_id: int):
    """Reactiva un producto (HTMX)."""
    producto = db.session.get(Producto, producto_id)
    if producto is None:
        return "Producto no encontrado", 404

    producto.activo = True
    db.session.commit()
    return render_template("productos/_fila.html", producto=producto)