# Proyecto Semestral BI — Transportes Rapiditos S.A. (Grupo 1)

Inteligencia de Negocios, INFB8101 Sección 412, UTEM. Todo el stack funciona en Linux y Windows.

## Requisitos

- XAMPP (Apache + MySQL/MariaDB activos)
- Python 3 y Git
- DBeaver Community (opcional, recomendado)
- Talend Open Studio (para la unidad de ETL)

## Puesta en marcha

```bash
git clone <url-del-repo>
cd proyecto-bi
python -m venv .venv
# Linux:   source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # Windows: copy .env.example .env
```

Levantar XAMPP:
- Linux: `sudo /opt/lampp/lampp start` (detener antes Apache/MariaDB del sistema si están corriendo).
- Windows: XAMPP Control Panel → Start en Apache y MySQL.

Crear el DWH: abrir phpMyAdmin (`http://localhost/phpmyadmin`), pestaña SQL, y ejecutar `sql/01_ddl.sql`. Para verificar la estructura, ejecutar `sql/99_validacion.sql`.

Pruebas y estilo (con XAMPP activo y el venv activado):

```bash
pytest -v        # ejecuta 01_ddl.sql sobre dwh_rapiditos_test (nunca toca dwh_rapiditos)
ruff check .
```

Si al ejecutar `01_ddl.sql` aparecen `#1558 Column count of mysql.proc is wrong` y `#1545 Failed to open mysql.event`, las tablas de sistema de MariaDB que trae XAMPP están desactualizadas (no es un error del script). Se arregla una sola vez, con XAMPP corriendo:

- Linux: `sudo /opt/lampp/bin/mysql_upgrade -u root` y luego `sudo /opt/lampp/lampp restartmysql`.
- Windows: `C:\xampp\mysql\bin\mysql_upgrade.exe -u root` y luego Stop/Start de MySQL en el Control Panel.

Informe (LaTeX), desde la carpeta `informe/`: `latexmk -xelatex informe.tex` (también compila con `-lualatex` o `-pdf`).

Dashboard: `streamlit run dashboard/app.py` → `http://localhost:8501`.

## Reglas del grupo

- Nombres de tablas y columnas en `snake_case` y minúsculas.
- Todo en `utf8mb4`.
- Nada de rutas absolutas.
- Antes de subir un script SQL, probarlo en una base limpia.
- Commits con mensajes descriptivos en español.
