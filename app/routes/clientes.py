from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms.cliente import ClienteForm
from app.models import Cliente
from app.security.decorators import requiere_permiso

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@clientes_bp.route("/")
@requiere_permiso("clientes.ver")
def listar():
    """Listado de clientes con búsqueda opcional."""
    buscar = request.args.get("q", "").strip()
    mostrar_inactivos = request.args.get("inactivos", "0") == "1"

    query = db.select(Cliente)
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)
    if buscar:
        patron = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Cliente.razon_social.ilike(patron),
                Cliente.numero_documento.ilike(patron),
                Cliente.nombre_comercial.ilike(patron),
            )
        )
    query = query.order_by(Cliente.razon_social)

    clientes = db.session.scalars(query).all()

    # Si la petición viene de HTMX, devolvemos solo la tabla (parcial)
    if request.headers.get("HX-Request") == "true":
        return render_template(
            "clientes/_tabla.html",
            clientes=clientes,
            buscar=buscar,
            mostrar_inactivos=mostrar_inactivos,
        )

    return render_template(
        "clientes/listar.html",
        clientes=clientes,
        buscar=buscar,
        mostrar_inactivos=mostrar_inactivos,
    )


@clientes_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("clientes.crear")
def crear():
    """Alta de cliente."""
    form = ClienteForm()
    if form.validate_on_submit():
        cliente = Cliente(
            tipo_documento=form.tipo_documento.data,
            numero_documento=form.numero_documento.data.strip(),
            razon_social=form.razon_social.data.strip(),
            nombre_comercial=(form.nombre_comercial.data or "").strip() or None,
            direccion=(form.direccion.data or "").strip() or None,
            telefono=(form.telefono.data or "").strip() or None,
            email=(form.email.data or "").strip() or None,
            activo=form.activo.data,
            tiene_credito = form.tiene_credito.data,
            limite_credito_usd = form.limite_credito_usd.data,
            dias_credito = form.dias_credito.data  
        )

        # Verificar unicidad del documento antes de insertar
        existente = db.session.scalar(
            db.select(Cliente).filter_by(numero_documento=cliente.numero_documento)
        )
        if existente:
            form.numero_documento.errors.append(
                "Ya existe un cliente con ese número de documento."
            )
            return render_template("clientes/form.html", form=form, cliente=None)

        db.session.add(cliente)
        db.session.commit()
        flash(f"Cliente '{cliente.razon_social}' creado correctamente.", "success")
        return redirect(url_for("clientes.listar"))

    return render_template("clientes/form.html", form=form, cliente=None)


@clientes_bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@requiere_permiso("clientes.editar")
def editar(cliente_id: int):
    """Edición de cliente."""
    cliente = db.session.get(Cliente, cliente_id)
    if cliente is None:
        flash("Cliente no encontrado.", "error")
        return redirect(url_for("clientes.listar"))

    form = ClienteForm(obj=cliente)
    if form.validate_on_submit():
        # Verificar unicidad del documento (excluyendo al propio cliente)
        existente = db.session.scalar(
            db.select(Cliente).filter(
                Cliente.numero_documento == form.numero_documento.data.strip(),
                Cliente.id != cliente.id,
            )
        )
        if existente:
            form.numero_documento.errors.append(
                "Ya existe otro cliente con ese número de documento."
            )
            return render_template("clientes/form.html", form=form, cliente=cliente)

        cliente.tipo_documento = form.tipo_documento.data
        cliente.numero_documento = form.numero_documento.data.strip()
        cliente.razon_social = form.razon_social.data.strip()
        cliente.nombre_comercial = (form.nombre_comercial.data or "").strip() or None
        cliente.direccion = (form.direccion.data or "").strip() or None
        cliente.telefono = (form.telefono.data or "").strip() or None
        cliente.email = (form.email.data or "").strip() or None
        cliente.activo = form.activo.data
        cliente.tiene_credito = form.tiene_credito.data
        cliente.limite_credito_usd = form.limite_credito_usd.data
        cliente.dias_credito = form.dias_credito.data

        db.session.commit()
        flash(f"Cliente '{cliente.razon_social}' actualizado.", "success")
        return redirect(url_for("clientes.listar"))

    return render_template("clientes/form.html", form=form, cliente=cliente)


@clientes_bp.route("/<int:cliente_id>/desactivar", methods=["POST"])
@requiere_permiso("clientes.editar")
def desactivar(cliente_id: int):
    """Desactiva un cliente (HTMX). Devuelve la fila actualizada."""
    cliente = db.session.get(Cliente, cliente_id)
    if cliente is None:
        return "Cliente no encontrado", 404

    cliente.activo = False
    db.session.commit()

    return render_template("clientes/_fila.html", cliente=cliente)


@clientes_bp.route("/<int:cliente_id>/activar", methods=["POST"])
@requiere_permiso("clientes.editar")
def activar(cliente_id: int):
    """Reactiva un cliente (HTMX). Devuelve la fila actualizada."""
    cliente = db.session.get(Cliente, cliente_id)
    if cliente is None:
        return "Cliente no encontrado", 404

    cliente.activo = True
    db.session.commit()

    return render_template("clientes/_fila.html", cliente=cliente)