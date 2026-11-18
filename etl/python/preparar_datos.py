"""Etapas 1 y 2 del ETL: lee las fuentes de data/raw/ y prepara los archivos que carga Apache Hop.

Salidas en data/processed/:
- clientes.csv: clientes SINTÉTICOS (ver clientes.py).
- transacciones.csv: muestra de transacciones de las 6 líneas en un formato común, con los
  códigos, unidades y monedas de cada fuente (Hop los convierte y los valida).
- zonas.csv: zonas de origen y destino de todas las líneas.
- tipo_cambio.csv: pesos chilenos por unidad de moneda y año (Banco Central de Chile).
- estadisticas_preparacion.csv: filas leídas y muestreadas por línea.

Transformaciones SINTÉTICAS, marcadas en las columnas fecha_sintetica y monto_sintetico:
- Fechas trasladadas a 2023-2025 cuando la fuente es de otro período, y días asignados al
  azar cuando la fuente solo informa el mes o el trimestre.
- Totales desagregados en transacciones (buses).
- Tarifa de buses estimada con un modelo calibrado con precios reales del SERNAC (2024).
- Asignación de cada transacción a un cliente sintético.

Uso:  python etl/python/preparar_datos.py
"""

import re
import time
import zipfile
from html import unescape
from pathlib import Path

import clientes as gen
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
OUT = RAIZ / "data" / "processed"
REF = RAIZ / "etl" / "referencias"

SEMILLA = 20261117
N_PERSONAS, N_EMPRESAS = 9500, 500
N = {"BUS": 25000, "TRN": 15000, "TAX": 25000, "LOG": 20000, "AER": 15000, "DEL": 20000}
INICIO, FIN = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")

COLUMNAS = [
    "numero_transaccion",
    "codigo_linea",
    "fecha",
    "codigo_cliente",
    "servicio_fuente",
    "codigo_zona_origen",
    "codigo_zona_destino",
    "canal_fuente",
    "pago_fuente",
    "estado_fuente",
    "moneda",
    "cantidad",
    "monto_bruto",
    "monto_descuento",
    "distancia",
    "unidad_distancia",
    "duracion_minutos",
    "peso",
    "unidad_peso",
    "fecha_sintetica",
    "monto_sintetico",
]
ZONAS = ["codigo_zona", "comuna", "ciudad", "region", "pais", "continente"]

estadisticas: list[dict] = []


def anotar(linea: str, etapa: str, filas: float) -> None:
    estadisticas.append({"codigo_linea": linea, "etapa": etapa, "filas": filas})
    print(f"  {linea} {etapa}: {filas:,}")


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def dia_al_azar(inicio_periodo: pd.Series, dias_periodo: pd.Series, rng) -> pd.Series:
    """Fecha SINTÉTICA: un día al azar dentro del período (mes o trimestre) de la fuente."""
    return inicio_periodo + pd.to_timedelta(rng.integers(0, dias_periodo.to_numpy()), unit="D")


def trasladar_ventanas(fechas: pd.Series, meses_fuente: int, rng) -> pd.Series:
    """Fecha SINTÉTICA para fuentes de pocos meses: desplaza cada fecha en un múltiplo del
    largo de la fuente, de modo que la muestra cubra 2023-2025 completo."""
    inicio = fechas.min().to_period("M")
    ventanas = 36 // meses_fuente
    k = rng.integers(0, ventanas, len(fechas))
    desfase = (pd.Period("2023-01", "M") - inicio).n + k * meses_fuente
    periodo = fechas.dt.to_period("M") + desfase
    inicio_mes = periodo.dt.to_timestamp()
    dia = np.minimum(fechas.dt.day.to_numpy(), periodo.dt.days_in_month.to_numpy())
    return inicio_mes + pd.to_timedelta(dia - 1, unit="D")


def cambiar_anio(fechas: pd.Series, rng) -> pd.Series:
    """Fecha SINTÉTICA: conserva mes y día y asigna al azar un año de 2023-2025."""
    anio = rng.integers(2023, 2026, len(fechas))
    dia = np.where((fechas.dt.month == 2) & (fechas.dt.day == 29), 28, fechas.dt.day)
    return pd.to_datetime({"year": anio, "month": fechas.dt.month, "day": dia})


def muestra(df: pd.DataFrame, n: int, rng, pesos=None) -> pd.DataFrame:
    if pesos is not None:
        p = np.asarray(pesos, float)
        idx = rng.choice(len(df), size=n, replace=True, p=p / p.sum())
    else:
        idx = rng.choice(len(df), size=min(n, len(df)), replace=False)
    return df.iloc[idx].reset_index(drop=True)


