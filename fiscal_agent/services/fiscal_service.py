"""Servicio fiscal con protección de concurrencia.

Usa un lock global para serializar el acceso a la impresora.
"""

import logging
import threading

from fiscal_agent.constants import COMANDOS_PERMITIDOS
from fiscal_agent.printer.exceptions import PrinterCommandError
from fiscal_agent.printer.hka_printer import HKAPrinter

from fiscal_agent.printer.base import (
    FacturaCliente,
    FacturaLinea,
    FacturaPago,
    ResultadoFactura,
    PrinterInfo,
    PrinterStatus,
)

logger = logging.getLogger(__name__)


class FiscalService:
    """Servicio de operaciones fiscales.

    Todas las operaciones adquieren un lock para garantizar acceso
    exclusivo al puerto COM.
    """

    def __init__(self):
        self._printer: HKAPrinter | None = None
        self._lock = threading.Lock()

    def _get_printer(self) -> HKAPrinter:
        """Devuelve la impresora, abriéndola si es necesario.

        Debe llamarse con el lock adquirido.
        """
        if self._printer is None or not self._printer.is_open():
            self._printer = HKAPrinter()
            self._printer.open()
        return self._printer

    def get_status(self) -> PrinterStatus:
        """Obtiene el estado actual de la impresora."""
        with self._lock:
            return self._get_printer().get_status()

    def get_info(self) -> PrinterInfo:
        """Obtiene la información S1 de la impresora."""
        with self._lock:
            return self._get_printer().get_info()

    def reset(self) -> None:
        """Cierra y reabre la conexión con la impresora.

        Útil si la comunicación se colgó.
        """
        with self._lock:
            if self._printer is not None:
                logger.info("Reset: cerrando conexión actual...")
                self._printer.close()
                self._printer = None
            # La próxima llamada a _get_printer() la reabrirá
            logger.info("Reset: conexión cerrada. Se reabrirá en la próxima operación.")

    def enviar_comando(self, nombre_comando: str) -> str:
        """Envía un comando crudo permitido por la whitelist.

        Args:
            nombre_comando: clave de COMANDOS_PERMITIDOS.

        Returns:
            Respuesta cruda de la impresora.

        Raises:
            PrinterCommandError: si el comando no está permitido.
        """
        if nombre_comando not in COMANDOS_PERMITIDOS:
            raise PrinterCommandError(
                f"Comando '{nombre_comando}' no permitido. "
                f"Comandos válidos: {list(COMANDOS_PERMITIDOS.keys())}"
            )

        comando_real = COMANDOS_PERMITIDOS[nombre_comando]
        logger.debug(f"Enviando comando '{nombre_comando}' ({comando_real})")

        with self._lock:
            return self._get_printer().send_command(comando_real)

    def close(self) -> None:
        """Cierra la conexión con la impresora."""
        with self._lock:
            if self._printer is not None:
                self._printer.close()
                self._printer = None

    def imprimir_texto_simple(
        self,
        texto: str,
        avanzar: bool = True,
        cortar: bool = True,
    ) -> None:
        """Imprime texto simple como Documento No Fiscal.

        Args:
            texto: el texto a imprimir.
            avanzar: si True, avanza el papel al final.
            cortar: si True, corta el papel al final.

        Raises:
            PrinterCommandError: si la impresora rechaza el comando.
        """
        with self._lock:
            printer = self._get_printer()
            printer.imprimir_texto_simple(texto)

            if avanzar:
                printer.avanzar_papel(3)

            if cortar:
                printer.cortar_papel()

    def imprimir_factura(
        self,
        cliente: FacturaCliente,
        lineas: list[FacturaLinea],
        pagos: list[FacturaPago],
    ) -> ResultadoFactura:
        """Imprime una factura fiscal.

        Raises:
            PrinterCommandError: si la impresora rechaza algún comando.
        """
        with self._lock:
            return self._get_printer().imprimir_factura(
                cliente=cliente,
                lineas=lineas,
                pagos=pagos,
            )
            
            
    def cancelar_transaccion_pendiente(self) -> bool:
        with self._lock:
            return self._get_printer().cancelar_transaccion_pendiente()


# Instancia global del servicio
fiscal_service = FiscalService()
