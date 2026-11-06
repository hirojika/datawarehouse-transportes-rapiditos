-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°1: creación del Modelo Multidimensional (Tipo Estrella), sin datos.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Profesor:          Luis Cofré B.
-- Fecha:             04-11-2026
--
-- Descripción:
--   Crea el esquema dwh con seis dimensiones y una tabla de hechos
--   (fact_venta) según docs/modelo_dimensional.md. El grano es una fila por
--   cada transacción de compra de un cliente por un servicio de una línea de
--   negocio, en una fecha.
--
-- Motor: PostgreSQL 17. El script es autónomo: no lee ni escribe archivos ni
--   depende de otros scripts, así que se ejecuta en cualquier equipo y desde
--   cualquier carpeta, dentro de una base existente (se recomienda una base
--   nueva, por ejemplo rapiditos, porque el script borra el esquema dwh).
--
-- Uso (igual en Windows, Linux y macOS):
--   pgAdmin: abrir este archivo en el Query Tool de la base y ejecutarlo
--            completo con F5, sin seleccionar texto.
--   psql:    psql -U <usuario> -d <base> -v ON_ERROR_STOP=1 -f 01_ddl.sql
--   En Windows, seguir guia_ejecucion_windows.pdf, que se entrega con este
--   script.
--   El script es idempotente: elimina y vuelve a crear el esquema dwh dentro
--   de una sola transacción. Si una sentencia falla, no queda nada a medias.
--
-- Norma de nomenclatura:
--   Tablas fact_/dim_, singular, snake_case y minúsculas.
--   PK id_<entidad>; llave natural codigo_<entidad>; FK con el nombre de la PK
--   referenciada (más sufijo de rol si aplica).
--   Restricciones pk_<tabla>, fk_<tabla>_<columna>, uq_<tabla>_<columna> y
--   ck_<tabla>_<columna>. Índices ix_<tabla>_<columna>.
-- =============================================================================

-- El archivo está en UTF-8. Sin esta línea, psql en Windows lo envía con la
-- codificación de la consola (WIN1252) y las tildes de los comentarios y de
-- los CHECK quedan guardadas mal ("DimensiÃ³n"), sin ningún error.
SET client_encoding = 'UTF8';

BEGIN;

DROP SCHEMA IF EXISTS dwh CASCADE;
CREATE SCHEMA dwh;
COMMENT ON SCHEMA dwh IS 'Datawarehouse de Transportes Rapiditos S.A.: modelo estrella de ventas';

-- -----------------------------------------------------------------------------
-- Dimensiones
-- -----------------------------------------------------------------------------

