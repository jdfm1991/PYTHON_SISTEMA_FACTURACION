"""Script manual para verificar la construcción de comandos."""

import sys
from pathlib import Path

# Agregar la raíz del proyecto al sys.path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


from decimal import Decimal

from fiscal_agent.printer import commands as cmd


def main():
    print("=== Pruebas de construcción de comandos ===\n")
    
    # Cliente
    print("Cliente RIF:", cmd.comando_cliente_rif("V", "12345678"))
    print("Cliente nombre:", cmd.comando_cliente_nombre("Juan Pérez"))
    print("Cliente línea 1:", cmd.comando_cliente_linea(1, "Av. Principal 123"))
    print()

    # Producto
    linea = cmd.comando_producto(
        codigo="P001",
        descripcion="Harina PAN 1kg",
        cantidad=Decimal("2.000"),
        precio_unitario_ves=Decimal("50.6250"),
        alicuota_porcentaje=Decimal("16.00"),
    )
    print("Producto:", linea)
    print()

    # Pago
    pago = cmd.comando_pago(
        forma_pago="efectivo_ves",
        monto_ves=Decimal("117.4500"),
    )
    print("Pago:", pago)
    print()

    # Cerrar
    print("Cerrar factura:", cmd.comando_cerrar_factura())
    print()


if __name__ == "__main__":
    main()