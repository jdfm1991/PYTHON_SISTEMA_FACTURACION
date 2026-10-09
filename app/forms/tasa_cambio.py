from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, DecimalField, StringField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional, Length


class TasaCambioForm(FlaskForm):
    """Formulario de alta/edición de tasas de cambio."""

    fecha = DateField(
        "Fecha",
        validators=[DataRequired(message="La fecha es obligatoria.")],
    )
    tasa_bcv = DecimalField(
        "Tasa BCV (VES/USD)",
        places=8,
        validators=[
            DataRequired(message="La tasa BCV es obligatoria."),
            NumberRange(
                min=0.00000001,
                message="La tasa debe ser mayor que cero.",
            ),
        ],
    )
    tasa_paralela = DecimalField(
        "Tasa paralela (VES/USD)",
        places=8,
        validators=[
            Optional(),
            NumberRange(
                min=0.00000001,
                message="La tasa debe ser mayor que cero.",
            ),
        ],
    )
    fuente = StringField(
        "Fuente",
        validators=[Optional(), Length(max=50, message="Máximo 50 caracteres.")],
        default="BCV",
    )
    submit = SubmitField("Guardar")