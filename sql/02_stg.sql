-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°2: esquema de staging (stg) del proceso ETL.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Profesor:          Luis Cofré B.
-- Fecha:             18-11-2026
--
-- Descripción:
--   Crea el esquema stg, donde el ETL de Apache Hop deja los datos tal como
--   llegan de los archivos preparados, antes de cargarlos al modelo estrella
--   (esquema dwh). Incluye la vista v_transaccion_conformada, que convierte
--   cada transacción a los códigos, unidades y moneda del modelo y calcula el
--   motivo de rechazo de las filas que no cumplen las reglas de calidad.
--
-- Motor: PostgreSQL 17. Se ejecuta igual que 01_ddl.sql (pgAdmin o psql) y
--   también lo ejecuta el workflow principal de Hop al inicio de cada carga.
--   Es idempotente: elimina y vuelve a crear el esquema stg en una sola
--   transacción.
--
-- Nomenclatura: tablas en singular, snake_case y minúsculas, sin prefijo
--   fact_/dim_ (no son parte del modelo estrella). Restricciones pk_, uq_ y
--   ck_ con el nombre de la tabla.
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

DROP SCHEMA IF EXISTS stg CASCADE;
CREATE SCHEMA stg;
COMMENT ON SCHEMA stg IS 'Staging del ETL: datos de las fuentes antes de cargarlos al esquema dwh';

CREATE TABLE stg.cliente (
    codigo_cliente     VARCHAR(20)   NOT NULL,
    nombre_cliente     VARCHAR(100),
    genero             VARCHAR(20),
    fecha_nacimiento   DATE,
    tipo_cliente       VARCHAR(20),
    comuna_residencia  VARCHAR(60),
    region_residencia  VARCHAR(60),
    segmento           VARCHAR(30),
    pais_residencia    VARCHAR(60),
    fecha_registro     DATE,
    CONSTRAINT pk_cliente PRIMARY KEY (codigo_cliente)
);
COMMENT ON TABLE stg.cliente IS 'Clientes SINTÉTICOS residentes en Chile, calibrados con el Censo 2024';
COMMENT ON COLUMN stg.cliente.codigo_cliente IS 'Llave natural del cliente (CLI- persona, EMP- empresa)';
COMMENT ON COLUMN stg.cliente.nombre_cliente IS 'Nombre sintético';
COMMENT ON COLUMN stg.cliente.genero IS 'Sexo según el Censo 2024 (NULL para empresas)';
COMMENT ON COLUMN stg.cliente.fecha_nacimiento IS 'Fecha de nacimiento sintética (NULL para empresas)';
COMMENT ON COLUMN stg.cliente.tipo_cliente IS 'persona o empresa';
COMMENT ON COLUMN stg.cliente.comuna_residencia IS 'Comuna de residencia, según la distribución del Censo 2024';
COMMENT ON COLUMN stg.cliente.region_residencia IS 'Región de residencia';
COMMENT ON COLUMN stg.cliente.segmento IS 'Segmento asignado por el generador (supuesto). No se carga al dwh: sirve para validar el análisis';
COMMENT ON COLUMN stg.cliente.pais_residencia IS 'País de residencia';
COMMENT ON COLUMN stg.cliente.fecha_registro IS 'Fecha de alta sintética, anterior a la primera compra';

CREATE TABLE stg.zona (
    codigo_zona  VARCHAR(20)  NOT NULL,
    comuna       VARCHAR(60),
    ciudad       VARCHAR(60),
    region       VARCHAR(60),
    pais         VARCHAR(60),
    continente   VARCHAR(30),
    CONSTRAINT pk_zona PRIMARY KEY (codigo_zona)
);
COMMENT ON TABLE stg.zona IS 'Zonas de origen y destino de todas las líneas, con su jerarquía geográfica';
COMMENT ON COLUMN stg.zona.codigo_zona IS 'Llave natural: prefijo de país y código de la fuente';
COMMENT ON COLUMN stg.zona.comuna IS 'Comuna, municipio, barrio, estación o aeropuerto';
COMMENT ON COLUMN stg.zona.ciudad IS 'Ciudad';
COMMENT ON COLUMN stg.zona.region IS 'Región, estado o departamento';
COMMENT ON COLUMN stg.zona.pais IS 'País';
COMMENT ON COLUMN stg.zona.continente IS 'Continente';

