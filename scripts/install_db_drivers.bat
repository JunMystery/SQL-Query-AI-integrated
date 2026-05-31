@echo off
setlocal
python -m pip install -r requirements-db.txt
python scripts\check_sql_drivers.py
