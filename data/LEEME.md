# Datos del proyecto

Los archivos de datos **no se incluyen en este repositorio**. Pesan cientos de megabytes y algunas licencias no permiten redistribuirlos. Esta página indica qué dataset usa cada línea de negocio, dónde obtenerlo y cómo lo usa el ETL.

| Carpeta | Contenido |
|---|---|
| `data/raw/<fuente>/` | Archivos originales, tal como se descargan (sin descomprimir ni modificar) |
| `data/raw/manifiesto.csv` | URL, tamaño, SHA-256 y fecha de cada archivo descargado por script |
| `data/processed/` | Archivos intermedios generados por el ETL (clientes sintéticos y transacciones preparadas por línea) |

## Cómo obtener los datos

1. Ejecutar `python etl/python/descargar_fuentes.py`. Descarga las fuentes públicas que no piden sesión: taxis, aerolínea, Censo y tipo de cambio.
2. Descargar a mano las fuentes que piden sesión y dejar cada archivo, sin descomprimir, en la carpeta indicada en la tabla siguiente.

## Datasets por línea de negocio

| Línea | Dataset | Carpeta y archivos | Obtención | Período | Licencia |
|---|---|---|---|---|---|
| Buses InterUrbanos Rapiditos | [Operación de pasajeros y despacho de vehículos en la modalidad de transporte de pasajeros por carretera](https://www.datos.gov.co/Transporte/Operaci-n-de-pasajeros-y-despacho-de-veh-culos-en-/eh75-8ah6), Superintendencia de Transporte (Colombia) | `buses/supertransporte_AAAA-MM-DD.csv` (72 días: el 8 y el 22 de cada mes, solo despachos en origen) | Script (API pública) | 2023 a 2025 (2024 casi sin datos en la fuente) | CC BY-SA 4.0 |
| Trenes Rapiditos | [UK Train Rides](https://mavenanalytics.io/data-playground/uk-train-rides), Maven Analytics | `tren/UK+Train+Rides.zip` (`railway.csv`, 31.653 pasajes) | Manual, con cuenta gratuita en Maven Analytics | Enero a abril de 2024 | Dominio público. **Datos ficticios** según el proveedor |
| Radio Taxis Rapiditos | [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), NYC Taxi & Limousine Commission: taxis verdes | `taxi/green_tripdata_AAAA-MM.parquet` (36 archivos) y `taxi/taxi_zone_lookup.csv` | Script | 2023 a 2025 | Sin licencia abierta específica; se distribuye "AS IS" |
| Logística y Distribución Rapiditos | [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), Kaggle | `logistica/archive.zip` (9 CSV, 99.441 pedidos) | Manual, con cuenta de Kaggle | 2016 a 2018 | CC BY-NC-SA 4.0: uso no comercial, con atribución |
| Aerolíneas Rapiditos | [Airline Origin and Destination Survey (DB1B), tabla Market](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FHK), Bureau of Transportation Statistics (EE.UU.) | `aerolinea/Origin_and_Destination_Survey_DB1BMarket_AAAA_T.zip` (10 trimestres) | Script | 2023 T1 a 2025 T2 (BTS aún no publica 2025 T3 ni T4) | Datos del gobierno federal de EE.UU. |
| URapid Delivery | [Delivery Center: Food & Goods orders in Brazil](https://www.kaggle.com/datasets/nosbielcs/brazilian-delivery-center), Kaggle | `delivery/archive.zip` (7 CSV, 368.999 pedidos) | Manual, con cuenta de Kaggle | Enero a abril de 2021 | "Data files © Original Authors": sin licencia abierta. Se usa solo con fines académicos y sus archivos no se redistribuyen |

## Fuentes de apoyo

| Uso | Dataset | Carpeta y archivos | Obtención | Licencia |
|---|---|---|---|---|
| Calibrar los clientes sintéticos | [Censo de Población y Vivienda 2024](https://censo2024.ine.gob.cl/estadisticas/), INE Chile: tabla D1, población por sexo y grupos de edad quinquenales | `censo/D1_Poblacion-censada-por-sexo-y-edad-en-grupos-quinquenales.xlsx` | Script | CC BY-SA 4.0, con atribución al INE |
| Tarifa de buses (modelo `a + b · km`) | [Costos de viajes nacionales a los destinos más turísticos en vacaciones de invierno](https://www.sernac.cl/portal/617/articles-81027_archivo_01.pdf), SERNAC (junio de 2024): tablas 4 y 7, transcritas en `etl/referencias/sernac_2024_buses.csv` | `sernac/articles-81027_archivo_01.pdf` | Script | Publicación pública |
| Municipios de Colombia (zona y distancia de buses) | [DIVIPOLA](https://www.datos.gov.co/resource/gdxc-w37w), DANE | `buses/divipola_municipios.csv` | Script | CC BY-SA 4.0 |
| Factor carretera / línea recta | [GeoNames](https://download.geonames.org/export/dump/), archivo de Chile | `geonames/CL.zip` | Script | CC BY 4.0 |
| Convertir montos a pesos chilenos | [Base de Datos Estadísticos](https://si3.bcentral.cl/siete), Banco Central de Chile: dólar observado (cuadro TCB_505) y paridades (TCB_510), promedios anuales 2023-2025 | `tipo_cambio/TCB_505.html` y `tipo_cambio/TCB_510.html` | Script | Publicación pública del Banco Central |

## Cómo usa el ETL cada dataset

Todas las transacciones se asignan a **clientes sintéticos** residentes en Chile, generados con la distribución por comuna, sexo y edad del Censo 2024: ningún dataset público comparte clientes entre líneas de negocio. Las fechas fuera de 2023-2025 se trasladan a ese período. Los montos se convierten a pesos chilenos con el tipo de cambio anual del Banco Central. Esas transformaciones son sintéticas y se marcan como tales en el código, en la base y en el informe.

| Línea | Archivos usados | Uso en el modelo estrella |
|---|---|---|
| Trenes | `railway.csv` | Estaciones de salida y llegada → `dim_zona`; tipo de compra (online o estación) → `dim_canal_venta`; medio de pago → `dim_medio_pago`; clase del pasaje → `dim_servicio.clase_servicio`; precio en GBP → montos; horas de salida y llegada → `duracion_minutos` |
| Taxis | `green_tripdata_*.parquet`, `taxi_zone_lookup.csv` | Zonas de recogida y llegada → `dim_zona`; distancia en millas → `distancia_km`; horas de inicio y término → `duracion_minutos`; tarifa en USD → montos; tipo de pago → `dim_medio_pago` |
| Buses | `supertransporte_*.csv`, `divipola_municipios.csv` | Municipios de origen y destino → `dim_zona`; nivel de servicio (básico o lujo) → `dim_servicio.clase_servicio`; cada pasajero, una transacción (muestra ponderada por pasajeros); distancia en línea recta entre municipios × factor carretera → `distancia_km`; tarifa estimada con el modelo del SERNAC → montos (**monto sintético**) |
| Logística | `olist_orders`, `olist_order_items`, `olist_products`, `olist_customers`, `olist_sellers`, `olist_order_payments` | Ciudad y estado del vendedor y del comprador → zona de origen y de destino; precio y flete en BRL → montos; peso del producto → `peso_kg`; tipo de pago → `dim_medio_pago` |
| Aerolínea | DB1B Market | Aeropuertos de origen y destino → `dim_zona`; pasajeros → `cantidad`; tarifa en USD → montos; distancia en millas → `distancia_km`; trimestre → fecha, con el día asignado de forma sintética |
| Delivery | `orders`, `channels`, `payments`, `deliveries`, `drivers`, `stores`, `hubs` | Canal → `dim_canal_venta`; medio de pago → `dim_medio_pago`; tipo de repartidor (moto o bicicleta) → `dim_servicio.medio_transporte`; distancia de entrega → `distancia_km`; monto del pedido y tarifa de envío en BRL → montos; ciudad del hub → `dim_zona` |

## Nota sobre la línea de buses

La fuente aprobada en el Avance N°1 era ANTT Monitriip "Bilhetes de Passagem" (Brasil), pero el portal `dados.antt.gov.br` rechazó las descargas el 17-11-2026 ("Request Rejected"), tanto las automatizadas como las hechas desde el navegador. Se reemplazó por los datos de la Superintendencia de Transporte de Colombia, que no traen precio: la tarifa se estima con precios reales de buses chilenos publicados por el SERNAC.