CREATE TABLE stg.transaccion (
    numero_transaccion   VARCHAR(30)    NOT NULL,
    codigo_linea         VARCHAR(3)     NOT NULL,
    fecha                DATE,
    codigo_cliente       VARCHAR(20),
    servicio_fuente      VARCHAR(40),
    codigo_zona_origen   VARCHAR(20),
    codigo_zona_destino  VARCHAR(20),
    canal_fuente         VARCHAR(40),
    pago_fuente          VARCHAR(40),
    estado_fuente        VARCHAR(20),
    moneda               VARCHAR(3),
    cantidad             INTEGER,
    monto_bruto          NUMERIC(14,2),
    monto_descuento      NUMERIC(14,2),
    distancia            NUMERIC(14,2),
    unidad_distancia     VARCHAR(5),
    duracion_minutos     INTEGER,
    peso                 NUMERIC(12,2),
    unidad_peso          VARCHAR(5),
    fecha_sintetica      BOOLEAN,
    monto_sintetico      BOOLEAN,
    CONSTRAINT pk_transaccion PRIMARY KEY (numero_transaccion)
);
COMMENT ON TABLE stg.transaccion IS 'Transacciones de las 6 líneas en formato común, con los códigos, unidades y moneda de cada fuente';
COMMENT ON COLUMN stg.transaccion.numero_transaccion IS 'Identificador de la transacción, prefijado por línea';
COMMENT ON COLUMN stg.transaccion.codigo_linea IS 'BUS, TRN, TAX, LOG, AER o DEL';
COMMENT ON COLUMN stg.transaccion.fecha IS 'Fecha de la compra, en 2023-2025';
COMMENT ON COLUMN stg.transaccion.codigo_cliente IS 'Cliente sintético asignado a la transacción';
COMMENT ON COLUMN stg.transaccion.servicio_fuente IS 'Clase o tipo de servicio, con el valor de la fuente';
COMMENT ON COLUMN stg.transaccion.codigo_zona_origen IS 'Zona de origen (stg.zona)';
COMMENT ON COLUMN stg.transaccion.codigo_zona_destino IS 'Zona de destino (stg.zona)';
COMMENT ON COLUMN stg.transaccion.canal_fuente IS 'Canal de venta con el valor de la fuente (NULL si la fuente no lo informa)';
COMMENT ON COLUMN stg.transaccion.pago_fuente IS 'Medio de pago con el valor de la fuente (NULL si la fuente no lo informa)';
COMMENT ON COLUMN stg.transaccion.estado_fuente IS 'valido, o el motivo por el que la fuente marca la transacción como no válida';
COMMENT ON COLUMN stg.transaccion.moneda IS 'Moneda de los montos: CLP, USD, GBP o BRL';
COMMENT ON COLUMN stg.transaccion.cantidad IS 'Pasajes, pasajeros o ítems';
COMMENT ON COLUMN stg.transaccion.monto_bruto IS 'Monto antes de descuentos, en la moneda de la fuente';
COMMENT ON COLUMN stg.transaccion.monto_descuento IS 'Descuento, en la moneda de la fuente';
COMMENT ON COLUMN stg.transaccion.distancia IS 'Distancia en la unidad de la fuente';
COMMENT ON COLUMN stg.transaccion.unidad_distancia IS 'km, mi (millas) o m (metros)';
COMMENT ON COLUMN stg.transaccion.duracion_minutos IS 'Duración del viaje o del pedido, en minutos';
COMMENT ON COLUMN stg.transaccion.peso IS 'Peso en la unidad de la fuente';
COMMENT ON COLUMN stg.transaccion.unidad_peso IS 'g (gramos) o kg';
COMMENT ON COLUMN stg.transaccion.fecha_sintetica IS 'TRUE si la fecha fue trasladada o asignada de forma sintética';
COMMENT ON COLUMN stg.transaccion.monto_sintetico IS 'TRUE si el monto fue estimado con un modelo (tarifa de buses)';

