from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class MovimientoInventario(db.Model):
    """Bitácora de movimientos de inventario.

    Cada entrada o salida de stock genera un registro aquí.
    Producto.stock_actual se actualiza en la misma transacción,
    pero este registro es la fuente de auditoría.
    """

    __tablename__ = "movimiento_inventario"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(
        ForeignKey("producto.id"), nullable=False, index=True
    )

    # --- Tipo de movimiento ---
    # entrada | salida | ajuste_positivo | ajuste_negativo (los ajustes vienen en FASE 3)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Cantidad siempre positiva; el tipo da el signo
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Snapshot del stock antes y después (para reconstruir la historia)
    stock_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    stock_nuevo: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # --- Referencia al documento que originó el movimiento ---
    # factura_venta | factura_compra | ajuste_manual
    referencia_tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    referencia_id: Mapped[int | None] = mapped_column(nullable=True, index=True)

    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    fecha_movimiento: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # --- Relaciones ORM ---
    producto: Mapped["Producto"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<MovimientoInventario producto={self.producto_id} "
            f"tipo={self.tipo} cantidad={self.cantidad}>"
        )