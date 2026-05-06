from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import subprocess
import os

default_args = {
    'owner': 'ryzhenkov',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 5),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'project_work_etl',
    default_args=default_args,
    description='ETL для кейса "Крутые уборщики" (из CRM и 1C в DWH)',
    schedule_interval='0 2 * * *',   # каждый день в 2:00 ночи
    catchup=False,
    tags=['etl', 'ryzhenkov']
)

# Абсолютный путь к ETL-скрипту
ETL_SCRIPT_PATH = r'C:\Users\wriko\airflow_docker\DE2026_Ryzhenkov\etl\etl_script.py'

def run_etl():
    """Запускает Python-скрипт ETL и проверяет код возврата."""
    result = subprocess.run(
        ['python', ETL_SCRIPT_PATH],
        capture_output=True,
        text=True,
        timeout=14400  # 4 часа максимум (на случай зависания)
    )
    if result.returncode != 0:
        raise Exception(f"ETL failed with error:\n{result.stderr}")
    print(result.stdout)

etl_task = PythonOperator(
    task_id='run_etl_script',
    python_callable=run_etl,
    dag=dag
)

etl_task
