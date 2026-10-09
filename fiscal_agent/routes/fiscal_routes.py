"""Rutas HTTP del agente fiscal."""

import logging
from dataclasses import asdict

from flask import Blueprint, jsonify, request

from fiscal_agent.constants import COMANDOS_PERMITIDOS
from fiscal_agent.printer.exceptions import FiscalError, PrinterCommandError
from fiscal_agent.services.fiscal_service import fiscal_service
from datetime import datetime

from fiscal_agent.schemas.factura import ValidacionError, parsear_factura

MAX_TEXTO_LEN = 200

logger = logging.getLogger(__name__)

fiscal_bp = Blueprint("fiscal", __name__)


@fiscal_bp.route("/health", methods=["GET"])
def health():
    """Endpoint de salud. Verifica que el agente esté corriendo.

    Opcionalmente verifica la impresora (parámetro ?check_printer=1).
    """
    check_printer = request.args.get("check_printer", "0") == "1"

    response = {
        "status": "ok",
        "service": "fiscal_agent",
    }

    if check_printer:
        try:
            status = fiscal_service.get_status()
            response["printer"] = {
                "is_ready": status.is_ready,
                "puede_imprimir": status.puede_imprimir,
                "error_code": status.error_code,
                "error_description": status.error_description,
            }
        except FiscalError as e:
            response["printer"] = {
                "is_ready": False,
                "error": str(e),
            }

    return jsonify(response), 200


@fiscal_bp.route("/estado", methods=["GET"])
def estado():
    """Devuelve el estado crudo de la impresora."""
    try:
        status = fiscal_service.get_status()
        return (
            jsonify(
                {
                    "success": True,
                    "status": asdict(status),
                }
            ),
            200,
        )
    except FiscalError as e:
        logger.error(f"Error al obtener estado: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            503,
        )


@fiscal_bp.route("/estado-formateado", methods=["GET"])
def estado_formateado():
    """Devuelve el estado con flags derivados para decisión del cliente."""
    try:
        status = fiscal_service.get_status()
        return (
            jsonify(
                {
                    "success": True,
                    "estado": {
                        "listo_para_operar": status.is_ready,
                        "puede_imprimir": status.puede_imprimir,
                        "requiere_atencion": status.requiere_atencion,
                        "modo": status.modo,
                        "descripcion": status.description,
                        "hay_error": status.error_code != "0",
                        "error": (
                            status.error_description
                            if status.error_code != "0"
                            else None
                        ),
                        "codigos_crudos": {
                            "status": status.code,
                            "error": status.error_code,
                        },
                    },
                }
            ),
            200,
        )
    except FiscalError as e:
        logger.error(f"Error al obtener estado formateado: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "estado": {
                        "listo_para_operar": False,
                        "puede_imprimir": False,
                        "requiere_atencion": True,
                        "modo": "desconocido",
                        "descripcion": "No se puede comunicar con la impresora",
                        "hay_error": True,
                        "error": str(e),
                        "codigos_crudos": None,
                    },
                }
            ),
            503,
        )


@fiscal_bp.route("/info", methods=["GET"])
def info():
    """Devuelve la información S1 de la impresora."""
    try:
        info = fiscal_service.get_info()
        return (
            jsonify(
                {
                    "success": True,
                    "info": asdict(info),
                }
            ),
            200,
        )
    except FiscalError as e:
        logger.error(f"Error al obtener info: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            503,
        )


@fiscal_bp.route("/reset", methods=["POST"])
def reset():
    """Cierra y reabre la conexión con la impresora."""
    try:
        fiscal_service.reset()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Conexión reiniciada. Se reabrirá en la próxima operación.",
                }
            ),
            200,
        )
    except FiscalError as e:
        logger.error(f"Error al hacer reset: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            500,
        )


@fiscal_bp.route("/comandos-permitidos", methods=["GET"])
def comandos_permitidos():
    """Lista los comandos crudos permitidos."""
    return (
        jsonify(
            {
                "success": True,
                "comandos": list(COMANDOS_PERMITIDOS.keys()),
            }
        ),
        200,
    )


