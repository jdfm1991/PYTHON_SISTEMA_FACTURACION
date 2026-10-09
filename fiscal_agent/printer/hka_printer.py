"""Implementación de FiscalPrinter para impresoras HKA.

Usa el SDK oficial `Tfhka` (DLL de Windows). Requiere que el SDK
esté en `fiscal_agent/vendor/Tfhka.py`.
"""

import logging
import sys
from pathlib import Path
import time

from fiscal_agent.config import Config
from fiscal_agent.printer.base import (
    FiscalPrinter,
    PrinterInfo,
    PrinterStatus,
    FacturaCliente,
    FacturaLinea,
    FacturaPago,
    ResultadoFactura,
)
from fiscal_agent.printer.exceptions import (
    PrinterCommandError,
    PrinterConnectionError,
    PrinterNotReadyError,
)

from fiscal_agent.constants import (
    CMD_CORTE_PARCIAL,
    CMD_FEED,
    CMD_NF_ABRIR,
    CMD_NF_CERRAR,
    ERRORES_QUE_REQUIEREN_ATENCION,
    ERROR_MESSAGES,
    MODOS,
    STATUS_DESCRIPTIONS,
    STATUS_READY,
)

from fiscal_agent.printer import commands as cmd_builder

logger = logging.getLogger(__name__)

# Agregar el directorio vendor al sys.path para importar Tfhka
_vendor_dir = str(Config.VENDOR_DIR)
if _vendor_dir not in sys.path:
    sys.path.insert(0, _vendor_dir)

try:
    import Tfhka
except ImportError as e:
    raise ImportError(
        f"No se pudo importar Tfhka. Verifica que esté en {_vendor_dir}. "
        f"Error original: {e}"
    ) from e


# Códigos de estado que indican que la impresora está lista
_READY_STATUS_CODES = {"4", "10"}  # modo fiscal en espera, o carga completa en espera
_READY_ERROR_CODE = "0"


