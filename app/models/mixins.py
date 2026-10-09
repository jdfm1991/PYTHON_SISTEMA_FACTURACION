from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Mixin que agrega fecha_creacion y fecha_actualizacion.

    Se hereda en modelos que necesitan auditoría temporal básica.
    No es una tabla por sí mismo; sus columnas se agregan a quien lo herede.
    """

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )