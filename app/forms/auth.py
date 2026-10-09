from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""

    username = StringField(
        "Usuario",
        validators=[DataRequired(message="Ingrese su usuario.")],
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(message="Ingrese su contraseña.")],
    )
    submit = SubmitField("Iniciar sesión")