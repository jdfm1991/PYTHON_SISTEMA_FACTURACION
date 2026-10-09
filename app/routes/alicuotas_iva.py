from flask import Blueprint, flash, redirect, render_template, url_for

from app.extensions import db
from app.forms.alicuota_iva import AlicuotaIVAForm
from app.models import AlicuotaIVA
from app.security.decorators import requiere_permiso

alicuotas_iva_bp = Blueprint(
    "alicuotas_iva", __name__, url_prefix="/alicuotas-iva"
)


@alicuotas_iva_bp.route("/")
@requiere_permiso("alicuotas_iva.ver")
def listar():
    """Listado de todas las alícuotas de IVA."""
    alicuotas = db.session.scalars(
        db.select(AlicuotaIVA).order_by(AlicuotaIVA.porcentaje)
    ).all()

    return render_template("alicuotas_iva/listar.html", alicuotas=alicuotas)


@alicuotas_iva_bp.route("/<int:alicuota_id>/editar", methods=["GET", "POST"])
@requiere_permiso("alicuotas_iva.editar")
def editar(alicuota_id: int):
    """Edición del porcentaje de una alícuota."""
    alicuota = db.session.get(AlicuotaIVA, alicuota_id)
    if alicuota is None:
        flash("Alícuota no encontrada.", "error")
        return redirect(url_for("alicuotas_iva.listar"))

    form = AlicuotaIVAForm(obj=alicuota)
    if form.validate_on_submit():
        alicuota.porcentaje = form.porcentaje.data
        db.session.commit()
        flash(
            f"Alícuota '{alicuota.descripcion}' actualizada a {alicuota.porcentaje}%.",
            "success",
        )
        return redirect(url_for("alicuotas_iva.listar"))

    return render_template(
        "alicuotas_iva/form.html", form=form, alicuota=alicuota
    )