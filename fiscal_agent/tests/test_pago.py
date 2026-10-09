"""Prueba de comandos de pago para diagnóstico."""
import sys
import time
from pathlib import Path
from decimal import Decimal

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fiscal_agent.printer.hka_printer import HKAPrinter


def test(nombre, comandos):
    """Ejecuta una prueba con comandos específicos."""
    print(f"\n=== {nombre} ===")
    printer = HKAPrinter()
    printer.open()

    # Estado inicial
    estado = printer._printer.ReadFpStatus()
    print(f"  Estado inicial: {estado}")

    for cmd in comandos:
        print(f"  Enviando: {cmd!r}")
        try:
            printer._printer.SendCmd(cmd)
        except Exception as e:
            print(f"    ERROR: {e}")

    time.sleep(2)

    # Estado final
    try:
        estado = printer._printer.ReadFpStatus()
        print(f"  Estado final: {estado}")
    except Exception as e:
        print(f"  ERROR al leer estado: {e}")

    # S1
    try:
        s1 = printer._printer.GetS1PrinterData()
        print(f"  Número factura: {s1._lastInvoiceNumber}")
        print(f"  Número máquina: {s1._registeredMachineNumber!r}")
    except Exception as e:
        print(f"  ERROR al leer S1: {e}")

    printer.close()
    print()


def main():
    print("=== DIAGNÓSTICO DE COMANDOS DE PAGO ===")

    # Prueba H: Solo el pago
    test("H - Solo el pago (2+01+24706)", [
        "201000000024706",
    ])

    # Prueba A: Pago mínimo
    test("A - Pago mínimo (2+01+1)", [
        "201000000000001",
    ])

    # Prueba B: Pago con tarjeta
    test("B - Pago con tarjeta (2+13+24706)", [
        "213000000024706",
    ])

    # Prueba C: Pago directo 101
    test("C - Pago directo (101)", [
        "101",
    ])

    # Prueba completa con cliente, líneas y pago
    test("Completa", [
        "iR*V12345678",
        "iS*JUAN PEREZ",
        "!000000506300002000P001HARINA PAN 1KG",
        "201000000024706",
    ])


if __name__ == "__main__":
    main()