-- dim_tiempo: jerarquía fecha → mes → trimestre → semestre → año.
-- La PK no es autoincremental: usa el formato AAAAMMDD. Cada atributo derivado
-- tiene un CHECK que lo obliga a coincidir con la fecha.
CREATE TABLE dwh.dim_tiempo (
    id_tiempo         INTEGER      NOT NULL,
    fecha             DATE         NOT NULL,
    dia               SMALLINT     NOT NULL,
    dia_semana        SMALLINT     NOT NULL,
    nombre_dia        VARCHAR(10)  NOT NULL,
    es_fin_de_semana  BOOLEAN      NOT NULL,
    semana_anio       SMALLINT     NOT NULL,
    mes               SMALLINT     NOT NULL,
    nombre_mes        VARCHAR(10)  NOT NULL,
    trimestre         SMALLINT     NOT NULL,
    semestre          SMALLINT     NOT NULL,
    anio              SMALLINT     NOT NULL,
    CONSTRAINT pk_dim_tiempo PRIMARY KEY (id_tiempo),
    CONSTRAINT uq_dim_tiempo_fecha UNIQUE (fecha),
    CONSTRAINT ck_dim_tiempo_id_tiempo CHECK (
        id_tiempo = EXTRACT(YEAR FROM fecha)::INTEGER * 10000
                  + EXTRACT(MONTH FROM fecha)::INTEGER * 100
                  + EXTRACT(DAY FROM fecha)::INTEGER),
    CONSTRAINT ck_dim_tiempo_dia CHECK (dia = EXTRACT(DAY FROM fecha)),
    CONSTRAINT ck_dim_tiempo_dia_semana CHECK (dia_semana = EXTRACT(ISODOW FROM fecha)),
    CONSTRAINT ck_dim_tiempo_es_fin_de_semana CHECK (
        es_fin_de_semana = (EXTRACT(ISODOW FROM fecha) >= 6)),
    CONSTRAINT ck_dim_tiempo_semana_anio CHECK (semana_anio = EXTRACT(WEEK FROM fecha)),
    CONSTRAINT ck_dim_tiempo_mes CHECK (mes = EXTRACT(MONTH FROM fecha)),
    CONSTRAINT ck_dim_tiempo_trimestre CHECK (trimestre = EXTRACT(QUARTER FROM fecha)),
    CONSTRAINT ck_dim_tiempo_semestre CHECK (
        semestre = CASE WHEN EXTRACT(MONTH FROM fecha) <= 6 THEN 1 ELSE 2 END),
    CONSTRAINT ck_dim_tiempo_anio CHECK (anio = EXTRACT(YEAR FROM fecha))
);
COMMENT ON TABLE dwh.dim_tiempo IS 'Dimensión tiempo con granularidad diaria';
COMMENT ON COLUMN dwh.dim_tiempo.id_tiempo IS 'PK. Fecha en formato AAAAMMDD (ej. 20250314)';
COMMENT ON COLUMN dwh.dim_tiempo.fecha IS 'Fecha calendario';
COMMENT ON COLUMN dwh.dim_tiempo.dia IS 'Día del mes (1-31)';
COMMENT ON COLUMN dwh.dim_tiempo.dia_semana IS '1 = lunes … 7 = domingo (ISO)';
COMMENT ON COLUMN dwh.dim_tiempo.nombre_dia IS 'Lunes … Domingo';
COMMENT ON COLUMN dwh.dim_tiempo.es_fin_de_semana IS 'TRUE si es sábado o domingo';
COMMENT ON COLUMN dwh.dim_tiempo.semana_anio IS 'Semana ISO del año (1-53)';
COMMENT ON COLUMN dwh.dim_tiempo.mes IS 'Mes (1-12)';
COMMENT ON COLUMN dwh.dim_tiempo.nombre_mes IS 'Enero … Diciembre';
COMMENT ON COLUMN dwh.dim_tiempo.trimestre IS 'Trimestre (1-4)';
COMMENT ON COLUMN dwh.dim_tiempo.semestre IS 'Semestre (1-2)';
COMMENT ON COLUMN dwh.dim_tiempo.anio IS 'Año';

-- dim_cliente: vista única del cliente. La llave natural unifica al cliente
-- entre todas las líneas de negocio.
CREATE TABLE dwh.dim_cliente (
    id_cliente         INTEGER      GENERATED BY DEFAULT AS IDENTITY,
    codigo_cliente     VARCHAR(20)  NOT NULL,
    nombre_cliente     VARCHAR(100) NOT NULL,
    genero             VARCHAR(20)  NULL,
    fecha_nacimiento   DATE         NULL,
    tipo_cliente       VARCHAR(20)  NOT NULL,
    comuna_residencia  VARCHAR(60)  NULL,
    region_residencia  VARCHAR(60)  NULL,
    pais_residencia    VARCHAR(60)  NOT NULL,
    fecha_registro     DATE         NULL,
    CONSTRAINT pk_dim_cliente PRIMARY KEY (id_cliente),
    CONSTRAINT uq_dim_cliente_codigo_cliente UNIQUE (codigo_cliente),
    CONSTRAINT ck_dim_cliente_tipo_cliente CHECK (tipo_cliente IN ('persona', 'empresa'))
);
COMMENT ON TABLE dwh.dim_cliente IS 'Dimensión cliente unificada entre las seis líneas de negocio';
COMMENT ON COLUMN dwh.dim_cliente.id_cliente IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.dim_cliente.codigo_cliente IS 'Llave natural (RUT o documento, unificado entre líneas)';
COMMENT ON COLUMN dwh.dim_cliente.nombre_cliente IS 'Nombre o razón social';
COMMENT ON COLUMN dwh.dim_cliente.genero IS 'Género declarado (NULL para empresas)';
COMMENT ON COLUMN dwh.dim_cliente.fecha_nacimiento IS 'Fecha de nacimiento (NULL para empresas)';
COMMENT ON COLUMN dwh.dim_cliente.tipo_cliente IS 'persona o empresa';
COMMENT ON COLUMN dwh.dim_cliente.comuna_residencia IS 'Comuna de residencia';
COMMENT ON COLUMN dwh.dim_cliente.region_residencia IS 'Región de residencia';
COMMENT ON COLUMN dwh.dim_cliente.pais_residencia IS 'País de residencia';
COMMENT ON COLUMN dwh.dim_cliente.fecha_registro IS 'Fecha de alta como cliente';

