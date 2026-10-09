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


class FacturaVenta(TimestampMixin, db.Model):
    """Factura de venta a cliente."""

    __tablename__ = "factura_venta"
    __table_args__ = (
        UniqueConstraint(
            "serie", "numero_fiscal", name="uq_factura_venta_serie_numero"
        ),
        UniqueConstraint(
            "numero_maquina", "numero_fiscal", name="uq_factura_venta_maquina_numero"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Identificación ---
    numero_interno: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    serie: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    numero_fiscal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    numero_maquina: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Relaciones principales ---
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"), nullable=False)
    tasa_cambio_id: Mapped[int] = mapped_column(
        ForeignKey("tasa_cambio.id"), nullable=False
    )
    # Snapshot de la tasa usada (inmutable históricamente)
    tasa_cambio_valor: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    # --- Clasificación ---
    modalidad: Mapped[str] = mapped_column(
        String(20), nullable=False, default="fiscal"
    )  # fiscal | libre | digital
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="borrador", index=True
    )  # borrador | en_impresion | emitida | error_fiscal | anulada | pagada

    # --- Fechas ---
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Montos en USD ---
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

    # --- Montos en VES ---
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

    # --- Tipo de venta y fiduciario ---
    tipo_venta: Mapped[str] = mapped_column(
        String(20), nullable=False, default="contado", server_default="contado"
    )
    fiduciario_id: Mapped[int | None] = mapped_column(
        ForeignKey("fiduciario.id"), nullable=True, index=True
    )

    # --- Vuelto e IGTF ---
    vuelto_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default="0.0000",
    )
    vuelto_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default="0.0000",
    )
    igtf_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default="0.0000",
    )
    igtf_total_ves: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
        server_default="0.0000",
    )
    # --- Anulación ---
    motivo_anulacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_anulacion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anulada_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id"), nullable=True
    )

    # --- Relaciones ORM ---
    cliente: Mapped["Cliente"] = relationship(lazy="joined")
    tasa_cambio: Mapped["TasaCambio"] = relationship(lazy="joined")
    detalles: Mapped[list["DetalleFacturaVenta"]] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pagos: Mapped[list["PagoFacturaVenta"]] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cuenta_por_cobrar: Mapped["CuentaPorCobrar | None"] = relationship(
        back_populates="factura",
        cascade="all, delete-orphan",
        uselist=False,
    )
    fiduciario: Mapped["Fiduciario | None"] = relationship(lazy="joined")
    anulada_por: Mapped["Usuario | None"] = relationship(
        foreign_keys=[anulada_por_id], lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<FacturaVenta {self.numero_interno} estado={self.estado}>"
