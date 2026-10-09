from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


class ClienteForm(FlaskForm):
    """Formulario de alta/edición de clientes."""

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
    razon_social = StringField(
        "Razón social / Nombre",
        validators=[
            DataRequired(message="La razón social es obligatoria."),
            Length(max=200, message="Máximo 200 caracteres."),
        ],
    )
    nombre_comercial = StringField(
        "Nombre comercial",
        validators=[Optional(), Length(max=200)],
    )
    direccion = StringField(
        "Dirección",
        validators=[Optional(), Length(max=300)],
    )
    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=30)],
    )
    email = StringField(
        "Correo electrónico",
        validators=[Optional(), Email(message="Correo inválido."), Length(max=120)],
    )
    activo = BooleanField("Activo", default=True)
    # --- Crédito ---
    tiene_credito = BooleanField("Crédito habilitado", default=False)
    limite_credito_usd = DecimalField(
        "Límite de crédito (USD)",
        places=4,
        validators=[
            Optional(),
            NumberRange(min=0, message="El límite no puede ser negativo."),
        ],
    )
    dias_credito = IntegerField(
        "Días de crédito",
        validators=[
            Optional(),
            NumberRange(min=1, max=365, message="Entre 1 y 365 días."),
        ],
    )

    submit = SubmitField("Guardar")
