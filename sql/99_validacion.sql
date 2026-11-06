-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Validación de la estructura del esquema dwh (Avance N°1).
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Fecha:             04-11-2026
--
-- Descripción:
--   Consultas de solo lectura a information_schema y pg_catalog que listan
--   tablas, columnas, llaves, restricciones CHECK e índices del DWH, y
--   verifican la nomenclatura. Ejecutar después de 01_ddl.sql, en la misma
--   base. Es autónomo: no lee ni escribe archivos, así que se ejecuta en
--   cualquier equipo y desde cualquier carpeta. Resultado esperado (filas por
--   consulta): 1, 7, 58, 14, 7, 20, 21, 7 y 0.
--
-- Uso (igual en Windows, Linux y macOS):
--   pgAdmin: seleccionar cada consulta y presionar F5; con el archivo completo,
--            pgAdmin muestra solo el resultado de la última.
--   psql:    psql -U <usuario> -d <base> -P pager=off -f 99_validacion.sql
--            (muestra todos los resultados seguidos)
--   En Windows, seguir guia_ejecucion_windows.pdf.
-- =============================================================================

-- 1. Versión del motor y codificación de la base
SELECT version()                          AS version_motor,
       current_database()                 AS base,
       pg_encoding_to_char(d.encoding)    AS codificacion
FROM pg_database d
WHERE d.datname = current_database();

-- 2. Tablas del esquema dwh con su comentario
SELECT t.table_name                                         AS tabla,
       obj_description(format('dwh.%I', t.table_name)::regclass, 'pg_class') AS comentario
FROM information_schema.tables t
WHERE t.table_schema = 'dwh'
ORDER BY t.table_name LIKE 'fact\_%', t.table_name;

-- 3. Columnas de cada tabla
SELECT c.table_name         AS tabla,
       c.ordinal_position   AS posicion,
       c.column_name        AS columna,
       format_type(a.atttypid, a.atttypmod) AS tipo,
       c.is_nullable        AS acepta_nulo,
       c.column_default     AS valor_por_defecto,
       c.identity_generation AS identity,
       col_description(a.attrelid, a.attnum) AS comentario
FROM information_schema.columns c
JOIN pg_attribute a
  ON a.attrelid = format('dwh.%I', c.table_name)::regclass
 AND a.attname  = c.column_name
WHERE c.table_schema = 'dwh'
ORDER BY c.table_name LIKE 'fact\_%', c.table_name, c.ordinal_position;

-- 4. Llaves primarias y únicas
SELECT tc.table_name       AS tabla,
       tc.constraint_type  AS tipo_restriccion,
       tc.constraint_name  AS restriccion,
       k.column_name       AS columna
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage k
  ON  k.constraint_schema = tc.constraint_schema
  AND k.constraint_name   = tc.constraint_name
WHERE tc.table_schema = 'dwh'
  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
ORDER BY tc.table_name LIKE 'fact\_%', tc.table_name, tc.constraint_type, k.ordinal_position;

-- 5. Llaves foráneas: columna de origen → tabla y columna referenciadas
SELECT k.table_name     AS tabla,
       k.constraint_name AS restriccion,
       k.column_name    AS columna,
       r.table_name     AS tabla_referenciada,
       r.column_name    AS columna_referenciada,
       rc.update_rule   AS al_actualizar,
       rc.delete_rule   AS al_eliminar
FROM information_schema.key_column_usage k
JOIN information_schema.referential_constraints rc
  ON  rc.constraint_schema = k.constraint_schema
  AND rc.constraint_name   = k.constraint_name
JOIN information_schema.key_column_usage r
  ON  r.constraint_schema = rc.unique_constraint_schema
  AND r.constraint_name   = rc.unique_constraint_name
  AND r.ordinal_position  = k.position_in_unique_constraint
WHERE k.table_schema = 'dwh'
ORDER BY k.table_name, k.ordinal_position, k.constraint_name;

-- 6. Restricciones CHECK con su definición
SELECT con.conrelid::regclass   AS tabla,
       con.conname              AS restriccion,
       pg_get_constraintdef(con.oid) AS definicion
FROM pg_constraint con
JOIN pg_namespace n ON n.oid = con.connamespace
WHERE n.nspname = 'dwh'
  AND con.contype = 'c'
ORDER BY con.conrelid::regclass::text LIKE 'dwh.fact\_%', 1, 2;

-- 7. Índices (los de pk_ y uq_ los crea cada restricción; los ix_, el script)
SELECT i.tablename AS tabla,
       i.indexname AS indice,
       i.indexdef  AS definicion
FROM pg_indexes i
WHERE i.schemaname = 'dwh'
ORDER BY i.tablename LIKE 'fact\_%', i.tablename, i.indexname;

-- 8. Resumen por tabla: columnas, llaves foráneas que salen de ella y veces
--    que es referenciada (estrella: solo fact_venta tiene FK)
SELECT t.table_name AS tabla,
       (SELECT COUNT(*)
          FROM information_schema.columns c
         WHERE c.table_schema = t.table_schema
           AND c.table_name   = t.table_name) AS total_columnas,
       (SELECT COUNT(*)
          FROM pg_constraint con
         WHERE con.contype  = 'f'
           AND con.conrelid = format('dwh.%I', t.table_name)::regclass) AS fk_salientes,
       (SELECT COUNT(*)
          FROM pg_constraint con
         WHERE con.contype   = 'f'
           AND con.confrelid = format('dwh.%I', t.table_name)::regclass) AS veces_referenciada
FROM information_schema.tables t
WHERE t.table_schema = 'dwh'
ORDER BY t.table_name LIKE 'fact\_%', t.table_name;

-- 9. Nomenclatura: restricciones e índices que no siguen la norma
--    (debe devolver 0 filas). Una PK se llama pk_<tabla>; las demás
--    restricciones e índices, <prefijo>_<tabla>_<columna>, donde la columna
--    es una de las que usa la restricción (un CHECK puede usar varias).
SELECT 'restricción' AS objeto, cl.relname AS tabla, con.conname AS nombre
FROM pg_constraint con
JOIN pg_class cl    ON cl.oid = con.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
WHERE n.nspname = 'dwh'
  AND con.contype IN ('p', 'f', 'u', 'c')
  AND NOT (
        (con.contype = 'p' AND con.conname = 'pk_' || cl.relname)
     OR (con.contype <> 'p' AND EXISTS (
            SELECT 1
            FROM unnest(con.conkey) AS k(attnum)
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
            WHERE con.conname = CASE con.contype WHEN 'f' THEN 'fk_'
                                                 WHEN 'u' THEN 'uq_'
                                                 ELSE 'ck_' END
                                || cl.relname || '_' || a.attname)))
UNION ALL
SELECT 'índice', i.tablename, i.indexname
FROM pg_indexes i
JOIN pg_index x ON x.indexrelid = format('dwh.%I', i.indexname)::regclass
WHERE i.schemaname = 'dwh'
  -- Los índices de pk_ y uq_ llevan el nombre de su restricción (ya revisado arriba)
  AND NOT EXISTS (SELECT 1 FROM pg_constraint con
                  WHERE con.conindid = x.indexrelid AND con.contype IN ('p', 'u'))
  AND NOT EXISTS (
        SELECT 1
        FROM unnest(x.indkey::int2[]) AS k(attnum)
        JOIN pg_attribute a ON a.attrelid = x.indrelid AND a.attnum = k.attnum
        WHERE i.indexname = 'ix_' || i.tablename || '_' || a.attname);
