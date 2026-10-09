"""Constantes del agente fiscal.

Whitelist de comandos seguros y mapeos de estados/errores.
"""

# --- Comandos crudos permitidos ---
# Solo comandos de lectura o de estado. NO se permiten comandos que
# impriman, emitan documentos fiscales, ni modifiquen configuración.
#
# Formato: clave (lo que envía el cliente) → comando real del SDK
COMANDOS_PERMITIDOS: dict[str, str] = {
    "estado": "s1",  # Leer estado (S1)
    "estado_detallado": "s1",  # Leer estado detallado
    "version": "s2",  # Leer versión del firmware
    "memoria_fiscal": "s3",  # Leer estado de memoria fiscal
    "reporte_auditoria": "s4",  # Leer contador de reportes de auditoría
    "ultima_factura": "s5",  # Leer última factura
}


# --- Descripciones de estados S1 ---
STATUS_DESCRIPTIONS: dict[str, str] = {
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


# --- Modos derivados del código ---
MODOS: dict[str, str] = {
    "0": "desconocido",
    "1": "prueba",
    "2": "prueba",
    "3": "prueba",
    "4": "fiscal",
    "5": "fiscal",
    "6": "fiscal",
    "7": "carga_completa",
    "8": "carga_completa",
    "9": "carga_completa",
    "10": "carga_completa",
    "11": "carga_completa",
    "12": "carga_completa",
}


# --- Códigos de estado que indican "listo para operar" ---
STATUS_READY = {"4", "10"}


# --- Mensajes de error amigables ---
ERROR_MESSAGES: dict[str, str] = {
    "0": "Sin error",
    "1": "Fin del papel. Cargue un nuevo rollo.",
    "2": "Error mecánico en la entrega de papel. Verifique el mecanismo.",
    "3": "Fin de papel y error mecánico. Cargue papel y verifique.",
    "80": "Comando o valor inválido.",
    "84": "Tasa de impuesto inválida.",
    "88": "No hay directivas asignadas.",
    "92": "Comando inválido.",
    "96": "Error fiscal.",
    "100": "Error en la memoria fiscal.",
    "108": "Memoria fiscal llena.",
    "112": "Buffer de la impresora completo.",
    "114": "Impresora no responde o está ocupada.",
    "128": "No se puede comunicar con la impresora. Verifique que esté encendida y en el puerto correcto.",
    "137": "La impresora no responde.",
    "144": "Error de checksum en la comunicación.",
}


# --- Códigos de error que requieren atención del operador ---
ERRORES_QUE_REQUIEREN_ATENCION = {"1", "2", "3", "100", "108"}

# --- Comandos para Documentos No Fiscales ---

# Apertura de un Documento No Fiscal
CMD_NF_ABRIR = "80"  # 800 + texto

# Cierre de un Documento No Fiscal
CMD_NF_CERRAR = "810"  # 810 + texto

# Estilos de texto (dentro de un Documento No Fiscal)
CMD_NF_NEGRITA = "80*"
CMD_NF_EXPANDIDO = "80>"
CMD_NF_CENTRADO = "80!"
CMD_NF_CENTRADO_NEGRITA = "80¡"
CMD_NF_DOBLE_ANCHO_NEGRITA = "80$"

# Comentario (fuera de un Documento No Fiscal)
CMD_COMENTARIO = "@"

# --- Comandos de control (verificar en el manual) ---
# Estos comandos pueden variar según el modelo. Verificar con el fabricante.
CMD_FEED = "A"  # Avance de papel (verificar)
CMD_CORTE_PARCIAL = "C"  # Corte parcial (verificar)
CMD_CORTE_TOTAL = "K"  # Corte total (verificar)


# --- Comandos de factura fiscal ---

# Datos del cliente
CMD_CLIENTE_RIF = "iR*"           # + tipo_documento + numero_documento
CMD_CLIENTE_NOMBRE = "iS*"        # + razon_social
CMD_CLIENTE_LINEA = "i{:02d}"     # + texto (i01..i09)

# Línea de producto: comando_iva + precio + cantidad + codigo + descripcion
CMD_PRODUCTO_IVA_EXENTO = " "     # Espacio = Exento
CMD_PRODUCTO_IVA_GENERAL = "!"    # Tasa 1 (16%)
CMD_PRODUCTO_IVA_REDUCIDA = '"'   # Tasa 2 (8%)
CMD_PRODUCTO_IVA_ADICIONAL = "#"  # Tasa 3 (31%)
CMD_PRODUCTO_IVA_PERCIBIDO = "$"  # Tasa 4

# Pagos
CMD_PAGO = "2"                    # + codigo_medio (2) + monto (12)
CMD_SUBTOTAL = "3"                # Imprime subtotal
CMD_CERRAR_FACTURA = "199"        # Cierra la factura

# Configuración
CMD_FLAG = "PJ{:02d}{:02d}"       # PJ + flag (2) + valor (2)


# --- Mapeos de alícuotas de IVA ---
ALICUOTA_A_COMANDO: dict[str, str] = {
    "0.00": CMD_PRODUCTO_IVA_EXENTO,
    "8.00": CMD_PRODUCTO_IVA_REDUCIDA,
    "16.00": CMD_PRODUCTO_IVA_GENERAL,
    "31.00": CMD_PRODUCTO_IVA_ADICIONAL,
}


# --- Mapeos de formas de pago ---
# NOTA: estos códigos son asumidos. El comerciante debe verificar su
# configuración real en la impresora (comandos PE).
FORMA_PAGO_A_CODIGO: dict[str, str] = {
    "efectivo_ves": "01",
    "transferencia_ves": "02",
    "pago_movil": "03",
    "tarjeta_debito_ves": "13",
    "tarjeta_credito_ves": "14",
    "cashea": "19",
    "efectivo_usd": "20",
    "transferencia_usd": "21",
    "tarjeta_internacional": "22",
    "cripto": "23",
}


# --- Precisión para formateo ---
PRECIO_DECIMALES = 2              # La impresora usa 2 decimales
PRECIO_ENTERO_DIGITOS = 8
CANTIDAD_DECIMALES = 3
CANTIDAD_ENTERO_DIGITOS = 5
MONTO_ENTERO_DIGITOS = 10
MONTO_DECIMALES = 2