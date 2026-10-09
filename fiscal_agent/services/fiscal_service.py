import logging
import threading
import time

from fiscal_agent.config import Config
from fiscal_agent.constants import COMANDOS_PERMITIDOS
from fiscal_agent.printer.exceptions import (
    PrinterCommandError,
    PrinterTimeoutError,
)
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
    """Servicio de operaciones fiscales con lock y reintentos."""

    def __init__(self):
        self._printer: HKAPrinter | None = None
        self._lock = threading.Lock()

    def _get_printer(self) -> HKAPrinter:
        """Devuelve la impresora, abriéndola si es necesario."""
        if self._printer is None or not self._printer.is_open():
            self._printer = HKAPrinter()
            self._printer.open()
        return self._printer

    def _con_reintentos(self, operacion, *args, **kwargs):
        """Ejecuta una operación con reintentos.

        Si falla con PrinterCommandError o PrinterTimeoutError,
        reintenta hasta PRINTER_MAX_RETRIES veces.
        """
        ultimo_error = None
        max_intentos = Config.PRINTER_MAX_RETRIES

        for intento in range(max_intentos):
            try:
                return operacion(*args, **kwargs)
            except (PrinterCommandError, PrinterTimeoutError) as e:
                ultimo_error = e
                if intento < max_intentos - 1:
                    logger.warning(
                        f"Intento {intento + 1} falló: {e}. "
                        f"Reintentando en {Config.PRINTER_RETRY_DELAY}s..."
                    )
                    time.sleep(Config.PRINTER_RETRY_DELAY)
                else:
                    logger.error(
                        f"Todos los reintentos fallaron: {e}"
                    )

        raise ultimo_error

    def get_status(self) -> PrinterStatus:
        """Obtiene el estado actual de la impresora."""
        with self._lock:
            return self._get_printer().get_status()

    def get_info(self) -> PrinterInfo:
        """Obtiene la información S1 de la impresora."""
        with self._lock:
            return self._get_printer().get_info()

    def reset(self) -> None:
        """Cierra la conexión con la impresora."""
        with self._lock:
            if self._printer is not None:
                logger.info("Reset: cerrando conexión actual...")
                self._printer.close()
                self._printer = None
            logger.info("Reset: conexión cerrada.")

    def cancelar_transaccion_pendiente(self) -> bool:
        """Cancela una transacción fiscal pendiente."""
        with self._lock:
            return self._get_printer().cancelar_transaccion_pendiente()

    def enviar_comando(self, nombre_comando: str) -> str:
        """Envía un comando crudo permitido por la whitelist."""
        if nombre_comando not in COMANDOS_PERMITIDOS:
            raise PrinterCommandError(
                f"Comando '{nombre_comando}' no permitido. "
                f"Comandos válidos: {list(COMANDOS_PERMITIDOS.keys())}"
            )

        comando_real = COMANDOS_PERMITIDOS[nombre_comando]

        with self._lock:
            return self._con_reintentos(
                self._get_printer().send_command,
                comando_real,
            )

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
        """Imprime texto simple como Documento No Fiscal."""
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
        """Imprime una factura fiscal."""
        with self._lock:
            return self._get_printer().imprimir_factura(
                cliente=cliente,
                lineas=lineas,
                pagos=pagos,
            )

# Instancia global del servicio
fiscal_service = FiscalService()