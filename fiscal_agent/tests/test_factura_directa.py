"""Prueba directa de factura enviando comandos uno por uno."""

import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fiscal_agent.printer.hka_printer import HKAPrinter


def main():
    printer = HKAPrinter()
    printer.open()

    print("=== PRUEBA 1: Documento No Fiscal ===")
    try:
        respuesta = printer._printer.SendCmd("800HOLA MUNDO")
        print(f"  Respuesta 800: {respuesta!r}")
        time.sleep(0.3)
        respuesta = printer._printer.SendCmd("810")
        print(f"  Respuesta 810: {respuesta!r}")
    except Exception as e:
        print(f"  ERROR: {e}")

    time.sleep(1)

    print("\n=== PRUEBA 2: Factura Fiscal ===")
    comandos = [
        "iR*V12345678",
        "iS*JUAN PEREZ",
        "!000000100000001000TESTPRODUCTO TEST",
        "199",
    ]
    for i, cmd in enumerate(comandos, 1):
        print(f"[{i}] Enviando: {cmd!r}")
        try:
            respuesta = printer._printer.SendCmd(cmd)
            print(f"    Respuesta: {respuesta!r}")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.5)

    printer.close()


if __name__ == "__main__":
    main()