-- dim_servicio: línea de negocio y medio de transporte en una sola tabla
-- (aplanada para mantener la estrella).
CREATE TABLE dwh.dim_servicio (
    id_servicio       INTEGER      GENERATED BY DEFAULT AS IDENTITY,
    codigo_servicio   VARCHAR(20)  NOT NULL,
    linea_negocio     VARCHAR(50)  NOT NULL,
    medio_transporte  VARCHAR(30)  NOT NULL,
    tipo_servicio     VARCHAR(20)  NOT NULL,
    clase_servicio    VARCHAR(30)  NOT NULL,
    CONSTRAINT pk_dim_servicio PRIMARY KEY (id_servicio),
    CONSTRAINT uq_dim_servicio_codigo_servicio UNIQUE (codigo_servicio),
    CONSTRAINT ck_dim_servicio_linea_negocio CHECK (linea_negocio IN (
        'Buses InterUrbanos Rapiditos',
        'Trenes Rapiditos',
        'Radio Taxis Rapiditos',
        'Logística y Distribución Rapiditos',
        'Aerolíneas Rapiditos',
        'URapid Delivery')),
    CONSTRAINT ck_dim_servicio_tipo_servicio CHECK (tipo_servicio IN ('pasajeros', 'carga'))
);
COMMENT ON TABLE dwh.dim_servicio IS 'Dimensión servicio: línea de negocio y medio de transporte';
COMMENT ON COLUMN dwh.dim_servicio.id_servicio IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.dim_servicio.codigo_servicio IS 'Llave natural';
COMMENT ON COLUMN dwh.dim_servicio.linea_negocio IS 'Una de las 6 líneas de negocio del enunciado (nombre literal)';
COMMENT ON COLUMN dwh.dim_servicio.medio_transporte IS 'bus, tren, taxi, camión, avión, moto/bicicleta';
COMMENT ON COLUMN dwh.dim_servicio.tipo_servicio IS 'pasajeros o carga';
COMMENT ON COLUMN dwh.dim_servicio.clase_servicio IS 'Ej. económica, ejecutiva, express, estándar';

-- dim_zona: dimensión de rol doble (origen y destino).
-- Jerarquía: comuna → ciudad → región → país → continente.
CREATE TABLE dwh.dim_zona (
    id_zona      INTEGER      GENERATED BY DEFAULT AS IDENTITY,
    codigo_zona  VARCHAR(20)  NOT NULL,
    comuna       VARCHAR(60)  NOT NULL,
    ciudad       VARCHAR(60)  NOT NULL,
    region       VARCHAR(60)  NOT NULL,
    pais         VARCHAR(60)  NOT NULL,
    continente   VARCHAR(30)  NOT NULL,
    CONSTRAINT pk_dim_zona PRIMARY KEY (id_zona),
    CONSTRAINT uq_dim_zona_codigo_zona UNIQUE (codigo_zona)
);
COMMENT ON TABLE dwh.dim_zona IS 'Dimensión zona geográfica, de rol doble (origen y destino)';
COMMENT ON COLUMN dwh.dim_zona.id_zona IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.dim_zona.codigo_zona IS 'Llave natural';
COMMENT ON COLUMN dwh.dim_zona.comuna IS 'Comuna (No aplica en destinos internacionales)';
COMMENT ON COLUMN dwh.dim_zona.ciudad IS 'Ciudad';
COMMENT ON COLUMN dwh.dim_zona.region IS 'Región';
COMMENT ON COLUMN dwh.dim_zona.pais IS 'País';
COMMENT ON COLUMN dwh.dim_zona.continente IS 'Continente';

