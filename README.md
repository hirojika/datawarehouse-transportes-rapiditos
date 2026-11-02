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

Crear el DWH: abrir phpMyAdmin (`http://localhost/phpmyadmin`), pestaña SQL, y ejecutar `sql/01_ddl.sql`.

Dashboard: `streamlit run dashboard/app.py` → `http://localhost:8501`.

## Reglas del grupo

- Nombres de tablas y columnas en `snake_case` y minúsculas.
- Todo en `utf8mb4`.
- Nada de rutas absolutas.
- Antes de subir un script SQL, probarlo en una base limpia.
- Commits con mensajes descriptivos en español.
