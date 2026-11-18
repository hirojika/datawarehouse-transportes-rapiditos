-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°2: consultas de verificación del Datawarehouse poblado.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Fecha:             18-11-2026
--
-- Uso: después de cargar el DWH (con el ETL o con 05_datos_dwh.sql), ejecutar
--   cada consulta por separado en el Query Tool de pgAdmin (seleccionarla y F5)
--   o el archivo completo con psql. Solo lee datos. Las consultas 1 a 4 usan
--   el esquema stg, que existe solo donde se ejecutó el ETL; la 5 y la 6 usan
--   solo el esquema dwh.
-- =============================================================================

-- 1. Filas por tabla después de la carga
SELECT 'stg' AS esquema, 'transaccion' AS tabla, COUNT(*) AS filas FROM stg.transaccion
UNION ALL SELECT 'stg', 'rechazo', COUNT(*) FROM stg.rechazo
UNION ALL SELECT 'dwh', 'dim_tiempo', COUNT(*) FROM dwh.dim_tiempo
UNION ALL SELECT 'dwh', 'dim_cliente', COUNT(*) FROM dwh.dim_cliente
UNION ALL SELECT 'dwh', 'dim_servicio', COUNT(*) FROM dwh.dim_servicio
UNION ALL SELECT 'dwh', 'dim_zona', COUNT(*) FROM dwh.dim_zona
UNION ALL SELECT 'dwh', 'dim_canal_venta', COUNT(*) FROM dwh.dim_canal_venta
UNION ALL SELECT 'dwh', 'dim_medio_pago', COUNT(*) FROM dwh.dim_medio_pago
UNION ALL SELECT 'dwh', 'fact_venta', COUNT(*) FROM dwh.fact_venta;

-- 2. Transacciones por línea: staging, rechazadas y cargadas
SELECT t.codigo_linea,
       COUNT(*) AS en_staging,
       COUNT(r.numero_transaccion) AS rechazadas,
       COUNT(f.numero_transaccion) AS cargadas,
       ROUND(100.0 * COUNT(f.numero_transaccion) / COUNT(*), 1) AS pct_cargado
  FROM stg.transaccion t
  LEFT JOIN stg.rechazo r USING (numero_transaccion)
  LEFT JOIN dwh.fact_venta f USING (numero_transaccion)
 GROUP BY t.codigo_linea
 ORDER BY t.codigo_linea;

-- 3. Transacciones rechazadas por motivo
SELECT motivo, codigo_linea, COUNT(*) AS filas
  FROM stg.rechazo
 GROUP BY motivo, codigo_linea
 ORDER BY filas DESC;

-- 4. Conciliación por línea: staging válido contra fact_venta (diferencias en 0)
SELECT v.codigo_linea,
       v.filas AS filas_staging, f.filas AS filas_dwh, v.filas - f.filas AS dif_filas,
       v.neto AS neto_staging, f.neto AS neto_dwh, v.neto - f.neto AS dif_neto
  FROM (SELECT codigo_linea, COUNT(*) AS filas, SUM(monto_neto) AS neto
          FROM stg.v_transaccion_conformada
         WHERE motivo_rechazo IS NULL
         GROUP BY codigo_linea) v
  JOIN (SELECT LEFT(numero_transaccion, 3) AS codigo_linea, COUNT(*) AS filas,
               SUM(monto_neto) AS neto
          FROM dwh.fact_venta
         GROUP BY 1) f USING (codigo_linea)
 ORDER BY v.codigo_linea;

-- 5. Ventas por línea de negocio y año (montos en millones de CLP)
SELECT s.linea_negocio, t.anio,
       COUNT(*) AS transacciones,
       COUNT(DISTINCT f.id_cliente) AS clientes,
       ROUND(SUM(f.monto_neto) / 1e6, 1) AS ventas_netas_mm,
       ROUND(AVG(f.monto_neto)) AS ticket_promedio
  FROM dwh.fact_venta f
  JOIN dwh.dim_servicio s USING (id_servicio)
  JOIN dwh.dim_tiempo t USING (id_tiempo)
 GROUP BY s.linea_negocio, t.anio
 ORDER BY s.linea_negocio, t.anio;

-- 6. Indicadores por año: clientes activos, frecuencia, gasto y clientes multilínea
SELECT t.anio,
       COUNT(DISTINCT f.id_cliente) AS clientes_activos,
       ROUND(COUNT(*)::NUMERIC / COUNT(DISTINCT f.id_cliente), 1) AS frecuencia_compra,
       ROUND(SUM(f.monto_neto) / COUNT(DISTINCT f.id_cliente)) AS gasto_anual_cliente,
       ROUND(100 * SUM(f.monto_descuento) / SUM(f.monto_bruto), 2) AS pct_descuento,
       (SELECT COUNT(*)
          FROM (SELECT f2.id_cliente
                  FROM dwh.fact_venta f2
                  JOIN dwh.dim_servicio s2 USING (id_servicio)
                  JOIN dwh.dim_tiempo t2 USING (id_tiempo)
                 WHERE t2.anio = t.anio
                 GROUP BY f2.id_cliente
                HAVING COUNT(DISTINCT s2.linea_negocio) > 1) m) AS clientes_multilinea
  FROM dwh.fact_venta f
  JOIN dwh.dim_tiempo t USING (id_tiempo)
 GROUP BY t.anio
 ORDER BY t.anio;
