from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp


class FiduciarioForm(FlaskForm):
    """Formulario de alta/edición de fiduciarios."""

    nombre = StringField(
        "Nombre",
        validators=[
            DataRequired(message="El nombre es obligatorio."),
            Length(max=150, message="Máximo 150 caracteres."),
        ],
    )
    tipo_documento = SelectField(
        "Tipo de documento",
        choices=[
            ("V", "V — Venezolano"),
            ("E", "E — Extranjero"),
            ("J", "J — Jurídico"),
            ("P", "P — Pasaporte"),
            ("G", "G — Gubernamental"),
        ],
        validators=[DataRequired(message="Seleccione un tipo de documento.")],
    )
    numero_documento = StringField(
        "Número de documento",
        validators=[
            DataRequired(message="El número de documento es obligatorio."),
            Length(max=20, message="Máximo 20 caracteres."),
            Regexp(r"^[0-9\-]+$", message="Solo dígitos y guiones."),
        ],
    )
    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=30)],
    )
    email = StringField(
        "Correo electrónico",
        validators=[Optional(), Email(message="Correo inválido."), Length(max=120)],
    )
    direccion = StringField(
        "Dirección",
        validators=[Optional(), Length(max=300)],
    )
    contacto = StringField(
        "Persona de contacto",
        validators=[Optional(), Length(max=150)],
    )
    notas = TextAreaField(
        "Notas",
        validators=[Optional(), Length(max=1000)],
    )
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar")