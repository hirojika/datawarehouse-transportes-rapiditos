# Propuesta de fuentes de información

**Estado: aprobada por el grupo el 05-11-2026** (decisiones en la sección 4). Está incorporada al informe, en la sección Fuentes de Información (`informe/secciones/fuentes_de_informacion.tex`), adelantada al Avance N°1.

**Actualizada el 17-11-2026 para el Avance N°2** (sección 5): todas las fuentes quedaron verificadas, y la línea de buses cambió de ANTT (Brasil) a Supertransporte (Colombia), porque el portal de ANTT rechaza las descargas.

Cada fuente indica su estado de verificación:
- **Verificado:** se leyó la página oficial del dataset.
- **Parcial:** solo se vieron extractos en resultados de búsqueda.
- **Por verificar:** no se pudo abrir la fuente y hay que revisarla en el navegador antes de usarla.

## 1. Lo que condiciona la elección

1. **Ningún dataset público comparte clientes entre líneas.** Los datos de transporte se publican anonimizados, así que no existe un "mismo cliente" que viaje en bus, tome taxi y pida delivery. La vista única del cliente del caso necesita una **capa de clientes sintética**: identidades generadas (RUT ficticio, edad, género, comuna de residencia), a las que se asignan las transacciones públicas de cada línea. Esa capa debe marcarse como sintética en el código, en la base y en el informe.
2. **El grano del modelo es la transacción.** Las fuentes que solo publican totales (por mes, ruta o servicio) no alimentan `fact_venta` directamente. Hay que desagregarlas en transacciones sintéticas que reproduzcan esos totales, es decir, datos **sintéticos calibrados con datos reales**.
3. **El período del objetivo son los últimos 3 años (2023-2025).** Las fuentes de otros años requieren trasladar sus fechas a ese período, y ese traslado también se documenta como transformación sintética.
4. **La empresa del caso es internacional.** Usar datos de varios países calza con el enunciado y con `dim_zona`, que tiene país y continente.

## 2. Fuente propuesta por línea de negocio

### Buses InterUrbanos Rapiditos: ANTT Monitriip "Bilhetes de Passagem" (Brasil)

| Aspecto | Detalle |
|---|---|
| Publicador | ANTT, Agência Nacional de Transportes Terrestres, en su portal de datos abiertos |
| Enlace | https://dados.antt.gov.br/dataset/monitriip-bilhetes-de-passagem |
| Contenido | Pasajes del transporte interestatal de pasajeros por bus |
| Período | Archivos CSV mensuales; en la búsqueda aparecen desde 2019 hasta noviembre de 2025. **Cubre 2023-2025** |
| Licencia | Creative Commons Atribución (según la ficha del diccionario de datos) |
| Campos vistos | `mes_emissao_bilhete`, `mes_viagem`, `ponto_origem_viagem`, `ponto_destino_viagem`, `tipo_servico`, `tipo_gratuidade`, `quantidade_bilhetes`, `media_valor_total`, `dp_valor_total` |
| Uso en el modelo | Origen y destino → `dim_zona`; tipo de servicio → `dim_servicio.clase_servicio`; cantidad y valor medio → transacciones; gratuidad → descuento |
| Advertencia | Por sus columnas, **parece agregado** por mes, origen, destino y tipo de servicio, no un registro por pasaje. Se desagrega en transacciones sintéticas calibradas |
| Estado | **Descartada el 17-11-2026.** El portal rechaza las descargas ("Request Rejected"), tanto automatizadas como desde el navegador. Se reemplazó por Supertransporte (Colombia); ver sección 5 |

Complemento chileno: la Encuesta Estructural de Transporte Interurbano de Pasajeros por Carretera (ETRANP) del INE, que es anual y agregada. Sirve para dar contexto en el informe, no para cargar transacciones.

### Trenes Rapiditos: Maven Analytics "UK Train Rides" (Reino Unido)

