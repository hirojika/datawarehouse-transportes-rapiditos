"""Etapa 1 del ETL (extracción): descarga las fuentes públicas que no requieren sesión.

Guarda cada archivo sin modificar en data/raw/<fuente>/ y registra URL, tamaño,
SHA-256 y fecha de descarga en data/raw/manifiesto.csv. Si el archivo ya existe,
no lo vuelve a descargar. Las fuentes que piden sesión o bloquean el acceso
automatizado (ANTT, UK Train Rides, Olist, Delivery Center) se descargan a mano;
ver docs/fuentes_de_informacion.md.

Uso:  python etl/python/descargar_fuentes.py
"""

import csv
import hashlib
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"

TLC = "https://d37ci6vzurychx.cloudfront.net"
BTS = "https://transtats.bts.gov/PREZIP/Origin_and_Destination_Survey_DB1BMarket_{}_{}.zip"
BCCH = (
    "https://si3.bcentral.cl/Siete/ES/Siete/Cuadro/CAP_TIPO_CAMBIO/MN_TIPO_CAMBIO4/{}"
    "?cbCalculo=NONE&cbFechaBase=&cbFechaInicio=2023&cbFechaTermino=2025&cbFrecuencia=ANNUAL"
)

MESES = [f"{a}-{m:02d}" for a in (2023, 2024, 2025) for m in range(1, 13)]

# Supertransporte (Colombia): despachos y pasajeros por terminal. El dataset completo tiene
# más de 30 millones de filas y la API tarda minutos en agregar, así que se descargan las
# filas de 2 días fijos por mes (8 y 22), solo despachos en origen.
SUPERTRANSPORTE = "https://www.datos.gov.co/resource/eh75-8ah6.csv?" + "{}"
DIAS_BUSES = [f"{m}-{d}" for m in MESES for d in ("08", "22")]


def url_buses(dia: str) -> str:
    return SUPERTRANSPORTE.format(
        urlencode(
            {
                "$where": f"fecha_despacho = '{dia}T00:00:00' AND tipo_despacho = 'ORIGEN'",
                "$limit": 500000,
            }
        )
    )


# BTS publica con unos 6 meses de desfase: el 17-11-2026 el último trimestre disponible era 2025 T2.
TRIMESTRES = [(a, t) for a in (2023, 2024, 2025) for t in (1, 2, 3, 4) if (a, t) <= (2025, 2)]

FUENTES = (
    [("taxi", f"{TLC}/trip-data/green_tripdata_{m}.parquet", None) for m in MESES]
    + [("taxi", f"{TLC}/misc/taxi_zone_lookup.csv", None)]
    + [("aerolinea", BTS.format(a, t), None) for a, t in TRIMESTRES]
    + [
        (
            "aerolinea",
            "https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVecbeg",
            "L_AIRPORT.csv",
        )
    ]
    + [
        (
            "censo",
            "https://censo2024.ine.gob.cl/wp-content/uploads/2025/03/"
            "D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx",
            None,
        ),
        ("tipo_cambio", BCCH.format("DOLAR_OBS_ADO/TCB_505"), "TCB_505.html"),
        ("tipo_cambio", BCCH.format("TCB_510_PARIDADES/TCB_510"), "TCB_510.html"),
        # Línea de buses (Colombia): municipios del DANE, tarifas del SERNAC y coordenadas de Chile
        (
            "buses",
            "https://www.datos.gov.co/resource/gdxc-w37w.csv?$limit=5000",
            "divipola_municipios.csv",
        ),
        ("sernac", "https://www.sernac.cl/portal/617/articles-81027_archivo_01.pdf", None),
        ("geonames", "https://download.geonames.org/export/dump/CL.zip", None),
    ]
    + [("buses", url_buses(d), f"supertransporte_{d}.csv") for d in DIAS_BUSES]
)


def descargar(url: str, destino: Path, intentos: int = 3) -> None:
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    for intento in range(1, intentos + 1):
        try:
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(temporal, "wb") as f:
                    for bloque in r.iter_content(1 << 20):
                        f.write(bloque)
            break
        # los portales a veces cortan la conexión al conectar o a mitad de la respuesta
        except (
            requests.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.Timeout,
        ):
            if intento == intentos:
                raise
            print(f"  conexión cortada, reintento {intento + 1} de {intentos}")
            time.sleep(10 * intento)
    temporal.replace(destino)  # sin archivos a medias si la descarga se corta


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main() -> None:
    manifiesto = RAW / "manifiesto.csv"
    previos = {}
    if manifiesto.exists():
        with open(manifiesto, encoding="utf-8", newline="") as f:
            previos = {fila["archivo"]: fila for fila in csv.DictReader(f)}

    filas = dict(previos)
    for carpeta, url, nombre in FUENTES:
        destino = RAW / carpeta / (nombre or url.rsplit("/", 1)[-1])
        clave = destino.relative_to(RAW).as_posix()
        if destino.exists() and clave in previos:
            print(f"ya existe   {clave}")
            continue
        if destino.exists():
            print(f"registrando {clave} (ya descargado)")
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            print(f"descargando {clave}")
            descargar(url, destino)
        filas[clave] = {
            "archivo": clave,
            "url": url,
            "bytes": destino.stat().st_size,
            "sha256": sha256(destino),
            "descargado": datetime.now().isoformat(timespec="seconds"),
        }
        # se reescribe tras cada archivo para no perder el registro si algo falla después
        with open(manifiesto, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["archivo", "url", "bytes", "sha256", "descargado"])
            w.writeheader()
            w.writerows(sorted(filas.values(), key=lambda x: x["archivo"]))

    print(f"Listo: {len(filas)} archivos en {manifiesto.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
