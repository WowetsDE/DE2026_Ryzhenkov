import psycopg2

config = {
    "host": "vpngw.avalon.ru",
    "port": 5432,
    "user": "pguser",
    "password": "****", # <--пароль указать
}


def test_connection(dbname):
    try:
        conn = psycopg2.connect(**config, dbname=dbname)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        print(f"Подключение к {dbname} успешно")
    except Exception as e:
        print(f"Ошибка подключения к {dbname}: {e}")


if __name__ == "__main__":
    test_connection("DE2026_MscDB")
    test_connection("DE2026_SPbDB")
    test_connection("DE2026_1c_db")
    test_connection("DE2026_Ryzhenkov")
