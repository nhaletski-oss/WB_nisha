import streamlit as st
import pandas as pd
import os
from st_aggrid import AgGrid, GridOptionsBuilder, AgGridTheme

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    return f"{int(x):,}".replace(",", " ")

@st.cache_data(ttl=3600)
def load_data():
    # Рынок
    market = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
    
    # Продажи
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

    # АГРЕГАЦИЯ ПРОДАЖ
    sales_agg = sales.groupby(['Предмет', 'Юрлицо'], as_index=False).agg(
        Мои_заказы=('Заказали на сумму, ₽', 'sum'),
        Мои_товары=('Артикул WB', 'count'),
        Мой_процент_выкупа=('Процент выкупа', 'mean')
    )

    # Агрегация запросов
    queries_agg = queries.groupby('Предмет', as_index=False).agg(
        Количество_запросов=('Количество запросов', 'sum')
    )

    return market, queries, sales_agg, queries_agg

# ЗАГРУЗКА
market, queries, sales_agg, queries_agg = load_data()

# ОБЪЕДИНЕНИЕ
base = market[[
    'Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
    'Выручка, ₽', '%  прироста выручки', 'Средний чек, ₽',
    'Оборачиваемость за неделю, дни', 'Процент выкупа'
]].copy()

base = pd.merge(base, queries_agg, on='Предмет', how='left')
base['Количество_запросов'] = base['Количество_запросов'].fillna(0)

# -------------------------------
# НАСТРОЙКИ
# -------------------------------
st.sidebar.title("⚙️ Настройки рекомендаций")
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20, step=5)
max_monopoly = st.sidebar.number_input("Макс. монополизация (%)", value=50, step=5)
min_queries = st.sidebar.number_input("Мин. запросов", value=100000, step=10000)
max_turnover = st.sidebar.number_input("Макс. оборачиваемость (дни)", value=30, step=5)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70, step=5)

# -------------------------------
# ФИЛЬТР ПО ЮРЛИЦУ
# -------------------------------
legal_entities = ['Любое'] + sorted(sales_agg['Юрлицо'].unique())
selected_legal = st.sidebar.selectbox("Юрлицо", legal_entities)

if selected_legal == "Любое":
    agg_all = sales_agg.groupby('Предмет', as_index=False).agg(
        Мои_заказы=('Мои_заказы', 'sum'),
        Юрлица=('Юрлицо', lambda x: ', '.join(sorted(x.unique()))),
        Мои_товары=('Мои_товары', 'sum'),
        Мой_процент_выкупа=('Мой_процент_выкупа', 'mean')
    )
    result = pd.merge(base, agg_all, on='Предмет', how='left')
    result['Юрлица'] = result['Юрлица'].fillna("—")
else:
    filtered_sales = sales_agg[sales_agg['Юрлицо'] == selected_legal]
    result = pd.merge(base, filtered_sales, on='Предмет', how='left')
    result['Юрлица'] = selected_legal

# ЗАПОЛНЕНИЕ ПРОПУСКОВ
result['Мои_заказы'] = result['Мои_заказы'].fillna(0)
result['Мои_товары'] = result['Мои_товары'].fillna(0)
result['Мой_процент_выкупа'] = result['Мой_процент_выкупа'].fillna(0)

# Доля рынка
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
            row['Мой_процент_выкупа'] >= min_buyout):
            return "🚀 Усиление"
        elif row['Мой_процент_выкупа'] < 70:
            return "⚠️ Выход / Анализ"
        else:
            return "📊 Мониторинг"

result['Рекомендация'] = result.apply(get_rec, axis=1)

# -------------------------------
# ФИЛЬТР ПО РЕКОМЕНДАЦИЯМ
# -------------------------------
rec_options = sorted(result['Рекомендация'].unique())
selected_recs = st.sidebar.multiselect("Рекомендация", rec_options, default=rec_options)
result = result[result['Рекомендация'].isin(selected_recs)].copy()

# -------------------------------
# ВЫВОД: ИСПОЛЬЗУЕМ AgGrid
# -------------------------------
st.title("🔍 Анализ ниш Wildberries")

# Готовим данные для отображения (форматирование чисел)
display_df = result.copy()
display_df['Выручка, ₽'] = display_df['Выручка, ₽'].apply(format_number)
display_df['Количество_запросов'] = display_df['Количество_запросов'].apply(format_number)
display_df['Мои_заказы'] = display_df['Мои_заказы'].apply(format_number)

# Выбираем колонки для отображения
cols_to_show = [
    'Предмет', 'Юрлица', 'Выручка, ₽', 'Количество_запросов', 'Монополизация, %',
    'Продавцы с заказами', 'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_процент_выкупа', 'Рекомендация'
]

# Настройка AgGrid
gb = GridOptionsBuilder.from_dataframe(display_df[cols_to_show])
gb.configure_default_column(
    filterable=True,
    sortable=True,
    resizable=True,
    editable=False
)
gb.configure_column("Предмет", width=200)
gb.configure_column("Выручка, ₽", width=130)
gb.configure_column("Количество_запросов", width=140)
gb.configure_column("Мои_заказы", width=120)
gb.configure_grid_options(domLayout='normal')

grid_options = gb.build()

AgGrid(
    display_df[cols_to_show],
    gridOptions=grid_options,
    theme=AgGridTheme.STREAMLIT,
    height=600,
    width='100%',
    allow_unsafe_jscode=False  # безопасно, т.к. формат уже применён
)

# -------------------------------
# ЗАПРОСЫ ПО ПРЕДМЕТУ
# -------------------------------
st.subheader("🔎 Запросы по предмету")
subjects = sorted(result['Предмет'].dropna().unique())
selected_subject = st.selectbox("Выберите предмет", subjects)

if selected_subject:
    q_filtered = queries[queries['Предмет'] == selected_subject].copy()
    
    # Расчёт динамики
    q_filtered['Δ Запросы, %'] = (
        (q_filtered['Количество запросов'] - q_filtered['Количество запросов (предыдущий период)']) /
        q_filtered['Количество запросов (предыдущий период)'].replace(0, 1) * 100
    ).round(1)
    
    q_filtered['Δ Заказы, %'] = (
        (q_filtered['Заказали товаров'] - q_filtered['Заказали товаров (предыдущий период)']) /
        q_filtered['Заказали товаров (предыдущий период)'].replace(0, 1) * 100
    ).round(1)
    
    q_filtered = q_filtered.sort_values('Заказали товаров', ascending=False)
    
    # Форматирование процентов
    def format_pct(x):
        if pd.isna(x) or x == 0:
            return "—"
        return f"{x:.1f}%"
    
    q_filtered_display = q_filtered[[
        'Поисковый запрос',
        'Количество запросов',
        'Количество запросов (предыдущий период)',
        'Δ Запросы, %',
        'Заказали товаров',
        'Заказали товаров (предыдущий период)',
        'Δ Заказы, %'
    ]].copy()
    
    q_filtered_display['Δ Запросы, %'] = q_filtered_display['Δ Запросы, %'].apply(format_pct)
    q_filtered_display['Δ Заказы, %'] = q_filtered_display['Δ Заказы, %'].apply(format_pct)
    
    st.dataframe(q_filtered_display, use_container_width=True, hide_index=True)