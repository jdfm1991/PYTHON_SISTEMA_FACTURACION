from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms.usuario import ResetPasswordForm, UsuarioCrearForm, UsuarioForm
from app.models import Usuario
from app.security.decorators import requiere_permiso

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@usuarios_bp.route("/")
@requiere_permiso("usuarios.ver")
def listar():
    """Listado de usuarios."""
    usuarios = db.session.scalars(
        db.select(Usuario).order_by(Usuario.username)
    ).all()
    return render_template("usuarios/listar.html", usuarios=usuarios)


@usuarios_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("usuarios.crear")
def crear():
    """Alta de usuario."""
    form = UsuarioCrearForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        existente = db.session.scalar(
            db.select(Usuario).filter_by(username=username)
        )
        if existente:
            form.username.errors.append("Ya existe un usuario con ese nombre.")
            return render_template("usuarios/form.html", form=form, usuario=None)

        if form.email.data:
            email_existente = db.session.scalar(
                db.select(Usuario).filter_by(email=form.email.data.strip())
            )
            if email_existente:
                form.email.errors.append("Ya existe un usuario con ese email.")
                return render_template("usuarios/form.html", form=form, usuario=None)

        usuario = Usuario(
            username=username,
            email=(form.email.data or "").strip() or None,
            nombre_completo=(form.nombre_completo.data or "").strip() or None,
            rol=form.rol.data,
            activo=form.activo.data,
        )
        usuario.set_password(form.password.data)

        db.session.add(usuario)
        db.session.commit()
        flash(f"Usuario '{usuario.username}' creado.", "success")
        return redirect(url_for("usuarios.listar"))

    return render_template("usuarios/form.html", form=form, usuario=None)


@usuarios_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@requiere_permiso("usuarios.editar")
def editar(usuario_id: int):
    """Edición de usuario (sin cambiar contraseña)."""
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios.listar"))

    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        username = form.username.data.strip()
        if username != usuario.username:
            existente = db.session.scalar(
                db.select(Usuario).filter(
                    Usuario.username == username, Usuario.id != usuario.id
                )
            )
            if existente:
                form.username.errors.append("Ya existe otro usuario con ese nombre.")
                return render_template("usuarios/form.html", form=form, usuario=usuario)

        usuario.username = username
        usuario.email = (form.email.data or "").strip() or None
        usuario.nombre_completo = (form.nombre_completo.data or "").strip() or None
        usuario.rol = form.rol.data
        usuario.activo = form.activo.data

        db.session.commit()
        flash(f"Usuario '{usuario.username}' actualizado.", "success")
        return redirect(url_for("usuarios.listar"))

    return render_template("usuarios/form.html", form=form, usuario=usuario)


@usuarios_bp.route("/<int:usuario_id>/reset-password", methods=["GET", "POST"])
@requiere_permiso("usuarios.editar")
def reset_password(usuario_id: int):
    """Reset de contraseña por admin."""
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios.listar"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        usuario.set_password(form.password_nuevo.data)
        db.session.commit()
        flash(f"Contraseña de '{usuario.username}' reseteada.", "success")
        return redirect(url_for("usuarios.listar"))

    return render_template("usuarios/reset_password.html", form=form, usuario=usuario)


@usuarios_bp.route("/<int:usuario_id>/desactivar", methods=["POST"])
@requiere_permiso("usuarios.editar")
def desactivar(usuario_id: int):
    """Desactiva un usuario. No puede desactivarse a sí mismo."""
    from flask_login import current_user

    if current_user.id == usuario_id:
        flash("No puedes desactivar tu propia cuenta.", "error")
        return redirect(url_for("usuarios.listar"))

    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios.listar"))

    usuario.activo = False
    db.session.commit()
    flash(f"Usuario '{usuario.username}' desactivado.", "success")
    return redirect(url_for("usuarios.listar"))


@usuarios_bp.route("/<int:usuario_id>/activar", methods=["POST"])
@requiere_permiso("usuarios.editar")
def activar(usuario_id: int):
    """Reactiva un usuario."""
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("usuarios.listar"))

    usuario.activo = True
    db.session.commit()
    flash(f"Usuario '{usuario.username}' activado.", "success")
    return redirect(url_for("usuarios.listar"))