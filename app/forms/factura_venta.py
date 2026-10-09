"""Formularios para facturas de venta."""

from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class CabeceraFacturaForm(FlaskForm):
    """Formulario de cabecera editable del borrador."""

    cliente_id = SelectField(
        "Cliente",
        coerce=int,
        validators=[DataRequired(message="Seleccione un cliente.")],
    )
    fecha_emision = DateField(
        "Fecha de emisión",
        validators=[DataRequired(message="La fecha es obligatoria.")],
    )
    modalidad = SelectField(
        "Modalidad",
        choices=[
            ("fiscal", "Fiscal"),
            ("libre", "Libre"),
            ("digital", "Digital"),
        ],
        validators=[DataRequired()],
    )
    observaciones = TextAreaField(
        "Observaciones",
        validators=[Optional(), Length(max=1000)],
    )


class DescuentoGlobalForm(FlaskForm):
    """Formulario de descuento global.

    Tipo puede ser 'porcentaje' o 'monto_usd'. El valor se interpreta
    según el tipo. El descuento es mutuamente excluyente.
    """

    tipo = SelectField(
        "Tipo",
        choices=[
            ("porcentaje", "Porcentaje (%)"),
            ("monto_usd", "Monto USD"),
        ],
        validators=[DataRequired()],
    )
    valor = DecimalField(
        "Valor",
        places=4,
        validators=[
            DataRequired(message="El valor es obligatorio."),
            NumberRange(min=0, message="El valor no puede ser negativo."),
        ],
    )