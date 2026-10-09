from flask import abort, redirect, request, url_for
from flask_login import current_user
from functools import wraps


def requiere_permiso(permiso: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.full_path))

            from app.security.permissions import tiene_permiso
            if not tiene_permiso(current_user.rol, permiso):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator