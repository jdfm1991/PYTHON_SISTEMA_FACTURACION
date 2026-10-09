from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms.fiduciario import FiduciarioForm
from app.models import Fiduciario
from app.security.decorators import requiere_permiso

fiduciarios_bp = Blueprint("fiduciarios", __name__, url_prefix="/fiduciarios")


@fiduciarios_bp.route("/")
@requiere_permiso("fiduciarios.ver")
def listar():
    """Listado de fiduciarios con búsqueda."""
    buscar = request.args.get("q", "").strip()
    mostrar_inactivos = request.args.get("inactivos", "0") == "1"

    query = db.select(Fiduciario)
    if not mostrar_inactivos:
        query = query.filter_by(activo=True)
    if buscar:
        patron = f"%{buscar}%"
        query = query.filter(
            db.or_(
                Fiduciario.nombre.ilike(patron),
                Fiduciario.numero_documento.ilike(patron),
            )
        )
    query = query.order_by(Fiduciario.nombre)

    fiduciarios = db.session.scalars(query).all()

    contexto = {
        "fiduciarios": fiduciarios,
        "buscar": buscar,
        "mostrar_inactivos": mostrar_inactivos,
    }

    if request.headers.get("HX-Request") == "true":
        return render_template("fiduciarios/_tabla.html", **contexto)
    return render_template("fiduciarios/listar.html", **contexto)


@fiduciarios_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("fiduciarios.crear")
def crear():
    """Alta de fiduciario."""
    form = FiduciarioForm()
    if form.validate_on_submit():
        fiduciario = Fiduciario(
            nombre=form.nombre.data.strip(),
            tipo_documento=form.tipo_documento.data,
            numero_documento=form.numero_documento.data.strip(),
            telefono=(form.telefono.data or "").strip() or None,
            email=(form.email.data or "").strip() or None,
            direccion=(form.direccion.data or "").strip() or None,
            contacto=(form.contacto.data or "").strip() or None,
            notas=(form.notas.data or "").strip() or None,
            activo=form.activo.data,
        )
        
        """ numero = form.numero_documento.data.strip() """
        existente = db.session.scalar(
            db.select(Fiduciario).filter_by(numero_documento=fiduciario.numero_documento)
        )
        if existente:
            form.numero_documento.errors.append(
                "Ya existe un fiduciario con ese número de documento."
            )
            return render_template("fiduciarios/form.html", form=form, fiduciario=None)

        db.session.add(fiduciario)
        db.session.commit()
        flash(f"Fiduciario '{fiduciario.nombre}' creado correctamente.", "success")
        return redirect(url_for("fiduciarios.listar"))

    return render_template("fiduciarios/form.html", form=form, fiduciario=None)


@fiduciarios_bp.route("/<int:fiduciario_id>/editar", methods=["GET", "POST"])
@requiere_permiso("fiduciarios.editar")
def editar(fiduciario_id: int):
    """Edición de fiduciario."""
    fiduciario = db.session.get(Fiduciario, fiduciario_id)
    if fiduciario is None:
        flash("Fiduciario no encontrado.", "error")
        return redirect(url_for("fiduciarios.listar"))

    form = FiduciarioForm(obj=fiduciario)
    if form.validate_on_submit():
        numero = form.numero_documento.data.strip()
        if numero != fiduciario.numero_documento:
            existente = db.session.scalar(
                db.select(Fiduciario).filter(
                    Fiduciario.numero_documento == numero,
                    Fiduciario.id != fiduciario.id,
                )
            )
            if existente:
                form.numero_documento.errors.append(
                    "Ya existe otro fiduciario con ese número de documento."
                )
                return render_template(
                    "fiduciarios/form.html", form=form, fiduciario=fiduciario
                )

        fiduciario.nombre = form.nombre.data.strip()
        fiduciario.tipo_documento = form.tipo_documento.data
        fiduciario.numero_documento = numero
        fiduciario.telefono = (form.telefono.data or "").strip() or None
        fiduciario.email = (form.email.data or "").strip() or None
        fiduciario.direccion = (form.direccion.data or "").strip() or None
        fiduciario.contacto = (form.contacto.data or "").strip() or None
        fiduciario.notas = (form.notas.data or "").strip() or None
        fiduciario.activo = form.activo.data

        db.session.commit()
        flash(f"Fiduciario '{fiduciario.nombre}' actualizado.", "success")
        return redirect(url_for("fiduciarios.listar"))

    return render_template("fiduciarios/form.html", form=form, fiduciario=fiduciario)


@fiduciarios_bp.route("/<int:fiduciario_id>/desactivar", methods=["POST"])
@requiere_permiso("fiduciarios.desactivar")
def desactivar(fiduciario_id: int):
    """Desactiva un fiduciario (HTMX)."""
    fiduciario = db.session.get(Fiduciario, fiduciario_id)
    if fiduciario is None:
        return "Fiduciario no encontrado", 404

    fiduciario.activo = False
    db.session.commit()
    return render_template("fiduciarios/_fila.html", fiduciario=fiduciario)


@fiduciarios_bp.route("/<int:fiduciario_id>/activar", methods=["POST"])
@requiere_permiso("fiduciarios.desactivar")
def activar(fiduciario_id: int):
    """Reactiva un fiduciario (HTMX)."""
    fiduciario = db.session.get(Fiduciario, fiduciario_id)
    if fiduciario is None:
        return "Fiduciario no encontrado", 404

    fiduciario.activo = True
    db.session.commit()
    return render_template("fiduciarios/_fila.html", fiduciario=fiduciario)
