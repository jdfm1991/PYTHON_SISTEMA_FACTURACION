from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin


class Usuario(UserMixin, TimestampMixin, db.Model):
    """Usuario del sistema con rol asignado.

    Hereda de UserMixin para obtener los métodos que Flask-Login espera:
    is_authenticated, is_active, is_anonymous, get_id.
    """

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(120), unique=True, nullable=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_completo: Mapped[str | None] = mapped_column(String(150), nullable=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="vendedor")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        """Genera el hash y lo guarda. Nunca guardar la contraseña en claro."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica un intento contra el hash almacenado."""
        return check_password_hash(self.password_hash, password)

    # Flask-Login usa `is_active` para saber si el usuario puede iniciar sesión.
    # Sobreescribimos UserMixin.is_active para respetar nuestro campo `activo`.
    @property
    def is_active(self) -> bool:
        return self.activo

    def __repr__(self) -> str:
        return f"<Usuario {self.username} rol={self.rol}>"