# ---------------------------------------------------------------- Buses (Colombia)
def tarifa_bus() -> tuple[dict, float]:
    """Modelo de tarifa por clase (CLP por pasaje de ida = a + b * km por carretera), ajustado
    por mínimos cuadrados con el SERNAC 2024, y factor carretera / línea recta de Chile."""
    s = pd.read_csv(REF / "sernac_2024_buses.csv")
    km = s["km_ida_vuelta"] / 2
    modelo = {}
    for clase, col in (("BASICO", "semi_cama_ida_vuelta"), ("LUJO", "salon_cama_ida_vuelta")):
        ok = s[col].notna()
        b, a = np.polyfit(km[ok], s.loc[ok, col] / 2, 1)
        modelo[clase] = (a, b)

    with zipfile.ZipFile(RAW / "geonames" / "CL.zip") as z:
        g = pd.read_csv(
            z.open("CL.txt"),
            sep="\t",
            header=None,
            usecols=[1, 4, 5, 6, 14],
            names=["nombre", "lat", "lon", "clase", "poblacion"],
            quoting=3,
        )
    g = g[g["clase"] == "P"].sort_values("poblacion", ascending=False).drop_duplicates("nombre")
    coord = g.set_index("nombre")[["lat", "lon"]]
    o, d = coord.loc[s["origen"]].to_numpy(), coord.loc[s["destino"]].to_numpy()
    recta = haversine_km(o[:, 0], o[:, 1], d[:, 0], d[:, 1])
    factor = float(np.median(km / recta))
    print(f"  BUS modelo de tarifa {modelo}, factor carretera/línea recta {factor:.3f}")
    return modelo, factor


def linea_buses(rng):
    mun = pd.read_csv(RAW / "buses" / "divipola_municipios.csv", dtype=str)
    mun.columns = [c.strip().lower() for c in mun.columns]
    for c in ("latitud", "longitud"):
        mun[c] = mun[c].str.replace(",", ".").astype(float)
    mun = mun.set_index("cod_mpio")

    archivos = sorted((RAW / "buses").glob("supertransporte_*.csv"))
    d = pd.concat([pd.read_csv(f, dtype=str) for f in archivos], ignore_index=True)
    anotar("BUS", "filas leídas", len(d))
    d["pasajeros"] = pd.to_numeric(d["pasajeros"], errors="coerce").fillna(0)
    d = d[d["clase_vehiculo"].isin(["BUS", "BUSETA", "MICROBUS"]) & (d["pasajeros"] > 0)]
    d = d[d["municipio_origen_ruta"].isin(mun.index) & d["municipio_destino_ruta"].isin(mun.index)]
    d = d[d["municipio_origen_ruta"] != d["municipio_destino_ruta"]]
    d["mes"] = pd.to_datetime(d["fecha_despacho"].str[:10]).dt.to_period("M")
    anotar("BUS", "filas útiles (bus, con pasajeros y municipios válidos)", len(d))

    # 2024 casi no tiene datos en la fuente: cada mes de 2024 con menos de la mitad de los
    # pasajeros del mismo mes de 2023 se reemplaza por ese mes de 2023, trasladado un año
    # (SINTÉTICO).
    pas_mes = d.groupby("mes")["pasajeros"].sum()
    d["trasladado"] = False
    for mes in pd.period_range("2024-01", "2024-12", freq="M"):
        if pas_mes.get(mes, 0) < 0.5 * pas_mes.get(mes - 12, 0):
            copia = d[d["mes"] == mes - 12].assign(mes=mes, trasladado=True)
            d = pd.concat([d[d["mes"] != mes], copia], ignore_index=True)

    t = muestra(d, N["BUS"], rng, pesos=d["pasajeros"])  # cada fila muestreada = 1 pasaje
    anotar("BUS", "muestra", len(t))
    inicio = t["mes"].dt.to_timestamp()
    t["fecha"] = dia_al_azar(inicio, t["mes"].dt.days_in_month, rng)

    modelo, factor = tarifa_bus()
    o, de = mun.loc[t["municipio_origen_ruta"]], mun.loc[t["municipio_destino_ruta"]]
    recta = haversine_km(
        o["latitud"].to_numpy(),
        o["longitud"].to_numpy(),
        de["latitud"].to_numpy(),
        de["longitud"].to_numpy(),
    )
    km = recta * factor
    clase = np.where(t["nivel_servicio"] == "BASICO", "BASICO", "LUJO")
    a = np.where(clase == "BASICO", modelo["BASICO"][0], modelo["LUJO"][0])
    b = np.where(clase == "BASICO", modelo["BASICO"][1], modelo["LUJO"][1])
    tarifa = np.round((a + b * km) / 100) * 100  # pesos chilenos, redondeado a la centena

    trx = pd.DataFrame(
        {
            "numero_transaccion": [f"BUS-{i:07d}" for i in range(1, len(t) + 1)],
            "codigo_linea": "BUS",
            "fecha": t["fecha"],
            "servicio_fuente": clase,
            "codigo_zona_origen": "CO-" + t["municipio_origen_ruta"],
            "codigo_zona_destino": "CO-" + t["municipio_destino_ruta"],
            "canal_fuente": None,
            "pago_fuente": None,
            "estado_fuente": "valido",
            "moneda": "CLP",
            "cantidad": 1,
            "monto_bruto": tarifa,
            "monto_descuento": 0.0,
            "distancia": km.round(2),
            "unidad_distancia": "km",
            "duracion_minutos": None,
            "peso": None,
            "unidad_peso": None,
            "fecha_sintetica": True,
            "monto_sintetico": True,
        }
    )
    usados = pd.unique(t[["municipio_origen_ruta", "municipio_destino_ruta"]].to_numpy().ravel())
    m = mun.loc[usados]
    zonas = pd.DataFrame(
        {
            "codigo_zona": "CO-" + m.index,
            "comuna": m["nom_mpio"].str.title(),
            "ciudad": m["nom_mpio"].str.title(),
            "region": m["dpto"].str.title(),
            "pais": "Colombia",
            "continente": "América del Sur",
        }
    )
    return trx, zonas