@fiscal_bp.route("/comando", methods=["POST"])
def comando():
    """Envía un comando crudo (whitelist)."""
    data = request.get_json(silent=True) or {}
    nombre = data.get("comando", "").strip()

    if not nombre:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Falta el campo 'comando'.",
                }
            ),
            400,
        )

    try:
        respuesta = fiscal_service.enviar_comando(nombre)
        return (
            jsonify(
                {
                    "success": True,
                    "comando": nombre,
                    "respuesta": respuesta,
                }
            ),
            200,
        )
    except PrinterCommandError as e:
        logger.warning(f"Comando inválido o fallido: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": "PrinterCommandError",
                }
            ),
            400,
        )
    except FiscalError as e:
        logger.error(f"Error al enviar comando: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            503,
        )


@fiscal_bp.route("/imprimir-texto", methods=["POST"])
def imprimir_texto():
    """Imprime un texto simple (Documento No Fiscal).

    Body JSON:
        {
            "texto": "Prueba de impresión"
        }
    """
    data = request.get_json(silent=True) or {}
    texto = (data.get("texto") or "").strip()

    if not texto:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "El campo 'texto' es obligatorio.",
                }
            ),
            400,
        )

    if len(texto) > MAX_TEXTO_LEN:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"El texto no puede exceder {MAX_TEXTO_LEN} caracteres.",
                }
            ),
            400,
        )

    try:
        fiscal_service.imprimir_texto_simple(texto)
        logger.info(f"Texto impreso: {texto!r}")

        return (
            jsonify(
                {
                    "success": True,
                    "texto_impreso": texto,
                    "lineas_enviadas": 1,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except PrinterCommandError as e:
        logger.error(f"Error al imprimir texto: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": "PrinterCommandError",
                }
            ),
            500,
        )
    except FiscalError as e:
        logger.error(f"Error fiscal al imprimir: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            503,
        )


@fiscal_bp.route("/imprimir-factura", methods=["POST"])
def imprimir_factura_endpoint():
    """Imprime una factura fiscal completa.

    Body JSON:
        {
            "cliente": {
                "tipo_documento": "V",
                "numero_documento": "12345678",
                "razon_social": "JUAN PEREZ",
                "direccion": "AV. PRINCIPAL, CARACAS"
            },
            "lineas": [
                {
                    "codigo": "P001",
                    "descripcion": "HARINA PAN 1KG",
                    "cantidad": "2.000",
                    "precio_unitario_ves": "50.63",
                    "alicuota_iva": "16.00"
                }
            ],
            "pagos": [
                {
                    "forma_pago": "efectivo_ves",
                    "monto_ves": "117.45"
                }
            ]
        }
    """
    data = request.get_json(silent=True)
    if not data:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "El cuerpo de la petición debe ser JSON válido.",
                }
            ),
            400,
        )

    # Validación
    try:
        cliente, lineas, pagos = parsear_factura(data)
    except ValidacionError as e:
        logger.warning(f"Validación fallida: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": "ValidacionError",
                }
            ),
            400,
        )

    # Impresión
    try:
        resultado = fiscal_service.imprimir_factura(
            cliente=cliente,
            lineas=lineas,
            pagos=pagos,
        )
        logger.info(
            f"Factura impresa: numero={resultado.numero_fiscal} "
            f"serie={resultado.serie}"
        )
        return jsonify(
            {
                "success": resultado.exito,
                "resultado": asdict(resultado),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        ), (200 if resultado.exito else 500)
    except PrinterCommandError as e:
        logger.error(f"Error al imprimir factura: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": "PrinterCommandError",
                }
            ),
            500,
        )
    except FiscalError as e:
        logger.error(f"Error fiscal al imprimir factura: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            ),
            503,
        )


@fiscal_bp.route("/cancelar-transaccion", methods=["POST"])
def cancelar_transaccion():
    """Cancela una transacción fiscal pendiente."""
    try:
        resultado = fiscal_service.cancelar_transaccion_pendiente()
        return (
            jsonify(
                {
                    "success": resultado,
                    "message": (
                        "Transacción cancelada" if resultado else "No se pudo cancelar"
                    ),
                }
            ),
            200,
        )
    except FiscalError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(e),
                }
            ),
            500,
        )