-- dim_canal_venta: canal por el que se realizó la compra.
CREATE TABLE dwh.dim_canal_venta (
    id_canal_venta      INTEGER      GENERATED BY DEFAULT AS IDENTITY,
    codigo_canal_venta  VARCHAR(20)  NOT NULL,
    nombre_canal_venta  VARCHAR(40)  NOT NULL,
    CONSTRAINT pk_dim_canal_venta PRIMARY KEY (id_canal_venta),
    CONSTRAINT uq_dim_canal_venta_codigo_canal_venta UNIQUE (codigo_canal_venta)
);
COMMENT ON TABLE dwh.dim_canal_venta IS 'Dimensión canal de venta';
COMMENT ON COLUMN dwh.dim_canal_venta.id_canal_venta IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.dim_canal_venta.codigo_canal_venta IS 'Llave natural';
COMMENT ON COLUMN dwh.dim_canal_venta.nombre_canal_venta IS 'app, web, boletería, call center, convenio empresa';

-- dim_medio_pago: medio con el que se pagó la compra.
CREATE TABLE dwh.dim_medio_pago (
    id_medio_pago      INTEGER      GENERATED BY DEFAULT AS IDENTITY,
    codigo_medio_pago  VARCHAR(20)  NOT NULL,
    nombre_medio_pago  VARCHAR(40)  NOT NULL,
    CONSTRAINT pk_dim_medio_pago PRIMARY KEY (id_medio_pago),
    CONSTRAINT uq_dim_medio_pago_codigo_medio_pago UNIQUE (codigo_medio_pago)
);
COMMENT ON TABLE dwh.dim_medio_pago IS 'Dimensión medio de pago';
COMMENT ON COLUMN dwh.dim_medio_pago.id_medio_pago IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.dim_medio_pago.codigo_medio_pago IS 'Llave natural';
COMMENT ON COLUMN dwh.dim_medio_pago.nombre_medio_pago IS 'efectivo, débito, crédito, transferencia, billetera digital';

-- -----------------------------------------------------------------------------
-- Tabla de hechos
-- -----------------------------------------------------------------------------

