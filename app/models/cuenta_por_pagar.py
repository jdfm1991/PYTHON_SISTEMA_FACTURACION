from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import TimestampMixin


class CuentaPorPagar(TimestampMixin, db.Model):
    """Saldo pendiente de una factura de compra.

    Relación 1:1 con FacturaCompra. Simétrica a CuentaPorCobrar.
    """

    __tablename__ = "cuenta_por_pagar"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_compra_id: Mapped[int] = mapped_column(
        ForeignKey("factura_compra.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # proveedor | financiera
    tipo_acreedor: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
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

    factura: Mapped["FacturaCompra"] = relationship(
        back_populates="cuenta_por_pagar", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<CuentaPorPagar factura={self.factura_compra_id} "
            f"acreedor={self.tipo_acreedor} saldo_usd={self.saldo_usd}>"
        )