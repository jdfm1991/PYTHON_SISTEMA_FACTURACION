"""Excepciones específicas del agente fiscal."""


class FiscalError(Exception):
    """Base para todas las excepciones fiscales."""


class PrinterConnectionError(FiscalError):
    """No se pudo conectar con la impresora fiscal."""


class PrinterNotReadyError(FiscalError):
    """La impresora no está lista para operar."""

    def __init__(self, status: str, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Impresora no lista [{status}]: {message}")


class PrinterCommandError(FiscalError):
    """La impresora rechazó un comando."""


class PrinterTimeoutError(FiscalError):
    """Timeout esperando respuesta de la impresora."""