CREATE TABLE stg.tipo_cambio (
    anio            SMALLINT       NOT NULL,
    moneda          VARCHAR(3)     NOT NULL,
    clp_por_unidad  NUMERIC(12,4)  NOT NULL,
    CONSTRAINT pk_tipo_cambio PRIMARY KEY (anio, moneda)
);
COMMENT ON TABLE stg.tipo_cambio IS 'Pesos chilenos por unidad de moneda, promedio anual (Banco Central de Chile)';
COMMENT ON COLUMN stg.tipo_cambio.anio IS 'Año';
COMMENT ON COLUMN stg.tipo_cambio.moneda IS 'Código de la moneda';
COMMENT ON COLUMN stg.tipo_cambio.clp_por_unidad IS 'Pesos chilenos por unidad de la moneda';

CREATE TABLE stg.equivalencia (
    dominio         VARCHAR(20)  NOT NULL,
    codigo_linea    VARCHAR(3)   NOT NULL,
    valor_fuente    VARCHAR(60)  NOT NULL,
    codigo_destino  VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_equivalencia PRIMARY KEY (dominio, codigo_linea, valor_fuente),
    CONSTRAINT ck_equivalencia_dominio CHECK (dominio IN ('servicio', 'canal_venta', 'medio_pago'))
);
COMMENT ON TABLE stg.equivalencia IS 'Reglas de negocio: valor de cada fuente y su código en las dimensiones del modelo';
COMMENT ON COLUMN stg.equivalencia.dominio IS 'servicio, canal_venta o medio_pago';
COMMENT ON COLUMN stg.equivalencia.codigo_linea IS 'Línea a la que aplica (* = todas)';
COMMENT ON COLUMN stg.equivalencia.valor_fuente IS 'Valor tal como viene en la fuente';
COMMENT ON COLUMN stg.equivalencia.codigo_destino IS 'Llave natural en la dimensión (NI = No informado)';

CREATE TABLE stg.rechazo (
    numero_transaccion  VARCHAR(30)  NOT NULL,
    codigo_linea        VARCHAR(3)   NOT NULL,
    motivo              VARCHAR(80)  NOT NULL,
    CONSTRAINT pk_rechazo PRIMARY KEY (numero_transaccion)
);
COMMENT ON TABLE stg.rechazo IS 'Transacciones que el ETL no cargó al dwh, con el motivo';
COMMENT ON COLUMN stg.rechazo.numero_transaccion IS 'Transacción rechazada';
COMMENT ON COLUMN stg.rechazo.codigo_linea IS 'Línea de la transacción';
COMMENT ON COLUMN stg.rechazo.motivo IS 'Regla de calidad que no cumplió';