| Aspecto | Detalle |
|---|---|
| Publicador | Maven Analytics (Data Playground); fuente original: Carlos Pacheco, vía Tableau Public |
| Enlace | https://mavenanalytics.io/data-playground/uk-train-rides |
| Contenido | Venta de pasajes de National Rail: tipo y clase de pasaje, fecha y hora del viaje, estaciones de salida y llegada, precio, estado del viaje y retrasos |
| Período | Enero a abril de 2024 |
| Licencia | Dominio público ("License: Public Domain") |
| Tamaño | La página del desafío dice 31.653 registros y 18 campos; la del dataset, 499 registros y 25 campos. Hay que confirmarlo al descargar |
| Uso en el modelo | Estaciones → `dim_zona`; precio → montos; tipo de compra (online o estación) → `dim_canal_venta`; medio de pago → `dim_medio_pago`; clase → `dim_servicio.clase_servicio` |
| Advertencia | **Son datos ficticios** según el propio proveedor ("Mock train ticket data for National Rail in the UK, from Jan to Apr 2024"). Además solo cubren 4 meses, así que hay que extenderlos a 2023-2025 |
| Estado | **Verificado**: carácter ficticio, período, licencia y fuente. Los nombres exactos de los campos se confirman al descargar, porque la descarga pide registrarse |

Complemento chileno: la Memoria Anual de EFE, que publica pasajeros transportados por servicio. Está en PDF y es agregada.

### Radio Taxis Rapiditos: NYC TLC Trip Record Data (Estados Unidos)

| Aspecto | Detalle |
|---|---|
| Publicador | NYC Taxi & Limousine Commission |
| Enlace | https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page |
| Contenido | Un registro por viaje de taxi (amarillo y verde): fecha y hora de recogida y de llegada, zona de origen y de destino, distancia, tarifa desglosada, tipo de tarifa, **tipo de pago** y número de pasajeros |
| Período | Taxis amarillos desde enero de 2009 hasta septiembre de 2026, con unos dos meses de desfase. **Cubre 2023-2025** |
| Formato | Parquet mensual, más una tabla de zonas (`taxi_zone_lookup.csv`) y diccionarios de datos en PDF |
| Términos | Sin licencia abierta específica; se distribuye "AS IS". La TLC no garantiza la exactitud de los datos |
| Uso en el modelo | Zonas → `dim_zona`; distancia, convertida de millas a km → `distancia_km`; duración, a partir de las horas → `duracion_minutos`; tarifas → montos; tipo de pago → `dim_medio_pago` |
| Advertencia | Volumen muy alto (millones de viajes al mes): hay que usar una muestra |
| Estado | **Verificado** |

### Logística y Distribución Rapiditos: Olist "Brazilian E-Commerce Public Dataset" (Brasil)

| Aspecto | Detalle |
|---|---|
| Publicador | Olist, en Kaggle (`olistbr/brazilian-ecommerce`) |
| Enlace | https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce |
| Contenido | Cerca de 100 mil pedidos con clientes, ítems, pagos, productos y vendedores. Incluye costo de envío por ítem (`freight_value`) y peso del producto en gramos (`product_weight_g`) |
| Período | 2016 a 2018: hay que trasladar las fechas a 2023-2025 |
| Licencia | CC BY-NC-SA 4.0 según una fuente secundaria. Permite uso académico, no comercial |
| Uso en el modelo | Ciudad y estado del cliente y del vendedor → zona de destino y de origen; precio y flete → montos; peso → `peso_kg`; tipo de pago → `dim_medio_pago` |
| Estado | **Parcial**: hay que confirmar la licencia y las columnas en la página de Kaggle |

Alternativa: **DataCo Smart Supply Chain** (Mendeley Data, versión 5 de marzo de 2019, licencia CC BY 4.0 verificada), https://data.mendeley.com/datasets/8gx2fvg2k6. Según fuentes secundarias trae segmento de cliente, modo de envío, mercado y región, con unos 180 mil pedidos. El segmento serviría para `tipo_cliente` (persona o empresa), pero no parece traer peso.

### Aerolíneas Rapiditos: BTS "Airline Origin and Destination Survey" (DB1B, Estados Unidos)

