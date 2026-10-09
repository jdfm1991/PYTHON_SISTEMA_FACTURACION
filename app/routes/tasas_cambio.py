from datetime import date

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.extensions import db
from app.forms.tasa_cambio import TasaCambioForm
from app.models import FacturaCompra, FacturaVenta, TasaCambio
from app.security.decorators import requiere_permiso


tasas_cambio_bp = Blueprint(
    "tasas_cambio", __name__, url_prefix="/tasas-cambio"
)

PER_PAGE = 30


def _tasa_vigente():
    """Devuelve la tasa vigente: la más reciente con fecha <= hoy."""
    return db.session.scalar(
        db.select(TasaCambio)
        .filter(TasaCambio.fecha <= date.today())
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )


def _contar_facturas(tasa_id: int) -> int:
    """Devuelve cuántas facturas usaron esta tasa."""
    total_ventas = db.session.scalar(
        db.select(db.func.count(FacturaVenta.id)).filter_by(tasa_cambio_id=tasa_id)
    )
    total_compras = db.session.scalar(
        db.select(db.func.count(FacturaCompra.id)).filter_by(tasa_cambio_id=tasa_id)
    )
    return (total_ventas or 0) + (total_compras or 0)


@tasas_cambio_bp.route("/")
@requiere_permiso("tasas_cambio.ver")
def listar():
    """Listado paginado de tasas de cambio."""
    desde = request.args.get("desde", type=str)
    hasta = request.args.get("hasta", type=str)

    query = db.select(TasaCambio)
    if desde:
        try:
            query = query.filter(TasaCambio.fecha >= date.fromisoformat(desde))
        except ValueError:
            flash("Fecha 'desde' inválida, se ignora.", "warning")
            desde = None
    if hasta:
        try:
            query = query.filter(TasaCambio.fecha <= date.fromisoformat(hasta))
        except ValueError:
            flash("Fecha 'hasta' inválida, se ignora.", "warning")
            hasta = None

    query = query.order_by(TasaCambio.fecha.desc())

    paginacion = db.paginate(
        query,
        page=request.args.get("page", 1, type=int),
        per_page=PER_PAGE,
        error_out=False,
    )

    # Conteo de facturas por cada tasa mostrada
    conteos = {
        tasa.id: _contar_facturas(tasa.id) for tasa in paginacion.items
    }

    vigente = _tasa_vigente()

    contexto = {
        "paginacion": paginacion,
        "conteos": conteos,
        "vigente": vigente,
        "desde": desde,
        "hasta": hasta,
    }

    if request.headers.get("HX-Request") == "true":
        return render_template("tasas_cambio/_tabla.html", **contexto)

    return render_template("tasas_cambio/listar.html", **contexto)


@tasas_cambio_bp.route("/crear", methods=["GET", "POST"])
@requiere_permiso("tasas_cambio.crear")
def crear():
    """Alta de nueva tasa de cambio."""
    form = TasaCambioForm()
    if form.validate_on_submit():
        # Verificar unicidad de fecha
        existente = db.session.scalar(
            db.select(TasaCambio).filter_by(fecha=form.fecha.data)
        )
        if existente:
            form.fecha.errors.append(
                "Ya existe una tasa registrada para esa fecha."
            )
            return render_template("tasas_cambio/form.html", form=form, tasa=None)

        tasa = TasaCambio(
            fecha=form.fecha.data,
            tasa_bcv=form.tasa_bcv.data,
            tasa_paralela=form.tasa_paralela.data,
            fuente=(form.fuente.data or "BCV").strip() or None,
        )
        db.session.add(tasa)
        db.session.commit()
        flash(
            f"Tasa del {tasa.fecha} registrada correctamente.", "success"
        )
        return redirect(url_for("tasas_cambio.listar"))

    return render_template("tasas_cambio/form.html", form=form, tasa=None)


@tasas_cambio_bp.route("/<int:tasa_id>/editar", methods=["GET", "POST"])
@requiere_permiso("tasas_cambio.editar")
def editar(tasa_id: int):
    """Edición de tasa existente."""
    tasa = db.session.get(TasaCambio, tasa_id)
    if tasa is None:
        flash("Tasa no encontrada.", "error")
        return redirect(url_for("tasas_cambio.listar"))

    # Contar facturas que usan esta tasa (para mostrar advertencia)
    facturas_usando = _contar_facturas(tasa.id)

    form = TasaCambioForm(obj=tasa)
    if form.validate_on_submit():
        # Verificar unicidad de fecha (excluyendo la propia)
        if form.fecha.data != tasa.fecha:
            existente = db.session.scalar(
                db.select(TasaCambio).filter(
                    TasaCambio.fecha == form.fecha.data,
                    TasaCambio.id != tasa.id,
                )
            )
            if existente:
                form.fecha.errors.append(
                    "Ya existe otra tasa registrada para esa fecha."
                )
                return render_template(
                    "tasas_cambio/form.html",
                    form=form,
                    tasa=tasa,
                    facturas_usando=facturas_usando,
                )

        tasa.fecha = form.fecha.data
        tasa.tasa_bcv = form.tasa_bcv.data
        tasa.tasa_paralela = form.tasa_paralela.data
        tasa.fuente = (form.fuente.data or "").strip() or None

        db.session.commit()
        flash(f"Tasa del {tasa.fecha} actualizada.", "success")
        return redirect(url_for("tasas_cambio.listar"))

    return render_template(
        "tasas_cambio/form.html",
        form=form,
        tasa=tasa,
        facturas_usando=facturas_usando,
    )