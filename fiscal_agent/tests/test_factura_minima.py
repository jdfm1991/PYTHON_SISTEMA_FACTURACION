"""Prueba mínima de factura fiscal."""

import time
from fiscal_agent.printer.hka_printer import HKAPrinter

printer = HKAPrinter()
printer.open()

print("=== Prueba de factura mínima ===")
print("Activando Flag 50...")
# Activar Flag 50
printer._printer.SendCmd("PJ5001")
time.sleep(0.3)

# Enviar factura
printer._printer.SendCmd("iR*V12345678")
printer._printer.SendCmd("iS*TEST")
printer._printer.SendCmd("!000000100000001000TESTPRODUCTO TEST")
printer._printer.SendCmd("199")

# Verificar estado
estado = printer._printer.ReadFpStatus()
print(f"Estado: {estado}")


# 4. Leer S1
s1 = printer._printer.GetS1PrinterData()
print(f"Número de factura: {s1._lastInvoiceNumber}")

printer.close()