| Aspecto | Detalle |
|---|---|
| Publicador | Bureau of Transportation Statistics, Departamento de Transporte de EE.UU. |
| Enlace | https://www.bts.gov/topics/airlines-and-airports/origin-and-destination-survey-data |
| Contenido | Muestra de pasajes aéreos: cada registro es un pasaje, con aerolínea, tarifa pagada y ruta |
| Período | Archivos trimestrales; hay de 2024. **Cubre 2023-2025.** La muestra es del 10 % de los pasajes y, según BTS, sube al 40 % desde julio de 2025 |
| Términos | Datos del gobierno federal de EE.UU. Hay que confirmar los términos en la página |
| Uso en el modelo | Aeropuertos de origen y destino → `dim_zona`; tarifa → montos; pasajeros → `cantidad`; trimestre → fecha, con el día asignado sintéticamente |
| Estado | **Parcial.** La página respondió con error 403; los datos vienen de resultados de búsqueda y de una guía de BTS |

Complemento chileno: las estadísticas mensuales de la Junta de Aeronáutica Civil (JAC), con tráfico por rutas, operadores y pares de ciudades. Son agregadas y no se confirmó un formato descargable.

### URapid Delivery: "Delivery Center: Food & Goods orders" (Brasil)

| Aspecto | Detalle |
|---|---|
| Publicador | Delivery Center, en Kaggle (según Gironews, 2021) |
| Enlace | Página original no encontrada. Hay una copia parcial en https://github.com/lore5g/Delivery-Center-Dataset-Brazil |
| Contenido | Tablas de pedidos, tiendas, canales, pagos, entregas y repartidores, con muestra de São Paulo, Río de Janeiro, Paraná y Rio Grande do Sul. La tabla de pedidos (verificada en la copia) tiene `channel_id`, `order_amount`, `order_delivery_fee`, `order_delivery_cost` y momentos del pedido, con 368.999 pedidos |
| Período | Enero a abril de 2021, según las fechas vistas en la copia. Hay que trasladar las fechas a 2023-2025 |
| Licencia | **No confirmada** |
| Uso en el modelo | Canal → `dim_canal_venta`; pago → `dim_medio_pago`; tipo de repartidor (moto o bicicleta) → `dim_servicio.medio_transporte`; montos y tarifa de envío → montos |
| Estado | **Por verificar**: hay que encontrar la página de Kaggle y su licencia antes de usarlo. Si la licencia no permite el uso, esta línea se genera de forma sintética |

## 3. Fuentes de apoyo

| Fuente | Para qué | Enlace | Estado |
|---|---|---|---|
| INE, Censo de Población y Vivienda 2024 | Calibrar la capa sintética de clientes con la distribución real por comuna, sexo y edad. Las bases de microdatos se publicaron el 04-12-2025 | https://www.ine.gob.cl/sala-de-prensa/prensa/general/noticia/2025/12/04/ine-publica-base-de-datos-del-censo-de-poblaci%C3%B3n-y-vivienda-2024 | Parcial |
| Tablas de zonas de cada fuente | `dim_zona`: zonas de taxi de Nueva York, puntos de origen y destino de ANTT, estaciones del Reino Unido y aeropuertos de EE.UU. | Incluidas en cada dataset | Según cada fuente |
| Tipos de cambio | Convertir USD, GBP y BRL a pesos chilenos (CLP), la moneda del modelo. Se propone usar los tipos de cambio publicados por el Banco Central de Chile | Por definir | Por verificar |

`dim_tiempo` no necesita fuente externa: se genera con un script SQL.

## 4. Decisiones del grupo (05-11-2026)

1. **Enfoque de datos:** combinación de transacciones públicas reales por línea con una capa de clientes sintética calibrada con el Censo 2024. **Aprobado.**
2. **Una fuente por línea:** la propuesta de la sección 2. En logística se usa Olist; DataCo queda como alternativa. **Aprobado.**
3. **Residencia de los clientes sintéticos:** **Chile**, calibrada con el Censo 2024.
4. **Fuentes con riesgo:** se aceptan Delivery Center (licencia no confirmada) y UK Train Rides (ficticia), declarando sus limitaciones en el informe. Si la licencia de Delivery Center no permite usarlo, URapid Delivery se genera de forma sintética, sin cambios en el modelo.
5. **Informe:** la sección Fuentes de Información se adelanta al **Avance N°1**.

Pendiente para la Fase 2: confirmar en el navegador lo que quedó en estado parcial o por verificar (diccionario de ANTT, página de BTS, columnas y licencia de Olist, página original de Delivery Center) y la fuente de los tipos de cambio.

