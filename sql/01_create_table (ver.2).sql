-- =====================================================
-- Скрипт создания хранилища данных (DWH)
-- База данных: DE2026_Ryzhenkov
-- Схема: dwh (создаётся внутри этой базы)
-- Модель: снежинка
-- Автор: Рыженков
-- Кейс: "Крутые уборщики"
-- =====================================================

-- 1. Создаём схему dwh (если её нет)
CREATE SCHEMA IF NOT EXISTS dwh;

-- =====================================================
-- 2. ТАБЛИЦЫ ИЗМЕРЕНИЙ (dimensions)
-- =====================================================

-- Города (справочник)
CREATE TABLE IF NOT EXISTS dwh.dim_city (
    city_id INT PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL
);
COMMENT ON TABLE dwh.dim_city IS 'Справочник городов (Москва, СПб)';
COMMENT ON COLUMN dwh.dim_city.city_id IS 'Идентификатор города (56 – Москва, 324 – СПб)';
COMMENT ON COLUMN dwh.dim_city.city_name IS 'Название города';

-- Дата (календарь)
CREATE TABLE IF NOT EXISTS dwh.dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day INT NOT NULL,
    quarter INT NOT NULL
);
COMMENT ON TABLE dwh.dim_date IS 'Календарь для агрегации по времени';
COMMENT ON COLUMN dwh.dim_date.date_key IS 'Ключ даты в формате YYYYMMDD';
COMMENT ON COLUMN dwh.dim_date.full_date IS 'Полная дата';
COMMENT ON COLUMN dwh.dim_date.year IS 'Год';
COMMENT ON COLUMN dwh.dim_date.month IS 'Месяц (1-12)';
COMMENT ON COLUMN dwh.dim_date.day IS 'День месяца (1-31)';
COMMENT ON COLUMN dwh.dim_date.quarter IS 'Квартал (1-4)';

-- Клиент
CREATE TABLE IF NOT EXISTS dwh.dim_client (
    client_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    city_id INT,
    FOREIGN KEY (city_id) REFERENCES dwh.dim_city(city_id)
);
COMMENT ON TABLE dwh.dim_client IS 'Клиенты компании';
COMMENT ON COLUMN dwh.dim_client.client_id IS 'ID клиента из CRM';
COMMENT ON COLUMN dwh.dim_client.name IS 'ФИО клиента';
COMMENT ON COLUMN dwh.dim_client.phone IS 'Номер телефона';
COMMENT ON COLUMN dwh.dim_client.city_id IS 'Город проживания/регистрации клиента';

-- Услуга
CREATE TABLE IF NOT EXISTS dwh.dim_service (
    service_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);
COMMENT ON TABLE dwh.dim_service IS 'Виды услуг (мойка, полировка и т.д.)';
COMMENT ON COLUMN dwh.dim_service.service_id IS 'ID услуги';
COMMENT ON COLUMN dwh.dim_service.name IS 'Название услуги';

-- Продавец (менеджер)
CREATE TABLE IF NOT EXISTS dwh.dim_seller (
    seller_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);
COMMENT ON TABLE dwh.dim_seller IS 'Продавцы / менеджеры, оформившие заказ';
COMMENT ON COLUMN dwh.dim_seller.seller_id IS 'ID менеджера';
COMMENT ON COLUMN dwh.dim_seller.name IS 'Имя менеджера';

-- Валюта
CREATE TABLE IF NOT EXISTS dwh.dim_currency (
    currency_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    code VARCHAR(3) NOT NULL
);
COMMENT ON TABLE dwh.dim_currency IS 'Валюты сделок (рубли, биткоин)';
COMMENT ON COLUMN dwh.dim_currency.currency_id IS 'ID валюты';
COMMENT ON COLUMN dwh.dim_currency.name IS 'Название валюты (Рубли, Биткоин)';
COMMENT ON COLUMN dwh.dim_currency.code IS 'Код валюты (RUB, BTN)';

