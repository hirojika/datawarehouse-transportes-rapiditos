-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°2: validación de consistencia de la carga del Datawarehouse.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Fecha:             18-11-2026
--
-- Descripción:
--   Es la última etapa del workflow principal de Apache Hop. Falla (y con
--   ella el workflow) si alguna de estas reglas no se cumple:
--   1. Cada transacción de staging terminó en fact_venta o en stg.rechazo,
--      sin pérdidas ni duplicados.
--   2. Por línea de negocio, la cantidad y el monto neto de fact_venta son
--      iguales a los de las transacciones válidas de staging.
--   3. Las seis líneas de negocio tienen ventas cargadas.
--   Se ejecuta como una sola sentencia (bloque DO).
-- =============================================================================
DO $$
DECLARE
    n_stg      BIGINT;
    n_hechos   BIGINT;
    n_rechazo  BIGINT;
    n_lineas   INTEGER;
    diferencia RECORD;
BEGIN
    SELECT COUNT(*) INTO n_stg FROM stg.transaccion;
    SELECT COUNT(*) INTO n_hechos FROM dwh.fact_venta;
    SELECT COUNT(*) INTO n_rechazo FROM stg.rechazo;
    IF n_stg <> n_hechos + n_rechazo THEN
        RAISE EXCEPTION 'Staging tiene % transacciones, pero hay % en fact_venta y % rechazadas',
            n_stg, n_hechos, n_rechazo;
    END IF;

    SELECT v.codigo_linea, v.filas AS filas_stg, COALESCE(f.filas, 0) AS filas_dwh,
           v.neto AS neto_stg, COALESCE(f.neto, 0) AS neto_dwh
      INTO diferencia
      FROM (SELECT codigo_linea, COUNT(*) AS filas, SUM(monto_neto) AS neto
              FROM stg.v_transaccion_conformada
             WHERE motivo_rechazo IS NULL
             GROUP BY codigo_linea) v
      LEFT JOIN (SELECT LEFT(numero_transaccion, 3) AS codigo_linea, COUNT(*) AS filas,
                        SUM(monto_neto) AS neto
                   FROM dwh.fact_venta
                  GROUP BY 1) f USING (codigo_linea)
     WHERE v.filas <> COALESCE(f.filas, 0) OR v.neto <> COALESCE(f.neto, 0)
     LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Línea %: staging tiene % filas y % de monto neto; fact_venta tiene % y %',
            diferencia.codigo_linea, diferencia.filas_stg, diferencia.neto_stg,
            diferencia.filas_dwh, diferencia.neto_dwh;
    END IF;

    SELECT COUNT(DISTINCT s.linea_negocio) INTO n_lineas
      FROM dwh.fact_venta f JOIN dwh.dim_servicio s USING (id_servicio);
    IF n_lineas <> 6 THEN
        RAISE EXCEPTION 'Solo % de las 6 líneas de negocio tienen ventas cargadas', n_lineas;
    END IF;

    RAISE NOTICE 'Carga consistente: % transacciones en staging, % en fact_venta, % rechazadas',
        n_stg, n_hechos, n_rechazo;
END
$$;