## 5. Revisión del Avance N°2 (17-11-2026)

Todas las fuentes se revisaron de nuevo antes de construir el ETL. El detalle de cada archivo, su licencia y su uso está en `data/LEEME.md`.

### 5.1 Estado final por línea

| Línea | Fuente | Estado | Obtención |
|---|---|---|---|
| Buses | **Supertransporte (Colombia)**, "Operación de pasajeros y despacho de vehículos en la modalidad de transporte de pasajeros por carretera", datos.gov.co, dataset `eh75-8ah6`, CC BY-SA 4.0 | Verificado | Script, por la API pública: 2 días por mes (8 y 22), solo despachos en origen |
| Trenes | UK Train Rides (Maven Analytics), dominio público, ficticio | Verificado: `railway.csv`, 31.653 pasajes y 18 columnas | Manual (cuenta de Maven) |
| Taxis | NYC TLC, taxis verdes 2023-2025 | Verificado | Script |
| Logística | Olist (Kaggle), CC BY-NC-SA 4.0 | Verificado: 9 CSV, 99.441 pedidos | Manual (cuenta de Kaggle) |
| Aerolínea | BTS DB1B Market, 2023 T1 a 2025 T2, más la tabla de aeropuertos `L_AIRPORT` | Verificado: 2025 T3 y T4 aún no se publican | Script |
| Delivery | Delivery Center (Kaggle), "Data files © Original Authors" (sin licencia abierta) | Verificado: 7 CSV, 368.999 pedidos | Manual (cuenta de Kaggle). Sus archivos no se publican (decisión del grupo) |

**Buses (Supertransporte):** trae pasajeros reales por terminal, municipio de origen y de destino, fecha, hora, clase de vehículo y nivel de servicio (básico o lujo). Limitaciones:
- No trae precio. La tarifa se estima con un modelo (sección 5.2).
- 2024 casi no tiene datos: 106 mil filas, frente a 12,3 millones en 2023 y 11,7 millones en 2025. Cada mes de 2024 con menos de la mitad de los pasajeros del mismo mes de 2023 se reemplaza por ese mes de 2023, trasladado un año. Ese traslado es sintético.
- Trae algunas fechas inválidas (años 2202, 2222 y 6202), que quedan fuera de la extracción.

### 5.2 Fuentes de apoyo aprobadas el 17-11-2026

| Fuente | Para qué | Licencia |
|---|---|---|
| INE, Censo 2024, tabla D1 (población por sexo y grupos quinquenales de edad, hoja 4 por comuna) | Distribución de comuna, sexo y edad de los clientes sintéticos | CC BY-SA 4.0 |
| Banco Central de Chile, cuadros TCB_505 (dólar observado) y TCB_510 (paridades), promedios anuales 2023-2025 | Convertir USD, GBP y BRL a CLP. Dólar: 839,07, 943,58 y 951,64 CLP | Publicación pública |
| SERNAC, "Costos de viajes nacionales a los destinos más turísticos en vacaciones de invierno" (junio de 2024), tablas 4 y 7 | Precios reales de pasajes de bus (semi cama y salón cama) y km por carretera de 28 rutas chilenas, para ajustar la tarifa de buses `a + b · km` | Publicación pública |
| DANE, DIVIPOLA (datos.gov.co, `gdxc-w37w`) | Nombre, departamento y coordenadas de los municipios colombianos, para `dim_zona` y la distancia | CC BY-SA 4.0 |
| GeoNames, archivo de Chile (`CL.zip`) | Coordenadas de las ciudades chilenas del SERNAC, para calcular cuánto más larga es la ruta por carretera que la línea recta (factor que se aplica a Colombia) | CC BY 4.0 |

Resultado del modelo de tarifa con estos datos: básico (semi cama), 6.918 + 18,8 CLP por km; lujo (salón cama), 6.917 + 26,6 CLP por km; factor carretera / línea recta, 1,21 (mediana de las 28 rutas).

### 5.3 Tamaño de la muestra

Unos 10.000 clientes (9.500 personas y 500 empresas) y 120.000 transacciones: 25.000 de buses, 15.000 de trenes, 25.000 de taxis, 20.000 de logística, 15.000 de aerolínea y 20.000 de delivery.
