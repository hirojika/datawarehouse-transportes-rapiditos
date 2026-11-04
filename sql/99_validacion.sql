-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Validación de la estructura de dwh_rapiditos (Avance N°1).
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Fecha:             02-11-2026
--
-- Descripción:
--   Consultas de solo lectura a information_schema que listan tablas,
--   columnas, llaves primarias, llaves únicas y llaves foráneas del DWH.
--   Ejecutar después de sql/01_ddl.sql. phpMyAdmin muestra un resultado por
--   cada consulta; sirve como evidencia (captura) para el informe.
-- =============================================================================

-- 1. Versión del motor
SELECT VERSION() AS version_motor;

-- 2. Tablas: motor, collation y comentario
SELECT t.TABLE_NAME      AS tabla,
       t.ENGINE          AS motor,
       t.TABLE_COLLATION AS collation_tabla,
       t.TABLE_COMMENT   AS comentario
FROM information_schema.TABLES t
WHERE t.TABLE_SCHEMA = 'dwh_rapiditos'
ORDER BY t.TABLE_NAME LIKE 'fact\_%', t.TABLE_NAME;

-- 3. Columnas de cada tabla
SELECT c.TABLE_NAME       AS tabla,
       c.ORDINAL_POSITION AS posicion,
       c.COLUMN_NAME      AS columna,
       c.COLUMN_TYPE      AS tipo,
       c.IS_NULLABLE      AS acepta_nulo,
       c.COLUMN_KEY       AS llave,
       c.COLUMN_DEFAULT   AS valor_por_defecto,
       c.EXTRA            AS extra,
       c.COLUMN_COMMENT   AS comentario
FROM information_schema.COLUMNS c
WHERE c.TABLE_SCHEMA = 'dwh_rapiditos'
ORDER BY c.TABLE_NAME LIKE 'fact\_%', c.TABLE_NAME, c.ORDINAL_POSITION;

-- 4. Llaves primarias y únicas
--    (MariaDB registra toda PK con el nombre PRIMARY)
SELECT tc.TABLE_NAME       AS tabla,
       tc.CONSTRAINT_TYPE  AS tipo_restriccion,
       tc.CONSTRAINT_NAME  AS restriccion,
       k.COLUMN_NAME       AS columna
FROM information_schema.TABLE_CONSTRAINTS tc
JOIN information_schema.KEY_COLUMN_USAGE k
  ON  k.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
  AND k.TABLE_NAME        = tc.TABLE_NAME
  AND k.CONSTRAINT_NAME   = tc.CONSTRAINT_NAME
WHERE tc.TABLE_SCHEMA = 'dwh_rapiditos'
  AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')
ORDER BY tc.TABLE_NAME LIKE 'fact\_%', tc.TABLE_NAME, tc.CONSTRAINT_TYPE, k.ORDINAL_POSITION;

-- 5. Llaves foráneas: columna de origen → tabla y columna referenciadas
SELECT k.TABLE_NAME             AS tabla,
       k.CONSTRAINT_NAME        AS restriccion,
       k.COLUMN_NAME            AS columna,
       k.REFERENCED_TABLE_NAME  AS tabla_referenciada,
       k.REFERENCED_COLUMN_NAME AS columna_referenciada,
       r.UPDATE_RULE            AS al_actualizar,
       r.DELETE_RULE            AS al_eliminar
FROM information_schema.KEY_COLUMN_USAGE k
JOIN information_schema.REFERENTIAL_CONSTRAINTS r
  ON  r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA
  AND r.CONSTRAINT_NAME   = k.CONSTRAINT_NAME
WHERE k.TABLE_SCHEMA = 'dwh_rapiditos'
  AND k.REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY k.TABLE_NAME, k.ORDINAL_POSITION, k.CONSTRAINT_NAME;

-- 6. Resumen por tabla: columnas, llaves foráneas que salen de ella
--    y veces que es referenciada (estrella: solo fact_venta tiene FK)
SELECT t.TABLE_NAME AS tabla,
       (SELECT COUNT(*)
          FROM information_schema.COLUMNS c
         WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA
           AND c.TABLE_NAME   = t.TABLE_NAME) AS total_columnas,
       (SELECT COUNT(*)
          FROM information_schema.KEY_COLUMN_USAGE k
         WHERE k.TABLE_SCHEMA = t.TABLE_SCHEMA
           AND k.TABLE_NAME   = t.TABLE_NAME
           AND k.REFERENCED_TABLE_NAME IS NOT NULL) AS fk_salientes,
       (SELECT COUNT(*)
          FROM information_schema.KEY_COLUMN_USAGE k
         WHERE k.TABLE_SCHEMA          = t.TABLE_SCHEMA
           AND k.REFERENCED_TABLE_NAME = t.TABLE_NAME) AS veces_referenciada
FROM information_schema.TABLES t
WHERE t.TABLE_SCHEMA = 'dwh_rapiditos'
ORDER BY t.TABLE_NAME LIKE 'fact\_%', t.TABLE_NAME;
