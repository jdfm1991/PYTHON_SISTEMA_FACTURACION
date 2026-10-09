from flask import Blueprint, render_template

from app.extensions import db
from app.models import Cliente, FacturaVenta, Producto
from app.security.decorators import requiere_permiso


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@requiere_permiso("dashboard.ver")
def dashboard():
    """Página principal del sistema."""
    total_clientes = db.session.scalar(
        db.select(db.func.count(Cliente.id)).filter_by(activo=True)
    )
    total_productos = db.session.scalar(
        db.select(db.func.count(Producto.id)).filter_by(activo=True)
    )
    total_facturas = db.session.scalar(
        db.select(db.func.count(FacturaVenta.id))
    )

    return render_template(
        "dashboard/index.html",
        total_clientes=total_clientes,
        total_productos=total_productos,
        total_facturas=total_facturas,
    )