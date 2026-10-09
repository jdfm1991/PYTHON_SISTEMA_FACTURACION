"""Tests del FacturacionService.confirmar_factura."""

from datetime import date
from decimal import Decimal
from app.extensions import db

import pytest

from app.constants import (
    TIPO_VENTA_CONTADO,
    TIPO_VENTA_CREDITO_DIRECTO,
    TIPO_VENTA_CREDITO_FIDUCIARIO,
)
from app.exceptions import (
    CreditoNoHabilitadoError,
    FacturaSinLineasError,
    FiduciarioNoValidoError,
    LimiteCreditoExcedidoError,
    PagoInvalidoError,
    StockInsuficienteError,
    TipoVentaInvalidoError,
)
from app.models import (
    AlicuotaIVA,
    Cliente,
    CuentaPorCobrar,
    FacturaVenta,
    Fiduciario,
    MovimientoInventario,
    PagoFacturaVenta,
    Producto,
    TasaCambio,
)
from app.services import facturacion


# ---------- Fixtures ----------


@pytest.fixture
def alicuota(db):
    a = AlicuotaIVA(codigo="GENERAL", descripcion="16%", porcentaje=Decimal("16.00"))
    db.session.add(a)
    db.session.flush()
    return a


@pytest.fixture
def tasa(db):
    t = TasaCambio(
        fecha=date.today(),
        tasa_bcv=Decimal("40.00000000"),
        fuente="BCV",
    )
    db.session.add(t)
    db.session.flush()
    return t


@pytest.fixture
def cliente(db):
    c = Cliente(
        tipo_documento="V",
        numero_documento="12345678",
        razon_social="Cliente Test",
        activo=True,
        tiene_credito=False,
    )
    db.session.add(c)
    db.session.flush()
    return c


@pytest.fixture
def cliente_con_credito(db):
    c = Cliente(
        tipo_documento="V",
        numero_documento="87654321",
        razon_social="Cliente Crédito",
        activo=True,
        tiene_credito=True,
        limite_credito_usd=Decimal("500.0000"),
        dias_credito=30,
    )
    db.session.add(c)
    db.session.flush()
    return c


@pytest.fixture
def fiduciario(db):
    f = Fiduciario(
        nombre="Cashea",
        tipo_documento="J",
        numero_documento="J-12345678",
        activo=True,
    )
    db.session.add(f)
    db.session.flush()
    return f


@pytest.fixture
def producto(db, alicuota):
    p = Producto(
        codigo="P001",
        nombre="Producto Test",
        precio_usd=Decimal("100.0000"),
        alicuota_iva_id=alicuota.id,
        stock_actual=Decimal("50.000"),
        activo=True,
    )
    db.session.add(p)
    db.session.flush()
    return p


def _crear_factura_borrador(cliente, producto, tasa, cantidad="1"):
    """Helper para crear un borrador con un detalle."""
    factura = facturacion.crear_borrador(cliente.id)
    facturacion.agregar_detalle(factura, producto.id, Decimal(cantidad))
    db.session.flush()
    return factura


# ---------- Tests ----------


def test_contado_pago_exacto_ves(db, cliente, producto, tasa):
    """Contado, pago exacto en VES. Estado: pagada. Sin CuentaPorCobrar."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    # total_usd = 100 + 16 = 116. En VES: 116 * 40 = 4640
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("4640.0000"),
    }]
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=pagos
    )

    assert factura.estado == "pagada"
    assert factura.tipo_venta == "contado"
    assert factura.vuelto_usd == Decimal("0.0000")
    assert factura.igtf_total_usd == Decimal("0.0000")

    # Movimiento de inventario creado
    movs = db.session.scalars(
        db.select(MovimientoInventario).filter_by(
            referencia_tipo="factura_venta", referencia_id=factura.id
        )
    ).all()
    assert len(movs) == 1
    assert movs[0].cantidad == Decimal("1.000")
    assert producto.stock_actual == Decimal("49.000")

    # Sin CuentaPorCobrar
    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is None


def test_contado_pago_exacto_usd_genera_igtf(db, cliente, producto, tasa):
    """Contado, pago en USD. Se registra IGTF (3%)."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    pagos = [{
        "forma_pago": "efectivo_usd",
        "moneda_pago": "USD",
        "monto": Decimal("116.0000"),
    }]
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=pagos
    )

    assert factura.estado == "pagada"
    assert factura.igtf_total_usd == Decimal("3.4800")  # 116 * 3%
    assert factura.igtf_total_ves == Decimal("139.2000")

    # El pago en sí tiene igtf
    pago = db.session.scalar(db.select(PagoFacturaVenta).filter_by(
        factura_venta_id=factura.id
    ))
    assert pago.aplica_igtf is True
    assert pago.monto_igtf_usd == Decimal("3.4800")


