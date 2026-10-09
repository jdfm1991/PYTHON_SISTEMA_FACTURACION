"""Cliente HTTP para comunicarse con el agente fiscal.

El sistema web NO habla directamente con la impresora.
Llama al agente por HTTP en localhost.
"""

from enum import Enum
from dataclasses import dataclass
from app.config import Config
import requests
import logging

logger = logging.getLogger(__name__)


class EstadoImpresion(str, Enum):
    """Estado de la impresión fiscal."""

    EXITOSA_CON_NUMERO = "exitosa_con_numero"  # Agente OK, número leído
    EXITOSA_SIN_NUMERO = "exitosa_sin_numero"  # Agente OK, número no leído (DT-001)
    AGENTE_NO_DISPONIBLE = "agente_no_disponible"  # Agente apagado, timeout, etc.
    ERROR_AGENTE = "error_agente"


@dataclass
class ResultadoImpresion:
    """Resultado de una impresión fiscal."""

    estado: EstadoImpresion
    numero_fiscal: int | None
    serie: str | None
    numero_maquina: str | None
    mensaje: str
    error: str | None = None

    @property
    def exito(self) -> bool:
        """True si la factura fue emitida (con o sin número leído)."""
        return self.estado in (
            EstadoImpresion.EXITOSA_CON_NUMERO,
            EstadoImpresion.EXITOSA_SIN_NUMERO,
        )

    @property
    def numero_leido(self) -> bool:
        """True si el número fiscal fue leído."""
        return (
            self.estado == EstadoImpresion.EXITOSA_CON_NUMERO
            and self.numero_fiscal is not None
        )


class FiscalClient:
    """Cliente HTTP del agente fiscal."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or Config.FISCAL_AGENT_URL).rstrip("/")
        self.timeout = timeout or Config.FISCAL_AGENT_TIMEOUT

    # --- Health check ---

    def health(self) -> bool:
        """Verifica que el agente esté corriendo (sin verificar impresora)."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def estado_formateado(self) -> dict | None:
        """Obtiene el estado del agente y la impresora."""
        try:
            r = requests.get(f"{self.base_url}/estado-formateado", timeout=self.timeout)
            if r.status_code == 200:
                return r.json()
            return None
        except requests.RequestException as e:
            logger.warning(f"Error al consultar estado del agente: {e}")
            return None

    # --- Impresión de factura ---

    def imprimir_factura(self, payload: dict) -> ResultadoImpresion:
        """Envía una factura al agente fiscal."""
        try:
            r = requests.post(
                f"{self.base_url}/imprimir-factura",
                json=payload,
                timeout=self.timeout,
            )

            if r.status_code == 200:
                data = r.json()
                resultado = data.get("resultado", {})
                exito = resultado.get("exito", False)
                numero_fiscal = resultado.get("numero_fiscal")
                numero_maquina = resultado.get("numero_maquina")
                mensaje = resultado.get("mensaje", "")

                if exito and numero_fiscal is not None:
                    return ResultadoImpresion(
                        estado=EstadoImpresion.EXITOSA_CON_NUMERO,
                        numero_fiscal=numero_fiscal,
                        serie=resultado.get("serie"),
                        numero_maquina=numero_maquina,
                        mensaje=mensaje or "Factura impresa correctamente",
                    )
                elif exito and numero_fiscal is None:
                    # Caso DT-001: factura emitida pero número no leído
                    return ResultadoImpresion(
                        estado=EstadoImpresion.EXITOSA_SIN_NUMERO,
                        numero_fiscal=None,
                        serie=None,
                        numero_maquina=numero_maquina,
                        mensaje=(
                            mensaje or
                            "Factura emitida pero no se pudo leer el número fiscal."
                        ),
                    )
                else:
                    # Agente respondió pero con error
                    return ResultadoImpresion(
                        estado=EstadoImpresion.ERROR_AGENTE,
                        numero_fiscal=None,
                        serie=None,
                        numero_maquina=numero_maquina,
                        mensaje=mensaje or "Error al imprimir",
                    )
            else:
                # Error HTTP (500, 503)
                try:
                    error_data = r.json()
                    error_msg = error_data.get("error", r.text)
                except Exception:
                    error_msg = r.text

                logger.error(
                    f"Agente fiscal devolvió {r.status_code}: {error_msg}"
                )
                return ResultadoImpresion(
                    estado=EstadoImpresion.ERROR_AGENTE,
                    numero_fiscal=None,
                    serie=None,
                    numero_maquina=None,
                    mensaje="Error del agente fiscal",
                    error=error_msg,
                )

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"No se puede conectar al agente fiscal: {e}")
            return ResultadoImpresion(
                estado=EstadoImpresion.AGENTE_NO_DISPONIBLE,
                numero_fiscal=None,
                serie=None,
                numero_maquina=None,
                mensaje="El agente fiscal no está disponible",
                error=str(e),
            )
        except requests.RequestException as e:
            logger.exception("Error inesperado al comunicarse con el agente")
            return ResultadoImpresion(
                estado=EstadoImpresion.AGENTE_NO_DISPONIBLE,
                numero_fiscal=None,
                serie=None,
                numero_maquina=None,
                mensaje="Error inesperado al comunicarse con el agente",
                error=str(e),
            )


# Instancia global
fiscal_client = FiscalClient()
