from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import TimestampMixin


class CuentaPorCobrar(TimestampMixin, db.Model):
    """Saldo pendiente de una factura de venta.

    Relación 1:1 con FacturaVenta.
    - tipo_deudor = 'cliente': el cliente debe directamente.
    - tipo_deudor = 'fiduciario': un tercero (Cashea) debe al comercio.
    """

    __tablename__ = "cuenta_por_cobrar"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_venta_id: Mapped[int] = mapped_column(
        ForeignKey("factura_venta.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # cliente | fiduciario
    tipo_deudor: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Solo si tipo_deudor = 'fiduciario'. FK al fiduciario.
    fiduciario_id: Mapped[int | None] = mapped_column(
        ForeignKey("fiduciario.id"), nullable=True, index=True
    )

    # Solo si el deudor es un tercero no registrado como fiduciario
    # (compatibilidad hacia atrás, uso excepcional).
    tercero_nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)

    monto_total_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    monto_total_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    saldo_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    saldo_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # pendiente | parcial | pagada | vencida | incobrable
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendiente", index=True
    )

    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Relaciones ORM ---
    factura: Mapped["FacturaVenta"] = relationship(
        back_populates="cuenta_por_cobrar", uselist=False
    )
    fiduciario: Mapped["Fiduciario | None"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<CuentaPorCobrar factura={self.factura_venta_id} "
            f"deudor={self.tipo_deudor} saldo_usd={self.saldo_usd}>"
        )