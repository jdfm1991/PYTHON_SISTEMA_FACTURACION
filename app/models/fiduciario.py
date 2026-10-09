from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Fiduciario(db.Model):
    """Tercero financiero (Cashea, financieras, etc.).

    No es un cliente. No compra. Financia compras de clientes y luego
    paga al comercio, cobrándole al cliente por su cuenta.
    """

    __tablename__ = "fiduciario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False, index=True
    )
    tipo_documento: Mapped[str] = mapped_column(String(1), nullable=False)
    numero_documento: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Fiduciario {self.tipo_documento}-{self.numero_documento} {self.nombre}>"