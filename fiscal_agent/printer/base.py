"""Interfaz abstracta para impresoras fiscales.

Cualquier implementación concreta (HKA, otra marca, mock para tests)
debe cumplir este contrato.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PrinterStatus:
    """Estado de la impresora."""

    code: str  # "0" .. "12"
    description: str  # descripción del estado
    error_code: str  # "0", "128", etc.
    error_description: str  # descripción del error
    is_ready: bool  # True si lista para operar

    # --- Campos derivados (calculados a partir de los anteriores) ---
    modo: str = "desconocido"  # "fiscal", "prueba", "carga_completa"
    puede_imprimir: bool = False  # puede emitir documentos fiscales
    requiere_atencion: bool = False  # requiere intervención del operador


@dataclass
class PrinterInfo:
    """Información S1 de la impresora."""

    rif: str
    machine_number: str
    current_date: str
    current_time: str
    last_invoice_number: int
    last_nc_number: int
    last_nd_number: int
    daily_closure_counter: int
    fiscal_reports_counter: int
    audit_reports_counter: int
    invoices_today: int
    nc_today: int
    non_fiscal_documents: int
    total_daily_sales: float


@dataclass
class FacturaLinea:
    """Datos de una línea de factura."""

    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario_ves: Decimal
    alicuota_porcentaje: Decimal


@dataclass
class FacturaPago:
    """Datos de un pago."""

    forma_pago: str
    monto_ves: Decimal


@dataclass
class FacturaCliente:
    """Datos del cliente para la factura."""

    tipo_documento: str
    numero_documento: str
    razon_social: str
    direccion: str | None = None


@dataclass
@dataclass
class ResultadoFactura:
    """Resultado de la impresión de una factura."""

    exito: bool
    numero_fiscal: int | None
    serie: str | None  # ← se queda por compatibilidad, pero no se usa
    numero_maquina: str | None  # ← nuevo
    mensaje: str


class FiscalPrinter(ABC):
    """Interfaz abstracta para impresoras fiscales."""

    @abstractmethod
    def open(self) -> None:
        """Abre la conexión con la impresora."""

    @abstractmethod
    def close(self) -> None:
        """Cierra la conexión."""

    @abstractmethod
    def is_open(self) -> bool:
        """Devuelve True si la conexión está abierta."""

    @abstractmethod
    def get_status(self) -> PrinterStatus:
        """Lee el estado de la impresora."""

    @abstractmethod
    def get_info(self) -> PrinterInfo:
        """Lee la información S1 de la impresora."""

    @abstractmethod
    def send_command(self, command: str) -> str:
        """Envía un comando crudo y devuelve la respuesta."""

    @abstractmethod
    def imprimir_factura(
        self,
        cliente: FacturaCliente,
        lineas: list[FacturaLinea],
        pagos: list[FacturaPago],
    ) -> ResultadoFactura:
        """Imprime una factura fiscal."""
