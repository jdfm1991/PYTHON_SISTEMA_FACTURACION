"""Datos iniciales del sistema.

Ejecutar con:
    flask seed

Registrar el comando en create_app():
    from app.seed import register_seed_command
    register_seed_command(app)
"""

from decimal import Decimal

from flask import Flask

from app.extensions import db
from app.models import AlicuotaIVA, Usuario

import click 
from flask.cli import with_appcontext

ALICUOTAS_INICIALES = [
    {
        "codigo": "EXENTA",
        "descripcion": "Alícuota Exenta o 0%",
        "porcentaje": Decimal("0.00"),
    },
    {
        "codigo": "REDUCIDA",
        "descripcion": "Alícuota Reducida 8%",
        "porcentaje": Decimal("8.00"),
    },
    {
        "codigo": "GENERAL",
        "descripcion": "Alícuota General 16%",
        "porcentaje": Decimal("16.00"),
    },
    {
        "codigo": "SUNTUARIA",
        "descripcion": "Alícuota Suntuaria o de Lujo 31%",
        "porcentaje": Decimal("31.00"),
    },
]


def seed_alicuotas() -> None:
    """Inserta las alícuotas de IVA si no existen. Idempotente."""
    for datos in ALICUOTAS_INICIALES:
        existente = db.session.execute(
            db.select(AlicuotaIVA).filter_by(codigo=datos["codigo"])
        ).scalar_one_or_none()
        if existente is None:
            db.session.add(AlicuotaIVA(**datos))
    db.session.commit()


def register_seed_command(app: Flask) -> None:
    """Registra `flask seed` como comando CLI."""

    @app.cli.command("seed")
    def seed_command() -> None:
        """Carga datos iniciales (idempotente)."""
        seed_alicuotas()
        print("Seed ejecutado correctamente.")

        


def register_seed_command(app: Flask) -> None:
    """Registra los comandos CLI `flask seed` y `flask crear-admin`."""

    @app.cli.command("seed")
    def seed_command() -> None:
        """Carga datos iniciales (idempotente)."""
        seed_alicuotas()
        print("Seed ejecutado correctamente.")

    @app.cli.command("crear-admin")
    @click.option("--username", prompt=True, help="Nombre de usuario")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Contraseña",
    )
    @click.option("--email", default=None, help="Email (opcional)")
    @click.option("--nombre", default=None, help="Nombre completo (opcional)")
    @with_appcontext
    def crear_admin_command(username, password, email, nombre):
        """Crea el usuario admin inicial."""
        existente = db.session.scalar(db.select(Usuario).filter_by(username=username))
        if existente:
            print(f"El usuario '{username}' ya existe.")
            return

        admin = Usuario(
            username=username,
            email=email,
            nombre_completo=nombre,
            rol="admin",
            activo=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Usuario admin '{username}' creado correctamente.")
