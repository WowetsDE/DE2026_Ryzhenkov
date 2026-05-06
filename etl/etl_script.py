import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
import logging
import warnings
import numpy as np
import re

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

# ========== НАСТРОЙКИ ПОДКЛЮЧЕНИЙ ==========
SOURCES = {
    "msk": {
        "dbname": "DE2026_MscDB",
        "user": "pguser",
        "password": "****", # <-- пароль сюда
        "host": "vpngw.avalon.ru",
        "port": 5432,
    },
    "spb": {
        "dbname": "DE2026_SPbDB",
        "user": "pguser",
        "password": "****", # <-- пароль сюда
        "host": "vpngw.avalon.ru",
        "port": 5432,
    },
    "onec": {
        "dbname": "DE2026_1c_db",
        "user": "pguser",
        "password": "****",# <-- пароль сюда
        "host": "vpngw.avalon.ru",
        "port": 5432,
    },
}

TARGET = {
    "dbname": "DE2026_Ryzhenkov",
    "user": "pguser",
    "password": "****",# <-- пароль сюда
    "host": "vpngw.avalon.ru",
    "port": 5432,
}

BATCH_SIZE = 10000


def get_connection(params):
    return psycopg2.connect(**params)


def execute_sql(conn, sql, data=None):
    cur = conn.cursor()
    try:
        if data:
            cur.execute(sql, data)
        else:
            cur.execute(sql)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()


def clean_amount(value):
    """Преобразует строку вида '$1,033.00' или '($732.00)' в число (float). Возвращает None для пустых."""
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    # Убираем скобки (отрицательные значения) и знак доллара, запятые
    s = re.sub(r"[^\d\-\.]", "", s)
    if s == "":
        return None
    try:
        return float(s)
    except:
        return None


def convert_numpy_types(row):
    """Преобразует numpy-типы в стандартные Python-типы."""
    return tuple(
        (
            None
            if pd.isna(v)
            else (
                int(v)
                if isinstance(v, (np.int64, np.int32))
                else (
                    float(v)
                    if isinstance(v, (np.float64, np.float32))
                    else str(v) if isinstance(v, (np.str_)) else v
                )
            )
        )
        for v in row
    )


def bulk_insert(conn, table, columns, rows, batch_size=None):
    """Массовая вставка с конвертацией типов."""
    if not rows:
        return
    batch_size = batch_size or BATCH_SIZE
    cols = ",".join(columns)
    values_template = ",".join(["%s"] * len(columns))
    query = f"INSERT INTO {table} ({cols}) VALUES %s ON CONFLICT DO NOTHING"

    converted_rows = [convert_numpy_types(row) for row in rows]

    try:
        cur = conn.cursor()
        psycopg2.extras.execute_values(
            cur,
            query,
            converted_rows,
            template=f"({values_template})",
            page_size=batch_size,
        )
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        raise e