-- Conformación: códigos, unidades y moneda del modelo, y reglas de calidad.
-- Los umbrales de "atípico" son reglas de negocio del proyecto.
CREATE VIEW stg.v_transaccion_conformada AS
WITH t AS (
    SELECT
        t.*,
        c.codigo_cliente AS cliente_existe,
        c.fecha_nacimiento,
        es.codigo_destino AS codigo_servicio,
        CASE WHEN t.canal_fuente IS NULL THEN 'NI' ELSE ec.codigo_destino END AS codigo_canal_venta,
        CASE WHEN t.pago_fuente IS NULL THEN 'NI' ELSE ep.codigo_destino END AS codigo_medio_pago,
        zo.codigo_zona AS zona_origen_existe,
        zd.codigo_zona AS zona_destino_existe,
        tc.clp_por_unidad,
        ROUND(t.monto_bruto * tc.clp_por_unidad, 2) AS bruto_clp,
        ROUND(t.monto_descuento * tc.clp_por_unidad, 2) AS descuento_clp,
        ROUND(t.distancia * CASE t.unidad_distancia
                                WHEN 'mi' THEN 1.609344
                                WHEN 'm' THEN 0.001
                                ELSE 1 END, 2) AS km
    FROM stg.transaccion t
    LEFT JOIN stg.cliente c ON c.codigo_cliente = t.codigo_cliente
    LEFT JOIN stg.equivalencia es
           ON es.dominio = 'servicio' AND es.codigo_linea = t.codigo_linea
          AND es.valor_fuente = t.servicio_fuente
    LEFT JOIN stg.equivalencia ec
           ON ec.dominio = 'canal_venta' AND ec.codigo_linea IN (t.codigo_linea, '*')
          AND ec.valor_fuente = t.canal_fuente
    LEFT JOIN stg.equivalencia ep
           ON ep.dominio = 'medio_pago' AND ep.codigo_linea IN (t.codigo_linea, '*')
          AND ep.valor_fuente = t.pago_fuente
    LEFT JOIN stg.zona zo ON zo.codigo_zona = t.codigo_zona_origen
    LEFT JOIN stg.zona zd ON zd.codigo_zona = t.codigo_zona_destino
    LEFT JOIN stg.tipo_cambio tc
           ON tc.anio = EXTRACT(YEAR FROM t.fecha) AND tc.moneda = t.moneda
)
SELECT
    numero_transaccion,
    codigo_linea,
    (EXTRACT(YEAR FROM fecha) * 10000 + EXTRACT(MONTH FROM fecha) * 100
     + EXTRACT(DAY FROM fecha))::INTEGER AS id_tiempo,
    codigo_cliente,
    codigo_servicio,
    codigo_zona_origen,
    codigo_zona_destino,
    codigo_canal_venta,
    codigo_medio_pago,
    EXTRACT(YEAR FROM AGE(fecha, fecha_nacimiento))::SMALLINT AS edad_cliente,
    cantidad,
    bruto_clp AS monto_bruto,
    descuento_clp AS monto_descuento,
    bruto_clp - descuento_clp AS monto_neto,
    km AS distancia_km,
    duracion_minutos,
    ROUND(peso * CASE unidad_peso WHEN 'g' THEN 0.001 ELSE 1 END, 2) AS peso_kg,
    CASE
        WHEN estado_fuente <> 'valido' THEN 'estado en la fuente: ' || estado_fuente
        WHEN fecha IS NULL OR fecha NOT BETWEEN DATE '2023-01-01' AND DATE '2025-12-31'
            THEN 'fecha fuera de 2023-2025'
        WHEN cliente_existe IS NULL THEN 'cliente inexistente'
        WHEN codigo_servicio IS NULL THEN 'servicio sin equivalencia'
        WHEN codigo_canal_venta IS NULL THEN 'canal de venta sin equivalencia'
        WHEN codigo_medio_pago IS NULL THEN 'medio de pago sin equivalencia'
        WHEN zona_origen_existe IS NULL OR zona_destino_existe IS NULL THEN 'zona inexistente'
        WHEN clp_por_unidad IS NULL THEN 'moneda sin tipo de cambio'
        WHEN monto_bruto IS NULL OR monto_bruto <= 0 THEN 'monto bruto no positivo'
        WHEN monto_descuento < 0 OR monto_descuento > monto_bruto THEN 'descuento fuera de rango'
        WHEN cantidad IS NULL OR cantidad NOT BETWEEN 1 AND 9 THEN 'cantidad fuera de 1 a 9'
        WHEN duracion_minutos < 0 THEN 'duración negativa'
        WHEN km < 0 THEN 'distancia negativa'
        WHEN km > CASE codigo_linea WHEN 'DEL' THEN 50 WHEN 'TAX' THEN 200 ELSE 20000 END
            THEN 'distancia atípica'
        WHEN codigo_linea IN ('TAX', 'DEL') AND bruto_clp > 1000000 THEN 'monto atípico'
    END AS motivo_rechazo
FROM t;
COMMENT ON VIEW stg.v_transaccion_conformada IS 'Transacciones convertidas a CLP, km y kg, con los códigos del modelo y el motivo de rechazo (NULL si pasa todas las reglas)';

COMMIT;
