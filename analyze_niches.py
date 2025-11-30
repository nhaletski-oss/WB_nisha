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
    # Загрузка рыночных данных
    raw = pd.read_excel("пример.xlsx", sheet_name="Предметы")

    # Разделение на рыночные метрики и данные по нишам
    market_metrics = raw[raw['Предмет'].notna()].copy()
    niche_data = raw[raw['Названия строк'].notna()].copy()

    # Переименование для объединения
    niche_data = niche_data.rename(columns={'Названия строк': 'Предмет'})
    niche_agg = niche_data[['Предмет', 'Сумма по полю Заказали товаров', 'Сумма по полю Количество запросов']].copy()
    niche_agg = niche_agg.rename(columns={
        'Сумма по полю Заказали товаров': 'Заказали_товаров',
        'Сумма по полю Количество запросов': 'Количество_запросов'
    })

    # Объединение
    market = pd.merge(market_metrics, niche_agg, on='Предмет', how='left')
    market['Заказали_товаров'] = market['Заказали_товаров'].fillna(0)
    market['Количество_запросов'] = market['Количество_запросов'].fillna(0)

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
        st.error("❌ Нет данных по продажам")
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

# Объединение с рыночными данными
result = pd.merge(market, sales_agg, on='Предмет', how='left')
result['Мои_заказы'] = result['Мои_заказы'].fillna(0)
result['Мой_процент_выкупа'] = result['Мой_процент_выкупа'].fillna(0)

# Доля рынка
result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, 1) * 100).round(2)

# Настройки рекомендаций
st.sidebar.title("⚙️ Настройки рекомендаций")
min_queries = st.sidebar.number_input("Мин. запросов", value=100000, step=10000)
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20, step=5)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70, step=5)

# Рекомендации
def get_rec(row):
    if row['Мои_заказы'] == 0:
        if row['Количество_запросов'] >= min_queries:
            return "✅ Вход"
        else:
            return "⏸ Не сейчас"
    else:
        if row['Моя_доля_рынка_%'] < 5 and row['Мой_процент_выкупа'] >= min_buyout:
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

# Сортировка по выручке (до форматирования!)
df = df.sort_values('Выручка, ₽', ascending=False).reset_index(drop=True)

# Форматирование только при выводе
display_df = df.copy()
for col in ['Выручка, ₽', 'Количество_запросов', 'Мои_заказы']:
    display_df[col] = display_df[col].apply(format_number)

# Вывод
st.title("🔍 Анализ ниш Wildberries")
st.dataframe(
    display_df[[
        'Предмет', 'Юрлицо', 'Выручка, ₽', 'Количество_запросов',
        'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_процент_выкупа', 'Рекомендация'
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