def etl():
    logging.info("Начало ETL")
    target_conn = get_connection(TARGET)

    try:
        # ---------- Подготовка последовательности для категорий ----------
        execute_sql(
            target_conn, "CREATE SEQUENCE IF NOT EXISTS dwh.seq_category START 1"
        )

        # 1. ГОРОДА
        cities = [(56, "Москва"), (324, "Санкт-Петербург")]
        for row in cities:
            execute_sql(
                target_conn,
                "INSERT INTO dwh.dim_city (city_id, city_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                row,
            )
        logging.info("dim_city заполнена")

        # 2. СТАТУСЫ
        statuses = [(1, "Открыт"), (2, "Выполнен"), (3, "Оплачен"), (0, "Неизвестен")]
        for row in statuses:
            execute_sql(
                target_conn,
                "INSERT INTO dwh.dim_status (status_id, status_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                row,
            )
        logging.info("dim_status заполнена")

        # 3. КАТЕГОРИИ РАСХОДОВ (из reporting.expense)
        with get_connection(SOURCES["onec"]) as onec_conn:
            onec_conn.cursor().execute("SET search_path TO reporting, public;")
            df_cat = pd.read_sql("SELECT DISTINCT category FROM expense", onec_conn)
            if not df_cat.empty:
                for cat in df_cat["category"]:
                    cur = target_conn.cursor()
                    cur.execute(
                        "SELECT 1 FROM dwh.dim_expense_category WHERE name = %s", (cat,)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO dwh.dim_expense_category (category_id, name) VALUES (nextval('dwh.seq_category'), %s)",
                            (cat,),
                        )
                    cur.close()
                    target_conn.commit()
        logging.info("dim_expense_category заполнена")

        # 4. ВАЛЮТЫ
        with get_connection(SOURCES["msk"]) as src_conn:
            src_conn.cursor().execute("SET search_path TO public;")
            df_curr = pd.read_sql("SELECT id, name, code FROM currency", src_conn)
            if not df_curr.empty:
                rows = [tuple(row) for row in df_curr.to_numpy()]
                bulk_insert(
                    target_conn,
                    "dwh.dim_currency",
                    ["currency_id", "name", "code"],
                    rows,
                )
        logging.info("dim_currency заполнена")

        # 5. УСЛУГИ
        services = set()
        for region in ["msk", "spb"]:
            with get_connection(SOURCES[region]) as src_conn:
                src_conn.cursor().execute("SET search_path TO public;")
                df = pd.read_sql("SELECT id, name FROM service", src_conn)
                for _, row in df.iterrows():
                    services.add((row["id"], row["name"]))
        if services:
            rows = list(services)
            bulk_insert(target_conn, "dwh.dim_service", ["service_id", "name"], rows)
        logging.info("dim_service заполнена")

        # 6. ПРОДАВЦЫ
        sellers = set()
        for region in ["msk", "spb"]:
            with get_connection(SOURCES[region]) as src_conn:
                src_conn.cursor().execute("SET search_path TO public;")
                df = pd.read_sql("SELECT id, name FROM seller", src_conn)
                for _, row in df.iterrows():
                    sellers.add((row["id"], row["name"]))
        if sellers:
            rows = list(sellers)
            bulk_insert(target_conn, "dwh.dim_seller", ["seller_id", "name"], rows)
        logging.info("dim_seller заполнена")

        # 7. КЛИЕНТЫ
        all_clients = []
        for region, city_id in [("msk", 56), ("spb", 324)]:
            with get_connection(SOURCES[region]) as src_conn:
                src_conn.cursor().execute("SET search_path TO public;")
                df = pd.read_sql("SELECT id, name, phone FROM client", src_conn)
                for _, row in df.iterrows():
                    all_clients.append((row["id"], row["name"], row["phone"], city_id))
        if all_clients:
            for i in range(0, len(all_clients), BATCH_SIZE):
                batch = all_clients[i : i + BATCH_SIZE]
                bulk_insert(
                    target_conn,
                    "dwh.dim_client",
                    ["client_id", "name", "phone", "city_id"],
                    batch,
                )
        logging.info("dim_client заполнена")

        # 8. ДАТЫ
        start_date = datetime(2021, 1, 1)
        end_date = datetime(2024, 12, 31)
        date_rows = []
        delta = (end_date - start_date).days
        for i in range(delta + 1):
            d = start_date + pd.Timedelta(days=i)
            date_key = int(d.strftime("%Y%m%d"))
            date_rows.append(
                (date_key, d.date(), d.year, d.month, d.day, (d.month - 1) // 3 + 1)
            )
        if date_rows:
            bulk_insert(
                target_conn,
                "dwh.dim_date",
                ["date_key", "full_date", "year", "month", "day", "quarter"],
                date_rows,
            )
        logging.info("dim_date заполнена")

        # 9. ФАКТЫ ПРОДАЖ (deal)
        for region, city_id in [("msk", 56), ("spb", 324)]:
            with get_connection(SOURCES[region]) as src_conn:
                src_conn.cursor().execute("SET search_path TO public;")
                chunks = pd.read_sql(
                    "SELECT id, datetime, amount, comment, status, service_id, currency_id, seller_id, client_id FROM deal",
                    src_conn,
                    chunksize=50000,
                )
                for chunk in chunks:
                    chunk["datetime"] = pd.to_datetime(chunk["datetime"])
                    chunk["date_key"] = (
                        chunk["datetime"].dt.strftime("%Y%m%d").astype(int)
                    )
                    chunk["status"] = chunk["status"].fillna(0)
                    chunk["amount"] = chunk["amount"].apply(clean_amount)
                    rows = []
                    for _, row in chunk.iterrows():
                        rows.append(
                            (
                                row["id"],
                                row["client_id"],
                                row["service_id"],
                                row["seller_id"],
                                row["currency_id"],
                                row["date_key"],
                                row["status"],
                                row["amount"],
                                row["comment"],
                            )
                        )
                    rows_with_city = [
                        (r[0], r[1], r[2], r[3], r[4], city_id, r[5], r[6], r[7], r[8])
                        for r in rows
                    ]
                    for i in range(0, len(rows_with_city), BATCH_SIZE):
                        batch = rows_with_city[i : i + BATCH_SIZE]
                        bulk_insert(
                            target_conn,
                            "dwh.fact_sales",
                            [
                                "sale_id",
                                "client_id",
                                "service_id",
                                "seller_id",
                                "currency_id",
                                "city_id",
                                "date_key",
                                "status_id",
                                "amount",
                                "comment",
                            ],
                            batch,
                        )
        logging.info("fact_sales заполнена")

        # 10. ФАКТЫ РАСХОДОВ (expense)
        # Словарь категорий
        cat_map = {}
        cur = target_conn.cursor()
        cur.execute("SELECT category_id, name FROM dwh.dim_expense_category")
        for row in cur.fetchall():
            cat_map[row[1]] = row[0]
        cur.close()

        with get_connection(SOURCES["onec"]) as src_conn:
            src_conn.cursor().execute("SET search_path TO reporting, public;")
            chunks = pd.read_sql(
                "SELECT id, datetime, amount, category FROM expense",
                src_conn,
                chunksize=50000,
            )
            for chunk in chunks:
                chunk["datetime"] = pd.to_datetime(chunk["datetime"])
                chunk["date_key"] = chunk["datetime"].dt.strftime("%Y%m%d").astype(int)
                chunk["amount"] = chunk["amount"].apply(clean_amount)
                rows = []
                for _, row in chunk.iterrows():
                    cat_id = cat_map.get(row["category"])
                    if cat_id is not None:
                        rows.append((cat_id, row["date_key"], row["amount"]))
                if rows:
                    bulk_insert(
                        target_conn,
                        "dwh.fact_expenses",
                        ["category_id", "date_key", "amount"],
                        rows,
                    )
        logging.info("fact_expenses заполнена")

        # 11. ФАКТЫ ДОХОДОВ (income)
        with get_connection(SOURCES["onec"]) as src_conn:
            src_conn.cursor().execute("SET search_path TO reporting, public;")
            chunks = pd.read_sql(
                "SELECT id, amount, city, date FROM income", src_conn, chunksize=50000
            )
            for chunk in chunks:
                chunk["date"] = pd.to_datetime(chunk["date"])
                chunk["date_key"] = chunk["date"].dt.strftime("%Y%m%d").astype(int)
                chunk["amount"] = chunk["amount"].apply(clean_amount)
                rows = []
                for _, row in chunk.iterrows():
                    rows.append((row["city"], row["date_key"], row["amount"]))
                if rows:
                    bulk_insert(
                        target_conn,
                        "dwh.fact_income",
                        ["city_id", "date_key", "amount"],
                        rows,
                    )
        logging.info("fact_income заполнена")

        # 12. ПРОГНОЗ (заглушка)
        forecast_rows = [
            (20240601, 56, 1800000.00, "model_v1"),
            (20240601, 324, 1200000.00, "model_v1"),
        ]
        bulk_insert(
            target_conn,
            "dwh.forecast_sales",
            ["date_key", "city_id", "predicted_amount", "model_version"],
            forecast_rows,
        )
        logging.info("forecast_sales заполнена (заглушка)")

        logging.info("ETL успешно завершён")

    except Exception as e:
        logging.error(f"Ошибка ETL: {e}")
        raise
    finally:
        target_conn.close()


if __name__ == "__main__":
    etl()