# ---------------------------------------------------------------- Trenes (Reino Unido)
ESTACIONES = {  # estación → (ciudad, nación del Reino Unido)
    "Birmingham New Street": ("Birmingham", "Inglaterra"),
    "Bristol Temple Meads": ("Bristol", "Inglaterra"),
    "Cardiff Central": ("Cardiff", "Gales"),
    "Coventry": ("Coventry", "Inglaterra"),
    "Crewe": ("Crewe", "Inglaterra"),
    "Didcot": ("Didcot", "Inglaterra"),
    "Doncaster": ("Doncaster", "Inglaterra"),
    "Durham": ("Durham", "Inglaterra"),
    "Edinburgh": ("Edimburgo", "Escocia"),
    "Edinburgh Waverley": ("Edimburgo", "Escocia"),
    "Leeds": ("Leeds", "Inglaterra"),
    "Leicester": ("Leicester", "Inglaterra"),
    "Liverpool Lime Street": ("Liverpool", "Inglaterra"),
    "London Euston": ("Londres", "Inglaterra"),
    "London Kings Cross": ("Londres", "Inglaterra"),
    "London Paddington": ("Londres", "Inglaterra"),
    "London St Pancras": ("Londres", "Inglaterra"),
    "London Waterloo": ("Londres", "Inglaterra"),
    "Manchester Piccadilly": ("Mánchester", "Inglaterra"),
    "Nottingham": ("Nottingham", "Inglaterra"),
    "Nuneaton": ("Nuneaton", "Inglaterra"),
    "Oxford": ("Oxford", "Inglaterra"),
    "Peterborough": ("Peterborough", "Inglaterra"),
    "Reading": ("Reading", "Inglaterra"),
    "Sheffield": ("Sheffield", "Inglaterra"),
    "Stafford": ("Stafford", "Inglaterra"),
    "Swindon": ("Swindon", "Inglaterra"),
    "Tamworth": ("Tamworth", "Inglaterra"),
    "Wakefield": ("Wakefield", "Inglaterra"),
    "Warrington": ("Warrington", "Inglaterra"),
    "Wolverhampton": ("Wolverhampton", "Inglaterra"),
    "York": ("York", "Inglaterra"),
}


def codigo_uk(estacion: pd.Series) -> pd.Series:
    return "UK-" + estacion.str.upper().str.replace(r"[^A-Z]+", "-", regex=True).str.slice(0, 17)


