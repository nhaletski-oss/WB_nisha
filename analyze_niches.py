import streamlit as st
import pandas as pd
from functools import lru_cache

# -------------------------------
# Настройка страницы
# -------------------------------
st.set_page_config(
    page_title="Анализ ниш Wildberries",
    layout="wide"
)

# -------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# -------------------------------
def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{int(x):,}".replace(",", " ")

@st.cache_data(ttl=3600)  # кэш на 1 час
def load_market_data():
    market = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
    queries_agg = queries.groupby('Предмет')['Количество запросов'].sum().reset_index()
    queries_agg.rename(columns={'Количество запросов': 'Количество_запросов'}, inplace=True)
    return market, queries_agg

@st.cache_data(ttl=3600)
def load_sales_data():
    files = ["ЦР_Продажи.xlsx", "МС_Продажи.xlsx"]
    sales_list = []
    for file in files:
        try:
            df = pd.read_excel(file, sheet_name="Товары")
            legal = file.split("_")[0]
            df["Юрлицо"] = legal
            sales_list.append(df)
        except FileNotFoundError:
            st.warning(f"⚠️ Файл {file} не найден")
    if not sales_list:
        st.error("❌ Нет файлов с продажами")
        st.stop()
    return pd.concat(sales_list, ignore_index=True)

@st.cache_data(ttl=3600)
def prepare_base_data():
    market, queries_agg = load_market_data()
    sales = load_sales_data()

    # Агрегация ваших продаж ПО ПРЕДМЕТУ И ЮРЛИЦУ
    sales_agg = sales.groupby(['Предмет', 'Юрлицо']).agg(
        Мои_заказы=('Заказали на сумму, ₽', 'sum'),
        Мои_товары=('Артикул WB', 'count'),
        Мой_выкуп_процент=('Процент выкупа', 'mean')
    ).round(2).reset_index()

    # Объединение рыночных данных с запросами
    base = market[[
        'Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
        'Выручка, ₽', '%  прироста выручки', 'Средний чек, ₽',
        'Оборачиваемость за неделю, дни', 'Процент выкупа'
    ]].merge(queries_agg, on='Предмет', how='left')
    base['Количество_запросов'] = base['Количество_запросов'].fillna(0)

    return base, sales_agg

# -------------------------------
# ЗАГРУЗКА ДАННЫХ
# -------------------------------
base, sales_agg = prepare_base_data()

# -------------------------------
# UI: НАСТРОЙКИ И ФИЛЬТРЫ
# -------------------------------
st.sidebar.title("⚙️ Настройки")
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20)
max_monopoly = st.sidebar.number_input("Макс. монополизация (%)", value=50)
min_queries = st.sidebar.number_input("Мин. запросов", value=100000)
max_turnover = st.sidebar.number_input("Макс. оборачиваемость (дни)", value=30)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70)

# Список юрлиц
legal_entities = sorted(sales_agg["Юрлицо"].unique())
selected_legal = st.sidebar.selectbox("Юрлицо", ["Любое"] + legal_entities)

# -------------------------------
# ОБЪЕДИНЕНИЕ БЕЗ ДУБЛИРОВАНИЯ
# -------------------------------
if selected_legal == "Любое":
    # Агрегируем ВСЕХ юрлиц по предмету
    sales_combined = sales_agg.groupby('Предмет').agg(
        Мои_заказы=('Мои_заказы', 'sum'),
        Юрлица=('Юрлицо', lambda x: ', '.join(sorted(x))),
        Мои_товары=('Мои_товары', 'sum'),
        Мой_выкуп_процент=('Мой_выкуп_процент', 'mean')
    ).round(2).reset_index()
    result = base.merge(sales_combined, on='Предмет', how='left')
else:
    # Фильтруем по юрлицу
    sales_filtered = sales_agg[sales_agg['Юрлицо'] == selected_legal]
    result = base.merge(sales_filtered, on='Предмет', how='left')

# Заполняем пропуски
for col in ['Мои_заказы', 'Мои_товары', 'Мой_выкуп_процент']:
    result[col] = result[col].fillna(0)
result['Юрлица'] = result['Юрлица'].fillna("—")

# Расчёт доли рынка
result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, 1) * 100).round(2)

# -------------------------------
# РЕКОМЕНДАЦИИ
# -------------------------------
def get_rec(row):
    if row['Мои_заказы'] == 0:
        if (row['Количество_запросов'] >= min_queries and
            row['Монополизация, %'] <= max_monopoly and
            row['%  прироста выручки'] >= min_growth and
            row['Оборачиваемость за неделю, дни'] <= max_turnover):
            return "✅ Вход"
        else:
            return "⏸ Не сейчас"
    else:
        if (row['Моя_доля_рынка_%'] < 5 and
            row['%  прироста выручки'] >= min_growth and
            row['Мой_выкуп_процент'] > 80):
            return "🚀 Усиление"
        elif row['Мой_выкуп_процент'] < 70:
            return "⚠️ Выход / Анализ"
        else:
            return "📊 Мониторинг"

result['Рекомендация'] = result.apply(get_rec, axis=1)

# -------------------------------
# ФИЛЬТР ПО РЕКОМЕНДАЦИИ
# -------------------------------
rec_options = sorted(result['Рекомендация'].unique())
selected_recs = st.sidebar.multiselect("Рекомендация", rec_options, default=rec_options)
result = result[result['Рекомендация'].isin(selected_recs)]

# -------------------------------
# ОТОБРАЖЕНИЕ
# -------------------------------
st.title("🔍 Анализ ниш Wildberries")

# Готовим колонки для отображения
cols = [
    'Предмет', 'Юрлица', 'Выручка, ₽', 'Количество_запросов', 'Монополизация, %',
    'Продавцы с заказами', 'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_выкуп_процент', 'Рекомендация'
]
result_display = result[cols].copy()
for col in ['Выручка, ₽', 'Количество_запросов', 'Мои_заказы']:
    result_display[col] = result_display[col].apply(format_number)

st.dataframe(result_display, use_container_width=True, height=700)

# -------------------------------
# ЭКСПОРТ
# -------------------------------
if st.sidebar.button("📥 Скачать Excel"):
    output = result[cols].copy()
    output['Выручка, ₽'] = output['Выручка, ₽'].astype(str)
    output['Количество_запросов'] = output['Количество_запросов'].astype(str)
    output['Мои_заказы'] = output['Мои_заказы'].astype(str)
    output.to_excel("Анализ_ниш_WB.xlsx", index=False)
    st.sidebar.success("✅ Файл готов")

# -------------------------------
# ЗАПРОСЫ ПО ПРЕДМЕТУ
# -------------------------------
st.subheader("🔎 Запросы по предмету")
queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
selected_subject = st.selectbox("Предмет", sorted(result['Предмет'].unique()))
if selected_subject:
    q_filtered = queries[queries['Предмет'] == selected_subject].sort_values('Заказали товаров', ascending=False)
    st.dataframe(q_filtered[['Поисковый запрос', 'Количество запросов', 'Заказали товаров']], use_container_width=True)