-- fact_venta: una fila por transacción de compra. Montos en pesos chilenos (CLP).
-- El monto neto es el bruto menos el descuento, y el descuento no supera al bruto.
CREATE TABLE dwh.fact_venta (
    id_venta            BIGINT         GENERATED BY DEFAULT AS IDENTITY,
    id_tiempo           INTEGER        NOT NULL,
    id_cliente          INTEGER        NOT NULL,
    id_servicio         INTEGER        NOT NULL,
    id_zona_origen      INTEGER        NOT NULL,
    id_zona_destino     INTEGER        NOT NULL,
    id_canal_venta      INTEGER        NOT NULL,
    id_medio_pago       INTEGER        NOT NULL,
    numero_transaccion  VARCHAR(30)    NOT NULL,
    edad_cliente        SMALLINT       NULL,
    cantidad            INTEGER        NOT NULL DEFAULT 1,
    monto_bruto         NUMERIC(12,2)  NOT NULL,
    monto_descuento     NUMERIC(12,2)  NOT NULL DEFAULT 0,
    monto_neto          NUMERIC(12,2)  NOT NULL,
    distancia_km        NUMERIC(10,2)  NULL,
    duracion_minutos    INTEGER        NULL,
    peso_kg             NUMERIC(10,2)  NULL,
    CONSTRAINT pk_fact_venta PRIMARY KEY (id_venta),
    CONSTRAINT uq_fact_venta_numero_transaccion UNIQUE (numero_transaccion),
    CONSTRAINT fk_fact_venta_id_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dwh.dim_tiempo (id_tiempo) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_cliente FOREIGN KEY (id_cliente)
        REFERENCES dwh.dim_cliente (id_cliente) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_servicio FOREIGN KEY (id_servicio)
        REFERENCES dwh.dim_servicio (id_servicio) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_zona_origen FOREIGN KEY (id_zona_origen)
        REFERENCES dwh.dim_zona (id_zona) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_zona_destino FOREIGN KEY (id_zona_destino)
        REFERENCES dwh.dim_zona (id_zona) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_canal_venta FOREIGN KEY (id_canal_venta)
        REFERENCES dwh.dim_canal_venta (id_canal_venta) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_medio_pago FOREIGN KEY (id_medio_pago)
        REFERENCES dwh.dim_medio_pago (id_medio_pago) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_fact_venta_edad_cliente CHECK (edad_cliente BETWEEN 0 AND 120),
    CONSTRAINT ck_fact_venta_cantidad CHECK (cantidad >= 1),
    CONSTRAINT ck_fact_venta_monto_bruto CHECK (monto_bruto >= 0),
    CONSTRAINT ck_fact_venta_monto_descuento CHECK (
        monto_descuento >= 0 AND monto_descuento <= monto_bruto),
    CONSTRAINT ck_fact_venta_monto_neto CHECK (monto_neto = monto_bruto - monto_descuento),
    CONSTRAINT ck_fact_venta_distancia_km CHECK (distancia_km >= 0),
    CONSTRAINT ck_fact_venta_duracion_minutos CHECK (duracion_minutos >= 0),
    CONSTRAINT ck_fact_venta_peso_kg CHECK (peso_kg >= 0)
);
COMMENT ON TABLE dwh.fact_venta IS 'Hechos de venta: una fila por transacción de compra de un cliente';
COMMENT ON COLUMN dwh.fact_venta.id_venta IS 'PK. Llave sustituta';
COMMENT ON COLUMN dwh.fact_venta.id_tiempo IS 'FK a dim_tiempo (fecha de la compra)';
COMMENT ON COLUMN dwh.fact_venta.id_cliente IS 'FK a dim_cliente';
COMMENT ON COLUMN dwh.fact_venta.id_servicio IS 'FK a dim_servicio';
COMMENT ON COLUMN dwh.fact_venta.id_zona_origen IS 'FK a dim_zona, rol origen';
COMMENT ON COLUMN dwh.fact_venta.id_zona_destino IS 'FK a dim_zona, rol destino';
COMMENT ON COLUMN dwh.fact_venta.id_canal_venta IS 'FK a dim_canal_venta';
COMMENT ON COLUMN dwh.fact_venta.id_medio_pago IS 'FK a dim_medio_pago';
COMMENT ON COLUMN dwh.fact_venta.numero_transaccion IS 'Dimensión degenerada: id del sistema de origen, prefijado por línea';
COMMENT ON COLUMN dwh.fact_venta.edad_cliente IS 'Edad al momento de la compra (no aditiva; NULL para empresas)';
COMMENT ON COLUMN dwh.fact_venta.cantidad IS 'Medida aditiva: pasajes, bultos o unidades';
COMMENT ON COLUMN dwh.fact_venta.monto_bruto IS 'Medida aditiva: monto antes de descuento (CLP)';
COMMENT ON COLUMN dwh.fact_venta.monto_descuento IS 'Medida aditiva: descuento aplicado (CLP)';
COMMENT ON COLUMN dwh.fact_venta.monto_neto IS 'Medida aditiva: monto pagado (CLP) = bruto - descuento';
COMMENT ON COLUMN dwh.fact_venta.distancia_km IS 'Medida aditiva: distancia recorrida en km';
COMMENT ON COLUMN dwh.fact_venta.duracion_minutos IS 'Medida aditiva: duración del servicio en minutos';
COMMENT ON COLUMN dwh.fact_venta.peso_kg IS 'Medida aditiva: peso en kg (solo logística y delivery)';

-- Índices sobre las llaves foráneas: PostgreSQL no los crea por su cuenta y
-- aceleran los cruces entre la tabla de hechos y las dimensiones.
CREATE INDEX ix_fact_venta_id_tiempo ON dwh.fact_venta (id_tiempo);
CREATE INDEX ix_fact_venta_id_cliente ON dwh.fact_venta (id_cliente);
CREATE INDEX ix_fact_venta_id_servicio ON dwh.fact_venta (id_servicio);
CREATE INDEX ix_fact_venta_id_zona_origen ON dwh.fact_venta (id_zona_origen);
CREATE INDEX ix_fact_venta_id_zona_destino ON dwh.fact_venta (id_zona_destino);
CREATE INDEX ix_fact_venta_id_canal_venta ON dwh.fact_venta (id_canal_venta);
CREATE INDEX ix_fact_venta_id_medio_pago ON dwh.fact_venta (id_medio_pago);

COMMIT;