def linea_trenes(rng):
    with zipfile.ZipFile(RAW / "tren" / "UK+Train+Rides.zip") as z:
        r = pd.read_csv(z.open("railway.csv"))
    anotar("TRN", "filas leídas", len(r))
    t = muestra(r, N["TRN"], rng)
    anotar("TRN", "muestra", len(t))

    # Descuentos del diccionario de la fuente: Railcard 1/3; Advance 1/2; Off-Peak 1/4.
    d_tarjeta = np.where(t["Railcard"].notna(), 1 / 3, 0.0)
    d_tipo = t["Ticket Type"].map({"Advance": 0.5, "Off-Peak": 0.25, "Anytime": 0.0}).to_numpy()
    bruto = (t["Price"] / ((1 - d_tarjeta) * (1 - d_tipo))).round(2)

    salida = pd.to_datetime(t["Date of Journey"] + " " + t["Departure Time"])
    llegada = pd.to_datetime(
        t["Date of Journey"] + " " + t["Actual Arrival Time"].fillna(t["Arrival Time"])
    )
    llegada = llegada.where(llegada >= salida, llegada + pd.Timedelta(days=1))
    fecha = trasladar_ventanas(pd.to_datetime(t["Date of Journey"]), 4, rng)

    trx = pd.DataFrame(
        {
            "numero_transaccion": "TRN-" + t["Transaction ID"],
            "codigo_linea": "TRN",
            "fecha": fecha,
            "servicio_fuente": t["Ticket Class"],
            "codigo_zona_origen": codigo_uk(t["Departure Station"]),
            "codigo_zona_destino": codigo_uk(t["Arrival Destination"]),
            "canal_fuente": t["Purchase Type"],
            "pago_fuente": t["Payment Method"],
            "estado_fuente": "valido",
            "moneda": "GBP",
            "cantidad": 1,
            "monto_bruto": bruto,
            "monto_descuento": (bruto - t["Price"]).round(2),
            "distancia": None,
            "unidad_distancia": None,
            "duracion_minutos": ((llegada - salida).dt.total_seconds() // 60).astype(int),
            "peso": None,
            "unidad_peso": None,
            "fecha_sintetica": True,
            "monto_sintetico": False,
        }
    )
    est = pd.Series(sorted(ESTACIONES))
    zonas = pd.DataFrame(
        {
            "codigo_zona": codigo_uk(est),
            "comuna": est,
            "ciudad": est.map(lambda e: ESTACIONES[e][0]),
            "region": est.map(lambda e: ESTACIONES[e][1]),
            "pais": "Reino Unido",
            "continente": "Europa",
        }
    ).drop_duplicates("codigo_zona")
    return trx, zonas


# ---------------------------------------------------------------- Taxis (Nueva York)
def linea_taxis(rng):
    archivos = sorted((RAW / "taxi").glob("green_tripdata_*.parquet"))
    columnas = [
        "lpep_pickup_datetime",
        "lpep_dropoff_datetime",
        "PULocationID",
        "DOLocationID",
        "RatecodeID",
        "passenger_count",
        "trip_distance",
        "total_amount",
        "tip_amount",
        "payment_type",
        "trip_type",
    ]
    partes, leidas = [], 0
    por_mes = N["TAX"] // len(archivos) + 1
    for f in archivos:
        df = pd.read_parquet(f, columns=columnas)
        leidas += len(df)
        mes = pd.Period(f.stem[-7:], "M")  # descarta registros con fechas fuera del mes del archivo
        df = df[df["lpep_pickup_datetime"].dt.to_period("M") == mes]
        partes.append(muestra(df, por_mes, rng).assign(archivo=f.stem))
    anotar("TAX", "filas leídas", leidas)
    t = pd.concat(partes, ignore_index=True)
    t = t.iloc[rng.choice(len(t), N["TAX"], replace=False)].reset_index(drop=True)
    anotar("TAX", "muestra", len(t))

    estado = t["payment_type"].map({3: "sin_cobro", 4: "disputa"}).fillna("valido")
    clase = t["RatecodeID"].map({1: "1", 2: "2", 3: "2"}).fillna("5")  # 2 = aeropuerto
    trx = pd.DataFrame(
        {
            "numero_transaccion": "TAX-"
            + t["archivo"].str[-7:].str.replace("-", "")
            + "-"
            + pd.Series(range(len(t))).astype(str).str.zfill(6),
            "codigo_linea": "TAX",
            "fecha": t["lpep_pickup_datetime"].dt.normalize(),
            "servicio_fuente": clase,
            "codigo_zona_origen": "US-NYC-" + t["PULocationID"].astype(str),
            "codigo_zona_destino": "US-NYC-" + t["DOLocationID"].astype(str),
            "canal_fuente": t["trip_type"].astype("Int64").astype(str),
            "pago_fuente": t["payment_type"].astype("Int64").astype(str).replace("<NA>", None),
            "estado_fuente": estado,
            "moneda": "USD",
            "cantidad": t["passenger_count"].fillna(1).clip(lower=1).astype(int),
            "monto_bruto": (t["total_amount"] - t["tip_amount"]).round(2),
            "monto_descuento": 0.0,
            "distancia": t["trip_distance"],
            "unidad_distancia": "mi",
            "duracion_minutos": (
                (t["lpep_dropoff_datetime"] - t["lpep_pickup_datetime"]).dt.total_seconds() // 60
            ).astype(int),
            "peso": None,
            "unidad_peso": None,
            "fecha_sintetica": False,
            "monto_sintetico": False,
        }
    )
    trx["canal_fuente"] = trx["canal_fuente"].replace("<NA>", None)
    z = pd.read_csv(RAW / "taxi" / "taxi_zone_lookup.csv")
    zonas = pd.DataFrame(
        {
            "codigo_zona": "US-NYC-" + z["LocationID"].astype(str),
            "comuna": z["Zone"].fillna("No informado"),
            "ciudad": z["Borough"].fillna("No informado"),
            "region": "Nueva York",
            "pais": "Estados Unidos",
            "continente": "América del Norte",
        }
    )
    return trx, zonas


# ---------------------------------------------------------------- Logística (Olist, Brasil)
ESTADOS_BR = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AM": "Amazonas",
    "AP": "Amapá",
    "BA": "Bahía",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MG": "Minas Gerais",
    "MS": "Mato Grosso del Sur",
    "MT": "Mato Grosso",
    "PA": "Pará",
    "PB": "Paraíba",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "PR": "Paraná",
    "RJ": "Río de Janeiro",
    "RN": "Río Grande del Norte",
    "RO": "Rondonia",
    "RR": "Roraima",
    "RS": "Río Grande del Sur",
    "SC": "Santa Catarina",
    "SE": "Sergipe",
    "SP": "São Paulo",
    "TO": "Tocantins",
}