def test_contado_pago_mixto_igtf_solo_sobre_usd(db, cliente, producto, tasa):
    """Contado, pago mixto VES + USD. IGTF solo sobre el monto USD."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    # Total: 116 USD. Pagamos 40 USD + resto (76 USD) en VES.
    # 76 USD * 40 = 3040 VES.
    pagos = [
        {
            "forma_pago": "efectivo_usd",
            "moneda_pago": "USD",
            "monto": Decimal("40.0000"),
        },
        {
            "forma_pago": "transferencia_ves",
            "moneda_pago": "VES",
            "monto": Decimal("3040.0000"),
        },
    ]
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=pagos
    )

    assert factura.estado == "pagada"
    # IGTF solo sobre 40 USD = 1.20
    assert factura.igtf_total_usd == Decimal("1.2000")


def test_contado_pago_mayor_genera_vuelto(db, cliente, producto, tasa):
    """Contado, pago mayor al total. Se calcula vuelto."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    # Total 116. Cliente paga 200.
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("8000.0000"),  # 200 USD * 40
    }]
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=pagos
    )

    assert factura.estado == "pagada"
    # vuelto_usd = 200 - 116 = 84
    assert factura.vuelto_usd == Decimal("84.0000")


def test_contado_pago_parcial_genera_cxc_cliente(db, cliente, producto, tasa):
    """Contado, pago parcial. Genera CuentaPorCobrar al cliente."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("2000.0000"),  # 50 USD
    }]
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=pagos
    )

    assert factura.estado == "emitida"  # queda saldo
    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is not None
    assert cxc.tipo_deudor == "cliente"
    assert cxc.fiduciario_id is None
    # Saldo: 116 - 50 = 66
    assert cxc.saldo_usd == Decimal("66.0000")


def test_credito_directo_sin_pago(db, cliente_con_credito, producto, tasa):
    """Crédito directo, sin pago. CxC al cliente con todo el total."""
    factura = _crear_factura_borrador(cliente_con_credito, producto, tasa)
    factura = facturacion.confirmar_factura(
        factura, tipo_venta=TIPO_VENTA_CREDITO_DIRECTO, pagos=[]
    )

    assert factura.estado == "emitida"
    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is not None
    assert cxc.saldo_usd == factura.total_usd
    assert cxc.fecha_vencimiento is not None  # 30 días después


def test_credito_fiduciario(db, cliente, producto, tasa, fiduciario):
    """Crédito con fiduciario. CxC contra el fiduciario."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    factura = facturacion.confirmar_factura(
        factura,
        tipo_venta=TIPO_VENTA_CREDITO_FIDUCIARIO,
        pagos=[],
        fiduciario_id=fiduciario.id,
    )

    assert factura.estado == "emitida"
    assert factura.fiduciario_id == fiduciario.id

    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is not None
    assert cxc.tipo_deudor == "fiduciario"
    assert cxc.fiduciario_id == fiduciario.id
    assert cxc.fecha_vencimiento is None


def test_factura_sin_lineas_falla(db, cliente, tasa):
    """Factura sin líneas no se puede confirmar."""
    factura = facturacion.crear_borrador(cliente.id)
    db.session.flush()

    with pytest.raises(FacturaSinLineasError):
        facturacion.confirmar_factura(
            factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=[]
        )


