-- =============================================================================
-- Proyecto Semestral de Inteligencia de Negocios (INFB8101, Sección 412, UTEM)
-- Caso: Transportes Rapiditos S.A.
-- Avance N°1: creación del Modelo Multidimensional (Tipo Estrella), sin datos.
--
-- Autores (Grupo 1): Ignacio Ahumada Poque, Leonardo Solís Ortiz,
--                    Vicente Fuentes Rodríguez, Gabriel García Vega
-- Profesor:          Luis Cofré B.
-- Fecha:             02-11-2026
--
-- Descripción:
--   Crea la base de datos dwh_rapiditos con seis dimensiones y una tabla de
--   hechos (fact_venta) según docs/modelo_dimensional.md. El grano es una fila
--   por cada transacción de compra de un cliente por un servicio de una línea
--   de negocio, en una fecha.
--
-- Uso:
--   Ejecutar de corrido en la pestaña SQL de phpMyAdmin (XAMPP) o en DBeaver.
--   El script es idempotente: elimina y vuelve a crear la base completa.
--
-- Norma de nomenclatura:
--   Tablas fact_/dim_, singular, snake_case y minúsculas.
--   PK id_<entidad>; llave natural codigo_<entidad>; FK con el nombre de la PK
--   referenciada (más sufijo de rol si aplica).
--   Restricciones fk_<tabla>_<columna> y uq_<tabla>_<columna>.
--   La PK se declara sin nombre: MariaDB la registra siempre como PRIMARY y
--   un nombre propio solo produciría el aviso #1280.
-- =============================================================================
/
DROP DATABASE IF EXISTS dwh_rapiditos;
CREATE DATABASE dwh_rapiditos
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;
USE dwh_rapiditos;

-- -----------------------------------------------------------------------------
-- Dimensiones
-- -----------------------------------------------------------------------------

