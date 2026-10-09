from flask import Flask, render_template

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    """Fábrica de la aplicación Flask."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Callback de Flask-Login para cargar el usuario desde la sesión
    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(Usuario, int(user_id))

    # Modelos (Alembic)
    from app import models  # noqa: F401

    # Blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.clientes import clientes_bp
    from app.routes.proveedores import proveedores_bp
    from app.routes.productos import productos_bp
    from app.routes.facturas_venta import facturas_venta_bp
    from app.routes.facturas_compra import facturas_compra_bp
    from app.routes.tasas_cambio import tasas_cambio_bp
    from app.routes.alicuotas_iva import alicuotas_iva_bp
    from app.routes.usuarios import usuarios_bp
    from app.routes.fiduciarios import fiduciarios_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(facturas_venta_bp)
    app.register_blueprint(facturas_compra_bp)
    app.register_blueprint(tasas_cambio_bp)
    app.register_blueprint(alicuotas_iva_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(fiduciarios_bp)

    # Manejo de errores
    @app.errorhandler(403)
    def prohibido(error):
        return render_template("errores/403.html"), 403

    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("errores/404.html"), 404

    @app.errorhandler(500)
    def error_interno(error):
        return render_template("errores/500.html"), 500

    # Comandos CLI
    from app.seed import register_seed_command

    register_seed_command(app)

    return app
