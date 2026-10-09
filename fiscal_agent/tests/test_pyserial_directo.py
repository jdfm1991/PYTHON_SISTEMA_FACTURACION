"""Prueba con pyserial directo, sin SDK."""
import time
import serial


def main():
    print("=== Prueba con pyserial directo ===")
    
    ser = serial.Serial('COM99', 9600, timeout=2)
    time.sleep(0.5)
    
    comandos = [
        b"iR*V12345678",
        b"iS*TEST",
        b"!000000100000001000TESTPRODUCTO TEST",
        b"199",
    ]
    
    for cmd in comandos:
        print(f"Enviando: {cmd!r}")
        ser.write(cmd)
        time.sleep(0.3)
        # Leer respuesta
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting)
            print(f"  Respuesta: {resp!r}")
    
    time.sleep(1)
    ser.close()
    print("Listo")


if __name__ == "__main__":
    main()