"""Pruebas de las funciones de preparación de datos (etl/python), sin base de datos."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl" / "python"))
import clientes  # noqa: E402
import preparar_datos as p  # noqa: E402


def test_trasladar_ventanas_cubre_2023_a_2025():
    rng = np.random.default_rng(0)
    fechas = pd.Series(pd.date_range("2024-01-01", "2024-04-30", freq="D")).sample(
        5000, replace=True, random_state=0
    )
    out = p.trasladar_ventanas(fechas.reset_index(drop=True), 4, rng)
    assert out.between(p.INICIO, p.FIN).all()
    assert out.dt.to_period("M").nunique() == 36


def test_cambiar_anio_conserva_mes_y_dia_y_corrige_29_de_febrero():
    rng = np.random.default_rng(0)
    fechas = pd.Series(pd.to_datetime(["2016-02-29", "2017-07-15", "2018-12-31"]))
    out = p.cambiar_anio(fechas, rng)
    assert out.dt.year.between(2023, 2025).all()
    assert list(out.dt.month) == [2, 7, 12]
    assert list(out.dt.day) == [28, 15, 31]


def test_haversine_santiago_valparaiso():
    km = p.haversine_km(-33.45, -70.67, -33.05, -71.62)
    assert km == pytest.approx(98, abs=5)


def test_asignar_respeta_los_pesos():
    rng = np.random.default_rng(0)
    cli = pd.DataFrame({"codigo_cliente": ["A", "B"], "w_BUS": [9.0, 1.0]})
    elegidos = pd.Series(clientes.asignar(cli, "BUS", 10000, rng))
    assert elegidos.value_counts(normalize=True)["A"] == pytest.approx(0.9, abs=0.02)
