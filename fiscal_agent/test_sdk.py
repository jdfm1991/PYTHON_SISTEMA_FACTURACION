"""Script de prueba de conexión al emulador VFP HKA.

Ejecutar con:
    python test_sdk.py
"""

import sys
import os

# Agregar vendor/ al path (si el SDK está ahí)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vendor"))

try:
    import Tfhka
except ImportError as e:
    print(f"ERROR: No se pudo importar Tfhka: {e}")
    print()
    print("Verifica que:")
    print("  1. El archivo Tfhka.py esté en vendor/ o en el PYTHONPATH.")
    print("  2. La DLL Tfhkaif.dll esté en el PATH o en la misma carpeta que Tfhka.py.")
    sys.exit(1)


def main():
    print("=== Prueba de conexión al emulador VFP HKA ===")
    print()

    # Crear instancia
    printer = Tfhka.Tfhka()

    # Intentar abrir la conexión
    print("Abriendo conexión a COM99...")
    if not printer.OpenFpctrl("COM99"):
        print("✗ No se pudo abrir COM99")
        print()
        print("Verifica que:")
        print("  1. El emulador VFP HKA esté corriendo.")
        print("  2. El puerto sea COM99.")
        print("  3. El baudrate sea 9600 (por defecto).")
        print("  4. Ningún otro programa esté usando COM99.")
        return

    print("✓ Conexión abierta")
    print()

    # Leer estado
    print("Leyendo estado...")
    try:
        status_str = printer.ReadFpStatus()
        print(f"  Retorno crudo: {status_str!r}")

        # El retorno es un string con partes separadas por tabulaciones
        partes = status_str.split("\t")
        print(f"  Partes: {partes}")

        if len(partes) >= 2:
            print(f"  Estado S1: {partes[0]}")
            print(f"  Estado S2: {partes[1]}")
        if len(partes) >= 3:
            print(f"  Descripción: {partes[2]}")
    except Exception as e:
        print(f"✗ Error al leer estado: {e}")

    print()

    # Leer datos S1
    print("Leyendo datos S1...")
    try:
        s1 = printer.GetS1PrinterData()

        # Atributos reales del objeto
        print(f"  RIF: {s1._rif}")
        print(f"  Máquina registrada: {s1._registeredMachineNumber}")
        print(f"  Fecha: {s1._currentPrinterDate}")
        print(f"  Hora: {s1._currentPrinterTime}")
        print(f"  Último número de factura: {s1._lastInvoiceNumber}")
        print(f"  Último número de NC: {s1._lastNCNumber}")
        print(f"  Último número de ND: {s1._lastDebtNoteNumber}")
        print(f"  Contador cierres diarios (Z): {s1._dailyClosureCounter}")
        print(f"  Contador reportes fiscales: {s1._fiscalReportsCounter}")
        print(f"  Contador reportes de auditoría: {s1._auditReportsCounter}")
        print(f"  Facturas del día: {s1._quantityOfInvoicesToday}")
        print(f"  NC del día: {s1._quantityOfNCToday}")
        print(f"  Documentos no fiscales: {s1._numberNonFiscalDocuments}")
        print(f"  Ventas totales del día: {s1._totalDailySales}")
    except Exception as e:
        print(f"✗ Error al leer S1: {e}")

if __name__ == "__main__":
    main()
