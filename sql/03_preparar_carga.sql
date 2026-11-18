-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°2: preparación del Datawarehouse para una carga completa.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Profesor:          Luis Cofré B.
-- Fecha:             18-11-2026
--
-- Descripción:
--   1. Vacía las tablas del esquema dwh y reinicia sus llaves sustitutas, para
--      que cada ejecución del ETL sea una carga completa y repetible.
--   2. Puebla dim_tiempo con un día por fila entre el 01-01-2023 y el
--      31-12-2025 (no depende de las fuentes).
--   3. Inserta el registro "No informado" (llave 0) en dim_canal_venta y
--      dim_medio_pago, para las fuentes que no informan esos datos (las FK de
--      fact_venta no aceptan NULL).
--
-- Requisito: el esquema dwh creado con 01_ddl.sql. Lo ejecuta el workflow
--   principal de Apache Hop antes de los pipelines de carga.
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

TRUNCATE dwh.fact_venta, dwh.dim_tiempo, dwh.dim_cliente, dwh.dim_servicio, dwh.dim_zona,
         dwh.dim_canal_venta, dwh.dim_medio_pago RESTART IDENTITY;

INSERT INTO dwh.dim_tiempo (id_tiempo, fecha, dia, dia_semana, nombre_dia, es_fin_de_semana,
                            semana_anio, mes, nombre_mes, trimestre, semestre, anio)
SELECT
    (EXTRACT(YEAR FROM f) * 10000 + EXTRACT(MONTH FROM f) * 100 + EXTRACT(DAY FROM f))::INTEGER,
    f,
    EXTRACT(DAY FROM f),
    EXTRACT(ISODOW FROM f),
    (ARRAY['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado',
           'Domingo'])[EXTRACT(ISODOW FROM f)],
    EXTRACT(ISODOW FROM f) >= 6,
    EXTRACT(WEEK FROM f),
    EXTRACT(MONTH FROM f),
    (ARRAY['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
           'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'])[EXTRACT(MONTH FROM f)],
    EXTRACT(QUARTER FROM f),
    CASE WHEN EXTRACT(MONTH FROM f) <= 6 THEN 1 ELSE 2 END,
    EXTRACT(YEAR FROM f)
-- Serie de enteros sumada a una fecha: con generate_series de fechas e intervalos el
-- cálculo pasa por la zona horaria y los cambios de horario saltan o repiten días.
FROM generate_series(0, DATE '2025-12-31' - DATE '2023-01-01') AS g(n),
     LATERAL (SELECT DATE '2023-01-01' + g.n AS f) AS x;

INSERT INTO dwh.dim_canal_venta (id_canal_venta, codigo_canal_venta, nombre_canal_venta)
VALUES (0, 'NI', 'No informado');

INSERT INTO dwh.dim_medio_pago (id_medio_pago, codigo_medio_pago, nombre_medio_pago)
VALUES (0, 'NI', 'No informado');

COMMIT;
