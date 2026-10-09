from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import TimestampMixin


class FacturaCompra(TimestampMixin, db.Model):
    """Factura de compra a proveedor."""

    __tablename__ = "factura_compra"
    __table_args__ = (
        UniqueConstraint("numero_interno", name="uq_factura_compra_numero_interno"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Identificación ---
    numero_interno: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    numero_factura_proveedor: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # --- Relaciones principales ---
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedor.id"), nullable=False
    )
    tasa_cambio_id: Mapped[int] = mapped_column(
        ForeignKey("tasa_cambio.id"), nullable=False
    )
    tasa_cambio_valor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # --- Clasificación ---
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="borrador", index=True
    )  # borrador | emitida | anulada | pagada

    # --- Fechas ---
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_factura_proveedor: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Montos USD y VES (misma estructura que FacturaVenta) ---
    subtotal_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000")
    )
    descuento_global_porcentaje: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    descuento_global_monto_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    base_imponible_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000")
    )
    iva_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000")
    )
    total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0.0000")
    )

    subtotal_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    descuento_global_monto_ves: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    base_imponible_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    iva_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Anulación ---
    motivo_anulacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_anulacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anulada_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )

    # --- Relaciones ORM ---
    proveedor: Mapped["Proveedor"] = relationship(lazy="joined")
    tasa_cambio: Mapped["TasaCambio"] = relationship(lazy="joined")
    detalles: Mapped[list["DetalleFacturaCompra"]] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cuenta_por_pagar: Mapped["CuentaPorPagar | None"] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        uselist=False,
    )
    anulada_por: Mapped["Usuario | None"] = relationship(
        foreign_keys=[anulada_por_id], lazy="joined"
    )
    pagos: Mapped[list["PagoFacturaCompra"]] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<FacturaCompra {self.numero_interno} estado={self.estado}>"
