import streamlit as st
import pandas as pd
import os

# === ВСТАВКА CSS ДЛЯ ЛЕВОГО ВЫРАВНИВАНИЯ ===
st.markdown = """
<style>
.stDataFrame table td,
.stDataFrame table th {
    text-align: left !important;
}
</style>
"""
st.markdown(st.markdown, unsafe_allow_html=True)

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

def format_revenue(x):
    """Форматирует выручку с пробелами"""
    if pd.isna(x) or x == 0:
        return "—"
    return f"{int(x):,}".replace(",", " ")

@st.cache_data(ttl=3600)
def load_data():
    market = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
    
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

    sales_agg = sales.groupby(['Предмет', 'Юрлицо'], as_index=False).agg(
        Мои_заказы=('Заказали на сумму, ₽', 'sum'),
        Мои_товары=('Артикул WB', 'count'),
        Мой_процент_выкупа=('Процент выкупа', 'mean')
    )

    queries_agg = queries.groupby('Предмет', as_index=False).agg(
        Количество_запросов=('Количество запросов', 'sum')
    )

    return market, queries, sales_agg, queries_agg

# ЗАГРУЗКА
market, queries, sales_agg, queries_agg = load_data()

# Проверки колонок
required_query_cols = [
    'Предмет', 'Поисковый запрос', 'Количество запросов',
    'Количество запросов (предыдущий период)',
    'Заказали товаров', 'Заказали товаров (предыдущий период)',
    'Конверсия в корзину', 'Конверсия в заказ'
]
missing_query_cols = [col for col in required_query_cols if col not in queries.columns]
if missing_query_cols:
    st.error(f"❌ В листе 'Запросы' отсутствуют колонки: {missing_query_cols}")
    st.stop()

required_market_cols = [
    'Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
    'Выручка, ₽', '%  прироста выручки', 'Средний чек, ₽',
    'Оборачиваемость за неделю, дни', 'Процент выкупа', 'Карточек товара'
]
missing_market_cols = [col for col in required_market_cols if col not in market.columns]
if missing_market_cols:
    st.error(f"❌ В листе 'Предметы' отсутствуют колонки: {missing_market_cols}")
    st.stop()

base = market[required_market_cols].copy()
base = pd.merge(base, queries_agg, on='Предмет', how='left')
base['Количество_запросов'] = base['Количество_запросов'].fillna(0)

# Расчёт "Ср. выкупы/карточки"
base['Средний чек, ₽'] = base['Средний чек, ₽'].replace(0, 1)
base['Карточек товара'] = base['Карточек товара'].replace(0, 1)
base['Ср. выкупы/карточки'] = (
    base['Выручка, ₽'] / base['Средний чек, ₽'] / base['Карточек товара']
).round(0).fillna(0).astype(int)

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

# Заполнение пропусков
result['Мои_заказы'] = result['Мои_заказы'].fillna(0)
result['Мои_товары'] = result['Мои_товары'].fillna(0)
result['Мой_процент_выкупа'] = result['Мой_процент_выкупа'].fillna(0)
result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, 1) * 100).round(2)

# ОКРУГЛЕНИЕ "Мой_процент_выкупа" до целого
result['Мой_процент_выкупа'] = result['Мой_процент_выкупа'].round(0).fillna(0).astype(int)

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
result = result.sort_values('Выручка, ₽', ascending=False).reset_index(drop=True)

# -------------------------------
# ВЕРХНЯЯ ТАБЛИЦА — ПОДГОТОВКА ДЛЯ ЛЕВОГО ВЫРАВНИВАНИЯ
# -------------------------------
st.title("🔍 Анализ ниш Wildberries")

display_df = result.copy()

# Преобразуем все числовые поля в строки БЕЗ разделителей, чтобы Streamlit не выравнивал по правому краю
# Но оставляем числовую логику до этого момента

def safe_int_str(x):
    if pd.isna(x) or x == 0:
        return "—"
    return str(int(x))

def safe_float_str(x, decimals=0):
    if pd.isna(x):
        return "—"
    if decimals == 0:
        return str(int(round(x)))
    else:
        return f"{x:.{decimals}f}"