class HKAPrinter(FiscalPrinter):
    """Implementación concreta para impresoras HKA."""

    def __init__(self, port: str = None, baudrate: int = None):
        self.port = port or Config.PRINTER_PORT
        self.baudrate = baudrate or Config.PRINTER_BAUDRATE
        self._printer = Tfhka.Tfhka()
        self._is_open = False

    def open(self) -> None:
        """Abre la conexión con la impresora."""
        if self._is_open:
            logger.debug("La impresora ya está abierta")
            return

        logger.info(f"Abriendo conexión a {self.port} a {self.baudrate} baudios...")
        try:
            if not self._printer.OpenFpctrl(self.port):
                raise PrinterConnectionError(
                    f"No se pudo abrir el puerto {self.port}. "
                    "Verifica que el emulador o impresora esté corriendo."
                )
            self._is_open = True
            logger.info("✓ Conexión establecida")

            # Activar Flag 50 (habilita IGTF y el uso del comando 199)
            # logger.info("Activando Flag 50 (IGTF y cierre con 199)...")
            # try:
            # self._printer.SendCmd("PJ5001")
            # logger.info("✓ Flag 50 activado")
            # except Exception as e:
            # logger.warning(f"No se pudo activar Flag 50: {e}")

        except PrinterConnectionError:
            raise
        except Exception as e:
            raise PrinterConnectionError(f"Error al abrir {self.port}: {e}") from e

    def close(self) -> None:
        """Cierra la conexión."""
        if not self._is_open:
            return
        try:
            self._printer.CloseFpctrl()
            self._is_open = False
            logger.info("Conexión cerrada")
        except Exception as e:
            logger.warning(f"Error al cerrar la conexión: {e}")

    def is_open(self) -> bool:
        return self._is_open

    def _ensure_open(self) -> None:
        """Lanza error si la impresora no está abierta."""
        if not self._is_open:
            raise PrinterConnectionError(
                "La impresora no está abierta. Llama a open() primero."
            )

    def get_status(self) -> PrinterStatus:
        """Lee el estado de la impresora."""
        self._ensure_open()

        try:
            raw = self._printer.ReadFpStatus()
        except Exception as e:
            raise PrinterCommandError(f"Error al leer estado: {e}") from e

        # El retorno es un string con formato "{code}   {error}   {desc}"
        partes = raw.split("   ")
        if len(partes) < 3:
            raise PrinterCommandError(
                f"Formato inesperado en el retorno del estado: {raw!r}"
            )

        code = partes[0].strip()
        error_code = partes[1].strip()

        status_desc = STATUS_DESCRIPTIONS.get(code, f"Estado {code}")
        error_desc = ERROR_MESSAGES.get(error_code, partes[2].strip())

        # Cálculos derivados
        is_ready = code in STATUS_READY and error_code == "0"
        modo = MODOS.get(code, "desconocido")
        puede_imprimir = is_ready and modo == "fiscal"
        requiere_atencion = error_code in ERRORES_QUE_REQUIEREN_ATENCION

        return PrinterStatus(
            code=code,
            description=status_desc,
            error_code=error_code,
            error_description=error_desc,
            is_ready=is_ready,
            modo=modo,
            puede_imprimir=puede_imprimir,
            requiere_atencion=requiere_atencion,
        )

    def get_info(self) -> PrinterInfo:
        """Lee la información S1 de la impresora."""
        self._ensure_open()

        try:
            s1 = self._printer.GetS1PrinterData()
        except Exception as e:
            raise PrinterCommandError(f"Error al leer S1: {e}") from e

        return PrinterInfo(
            rif=s1._rif,
            machine_number=s1._registeredMachineNumber,
            current_date=s1._currentPrinterDate,
            current_time=s1._currentPrinterTime,
            last_invoice_number=s1._lastInvoiceNumber,
            last_nc_number=s1._lastNCNumber,
            last_nd_number=s1._lastDebtNoteNumber,
            daily_closure_counter=s1._dailyClosureCounter,
            fiscal_reports_counter=s1._fiscalReportsCounter,
            audit_reports_counter=s1._auditReportsCounter,
            invoices_today=s1._quantityOfInvoicesToday,
            nc_today=s1._quantityOfNCToday,
            non_fiscal_documents=s1._numberNonFiscalDocuments,
            total_daily_sales=float(s1._totalDailySales),
        )

    def send_command(self, command: str) -> str:
        """Envía un comando crudo y devuelve la respuesta."""
        self._ensure_open()
        logger.debug(f"Enviando comando: {command!r}")
        try:
            return self._printer.SendCmd(command)
        except Exception as e:
            raise PrinterCommandError(f"Error al enviar comando: {e}") from e

    def imprimir_texto_simple(self, texto: str) -> None:
        """Imprime texto simple como Documento No Fiscal."""
        self._ensure_open()

        logger.debug(f"Imprimiendo texto: {texto!r}")

        # Abrir Documento No Fiscal con el texto
        self._printer.SendCmd(f"800{texto}")

        # Cerrar el Documento No Fiscal (comando independiente)
        self._printer.SendCmd("810")

    def avanzar_papel(self, lineas: int = 3) -> None:
        """Avanza el papel algunas líneas.

        ADVERTENCIA: verificar el comando en el manual de la impresora.
        """
        self._ensure_open()
        logger.debug(f"Avanzando {lineas} líneas de papel")
        for _ in range(lineas):
            try:
                self._printer.SendCmd(CMD_FEED)
            except Exception as e:
                logger.warning(f"Error al avanzar papel: {e}")
                break

    def cortar_papel(self) -> None:
        """Corta el papel.

        ADVERTENCIA: verificar el comando en el manual.
        Algunos modelos no soportan corte total.
        """
        self._ensure_open()
        logger.debug("Cortando papel")
        try:
            self._printer.SendCmd(CMD_CORTE_PARCIAL)
        except Exception as e:
            logger.warning(f"Error al cortar papel: {e}")

    def _enviar_datos_cliente(self, cliente: FacturaCliente) -> None:
        """Envía los comandos de datos del cliente."""
        self._printer.SendCmd(
            cmd_builder.comando_cliente_rif(
                cliente.tipo_documento, cliente.numero_documento
            )
        )
        self._printer.SendCmd(cmd_builder.comando_cliente_nombre(cliente.razon_social))

        if cliente.direccion:
            self._printer.SendCmd(
                cmd_builder.comando_cliente_linea(1, cliente.direccion)
            )

    def _enviar_linea(self, linea: FacturaLinea) -> None:
        """Envía una línea de producto."""
        comando = cmd_builder.comando_producto(
            codigo=linea.codigo,
            descripcion=linea.descripcion,
            cantidad=linea.cantidad,
            precio_unitario_ves=linea.precio_unitario_ves,
            alicuota_porcentaje=linea.alicuota_porcentaje,
        )
        self._printer.SendCmd(comando)

    def _enviar_pago(self, pago: FacturaPago) -> None:
        """Envía un pago."""
        comando = cmd_builder.comando_pago(
            forma_pago=pago.forma_pago,
            monto_ves=pago.monto_ves,
        )
        self._printer.SendCmd(comando)

    def imprimir_factura(self, cliente, lineas, pagos):
        """Imprime una factura fiscal completa."""
        self._ensure_open()
        self._verificar_lista() 

        logger.info("=== INICIO DE IMPRESIÓN DE FACTURA ===")

        if not lineas:
            raise PrinterCommandError("La factura debe tener al menos una línea.")

        # --- Verificar estado ANTES de empezar ---
        status_antes = self._printer.ReadFpStatus()
        logger.info(f"Estado antes de imprimir: {status_antes}")
        partes = status_antes.split("   ")
        if len(partes) >= 2:
            codigo = partes[0].strip()
            error_code = partes[1].strip()
            
            if codigo != "4":
                raise PrinterNotReadyError(
                    status=codigo,
                    message=f"La impresora no está lista. Estado: {status_antes}",
                )
            
            if error_code != "0":
                raise PrinterNotReadyError(
                    status=error_code,
                    message=f"La impresora tiene un error: {status_antes}",
                )

        # 1) Datos del cliente
        cmd = cmd_builder.comando_cliente_rif(
            cliente.tipo_documento, cliente.numero_documento
        )
        logger.info(f"  → {cmd!r}")
        self._printer.SendCmd(cmd)

        cmd = cmd_builder.comando_cliente_nombre(cliente.razon_social)
        logger.info(f"  → {cmd!r}")
        self._printer.SendCmd(cmd)

        if cliente.direccion:
            cmd = cmd_builder.comando_cliente_linea(1, cliente.direccion)
            logger.info(f"  → {cmd!r}")
            self._printer.SendCmd(cmd)

        # 2) Líneas de producto
        for i, linea in enumerate(lineas):
            cmd = cmd_builder.comando_producto(
                codigo=linea.codigo,
                descripcion=linea.descripcion,
                cantidad=linea.cantidad,
                precio_unitario_ves=linea.precio_unitario_ves,
                alicuota_porcentaje=linea.alicuota_porcentaje,
            )
            logger.info(f"  Línea {i+1}: {cmd!r}")
            self._printer.SendCmd(cmd)

        # 3) Pago (el cierre es automático)
        if not pagos:
            raise PrinterCommandError(
                "Se requiere al menos un pago para cerrar la factura "
                "(sin 199, el cierre es automático por pago)."
            )

        for i, pago in enumerate(pagos):
            cmd = cmd_builder.comando_pago(pago.forma_pago, pago.monto_ves)
            logger.info(f"  Pago {i+1}: {cmd!r}")
            self._printer.SendCmd(cmd)

        # 4) NO ENVIAR 199.
        #    El cierre es automático cuando el pago cubre el total.

        # 5) Esperar a que el emulador termine
        logger.info("Esperando a que la impresora termine...")
        time.sleep(5)

        # 6) Leer estado para diagnóstico
        try:
            status_despues = self._printer.ReadFpStatus()
            logger.info(f"Estado después del pago: {status_despues}")
        except Exception as e:
            logger.warning(f"Error al leer estado: {e}")

        # 7) Leer S1
        logger.info("Leyendo S1...")
        for intento in range(5):
            try:
                s1 = self._printer.GetS1PrinterData()
                numero_fiscal = int(s1._lastInvoiceNumber)
                numero_maquina = s1._registeredMachineNumber
                logger.info(
                    f"S1 leído: numero_fiscal={numero_fiscal}, "
                    f"numero_maquina={numero_maquina}"
                )

                if numero_fiscal == 0:
                    return ResultadoFactura(
                        exito=False,
                        numero_fiscal=None,
                        serie=None,
                        numero_maquina=numero_maquina,
                        mensaje="La impresora no asignó número fiscal.",
                    )

                return ResultadoFactura(
                    exito=True,
                    numero_fiscal=numero_fiscal,
                    serie=None,
                    numero_maquina=numero_maquina,
                    mensaje="Factura impresa correctamente",
                )
            except Exception as e:
                logger.warning(f"Intento {intento + 1} falló: {e}")
                time.sleep(2)

        return ResultadoFactura(
            exito=True,
            numero_fiscal=None,
            serie=None,
            numero_maquina=None,
            mensaje="Factura emitida pero no se pudo leer el número fiscal.",
        )

    def cancelar_transaccion_pendiente(self) -> bool:
        """Cancela una transacción fiscal pendiente si existe.

        Útil para recuperarse de un estado inconsistente.
        Envía un comando de cancelación o un cierre forzado.
        """
        self._ensure_open()

        try:
            status = self.get_status()
            logger.info(f"Estado actual: {status.code} - {status.description}")

            # Si está emitiendo un documento fiscal (código 5),
            # intentar cerrar con 199 para cancelar.
            if status.code == "5":
                logger.warning(
                    "Transacción fiscal pendiente. Enviando 199 para cerrar..."
                )
                try:
                    self._printer.SendCmd("199")
                    logger.info("199 enviado. Verificando estado...")
                except Exception as e:
                    logger.warning(f"Error al enviar 199: {e}")

            return True
        except Exception as e:
            logger.error(f"Error al cancelar transacción: {e}")
            return False
        
        
    def _verificar_lista(self) -> None:
        """Verifica que la impresora esté lista para operar.
        
        Lanza PrinterNotReadyError si hay error.
        """
        status_raw = self._printer.ReadFpStatus()
        partes = status_raw.split("   ")
        if len(partes) < 2:
            raise PrinterCommandError(
                f"Formato de estado inesperado: {status_raw!r}"
            )
        
        codigo = partes[0].strip()
        error_code = partes[1].strip()
        error_desc = partes[2].strip() if len(partes) >= 3 else ""
        
        if codigo not in _READY_STATUS_CODES:
            raise PrinterNotReadyError(
                status=codigo,
                message=f"Estado no listo: {status_raw}",
            )
        
        if error_code != "0":
            raise PrinterNotReadyError(
                status=error_code,
                message=f"Error activo: {error_desc}",
            )


# Descripciones de estados según el código
_STATUS_DESCRIPTIONS = {
    "0": "Estado desconocido",
    "1": "Modo prueba, en espera",
    "2": "Modo prueba, emitiendo documentos fiscales",
    "3": "Modo prueba, emitiendo documentos no fiscales",
    "4": "Modo fiscal, en espera",
    "5": "Modo fiscal, emitiendo documentos fiscales",
    "6": "Modo fiscal, emitiendo documentos no fiscales",
    "7": "Cercana carga completa, en espera",
    "8": "Cercana carga completa, no fiscales",
    "9": "Cercana carga completa, no fiscales",
    "10": "Carga completa, en espera",
    "11": "Carga completa, fiscales",
    "12": "Carga completa, no fiscales",
}