def codigo_br(estado: pd.Series, ciudad: pd.Series) -> pd.Series:
    limpio = (
        ciudad.str.upper()
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.replace(r"[^A-Z]+", "-", regex=True)
        .str.strip("-")
    )
    return ("BR-" + estado + "-" + limpio).str.slice(0, 20)


def zonas_br(estado: pd.Series, ciudad: pd.Series) -> pd.DataFrame:
    z = pd.DataFrame({"estado": estado, "ciudad": ciudad.str.title()}).drop_duplicates()
    return pd.DataFrame(
        {
            "codigo_zona": codigo_br(z["estado"], z["ciudad"]),
            "comuna": z["ciudad"],
            "ciudad": z["ciudad"],
            "region": z["estado"].map(ESTADOS_BR),
            "pais": "Brasil",
            "continente": "América del Sur",
        }
    )


def linea_logistica(rng):
    z = zipfile.ZipFile(RAW / "logistica" / "archive.zip")
    rd = lambda n: pd.read_csv(z.open(f"olist_{n}_dataset.csv"))  # noqa: E731
    pedidos, items, productos = rd("orders"), rd("order_items"), rd("products")
    clientes, vendedores, pagos, geo = (
        rd("customers"),
        rd("sellers"),
        rd("order_payments"),
        rd("geolocation"),
    )
    anotar("LOG", "filas leídas", len(pedidos))

    items = items.merge(productos[["product_id", "product_weight_g"]], on="product_id", how="left")
    por_pedido = items.groupby("order_id").agg(
        cantidad=("order_item_id", "size"),
        flete=("freight_value", "sum"),
        peso_g=("product_weight_g", "sum"),
        seller_id=("seller_id", "first"),
    )
    pago = pagos.sort_values("payment_value").drop_duplicates("order_id", keep="last")
    t = (
        pedidos.merge(por_pedido, on="order_id")
        .merge(clientes, on="customer_id")
        .merge(vendedores, on="seller_id")
        .merge(pago[["order_id", "payment_type"]], on="order_id", how="left")
    )
    t = muestra(t, N["LOG"], rng)
    anotar("LOG", "muestra", len(t))

    centro = geo.groupby("geolocation_zip_code_prefix")[
        ["geolocation_lat", "geolocation_lng"]
    ].mean()
    o = centro.reindex(t["seller_zip_code_prefix"]).to_numpy()
    d = centro.reindex(t["customer_zip_code_prefix"]).to_numpy()
    compra = pd.to_datetime(t["order_purchase_timestamp"])
    entrega = pd.to_datetime(t["order_delivered_customer_date"])
    estado = np.where(t["order_status"].isin(["canceled", "unavailable"]), "cancelado", "valido")

    trx = pd.DataFrame(
        {
            "numero_transaccion": "LOG-" + t["order_id"].str[:20],
            "codigo_linea": "LOG",
            "fecha": cambiar_anio(compra.dt.normalize(), rng),
            "servicio_fuente": "estandar",
            "codigo_zona_origen": codigo_br(t["seller_state"], t["seller_city"].str.title()),
            "codigo_zona_destino": codigo_br(t["customer_state"], t["customer_city"].str.title()),
            "canal_fuente": "marketplace",
            "pago_fuente": t["payment_type"],
            "estado_fuente": estado,
            "moneda": "BRL",
            "cantidad": t["cantidad"],
            "monto_bruto": t["flete"].round(2),
            "monto_descuento": 0.0,
            "distancia": haversine_km(o[:, 0], o[:, 1], d[:, 0], d[:, 1]).round(2),
            "unidad_distancia": "km",
            "duracion_minutos": ((entrega - compra).dt.total_seconds() // 60).astype("Int64"),
            "peso": t["peso_g"],
            "unidad_peso": "g",
            "fecha_sintetica": True,
            "monto_sintetico": False,
        }
    )
    zonas = pd.concat(
        [
            zonas_br(t["seller_state"], t["seller_city"]),
            zonas_br(t["customer_state"], t["customer_city"]),
        ]
    )
    return trx, zonas


# ---------------------------------------------------------------- Aerolínea (BTS, EE.UU.)
def linea_aerolinea(rng):
    archivos = sorted((RAW / "aerolinea").glob("Origin_and_Destination_Survey_DB1BMarket_*.zip"))
    columnas = [
        "MktID",
        "Year",
        "Quarter",
        "Origin",
        "OriginStateName",
        "Dest",
        "DestStateName",
        "Passengers",
        "MktFare",
        "MktDistance",
        "MktDistanceGroup",
        "BulkFare",
    ]
    trimestres = 12  # 10 publicados + 2025 T3 y T4 trasladados desde 2024
    por_trim = N["AER"] // trimestres + 1
    partes, leidas = [], 0
    for f in archivos:
        anio, trim = map(int, re.findall(r"(\d{4})_(\d)", f.name)[0])
        extra = 2 if (anio == 2024 and trim >= 3) else 1
        frac = None
        with zipfile.ZipFile(f) as z:
            nombre = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            elegidas = []
            for trozo in pd.read_csv(
                z.open(nombre), usecols=columnas, chunksize=1_000_000, encoding="latin-1"
            ):
                leidas += len(trozo)
                if frac is None:  # ~6,5 millones de filas por trimestre
                    frac = min(1.0, por_trim * extra * 3 / 6_500_000)
                elegidas.append(trozo.sample(frac=frac, random_state=int(rng.integers(1 << 31))))
        sel = muestra(pd.concat(elegidas), por_trim * extra, rng)
        if extra == 2:  # mitad del trimestre de 2024 se traslada a 2025 (SINTÉTICO)
            sel["trasladado"] = np.arange(len(sel)) % 2 == 1
            sel.loc[sel["trasladado"], "Year"] = 2025
        partes.append(sel)
        print(f"    {f.name}: {len(sel):,}")
    anotar("AER", "filas leídas", leidas)
    t = pd.concat(partes, ignore_index=True)
    t = t.iloc[rng.choice(len(t), N["AER"], replace=False)].reset_index(drop=True)
    t["MktID"] = t["MktID"].astype(str) + np.where(t.get("trasladado", False) == True, "T", "")  # noqa: E712
    anotar("AER", "muestra", len(t))

    inicio = pd.PeriodIndex.from_fields(year=t["Year"], quarter=t["Quarter"], freq="Q")
    fecha = dia_al_azar(
        pd.Series(inicio.to_timestamp()), pd.Series(inicio.days_in_month * 0 + 90), rng
    )
    clase = t["MktDistanceGroup"].map(
        lambda g: "corto" if g <= 2 else ("medio" if g <= 5 else "largo")
    )
    estado = np.where(t["BulkFare"] == 1, "tarifa_masiva", "valido")
    trx = pd.DataFrame(
        {
            "numero_transaccion": "AER-" + t["MktID"],
            "codigo_linea": "AER",
            "fecha": fecha,
            "servicio_fuente": clase,
            "codigo_zona_origen": "US-AP-" + t["Origin"],
            "codigo_zona_destino": "US-AP-" + t["Dest"],
            "canal_fuente": None,
            "pago_fuente": None,
            "estado_fuente": estado,
            "moneda": "USD",
            "cantidad": t["Passengers"].astype(int),
            "monto_bruto": (t["MktFare"] * t["Passengers"]).round(2),
            "monto_descuento": 0.0,
            "distancia": t["MktDistance"],
            "unidad_distancia": "mi",
            "duracion_minutos": None,
            "peso": None,
            "unidad_peso": None,
            "fecha_sintetica": True,
            "monto_sintetico": False,
        }
    )
    ap = pd.read_csv(RAW / "aerolinea" / "L_AIRPORT.csv", encoding="latin-1").set_index("Code")[
        "Description"
    ]
    cod = pd.concat(
        [
            t[["Origin", "OriginStateName"]].set_axis(["c", "e"], axis=1),
            t[["Dest", "DestStateName"]].set_axis(["c", "e"], axis=1),
        ]
    ).drop_duplicates("c")
    codigos = cod["c"].to_numpy()
    desc = ap.reindex(codigos).to_numpy()
    desc = np.where(pd.isna(desc), codigos + ": " + codigos, desc)  # aeropuerto sin descripción
    zonas = pd.DataFrame(
        {
            "codigo_zona": "US-AP-" + cod["c"].to_numpy(),
            "comuna": [x.split(": ", 1)[-1][:60] for x in desc],
            "ciudad": [x.split(":")[0].split(",")[0][:60] for x in desc],
            "region": cod["e"].to_numpy(),
            "pais": "Estados Unidos",
            "continente": "América del Norte",
        }
    )
    return trx, zonas


# --------------------------------------------------------- Delivery (Delivery Center, Brasil)
def linea_delivery(rng):
    z = zipfile.ZipFile(RAW / "delivery" / "archive.zip")
    rd = lambda n, **k: pd.read_csv(z.open(n), encoding="latin-1", **k)  # noqa: E731
    o = rd(
        "orders.csv",
        usecols=[
            "order_id",
            "store_id",
            "channel_id",
            "payment_order_id",
            "delivery_order_id",
            "order_status",
            "order_amount",
            "order_delivery_fee",
            "order_moment_created",
            "order_metric_cycle_time",
        ],
    )
    anotar("DEL", "filas leídas", len(o))
    t = muestra(o, N["DEL"], rng)
    anotar("DEL", "muestra", len(t))

    canales = rd("channels.csv").set_index("channel_id")["channel_type"]
    tiendas = rd("stores.csv").set_index("store_id")
    hubs = rd("hubs.csv").set_index("hub_id")
    entregas = (
        rd("deliveries.csv").drop_duplicates("delivery_order_id").set_index("delivery_order_id")
    )
    choferes = rd("drivers.csv").set_index("driver_id")["driver_modal"]
    pagos = rd("payments.csv")
    voucher = (
        pagos[pagos["payment_method"].str.startswith("VOUCHER")]
        .groupby("payment_order_id")["payment_amount"]
        .sum()
    )
    otros = pagos[~pagos["payment_method"].str.startswith("VOUCHER")].sort_values("payment_amount")
    principal = otros.drop_duplicates("payment_order_id", keep="last").set_index(
        "payment_order_id"
    )["payment_method"]

    tienda = tiendas.reindex(t["store_id"])
    hub = hubs.reindex(tienda["hub_id"])
    ent = entregas.reindex(t["delivery_order_id"])
    modal = choferes.reindex(ent["driver_id"]).fillna("SIN_DATO").to_numpy()
    servicio = pd.Series(modal) + "|" + tienda["store_segment"].fillna("SIN_DATO").to_numpy()
    creado = pd.to_datetime(t["order_moment_created"], format="%m/%d/%Y %I:%M:%S %p")
    bruto = (t["order_amount"] + t["order_delivery_fee"]).round(2)
    descuento = np.minimum(voucher.reindex(t["payment_order_id"]).fillna(0).to_numpy(), bruto)
    zona = codigo_br(hub["hub_state"].to_numpy(), pd.Series(hub["hub_city"].str.title().to_numpy()))

    trx = pd.DataFrame(
        {
            "numero_transaccion": "DEL-" + t["order_id"].astype(str),
            "codigo_linea": "DEL",
            "fecha": trasladar_ventanas(creado.dt.normalize(), 4, rng),
            "servicio_fuente": servicio,
            "codigo_zona_origen": zona,
            "codigo_zona_destino": zona,
            "canal_fuente": canales.reindex(t["channel_id"]).to_numpy(),
            "pago_fuente": principal.reindex(t["payment_order_id"]).to_numpy(),
            "estado_fuente": np.where(t["order_status"] == "CANCELED", "cancelado", "valido"),
            "moneda": "BRL",
            "cantidad": 1,
            "monto_bruto": bruto,
            "monto_descuento": np.round(descuento, 2),
            "distancia": ent["delivery_distance_meters"].to_numpy(),
            "unidad_distancia": "m",
            # tiempo de ciclo del pedido (minutos), según la fuente
            "duracion_minutos": t["order_metric_cycle_time"].round().astype("Int64"),
            "peso": None,
            "unidad_peso": None,
            "fecha_sintetica": True,
            "monto_sintetico": False,
        }
    )
    zonas = zonas_br(hubs["hub_state"], hubs["hub_city"])
    return trx, zonas


# ---------------------------------------------------------------- Tipo de cambio
def tipo_cambio() -> pd.DataFrame:
    """CLP por unidad de moneda, promedio anual 2023-2025 (Banco Central de Chile)."""

    def fila(archivo: str, serie: str) -> list[float]:
        html = (RAW / "tipo_cambio" / archivo).read_text(encoding="utf-8", errors="replace")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            celdas = [
                unescape(re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            ]
            celdas = [c for c in celdas if c]
            if celdas and celdas[0].startswith(serie):
                # columnas 2023, 2024 y 2025, en formato chileno (1.234,56)
                return [float(c.replace(".", "").replace(",", ".")) for c in celdas[1:4]]
        raise ValueError(f"No se encontró la serie {serie!r} en {archivo}")

    usd = fila("TCB_505.html", "Dólar observado")
    brl = fila("TCB_510.html", "Brasil: Real")
    gbp = fila("TCB_510.html", "Reino Unido: Libra esterlina")
    filas = []
    for i, anio in enumerate((2023, 2024, 2025)):
        filas += [
            {"anio": anio, "moneda": "CLP", "clp_por_unidad": 1.0},
            {"anio": anio, "moneda": "USD", "clp_por_unidad": usd[i]},
            {"anio": anio, "moneda": "BRL", "clp_por_unidad": round(usd[i] / brl[i], 4)},
            {"anio": anio, "moneda": "GBP", "clp_por_unidad": round(usd[i] / gbp[i], 4)},
        ]
    return pd.DataFrame(filas)


def main() -> None:
    rng = np.random.default_rng(SEMILLA)
    OUT.mkdir(parents=True, exist_ok=True)
    print("Clientes sintéticos")
    cli = gen.generar(
        RAW / "censo" / "D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx",
        N_PERSONAS,
        N_EMPRESAS,
        rng,
    )

    lineas = {
        "BUS": linea_buses,
        "TRN": linea_trenes,
        "TAX": linea_taxis,
        "LOG": linea_logistica,
        "AER": linea_aerolinea,
        "DEL": linea_delivery,
    }
    trx, zonas = [], []
    for codigo, funcion in lineas.items():
        print(f"Línea {codigo}")
        inicio = time.perf_counter()
        t, z = funcion(rng)
        anotar(codigo, "segundos", round(time.perf_counter() - inicio, 1))
        t["codigo_cliente"] = gen.asignar(cli, codigo, len(t), rng)
        trx.append(t)
        zonas.append(z)
    trx = pd.concat(trx, ignore_index=True)

    # Supuesto: las empresas compran por convenio.
    es_empresa = trx["codigo_cliente"].str.startswith("EMP-")
    trx.loc[es_empresa, "canal_fuente"] = "convenio"

    # Fecha de registro SINTÉTICA: hasta 2 años antes de la primera compra.
    primera = trx.groupby("codigo_cliente")["fecha"].min()
    cli["fecha_registro"] = cli["codigo_cliente"].map(primera)
    sin_compra = cli["fecha_registro"].isna()
    cli.loc[sin_compra, "fecha_registro"] = INICIO + pd.to_timedelta(
        rng.integers(0, (FIN - INICIO).days, sin_compra.sum()), unit="D"
    )
    cli["fecha_registro"] = (
        pd.to_datetime(cli["fecha_registro"])
        - pd.to_timedelta(rng.integers(0, 730, len(cli)), unit="D")
    ).dt.date

    assert trx["numero_transaccion"].is_unique, "numero_transaccion repetido"
    assert trx["fecha"].between(INICIO, FIN).all(), "fechas fuera de 2023-2025"
    assert trx["numero_transaccion"].str.len().max() <= 30

    trx["fecha"] = trx["fecha"].dt.date
    # enteros sin ".0": al unir líneas con nulos pandas los deja como decimales
    for c in ("cantidad", "duracion_minutos"):
        trx[c] = pd.to_numeric(trx[c]).round().astype("Int64")
    trx[COLUMNAS].to_csv(OUT / "transacciones.csv", index=False)
    (
        pd.concat(zonas)[ZONAS]
        .drop_duplicates("codigo_zona")
        .sort_values("codigo_zona")
        .to_csv(OUT / "zonas.csv", index=False)
    )
    cli.drop(columns=[c for c in cli if c.startswith("w_")]).to_csv(
        OUT / "clientes.csv", index=False
    )
    tipo_cambio().to_csv(OUT / "tipo_cambio.csv", index=False)
    pd.DataFrame(estadisticas).to_csv(OUT / "estadisticas_preparacion.csv", index=False)
    print(f"Listo: {len(trx):,} transacciones y {len(cli):,} clientes en {OUT.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