-- Статус сделки
CREATE TABLE IF NOT EXISTS dwh.dim_status (
    status_id INT PRIMARY KEY,
    status_name VARCHAR(20) NOT NULL
);
COMMENT ON TABLE dwh.dim_status IS 'Статус заказа (1 – Новый, 2 – Отменён, 3 – Завершён)';
COMMENT ON COLUMN dwh.dim_status.status_id IS 'ID статуса';
COMMENT ON COLUMN dwh.dim_status.status_name IS 'Название статуса';

-- Категория расходов
CREATE TABLE IF NOT EXISTS dwh.dim_expense_category (
    category_id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);
COMMENT ON TABLE dwh.dim_expense_category IS 'Категории расходов (Бек-офис, комиссии по регионам)';
COMMENT ON COLUMN dwh.dim_expense_category.category_id IS 'ID категории';
COMMENT ON COLUMN dwh.dim_expense_category.name IS 'Название категории';

-- =====================================================
-- 3. ТАБЛИЦЫ ФАКТОВ (facts)
-- =====================================================

-- Продажи
CREATE TABLE IF NOT EXISTS dwh.fact_sales (
    sale_id BIGSERIAL PRIMARY KEY,
    client_id INT NOT NULL,
    service_id INT NOT NULL,
    seller_id INT NOT NULL,
    currency_id INT NOT NULL,
    city_id INT NOT NULL,
    date_key INT NOT NULL,
    status_id INT NOT NULL,
    amount NUMERIC(15,2) NOT NULL,
    comment TEXT,
    FOREIGN KEY (client_id) REFERENCES dwh.dim_client(client_id),
    FOREIGN KEY (service_id) REFERENCES dwh.dim_service(service_id),
    FOREIGN KEY (seller_id) REFERENCES dwh.dim_seller(seller_id),
    FOREIGN KEY (currency_id) REFERENCES dwh.dim_currency(currency_id),
    FOREIGN KEY (city_id) REFERENCES dwh.dim_city(city_id),
    FOREIGN KEY (date_key) REFERENCES dwh.dim_date(date_key),
    FOREIGN KEY (status_id) REFERENCES dwh.dim_status(status_id)
);
COMMENT ON TABLE dwh.fact_sales IS 'Факт продаж (сделки из CRM Москва и СПб)';
COMMENT ON COLUMN dwh.fact_sales.sale_id IS 'Уникальный идентификатор записи';
COMMENT ON COLUMN dwh.fact_sales.client_id IS 'Клиент (FK)';
COMMENT ON COLUMN dwh.fact_sales.service_id IS 'Услуга (FK)';
COMMENT ON COLUMN dwh.fact_sales.seller_id IS 'Менеджер (FK)';
COMMENT ON COLUMN dwh.fact_sales.currency_id IS 'Валюта сделки (FK)';
COMMENT ON COLUMN dwh.fact_sales.city_id IS 'Город (регион) сделки (FK)';
COMMENT ON COLUMN dwh.fact_sales.date_key IS 'Дата сделки (FK к dim_date)';
COMMENT ON COLUMN dwh.fact_sales.status_id IS 'Статус сделки (FK)';
COMMENT ON COLUMN dwh.fact_sales.amount IS 'Сумма в валюте сделки';
COMMENT ON COLUMN dwh.fact_sales.comment IS 'Детали заказа (цвет, марка, адрес)';

-- Расходы (из 1С)
CREATE TABLE IF NOT EXISTS dwh.fact_expenses (
    expense_id BIGSERIAL PRIMARY KEY,
    category_id INT NOT NULL,
    date_key INT NOT NULL,
    amount NUMERIC(15,2) NOT NULL,
    FOREIGN KEY (category_id) REFERENCES dwh.dim_expense_category(category_id),
    FOREIGN KEY (date_key) REFERENCES dwh.dim_date(date_key)
);
COMMENT ON TABLE dwh.fact_expenses IS 'Факт расходов (из 1С)';
COMMENT ON COLUMN dwh.fact_expenses.expense_id IS 'ID расхода';
COMMENT ON COLUMN dwh.fact_expenses.category_id IS 'Категория расхода (FK)';
COMMENT ON COLUMN dwh.fact_expenses.date_key IS 'Дата расхода (FK)';
COMMENT ON COLUMN dwh.fact_expenses.amount IS 'Сумма расхода';

