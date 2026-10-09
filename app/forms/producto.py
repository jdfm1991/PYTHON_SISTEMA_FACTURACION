from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
)

from app.extensions import db
from app.models import AlicuotaIVA


class ProductoForm(FlaskForm):
    """Formulario de alta/edición de productos.

    Nota: `stock_actual` no está aquí. Solo se modifica
    a través de movimientos de inventario (FASE 4).
    """

    codigo = StringField(
        "Código",
        validators=[
            DataRequired(message="El código es obligatorio."),
            Length(max=50, message="Máximo 50 caracteres."),
            Regexp(
                r"^[A-Za-z0-9\-\.\_]+$",
                message="Solo letras, números, guiones, puntos y guion bajo.",
            ),
        ],
    )
    nombre = StringField(
        "Nombre",
        validators=[
            DataRequired(message="El nombre es obligatorio."),
            Length(max=200, message="Máximo 200 caracteres."),
        ],
    )
    descripcion = TextAreaField(
        "Descripción",
        validators=[Optional(), Length(max=500)],
    )
    precio_usd = DecimalField(
        "Precio (USD)",
        places=4,
        validators=[
            DataRequired(message="El precio es obligatorio."),
            NumberRange(
                min=0.0001,
                message="El precio debe ser mayor que cero.",
            ),
        ],
    )
    alicuota_iva_id = SelectField(
        "Alícuota de IVA",
        coerce=int,
        validators=[DataRequired(message="Seleccione una alícuota.")],
    )
    stock_minimo = DecimalField(
        "Stock mínimo",
        places=3,
        validators=[
            Optional(),
            NumberRange(min=0, message="El stock mínimo no puede ser negativo."),
        ],
    )
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar alícuotas dinámicamente en cada instanciación
        self.alicuota_iva_id.choices = [
            (a.id, f"{a.codigo} ({a.porcentaje}%)")
            for a in db.session.scalars(
                db.select(AlicuotaIVA).order_by(AlicuotaIVA.porcentaje)
            )
        ]