import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{int(x):,}".replace(",", " ")

def load_market_data():
    market = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
    return market, queries

def load_sales_data():
    files = ["ЦР_Продажи.xlsx", "МС_Продажи.xlsx"]
    all_sales = []
    for file in files:
        if os.path.exists(file):
            df = pd.read_excel(file, sheet_name="Товары")
            df["Юрлицо"] = file.split("_")[0]
            all_sales.append(df)
        else:
            st.warning(f"⚠️ Файл {file} не найден")
    if not all_sales:
        st.error("❌ Нет данных по продажам")
        st.stop()
    return pd.concat(all_sales, ignore_index=True)

# ЗАГРУЗКА ДАННЫХ
market, queries = load_market_data()
sales = load_sales_data()

# АГРЕГАЦИЯ ПРОДАЖ
sales_agg = sales.groupby(['Предмет', 'Юрлицо']).agg(
    Мои_заказы=('Заказали на сумму, ₽', 'sum'),
    Мои_товары=('Артикул WB', 'count'),
    Мой_выкуп_процент=('Процент выкупа', 'mean')
).round(2).reset_index()

# АГРЕГАЦИЯ ЗАПРОСОВ
queries_agg = queries.groupby('Предмет')['Количество запросов'].sum().reset_index()
queries_agg.rename(columns={'Количество запросов': 'Количество_запросов'}, inplace=True)

# ОБЪЕДИНЕНИЕ РЫНОЧНЫХ ДАННЫХ
base = market[['Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
               'Выручка, ₽', '%  прироста выручки', 'Средний чек, ₽',
               'Оборачиваемость за неделю, дни', 'Процент выкупа']].copy()

base = pd.merge(base, sales_agg, on='Предмет', how='left')
base = pd.merge(base, queries_agg, on='Предмет', how='left')

# ЗАПОЛНЕНИЕ ПРОПУСКОВ
for col in ['Мои_заказы', 'Мои_товары', 'Мой_выкуп_процент', 'Количество_запросов']:
    base[col] = base[col].fillna(0)

# НАСТРОЙКИ РЕКОМЕНДАЦИЙ
st.sidebar.title("⚙️ Настройки рекомендаций")
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20, step=5)
max_monopoly = st.sidebar.number_input("Макс. монополизация (%)", value=50, step=5)
min_queries = st.sidebar.number_input("Мин. запросов", value=100000, step=10000)
max_turnover = st.sidebar.number_input("Макс. оборачиваемость (дни)", value=30, step=5)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70, step=5)

# ФИЛЬТР ПО ЮРЛИЦУ
legal_entities = sorted(sales_agg["Юрлицо"].dropna().unique())
selected_legal = st.sidebar.selectbox("Юрлицо", ["Любое"] + legal_entities)

if selected_legal != "Любое":
    df_filtered = base[base['Юрлицо'] == selected_legal].copy()
else:
    # Агрегация по предмету
    grouped = sales_agg.groupby('Предмет').agg(
        Мои_заказы=('Мои_заказы', 'sum'),
        Юрлица=('Юрлицо', lambda x: ', '.join(sorted(x.unique()))),
        Мои_товары=('Мои_товары', 'sum'),
        Мой_выкуп_процент=('Мой_выкуп_процент', 'mean')
    ).round(2).reset_index()
    df_filtered = base.merge(grouped, on='Предмет', how='left')
    df_filtered['Юрлица'] = df_filtered['Юрлица'].fillna("—")
    df_filtered['Мои_заказы'] = df_filtered['Мои_заказы'].fillna(0)
    df_filtered['Мой_выкуп_процент'] = df_filtered['Мой_выкуп_процент'].fillna(0)

# РАСЧЁТ ДОЛИ РЫНКА
df_filtered['Моя_доля_рынка_%'] = (
    df_filtered['Мои_заказы'] / df_filtered['Выручка, ₽'].replace(0, 1) * 100
).round(2)

# ФУНКЦИЯ РЕКОМЕНДАЦИИ
def get_recommendation(row):
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
            row['Мой_выкуп_проcент'] > 80):
            return "🚀 Усиление"
        elif row['Мой_выкуп_процент'] < 70:
            return "⚠️ Выход / Анализ"
        else:
            return "📊 Мониторинг"

df_filtered['Рекомендация'] = df_filtered.apply(get_recommendation, axis=1)

# СОРТИРОВКА
df_sorted = df_filtered.sort_values('Выручка, ₽', ascending=False).reset_index(drop=True)

# ОТОБРАЖЕНИЕ
st.title("🔍 Анализ ниш Wildberries")
display_df = df_sorted.copy()
for col in ['Выручка, ₽', 'Количество_запросов', 'Мои_заказы']:
    display_df[col] = display_df[col].apply(format_number)

st.dataframe(
    display_df[[
        'Предмет', 'Юрлица', 'Выручка, ₽', 'Количество_запросов', 'Монополизация, %',
        'Продавцы с заказами', 'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_выкуп_процент', 'Рекомендация'
    ]].rename(columns={'Мои_заказы': 'Мои заказы, ₽'}),
    use_container_width=True,
    hide_index=True
)

# ЗАПРОСЫ ПО ПРЕДМЕТУ
st.subheader("🔎 Запросы по предмету")
subjects = sorted(df_sorted['Предмет'].unique())
selected_subject = st.selectbox("Выберите предмет", subjects)

if selected_subject:
    q_filtered = queries[queries['Предмет'] == selected_subject].copy()
    q_filtered = q_filtered.sort_values('Заказали товаров', ascending=False)
    st.dataframe(
        q_filtered[['Поисковый запрос', 'Количество запросов', 'Заказали товаров']],
        use_container_width=True
    )