def test_tipo_venta_invalido_falla(db, cliente, producto, tasa):
    factura = _crear_factura_borrador(cliente, producto, tasa)
    with pytest.raises(TipoVentaInvalidoError):
        facturacion.confirmar_factura(
            factura, tipo_venta="invalido", pagos=[]
        )


def test_stock_insuficiente_hace_rollback(db, cliente, producto, tasa):
    """Si el stock es insuficiente, todo falla."""
    factura = facturacion.crear_borrador(cliente.id)
    facturacion.agregar_detalle(factura, producto.id, Decimal("999"))  # más que stock
    db.session.flush()

    with pytest.raises(StockInsuficienteError):
        facturacion.confirmar_factura(
            factura, tipo_venta=TIPO_VENTA_CONTADO, pagos=[]
        )

    # El estado sigue en borrador
    assert factura.estado == "borrador"
    # El stock no cambió
    assert producto.stock_actual == Decimal("50.000")


def test_credito_sin_habilitar_falla(db, cliente, producto, tasa):
    """Cliente sin crédito habilitado no puede ser crédito directo."""
    factura = _crear_factura_borrador(cliente, producto, tasa)
    with pytest.raises(CreditoNoHabilitadoError):
        facturacion.confirmar_factura(
            factura, tipo_venta=TIPO_VENTA_CREDITO_DIRECTO, pagos=[]
        )


def test_limite_credito_excedido_falla(db, cliente_con_credito, producto, tasa):
    """Crédito excedido al facturar."""
    # Límite 500, ya tiene un cargo de 400.
    factura_vieja = _crear_factura_borrador(cliente_con_credito, producto, tasa)
    facturacion.confirmar_factura(
        factura_vieja, tipo_venta=TIPO_VENTA_CREDITO_DIRECTO, pagos=[]
    )

    # Ahora intentamos facturar 116 más. Total: 116 + 116 = 232 < 500. OK.
    # Pero si creamos una factura de 500, excede.
    # Vamos a forzar: crear una factura por 500 USD (5 productos a 100)
    factura2 = facturacion.crear_borrador(cliente_con_credito.id)
    facturacion.agregar_detalle(factura2, producto.id, Decimal("4"))

    # Factura 1 tiene total 116. Factura 2 tiene total 464. Suma 580 > 500.
    with pytest.raises(LimiteCreditoExcedidoError):
        facturacion.confirmar_factura(
            factura2, tipo_venta=TIPO_VENTA_CREDITO_DIRECTO, pagos=[]
        )


def test_fiduciario_inexistente_falla(db, cliente, producto, tasa):
    factura = _crear_factura_borrador(cliente, producto, tasa)
    with pytest.raises(FiduciarioNoValidoError):
        facturacion.confirmar_factura(
            factura,
            tipo_venta=TIPO_VENTA_CREDITO_FIDUCIARIO,
            pagos=[],
            fiduciario_id=99999,
        )


def test_pago_monto_negativo_falla(db, cliente, producto, tasa):
    factura = _crear_factura_borrador(cliente, producto, tasa)
    with pytest.raises(PagoInvalidoError):
        facturacion.confirmar_factura(
            factura,
            tipo_venta=TIPO_VENTA_CONTADO,
            pagos=[{
                "forma_pago": "efectivo_ves",
                "moneda_pago": "VES",
                "monto": Decimal("-10"),
            }],
        )
        
        
def test_cxc_monto_total_es_el_total_de_la_factura(db, cliente_con_credito, producto, tasa):
    """Al crear una CxC, monto_total_usd es el total de la factura."""
    factura = _crear_factura_borrador(cliente_con_credito, producto, tasa)
    # Total 116 USD. Pagamos 50 USD.
    pagos = [{
        "forma_pago": "efectivo_ves",
        "moneda_pago": "VES",
        "monto": Decimal("2000.0000"),
    }]
    facturacion.confirmar_factura(
        factura, tipo_venta="contado", pagos=pagos
    )

    cxc = db.session.scalar(
        db.select(CuentaPorCobrar).filter_by(factura_venta_id=factura.id)
    )
    assert cxc is not None
    assert cxc.monto_total_usd == factura.total_usd  # 116
    assert cxc.saldo_usd == Decimal("66.0000")        # 66