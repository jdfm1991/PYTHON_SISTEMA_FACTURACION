from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class PagoFacturaVenta(db.Model):
    """Pago (individual o parte de un pago mixto) de una factura de venta.

    Una factura puede tener 0, 1 o N pagos.
    Si la suma de pagos < total de la factura, se genera CuentaPorCobrar.
    """

    __tablename__ = "pago_factura_venta"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_venta_id: Mapped[int] = mapped_column(
        ForeignKey("factura_venta.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # efectivo | transferencia | tarjeta_credito | tarjeta_debito | pago_movil | credito
    forma_pago: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    monto_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    monto_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Snapshot de la tasa al momento del pago.
    # Un pago en VES hecho días después de la factura usa otra tasa.
    tasa_cambio_valor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
        # --- Moneda e IGTF ---
    moneda_pago: Mapped[str] = mapped_column(
        String(3), nullable=False, default="VES", server_default="VES"
    )
    aplica_igtf: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    monto_igtf_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000"),
        server_default="0.0000"
    )
    monto_igtf_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000"),
        server_default="0.0000"
    )

    # --- Relaciones ORM ---
    factura: Mapped["FacturaVenta"] = relationship(back_populates="pagos")

    def __repr__(self) -> str:
        return (
            f"<PagoFacturaVenta factura={self.factura_venta_id} "
            f"forma={self.forma_pago} monto_usd={self.monto_usd}>"
        )