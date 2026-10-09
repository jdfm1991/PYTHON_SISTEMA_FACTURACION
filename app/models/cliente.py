from datetime import datetime

from decimal import Decimal
from sqlalchemy import Boolean, DateTime, String, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Cliente(db.Model):
    """Clientes del sistema."""

    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_documento: Mapped[str] = mapped_column(String(1), nullable=False)
    numero_documento: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    razon_social: Mapped[str] = mapped_column(String(200), nullable=False)
    nombre_comercial: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        # --- Crédito ---
    tiene_credito: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    limite_credito_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    dias_credito: Mapped[int | None] = mapped_column(nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Cliente {self.tipo_documento}-{self.numero_documento} {self.razon_social}>"