# Форматируем колонки как строки для левого выравнивания
formatted_display = pd.DataFrame()
formatted_display['Предмет'] = display_df['Предмет'].fillna("—").astype(str)
formatted_display['Юрлица'] = display_df['Юрлица'].astype(str)
formatted_display['Процент выкупа'] = display_df['Процент выкупа'].apply(safe_int_str)
formatted_display['Выручка, ₽'] = display_df['Выручка, ₽'].apply(format_revenue)  # уже строка
formatted_display['Ср. выкупы/карточки'] = display_df['Ср. выкупы/карточки'].apply(safe_int_str)
formatted_display['Количество_запросов'] = display_df['Количество_запросов'].apply(safe_int_str)
formatted_display['Монополизация, %'] = display_df['Монополизация, %'].apply(lambda x: safe_float_str(x, 1))
formatted_display['Продавцы с заказами'] = display_df['Продавцы с заказами'].apply(safe_int_str)
formatted_display['Мои_заказы'] = display_df['Мои_заказы'].apply(safe_int_str)
formatted_display['Моя_доля_рынка_%'] = display_df['Моя_доля_рынка_%'].apply(lambda x: safe_float_str(x, 2))
formatted_display['Мой_процент_выкупа'] = display_df['Мой_процент_выкупа'].apply(safe_int_str)  # ОКРУГЛЕНО ДО ЦЕЛОГО
formatted_display['Рекомендация'] = display_df['Рекомендация'].astype(str)

# Порядок колонок
columns_order = [
    'Предмет',
    'Юрлица',
    'Процент выкупа',
    'Выручка, ₽',
    'Ср. выкупы/карточки',
    'Количество_запросов',
    'Монополизация, %',
    'Продавцы с заказами',
    'Мои_заказы',
    'Моя_доля_рынка_%',
    'Мой_процент_выкупа',
    'Рекомендация'
]

st.dataframe(
    formatted_display[columns_order],
    use_container_width=True,
    hide_index=True
)

# -------------------------------
# НИЖНЯЯ ТАБЛИЦА
# -------------------------------
st.subheader("🔎 Запросы по предмету")
subjects = sorted(result['Предмет'].dropna().unique())
selected_subject = st.selectbox("Выберите предмет", subjects)

if selected_subject:
    q_filtered = queries[queries['Предмет'] == selected_subject].copy()
    
    q_filtered['Δ Запросы, %'] = (
        (q_filtered['Количество запросов'] - q_filtered['Количество запросов (предыдущий период)']) /
        q_filtered['Количество запросов (предыдущий период)'].replace(0, 1) * 100
    ).round(1)
    
    q_filtered['Δ Заказы, %'] = (
        (q_filtered['Заказали товаров'] - q_filtered['Заказали товаров (предыдущий период)']) /
        q_filtered['Заказали товаров (предыдущий период)'].replace(0, 1) * 100
    ).round(1)
    
    q_filtered.rename(columns={
        'Количество запросов (предыдущий период)': 'Количество запросов (пред.)',
        'Заказали товаров (предыдущий период)': 'Заказали товаров (пред.)'
    }, inplace=True)
    
    # Форматируем нижнюю таблицу как строки для левого выравнивания
    lower_display = pd.DataFrame()
    lower_display['Поисковый запрос'] = q_filtered['Поисковый запрос'].fillna("—").astype(str)
    lower_display['Количество запросов'] = q_filtered['Количество запросов'].apply(safe_int_str)
    lower_display['Конверсия в корзину'] = q_filtered['Конверсия в корзину'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    )
    lower_display['Количество запросов (пред.)'] = q_filtered['Количество запросов (пред.)'].apply(safe_int_str)
    lower_display['Δ Запросы, %'] = q_filtered['Δ Запросы, %'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    )
    lower_display['Конверсия в заказ'] = q_filtered['Конверсия в заказ'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    )
    lower_display['Заказали товаров'] = q_filtered['Заказали товаров'].apply(safe_int_str)
    lower_display['Заказали товаров (пред.)'] = q_filtered['Заказали товаров (пред.)'].apply(safe_int_str)
    lower_display['Δ Заказы, %'] = q_filtered['Δ Заказы, %'].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "—"
    )

    lower_columns = [
        'Поисковый запрос',
        'Количество запросов',
        'Конверсия в корзину',
        'Количество запросов (пред.)',
        'Δ Запросы, %',
        'Конверсия в заказ',
        'Заказали товаров',
        'Заказали товаров (пред.)',
        'Δ Заказы, %'
    ]

    st.dataframe(
        lower_display[lower_columns],
        use_container_width=True,
        hide_index=True
    )