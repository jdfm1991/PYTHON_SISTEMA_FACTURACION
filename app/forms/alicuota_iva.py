from flask_wtf import FlaskForm
from wtforms import DecimalField, SubmitField
from wtforms.validators import DataRequired, NumberRange


class AlicuotaIVAForm(FlaskForm):
    """Formulario de edición del porcentaje de una alícuota de IVA.

    Solo el porcentaje es editable. Código y descripción son inmutables
    porque representan categorías fiscales definidas por ley.
    """

    porcentaje = DecimalField(
        "Porcentaje (%)",
        places=2,
        validators=[
            DataRequired(message="El porcentaje es obligatorio."),
            NumberRange(
                min=0,
                max=100,
                message="El porcentaje debe estar entre 0 y 100.",
            ),
        ],
    )
    submit = SubmitField("Guardar")