"""Mapa de permisos por rol.

Cada rol tiene un conjunto de permisos. Los wildcards ("*", "productos.*")
se expanden en runtime. El rol "admin" tiene acceso total.

Convención de nombres de permisos: <dominio>.<accion>.
Acciones comunes: ver, crear, editar, desactivar, anular.
"""

PERMISSIONS: dict[str, set[str]] = {
    "admin": {"*"},
    "vendedor": {
        "dashboard.ver",
        "clientes.ver",
        "clientes.crear",
        "clientes.editar",
        "productos.ver",
        "alicuotas.ver",
        "tasas_cambio.ver",
        "facturas_venta.ver",
        "facturas_venta.crear",
        "fiduciarios.ver",
    },
    "almacenista": {
        "dashboard.ver",
        "productos.ver",
        "productos.crear",
        "productos.editar",
        "productos.desactivar",
        "alicuotas.ver",
        "proveedores.ver",
        "proveedores.crear",
        "proveedores.editar",
        "facturas_compra.ver",
        "facturas_compra.crear",
        "tasas_cambio.ver",
    },
    "contador": {
        "dashboard.ver",
        "clientes.ver",
        "proveedores.ver",
        "productos.ver",
        "alicuotas.ver",
        "alicuotas.editar",
        "tasas_cambio.ver",
        "tasas_cambio.crear",
        "tasas_cambio.editar",
        "facturas_venta.ver",
        "facturas_venta.anular",
        "facturas_compra.ver",
        "facturas_compra.anular",
        "fiduciarios.ver",
        "fiduciarios.crear",
        "fiduciarios.editar",
    },
}

ROLES_DISPONIBLES = list(PERMISSIONS.keys())


def tiene_permiso(rol: str, permiso: str) -> bool:
    """Devuelve True si el rol tiene el permiso indicado.

    Soporta wildcards:
    - "*" concede todos los permisos.
    - "productos.*" concede todos los permisos del dominio "productos".
    """
    if rol not in PERMISSIONS:
        return False

    permisos = PERMISSIONS[rol]
    if "*" in permisos:
        return True
    if permiso in permisos:
        return True

    # Wildcard de dominio: "productos.*" concede "productos.crear", "productos.ver", etc.
    dominio = permiso.split(".", 1)[0]
    if f"{dominio}.*" in permisos:
        return True

    return False
