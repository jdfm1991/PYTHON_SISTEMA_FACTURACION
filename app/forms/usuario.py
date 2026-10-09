from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from app.security.permissions import ROLES_DISPONIBLES


class UsuarioForm(FlaskForm):
    """Formulario de alta/edición de usuarios (admin)."""

    username = StringField(
        "Usuario",
        validators=[
            DataRequired(message="El usuario es obligatorio."),
            Length(min=3, max=50, message="Entre 3 y 50 caracteres."),
        ],
    )
    email = StringField(
        "Email",
        validators=[Optional(), Email(message="Correo inválido."), Length(max=120)],
    )
    nombre_completo = StringField(
        "Nombre completo",
        validators=[Optional(), Length(max=150)],
    )
    rol = SelectField(
        "Rol",
        choices=[(r, r.capitalize()) for r in ROLES_DISPONIBLES],
        validators=[DataRequired(message="Seleccione un rol.")],
    )
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar")


class UsuarioCrearForm(UsuarioForm):
    """Alta de usuario. Incluye contraseña."""

    password = PasswordField(
        "Contraseña",
        validators=[
            DataRequired(message="La contraseña es obligatoria."),
            Length(min=8, message="Mínimo 8 caracteres."),
        ],
    )
    password_confirm = PasswordField(
        "Repetir contraseña",
        validators=[
            DataRequired(message="Repita la contraseña."),
            EqualTo("password", message="Las contraseñas no coinciden."),
        ],
    )


class CambioPasswordForm(FlaskForm):
    """Cambio de contraseña propio."""

    password_actual = PasswordField(
        "Contraseña actual",
        validators=[DataRequired(message="Ingrese su contraseña actual.")],
    )
    password_nuevo = PasswordField(
        "Nueva contraseña",
        validators=[
            DataRequired(message="Ingrese la nueva contraseña."),
            Length(min=8, message="Mínimo 8 caracteres."),
        ],
    )
    password_confirm = PasswordField(
        "Repetir nueva contraseña",
        validators=[
            DataRequired(message="Repita la nueva contraseña."),
            EqualTo("password_nuevo", message="Las contraseñas no coinciden."),
        ],
    )
    submit = SubmitField("Cambiar contraseña")


class ResetPasswordForm(FlaskForm):
    """Reset de contraseña por admin."""

    password_nuevo = PasswordField(
        "Nueva contraseña",
        validators=[
            DataRequired(message="Ingrese la nueva contraseña."),
            Length(min=8, message="Mínimo 8 caracteres."),
        ],
    )
    password_confirm = PasswordField(
        "Repetir nueva contraseña",
        validators=[
            DataRequired(message="Repita la nueva contraseña."),
            EqualTo("password_nuevo", message="Las contraseñas no coinciden."),
        ],
    )
    submit = SubmitField("Resetear contraseña")