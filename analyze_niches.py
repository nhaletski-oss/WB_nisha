import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{int(x):,}".replace(",", " ")

@st.cache_data(ttl=3600)
def load_data():
    # Загрузка рыночных данных — только строки с колонкой "Предмет"
    market_full = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    market = market_full[market_full['Предмет'].notna()].copy()

    # Загрузка запросов
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")

    # Загрузка продаж
    sales_list = []
    for fname in ["ЦР_Продажи.xlsx", "МС_Продажи.xlsx"]:
        if os.path.exists(fname):
            df = pd.read_excel(fname, sheet_name="Товары")
            df["Юрлицо"] = fname.split("_")[0]
            sales_list.append(df)
        else:
            st.warning(f"⚠️ Файл {fname} не найден")
    if not sales_list:
        st.error("❌ Нет файлов продаж")
        st.stop()
    sales = pd.concat(sales_list, ignore_index=True)
    return market, queries, sales

market, queries, sales = load_data()

# Агрегация продаж
sales_agg = sales.groupby(['Предмет', 'Юрлицо'], as_index=False).agg(
    Мои_заказы=('Заказали на сумму, ₽', 'sum'),
    Мои_товары=('Артикул WB', 'count'),
    Мой_процент_выкупа=('Процент выкупа', 'mean')
)

# Агрегация запросов
queries_agg = queries.groupby('Предмет', as_index=False).agg(
    Количество_запросов=('Количество запросов', 'sum')
)

# Объединение рыночных данных с запросами и продажами
result = pd.merge(market, queries_agg, on='Предмет', how='left')
result = pd.merge(result, sales_agg, on='Предмет', how='left')

# Заполнение пропусков
for col in ['Мои_заказы', 'Мои_товары', 'Мой_процент_выкупа', 'Количество_запросов']:
    result[col] = result[col].fillna(0)

# Доля рынка
result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, 1) * 100).round(2)

# Настройки рекомендаций
st.sidebar.title("⚙️ Настройки рекомендаций")
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20, step=5)
max_monopoly = st.sidebar.number_input("Макс. монополизация (%)", value=50, step=5)
min_queries = st.sidebar.number_input("Мин. запросов", value=100000, step=10000)
max_turnover = st.sidebar.number_input("Макс. оборачиваемость (дни)", value=30, step=5)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70, step=5)

# Рекомендации
def get_rec(row):
    if row['Мои_заказы'] == 0:
        if (row['Количество_запросов'] >= min_queries and
            row['Монополизация, %'] <= max_monopoly and
            row['% прироста выручки'] >= min_growth and
            row['Оборачиваемость за неделю, дни'] <= max_turnover):
            return "✅ Вход"
        else:
            return "⏸ Не сейчас"
    else:
        if (row['Моя_доля_рынка_%'] < 5 and
            row['% прироста выручки'] >= min_growth and
            row['Мой_процент_выкупа'] >= min_buyout):
            return "🚀 Усиление"
        elif row['Мой_процент_выкупа'] < 70:
            return "⚠️ Выход / Анализ"
        else:
            return "📊 Мониторинг"

result['Рекомендация'] = result.apply(get_rec, axis=1)

# Фильтр по рекомендации
rec_options = sorted(result['Рекомендация'].unique())
selected_recs = st.sidebar.multiselect("Рекомендация", rec_options, default=rec_options)
df = result[result['Рекомендация'].isin(selected_recs)].copy()

# Сортировка ПО ЧИСЛОВЫМ КОЛОНКАМ (до форматирования!)
df = df.sort_values('Выручка, ₽', ascending=False).reset_index(drop=True)

# Подготовка к отображению
display_df = df.copy()
for col in ['Выручка, ₽', 'Количество_запросов', 'Мои_заказы']:
    display_df[col] = display_df[col].apply(format_number)

# Вывод
st.title("🔍 Анализ ниш Wildberries")
st.dataframe(
    display_df[[
        'Предмет', 'Юрлицо', 'Выручка, ₽', 'Количество_запросов', 'Монополизация, %',
        'Продавцы с заказами', 'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_процент_выкупа', 'Рекомендация'
    ]],
    use_container_width=True,
    hide_index=True
)

# Запросы по предмету
st.subheader("🔎 Запросы по предмету")
subjects = sorted(df['Предмет'].dropna().unique())
selected_subject = st.selectbox("Выберите предмет", subjects)
if selected_subject:
    q = queries[queries['Предмет'] == selected_subject].copy()
    q = q.sort_values('Заказали товаров', ascending=False)
    st.dataframe(q[['Поисковый запрос', 'Количество запросов', 'Заказали товаров']], use_container_width=True)