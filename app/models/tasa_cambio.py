from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TasaCambio(db.Model):
    """Histórico de tasas de cambio VES/USD."""

    __tablename__ = "tasa_cambio"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    tasa_bcv: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tasa_paralela: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    fuente: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TasaCambio {self.fecha} BCV={self.tasa_bcv}>"