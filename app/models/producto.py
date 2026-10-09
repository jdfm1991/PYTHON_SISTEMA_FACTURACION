from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Producto(db.Model):
    """Productos del catálogo."""

    __tablename__ = "producto"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    precio_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    alicuota_iva_id: Mapped[int] = mapped_column(
        ForeignKey("alicuota_iva.id"), nullable=False
    )
    stock_actual: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=Decimal("0.000"), nullable=False
    )
    stock_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    alicuota_iva: Mapped["AlicuotaIVA"] = relationship(lazy="joined")
    
    movimientos: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="producto",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Producto {self.codigo} {self.nombre}>"