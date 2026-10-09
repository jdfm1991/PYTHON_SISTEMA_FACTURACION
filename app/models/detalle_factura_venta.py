from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class DetalleFacturaVenta(db.Model):
    """Línea de detalle de una factura de venta.

    Guarda snapshots de los datos del producto, precio y alícuota
    para que la factura permanezca inmutable históricamente.
    """

    __tablename__ = "detalle_factura_venta"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_venta_id: Mapped[int] = mapped_column(
        ForeignKey("factura_venta.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), nullable=False)

    # --- Snapshots del producto ---
    codigo_producto: Mapped[str] = mapped_column(String(50), nullable=False)
    nombre_producto: Mapped[str] = mapped_column(String(200), nullable=False)

    # --- Cantidad y precios ---
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    precio_unitario_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    precio_unitario_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # --- IVA ---
    alicuota_iva_id: Mapped[int] = mapped_column(
        ForeignKey("alicuota_iva.id"), nullable=False
    )
    alicuota_iva_porcentaje: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )

    # --- Descuentos (mutuamente excluyentes) ---
    descuento_porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    descuento_monto_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    descuento_monto_ves: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    # --- Totales de línea ---
    subtotal_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    subtotal_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    iva_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    iva_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    total_usd: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    total_ves: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))

    # --- Relaciones ORM ---
    factura: Mapped["FacturaVenta"] = relationship(back_populates="detalles")
    producto: Mapped["Producto"] = relationship(lazy="joined")
    alicuota_iva: Mapped["AlicuotaIVA"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"<DetalleFacturaVenta factura={self.factura_venta_id} producto={self.codigo_producto} cant={self.cantidad}>"