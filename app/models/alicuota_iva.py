from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class AlicuotaIVA(db.Model):
    """Alícuotas de IVA aplicables en Venezuela."""

    __tablename__ = "alicuota_iva"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(100), nullable=False)
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    def __repr__(self) -> str:
        return f"<AlicuotaIVA {self.codigo} ({self.porcentaje}%)>"