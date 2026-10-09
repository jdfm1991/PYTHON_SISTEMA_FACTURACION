from urllib.parse import urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms.auth import LoginForm
from app.forms.usuario import CambioPasswordForm
from app.models import Usuario

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Inicio de sesión."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        usuario = db.session.scalar(
            db.select(Usuario).filter_by(username=form.username.data.strip())
        )

        if usuario is None or not usuario.check_password(form.password.data):
            # Mensaje genérico: no revelar si el usuario existe
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("auth/login.html", form=form)

        if not usuario.activo:
            flash("Su cuenta está desactivada.", "error")
            return render_template("auth/login.html", form=form)

        login_user(usuario)
        usuario.ultimo_login = db.func.now()
        db.session.commit()

        flash(f"Bienvenido, {usuario.nombre_completo or usuario.username}.", "success")

        # Redirigir a la página que intentaba acceder, si es válida
        next_url = request.args.get("next")
        if next_url and _es_url_segura(next_url):
            return redirect(next_url)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Cierre de sesión."""
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/perfil")
@login_required
def perfil():
    """Página de perfil del usuario actual."""
    return render_template("perfil/index.html")


@auth_bp.route("/perfil/cambiar-password", methods=["GET", "POST"])
@login_required
def cambiar_password():
    """Cambio de contraseña propio."""
    form = CambioPasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.password_actual.data):
            form.password_actual.errors.append("Contraseña actual incorrecta.")
            return render_template("perfil/cambiar_password.html", form=form)

        current_user.set_password(form.password_nuevo.data)
        db.session.commit()
        flash("Contraseña actualizada.", "success")
        return redirect(url_for("auth.perfil"))

    return render_template("perfil/cambiar_password.html", form=form)


def _es_url_segura(url: str) -> bool:
    """Verifica que la URL de redirección sea del mismo dominio.

    Evita ataques de open redirect: si `next` es una URL externa,
    la rechazamos y usamos el dashboard por defecto.
    """
    if not url:
        return False
    parsed = urlparse(url)
    # URL sin netloc (relativa) es segura. URL con netloc debe coincidir con el host.
    return not parsed.netloc or parsed.netloc == request.host