-- dim_tiempo: jerarquía fecha → mes → trimestre → semestre → año.
-- La PK no es autoincremental: usa el formato AAAAMMDD.
CREATE TABLE dim_tiempo (
    id_tiempo         INT UNSIGNED      NOT NULL COMMENT 'PK. Fecha en formato AAAAMMDD (ej. 20250314)',
    fecha             DATE              NOT NULL COMMENT 'Fecha calendario',
    dia               TINYINT UNSIGNED  NOT NULL COMMENT 'Día del mes (1-31)',
    dia_semana        TINYINT UNSIGNED  NOT NULL COMMENT '1 = lunes … 7 = domingo',
    nombre_dia        VARCHAR(10)       NOT NULL COMMENT 'Lunes … Domingo',
    es_fin_de_semana  TINYINT(1)        NOT NULL COMMENT '1 si es sábado o domingo',
    semana_anio       TINYINT UNSIGNED  NOT NULL COMMENT 'Semana ISO del año',
    mes               TINYINT UNSIGNED  NOT NULL COMMENT 'Mes (1-12)',
    nombre_mes        VARCHAR(10)       NOT NULL COMMENT 'Enero … Diciembre',
    trimestre         TINYINT UNSIGNED  NOT NULL COMMENT 'Trimestre (1-4)',
    semestre          TINYINT UNSIGNED  NOT NULL COMMENT 'Semestre (1-2)',
    anio              SMALLINT UNSIGNED NOT NULL COMMENT 'Año',
    PRIMARY KEY (id_tiempo),
    CONSTRAINT uq_dim_tiempo_fecha UNIQUE (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión tiempo con granularidad diaria';

-- dim_cliente: vista única del cliente. La llave natural unifica al cliente
-- entre todas las líneas de negocio.
CREATE TABLE dim_cliente (
    id_cliente         INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    codigo_cliente     VARCHAR(20)  NOT NULL COMMENT 'Llave natural (RUT o documento, unificado entre líneas)',
    nombre_cliente     VARCHAR(100) NOT NULL COMMENT 'Nombre o razón social',
    genero             VARCHAR(20)  NULL     COMMENT 'Género declarado (NULL para empresas)',
    fecha_nacimiento   DATE         NULL     COMMENT 'Fecha de nacimiento (NULL para empresas)',
    tipo_cliente       VARCHAR(20)  NOT NULL COMMENT 'persona o empresa',
    comuna_residencia  VARCHAR(60)  NULL     COMMENT 'Comuna de residencia',
    region_residencia  VARCHAR(60)  NULL     COMMENT 'Región de residencia',
    pais_residencia    VARCHAR(60)  NOT NULL COMMENT 'País de residencia',
    fecha_registro     DATE         NULL     COMMENT 'Fecha de alta como cliente',
    PRIMARY KEY (id_cliente),
    CONSTRAINT uq_dim_cliente_codigo_cliente UNIQUE (codigo_cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión cliente unificada entre las seis líneas de negocio';

-- dim_servicio: línea de negocio y medio de transporte en una sola tabla
-- (aplanada para mantener la estrella).
CREATE TABLE dim_servicio (
    id_servicio       INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    codigo_servicio   VARCHAR(20)  NOT NULL COMMENT 'Llave natural',
    linea_negocio     VARCHAR(50)  NOT NULL COMMENT 'Una de las 6 líneas de negocio del enunciado',
    medio_transporte  VARCHAR(30)  NOT NULL COMMENT 'bus, tren, taxi, camión, avión, moto/bicicleta',
    tipo_servicio     VARCHAR(20)  NOT NULL COMMENT 'pasajeros o carga',
    clase_servicio    VARCHAR(30)  NOT NULL COMMENT 'Ej. económica, ejecutiva, express, estándar',
    PRIMARY KEY (id_servicio),
    CONSTRAINT uq_dim_servicio_codigo_servicio UNIQUE (codigo_servicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión servicio: línea de negocio y medio de transporte';

-- dim_zona: dimensión de rol doble (origen y destino).
-- Jerarquía: comuna → ciudad → región → país → continente.
CREATE TABLE dim_zona (
    id_zona      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    codigo_zona  VARCHAR(20)  NOT NULL COMMENT 'Llave natural',
    comuna       VARCHAR(60)  NOT NULL COMMENT 'Comuna',
    ciudad       VARCHAR(60)  NOT NULL COMMENT 'Ciudad',
    region       VARCHAR(60)  NOT NULL COMMENT 'Región',
    pais         VARCHAR(60)  NOT NULL COMMENT 'País',
    continente   VARCHAR(30)  NOT NULL COMMENT 'Continente',
    PRIMARY KEY (id_zona),
    CONSTRAINT uq_dim_zona_codigo_zona UNIQUE (codigo_zona)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión zona geográfica, de rol doble (origen y destino)';

-- dim_canal_venta: canal por el que se realizó la compra.
CREATE TABLE dim_canal_venta (
    id_canal_venta      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    codigo_canal_venta  VARCHAR(20)  NOT NULL COMMENT 'Llave natural',
    nombre_canal_venta  VARCHAR(40)  NOT NULL COMMENT 'app, web, boletería, call center, convenio empresa',
    PRIMARY KEY (id_canal_venta),
    CONSTRAINT uq_dim_canal_venta_codigo_canal_venta UNIQUE (codigo_canal_venta)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión canal de venta';

-- dim_medio_pago: medio con el que se pagó la compra.
CREATE TABLE dim_medio_pago (
    id_medio_pago      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    codigo_medio_pago  VARCHAR(20)  NOT NULL COMMENT 'Llave natural',
    nombre_medio_pago  VARCHAR(40)  NOT NULL COMMENT 'efectivo, débito, crédito, transferencia, billetera digital',
    PRIMARY KEY (id_medio_pago),
    CONSTRAINT uq_dim_medio_pago_codigo_medio_pago UNIQUE (codigo_medio_pago)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Dimensión medio de pago';

-- -----------------------------------------------------------------------------
-- Tabla de hechos
-- -----------------------------------------------------------------------------

-- fact_venta: una fila por transacción de compra. Montos en pesos chilenos (CLP).
CREATE TABLE fact_venta (
    id_venta            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT COMMENT 'PK. Llave sustituta',
    id_tiempo           INT UNSIGNED     NOT NULL COMMENT 'FK a dim_tiempo (fecha de la compra)',
    id_cliente          INT UNSIGNED     NOT NULL COMMENT 'FK a dim_cliente',
    id_servicio         INT UNSIGNED     NOT NULL COMMENT 'FK a dim_servicio',
    id_zona_origen      INT UNSIGNED     NOT NULL COMMENT 'FK a dim_zona, rol origen',
    id_zona_destino     INT UNSIGNED     NOT NULL COMMENT 'FK a dim_zona, rol destino',
    id_canal_venta      INT UNSIGNED     NOT NULL COMMENT 'FK a dim_canal_venta',
    id_medio_pago       INT UNSIGNED     NOT NULL COMMENT 'FK a dim_medio_pago',
    numero_transaccion  VARCHAR(30)      NOT NULL COMMENT 'Dimensión degenerada: id del sistema de origen, prefijado por línea',
    edad_cliente        TINYINT UNSIGNED NULL     COMMENT 'Edad al momento de la compra (no aditiva; NULL para empresas)',
    cantidad            INT UNSIGNED     NOT NULL DEFAULT 1 COMMENT 'Medida aditiva: pasajes, bultos o unidades',
    monto_bruto         DECIMAL(12,2)    NOT NULL COMMENT 'Medida aditiva: monto antes de descuento (CLP)',
    monto_descuento     DECIMAL(12,2)    NOT NULL DEFAULT 0 COMMENT 'Medida aditiva: descuento aplicado (CLP)',
    monto_neto          DECIMAL(12,2)    NOT NULL COMMENT 'Medida aditiva: monto pagado (CLP)',
    distancia_km        DECIMAL(10,2)    NULL     COMMENT 'Medida aditiva: distancia recorrida en km',
    duracion_minutos    INT UNSIGNED     NULL     COMMENT 'Medida aditiva: duración del servicio en minutos',
    peso_kg             DECIMAL(10,2)    NULL     COMMENT 'Medida aditiva: peso en kg (solo logística y delivery)',
    PRIMARY KEY (id_venta),
    CONSTRAINT uq_fact_venta_numero_transaccion UNIQUE (numero_transaccion),
    CONSTRAINT fk_fact_venta_id_tiempo FOREIGN KEY (id_tiempo)
        REFERENCES dim_tiempo (id_tiempo) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_cliente FOREIGN KEY (id_cliente)
        REFERENCES dim_cliente (id_cliente) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_servicio FOREIGN KEY (id_servicio)
        REFERENCES dim_servicio (id_servicio) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_zona_origen FOREIGN KEY (id_zona_origen)
        REFERENCES dim_zona (id_zona) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_zona_destino FOREIGN KEY (id_zona_destino)
        REFERENCES dim_zona (id_zona) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_canal_venta FOREIGN KEY (id_canal_venta)
        REFERENCES dim_canal_venta (id_canal_venta) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_fact_venta_id_medio_pago FOREIGN KEY (id_medio_pago)
        REFERENCES dim_medio_pago (id_medio_pago) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Hechos de venta: una fila por transacción de compra de un cliente';
