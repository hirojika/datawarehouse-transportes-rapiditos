"""Etapa 2 del ETL (síntesis): clientes sintéticos residentes en Chile.

DATOS SINTÉTICOS. Ningún dataset público comparte clientes entre líneas de negocio,
así que la vista única del cliente se construye con identidades generadas:
- Comuna, sexo y edad siguen la distribución real del Censo 2024 (INE, tabla D1, hoja 4).
- El segmento, la afinidad con cada línea y el nivel de actividad son SUPUESTOS del
  generador (constantes de este archivo). Los segmentos que aparezcan en el análisis
  reflejan estos supuestos, no hallazgos sobre clientes reales.
"""

from pathlib import Path

import numpy as np
import pandas as pd

LINEAS = ["BUS", "TRN", "TAX", "LOG", "AER", "DEL"]

# Supuesto: probabilidad de cada segmento según el tramo de edad (filas suman 1).
SEGMENTOS = ["joven_digital", "viajero_frecuente", "pendular", "hogar", "ocasional"]
PROB_SEGMENTO = {  # (edad mínima, edad máxima): probabilidades en el orden de SEGMENTOS
    (18, 29): [0.40, 0.10, 0.20, 0.10, 0.20],
    (30, 44): [0.15, 0.20, 0.20, 0.25, 0.20],
    (45, 64): [0.05, 0.20, 0.20, 0.25, 0.30],
    (65, 120): [0.02, 0.10, 0.15, 0.23, 0.50],
}

# Supuesto: afinidad relativa de cada segmento con cada línea, en el orden de LINEAS.
AFINIDAD = {
    "joven_digital": [1.0, 1.0, 4.0, 2.0, 1.0, 5.0],
    "viajero_frecuente": [1.0, 3.0, 3.0, 1.0, 6.0, 1.0],
    "pendular": [5.0, 4.0, 1.0, 1.0, 0.5, 1.0],
    "hogar": [1.0, 1.0, 1.0, 5.0, 1.0, 3.0],
    "ocasional": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "empresa": [0.3, 2.0, 2.0, 8.0, 4.0, 0.5],
}
# Supuesto: actividad base por segmento; se multiplica por un factor lognormal individual.
ACTIVIDAD_BASE = {s: 1.0 for s in AFINIDAD} | {"ocasional": 0.3, "empresa": 2.0}

# Supuesto: quienes viven en la Región Metropolitana usan más taxi y delivery;
# en el resto del país, más bus y logística.
AJUSTE_RM = [1.0, 1.0, 1.5, 1.0, 1.0, 1.5]
AJUSTE_REGIONES = [1.5, 1.0, 1.0, 1.3, 1.0, 1.0]

FECHA_CENSO = pd.Timestamp("2024-04-09")  # inicio del levantamiento censal


def leer_censo(ruta: Path) -> pd.DataFrame:
    """Población por comuna, grupo quinquenal y sexo (solo filas de comunas)."""
    d = pd.read_excel(ruta, sheet_name="4", header=3)
    d = d[d["Código comuna"].fillna(0).astype(int) != 0]
    d = d[d["Grupos de edad"].str.contains(r"^\d", na=False)]
    edades = d["Grupos de edad"].str.extract(r"^(\d+)(?: a (\d+))?")
    d = d.assign(
        edad_min=edades[0].astype(int),
        edad_max=edades[1].fillna(90).astype(int),  # "85 o más" se acota a 90
    )
    return d


def generar(ruta_censo: Path, n_personas: int, n_empresas: int, rng: np.random.Generator):
    """Devuelve un DataFrame de clientes con su peso de compra por línea (columnas w_<LINEA>)."""
    censo = leer_censo(ruta_censo)
    # Solo mayores de 18: del grupo "15 a 19" quedan las edades 18 y 19 (2 de 5).
    censo = censo[censo["edad_max"] >= 18].copy()
    factor = np.where(censo["edad_min"] < 18, 2 / 5, 1.0)
    censo["edad_min"] = censo["edad_min"].clip(lower=18)
    celdas = pd.concat(
        [
            censo.assign(genero="Masculino", poblacion=censo["Hombres"] * factor),
            censo.assign(genero="Femenino", poblacion=censo["Mujeres"] * factor),
        ],
        ignore_index=True,
    )
    p = celdas["poblacion"].to_numpy(float)
    elegidas = celdas.iloc[rng.choice(len(celdas), size=n_personas, p=p / p.sum())]

    edad = rng.integers(elegidas["edad_min"], elegidas["edad_max"] + 1)
    dias = rng.integers(0, 365, size=n_personas)
    nacimiento = FECHA_CENSO - pd.to_timedelta(edad * 365.25 + dias, unit="D")

    segmento = np.empty(n_personas, dtype=object)
    for (desde, hasta), probs in PROB_SEGMENTO.items():
        m = (edad >= desde) & (edad <= hasta)
        segmento[m] = rng.choice(SEGMENTOS, size=m.sum(), p=probs)

    personas = pd.DataFrame(
        {
            "codigo_cliente": [f"CLI-{i:06d}" for i in range(1, n_personas + 1)],
            "nombre_cliente": [f"Cliente Sintético {i:06d}" for i in range(1, n_personas + 1)],
            "genero": elegidas["genero"].to_numpy(),
            "fecha_nacimiento": nacimiento.normalize().date,
            "tipo_cliente": "persona",
            "comuna_residencia": elegidas["Comuna"].to_numpy(),
            "region_residencia": elegidas["Región"].to_numpy(),
            "segmento": segmento,
        }
    )

    # Empresas: comuna proporcional a la población total de cada comuna.
    tot = censo.groupby(["Región", "Comuna"], as_index=False)["Población censada"].sum()
    pt = tot["Población censada"].to_numpy(float)
    ce = tot.iloc[rng.choice(len(tot), size=n_empresas, p=pt / pt.sum())]
    empresas = pd.DataFrame(
        {
            "codigo_cliente": [f"EMP-{i:06d}" for i in range(1, n_empresas + 1)],
            "nombre_cliente": [f"Empresa Sintética {i:06d}" for i in range(1, n_empresas + 1)],
            "genero": None,
            "fecha_nacimiento": None,
            "tipo_cliente": "empresa",
            "comuna_residencia": ce["Comuna"].to_numpy(),
            "region_residencia": ce["Región"].to_numpy(),
            "segmento": "empresa",
        }
    )

    clientes = pd.concat([personas, empresas], ignore_index=True)
    clientes["pais_residencia"] = "Chile"

    actividad = clientes["segmento"].map(ACTIVIDAD_BASE).to_numpy() * rng.lognormal(
        0, 0.8, len(clientes)
    )
    es_rm = clientes["region_residencia"].str.contains("Metropolitana").to_numpy()
    ajuste = np.where(es_rm[:, None], AJUSTE_RM, AJUSTE_REGIONES)
    afinidad = np.vstack(clientes["segmento"].map(AFINIDAD).to_numpy())
    pesos = afinidad * ajuste * actividad[:, None]
    for j, linea in enumerate(LINEAS):
        clientes[f"w_{linea}"] = pesos[:, j]
    return clientes


def asignar(clientes: pd.DataFrame, linea: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """Elige un cliente para cada una de las n transacciones de la línea, según su peso."""
    w = clientes[f"w_{linea}"].to_numpy()
    return clientes["codigo_cliente"].to_numpy()[rng.choice(len(w), size=n, p=w / w.sum())]
