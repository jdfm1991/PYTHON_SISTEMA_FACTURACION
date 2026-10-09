from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class PagoFacturaCompra(db.Model):
    """Pago de una factura de compra.

    A diferencia de las ventas, NO se separa el IGTF. El IGTF es un
    impuesto del proveedor, no del comercio. Se registra como parte
    del monto del pago.
    """

    __tablename__ = "pago_factura_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_compra_id: Mapped[int] = mapped_column(
        ForeignKey("factura_compra.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # efectivo_ves | efectivo_usd | transferencia_ves | ... | credito
    forma_pago: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    moneda_pago: Mapped[str] = mapped_column(
        String(3), nullable=False, default="VES", server_default="VES"
    )

    monto_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    monto_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    tasa_cambio_valor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    factura: Mapped["FacturaCompra"] = relationship(back_populates="pagos")

    def __repr__(self) -> str:
        return (
            f"<PagoFacturaCompra factura={self.factura_compra_id} "
            f"forma={self.forma_pago} monto_usd={self.monto_usd}>"
        )