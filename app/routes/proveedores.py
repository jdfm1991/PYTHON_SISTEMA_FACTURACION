from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms.proveedor import ProveedorForm
from app.models import Proveedor
from app.security.decorators import requiere_permiso

proveedores_bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")


@proveedores_bp.route("/")
@requiere_permiso("proveedores.ver")
def listar():
    """Listado de proveedores con búsqueda opcional."""
    buscar = request.args.get("q", "").strip()
    mostrar_inactivos = request.args.get("inactivos", "0") == "1"

    query = db.select(Proveedor)
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)
    if buscar:
        patron = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Proveedor.razon_social.ilike(patron),
                Proveedor.numero_documento.ilike(patron),
                Proveedor.nombre_comercial.ilike(patron),
            )
        )
    query = query.order_by(Proveedor.razon_social)

    proveedores = db.session.scalars(query).all()

    # Si la petición viene de HTMX, devolvemos solo la tabla (parcial)
    if request.headers.get("HX-Request") == "true":
        return render_template(
            "proveedores/_tabla.html",
            proveedores=proveedores,
            buscar=buscar,
            mostrar_inactivos=mostrar_inactivos,
        )

    return render_template(
        "proveedores/listar.html",
        proveedores=proveedores,
        buscar=buscar,
        mostrar_inactivos=mostrar_inactivos,
    )


@proveedores_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("proveedores.crear")
def crear():
    """Alta de Proveedor."""
    form = ProveedorForm()
    if form.validate_on_submit():
        proveedor = Proveedor(
            tipo_documento=form.tipo_documento.data,
            numero_documento=form.numero_documento.data.strip(),
            razon_social=form.razon_social.data.strip(),
            nombre_comercial=(form.nombre_comercial.data or "").strip() or None,
            direccion=(form.direccion.data or "").strip() or None,
            telefono=(form.telefono.data or "").strip() or None,
            email=(form.email.data or "").strip() or None,
            activo=form.activo.data,
        )

        # Verificar unicidad del documento antes de insertar
        existente = db.session.scalar(
            db.select(Proveedor).filter_by(numero_documento=proveedor.numero_documento)
        )
        if existente:
            form.numero_documento.errors.append(
                "Ya existe un proveedor con ese número de documento."
            )
            return render_template("proveedores/form.html", form=form, proveedor=None)

        db.session.add(proveedor)
        db.session.commit()
        flash(f"Proveedor '{proveedor.razon_social}' creado correctamente.", "success")
        return redirect(url_for("proveedores.listar"))

    return render_template("proveedores/form.html", form=form, proveedor=None)


@proveedores_bp.route("/<int:proveedor_id>/editar", methods=["GET", "POST"])
@requiere_permiso("proveedores.editar")
def editar(proveedor_id: int):
    """Edición de proveedor."""
    proveedor = db.session.get(Proveedor, proveedor_id)
    if proveedor is None:
        flash("Proveedor no encontrado.", "error")
        return redirect(url_for("proveedores.listar"))

    form = ProveedorForm(obj=proveedor)
    if form.validate_on_submit():
        # Verificar unicidad del documento (excluyendo al propio proveedor)
        existente = db.session.scalar(
            db.select(Proveedor).filter(
                Proveedor.numero_documento == form.numero_documento.data.strip(),
                Proveedor.id != proveedor.id,
            )
        )
        if existente:
            form.numero_documento.errors.append(
                "Ya existe otro proveedor con ese número de documento."
            )
            return render_template("proveedores/form.html", form=form, proveedor=proveedor)

        proveedor.tipo_documento = form.tipo_documento.data
        proveedor.numero_documento = form.numero_documento.data.strip()
        proveedor.razon_social = form.razon_social.data.strip()
        proveedor.nombre_comercial = (form.nombre_comercial.data or "").strip() or None
        proveedor.direccion = (form.direccion.data or "").strip() or None
        proveedor.telefono = (form.telefono.data or "").strip() or None
        proveedor.email = (form.email.data or "").strip() or None
        proveedor.activo = form.activo.data

        db.session.commit()
        flash(f"Proveedor '{proveedor.razon_social}' actualizado.", "success")
        return redirect(url_for("proveedores.listar"))

    return render_template("proveedores/form.html", form=form, proveedor=proveedor)


@proveedores_bp.route("/<int:proveedor_id>/desactivar", methods=["POST"])
@requiere_permiso("proveedores.editar")
def desactivar(proveedor_id: int):
    """Desactiva un proveedor (HTMX). Devuelve la fila actualizada."""
    proveedor = db.session.get(Proveedor, proveedor_id)
    if proveedor is None:
        return "Proveedor no encontrado", 404

    proveedor.activo = False
    db.session.commit()

    return render_template("proveedores/_fila.html", proveedor=proveedor)


@proveedores_bp.route("/<int:proveedor_id>/activar", methods=["POST"])
@requiere_permiso("proveedores.editar")
def activar(proveedor_id: int):
    """Reactiva un proveedor (HTMX). Devuelve la fila actualizada."""
    proveedor = db.session.get(Proveedor, proveedor_id)
    if proveedor is None:
        return "Proveedor no encontrado", 404

    proveedor.activo = True
    db.session.commit()

    return render_template("proveedores/_fila.html", proveedor=proveedor)