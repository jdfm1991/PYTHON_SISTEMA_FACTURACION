from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


class CabeceraCompraForm(FlaskForm):
    """Formulario de cabecera editable del borrador de compra."""

    proveedor_id = SelectField(
        "Proveedor",
        coerce=int,
        validators=[DataRequired(message="Seleccione un proveedor.")],
    )
    fecha_emision = DateField(
        "Fecha de emisión",
        validators=[DataRequired(message="La fecha es obligatoria.")],
    )
    numero_factura_proveedor = StringField(
        "Número de factura del proveedor",
        validators=[Optional(), Length(max=50)],
    )
    fecha_factura_proveedor = DateField(
        "Fecha de la factura del proveedor",
        validators=[Optional()],
    )
    observaciones = TextAreaField(
        "Observaciones",
        validators=[Optional(), Length(max=1000)],
    )