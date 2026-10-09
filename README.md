# Sistema de Facturación e Inventario

Sistema web de facturación e inventario para pequeños comercios, con agente
de impresión fiscal independiente.

## Componentes

### 1. Sistema Web (`app/`)

Aplicación Flask con gestión de catálogos, facturación, inventario y usuarios.

**Entorno virtual:** `venv-web/`

**Instalación:**
```bash
python -m venv venv-web
venv-web\Scripts\activate       # Windows
pip install -r requirements.txt

## Ejecución del agente fiscal

**IMPORTANTE:** el agente debe ejecutarse SIEMPRE desde la raíz del proyecto:

```bash
cd facturacion_inventario     # raíz
python -m fiscal_agent.run_agent


# Deuda Técnica del Agente Fiscal

## DT-001: Error de comunicación post-emisión con emulador VFP HKA

**Estado:** ABIERTA
**Prioridad:** MEDIA
**Fecha:** 2026-10-08

### Descripción
Después de emitir una factura fiscal en el emulador VFP HKA, la comunicación
serie se corrompe. El agente no puede leer el número fiscal desde S1.

### Síntomas
- La factura SÍ se emite (visible en el papel del emulador).
- El contador de facturas incrementa.
- El agente no puede leer el número fiscal.
- El emulador queda en estado inconsistente.

### Causa probable
Incompatibilidad entre SDK Tfhka y emulador VFP HKA (versiones antiguas).

### Impacto
- ALTO en producción (no se lee número fiscal automáticamente).
- BAJO en MVP (la factura se emite, el número aparece en el ticket).

### Mitigación actual
- El agente devuelve exito=True con numero_fiscal=None.
- El sistema web registra "emitida sin número fiscal".
- El usuario ingresa el número manualmente desde el ticket.

### Solución propuesta
1. Probar con impresora fiscal física.
2. Probar con SDK actualizado.
3. Probar con otro emulador.
4. Contactar a HKA.
5. Implementar lectura diferida del número fiscal.

### Criterio de cierre
El agente puede leer el número fiscal automáticamente después de emitir
una factura en hardware real.