-- Доходы (поступления от клиентов, из 1С)
CREATE TABLE IF NOT EXISTS dwh.fact_income (
    income_id BIGSERIAL PRIMARY KEY,
    city_id INT NOT NULL,
    date_key INT NOT NULL,
    amount NUMERIC(15,2) NOT NULL,
    FOREIGN KEY (city_id) REFERENCES dwh.dim_city(city_id),
    FOREIGN KEY (date_key) REFERENCES dwh.dim_date(date_key)
);
COMMENT ON TABLE dwh.fact_income IS 'Факт поступлений денег (из 1С)';
COMMENT ON COLUMN dwh.fact_income.income_id IS 'ID записи';
COMMENT ON COLUMN dwh.fact_income.city_id IS 'Город (регион) платежа (FK)';
COMMENT ON COLUMN dwh.fact_income.date_key IS 'Дата платежа (FK)';
COMMENT ON COLUMN dwh.fact_income.amount IS 'Сумма поступления';

-- =====================================================
-- 4. ПРОГНОЗНЫЙ СЛОЙ (результат работы "чёрного ящика")
-- =====================================================
CREATE TABLE IF NOT EXISTS dwh.forecast_sales (
    forecast_id BIGSERIAL PRIMARY KEY,
    date_key INT NOT NULL,
    city_id INT NOT NULL,
    predicted_amount NUMERIC(15,2) NOT NULL,
    model_version VARCHAR(20),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (date_key) REFERENCES dwh.dim_date(date_key),
    FOREIGN KEY (city_id) REFERENCES dwh.dim_city(city_id)
);
COMMENT ON TABLE dwh.forecast_sales IS 'Прогноз выручки от внешней модели («чёрный ящик»)';
COMMENT ON COLUMN dwh.forecast_sales.forecast_id IS 'ID прогноза';
COMMENT ON COLUMN dwh.forecast_sales.date_key IS 'Дата (месяц) прогноза (FK)';
COMMENT ON COLUMN dwh.forecast_sales.city_id IS 'Город (FK)';
COMMENT ON COLUMN dwh.forecast_sales.predicted_amount IS 'Прогнозируемая выручка';
COMMENT ON COLUMN dwh.forecast_sales.model_version IS 'Версия модели (для отслеживания)';
COMMENT ON COLUMN dwh.forecast_sales.generated_at IS 'Время расчёта прогноза';

-- =====================================================
-- 5. ИНДЕКСЫ ДЛЯ УСКОРЕНИЯ ЗАПРОСОВ (особенно важны для фактов)
-- =====================================================

-- Индексы для таблицы фактов продаж
CREATE INDEX IF NOT EXISTS idx_fact_sales_date    ON dwh.fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_city    ON dwh.fact_sales(city_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_client  ON dwh.fact_sales(client_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_status  ON dwh.fact_sales(status_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_service ON dwh.fact_sales(service_id);

-- Индексы для факта расходов
CREATE INDEX IF NOT EXISTS idx_fact_expenses_date ON dwh.fact_expenses(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_expenses_cat  ON dwh.fact_expenses(category_id);

-- Индексы для факта доходов
CREATE INDEX IF NOT EXISTS idx_fact_income_date   ON dwh.fact_income(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_income_city   ON dwh.fact_income(city_id);

-- Индексы для прогнозной таблицы
CREATE INDEX IF NOT EXISTS idx_forecast_date      ON dwh.forecast_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_forecast_city      ON dwh.forecast_sales(city_id);
