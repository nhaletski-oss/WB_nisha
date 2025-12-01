import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

# ------- Утилиты -------
def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    try:
        return f"{int(x):,}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"

@st.cache_data(ttl=3600)
def load_data():
    # Загружаем market и queries из одного файла (как у тебя)
    market = pd.read_excel("пример.xlsx", sheet_name="Предметы")
    queries = pd.read_excel("пример.xlsx", sheet_name="Запросы")
    
    sales_list = []
    for fname in ["ЦР_Продажи.xlsx", "МС_Продажи.xlsx"]:
        if os.path.exists(fname):
            df = pd.read_excel(fname, sheet_name="Товары")
            # Явно ставим значение Юрлицо, чтобы потом можно было фильтровать
            df["Юрлицо"] = fname.split("_")[0]
            sales_list.append(df)
        else:
            st.warning(f"⚠️ Файл {fname} не найден")

    if not sales_list:
        st.error("❌ Нет файлов продаж")
        st.stop()

    sales = pd.concat(sales_list, ignore_index=True)
    return market, queries, sales

# ------- Загрузка -------
try:
    market, queries, sales = load_data()
except Exception as e:
    st.error(f"❌ Ошибка загрузки данных: {e}")
    st.stop()

# ------- Преобразования -------
def convert_to_numeric(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def get_columns(df, preferred_columns, default_values=None):
    """
    Возвращает DataFrame, содержащий ровно preferred_columns.
    Если колонки нет в исходном df — подставляет значение из default_values
    или NaN.
    """
    result = {}
    for col in preferred_columns:
        if col in df.columns:
            result[col] = df[col]
        elif default_values and col in default_values:
            # если значение по умолчанию скаляр — заполним им всю колонку
            val = default_values[col]
            result[col] = pd.Series([val] * len(df), index=df.index)
        else:
            result[col] = pd.Series([np.nan] * len(df), index=df.index)
    return pd.DataFrame(result)

# Конвертация числовых колонок продаж
numeric_sales_cols = ['Заказали на сумму, ₽', 'Выкупили на сумму, ₽']
sales = convert_to_numeric(sales, numeric_sales_cols)

# Агрегация продаж по Предмет + Юрлицо
if 'Артикул WB' not in sales.columns:
    count_col = sales.columns[0] if len(sales.columns) > 0 else None
else:
    count_col = 'Артикул WB'

agg_kwargs = {}
if count_col:
    agg_kwargs['Мои_товары'] = (count_col, 'count')
else:
    # если нет колонки, считаем по любой непустой строке
    agg_kwargs['Мои_товары'] = (sales.columns[0], 'count')

# Суммируем деньги (если есть)
if 'Заказали на сумму, ₽' in sales.columns:
    agg_kwargs['Мои_заказы'] = ('Заказали на сумму, ₽', 'sum')
else:
    sales['Заказали на сумму, ₽'] = 0
    agg_kwargs['Мои_заказы'] = ('Заказали на сумму, ₽', 'sum')

if 'Выкупили на сумму, ₽' in sales.columns:
    agg_kwargs['Мои_выкупы'] = ('Выкупили на сумму, ₽', 'sum')
else:
    sales['Выкупили на сумму, ₽'] = 0
    agg_kwargs['Мои_выкупы'] = ('Выкупили на сумму, ₽', 'sum')

sales_agg = sales.groupby(['Предмет', 'Юрлицо'], as_index=False).agg(**agg_kwargs)

# Корректные числовые типы и процент выкупа
sales_agg['Мои_заказы'] = pd.to_numeric(sales_agg['Мои_заказы'], errors='coerce').fillna(0)
sales_agg['Мои_выкупы'] = pd.to_numeric(sales_agg['Мои_выкупы'], errors='coerce').fillna(0)
sales_agg['Мои_товары'] = pd.to_numeric(sales_agg['Мои_товары'], errors='coerce').fillna(0)

sales_agg['Мой_процент_выкупа'] = (
    (sales_agg['Мои_выкупы'] / sales_agg['Мои_заказы'].replace(0, np.nan) * 100)
).round(2).fillna(0)

# Агрегация запросов
if 'Количество запросов' in queries.columns:
    queries = convert_to_numeric(queries, ['Количество запросов'])
    queries_agg = queries.groupby('Предмет', as_index=False).agg(
        Количество_запросов=('Количество запросов', 'sum')
    )
else:
    queries_agg = pd.DataFrame({'Предмет': [], 'Количество_запросов': []})

# Объединяем рынок (market)
expected_market_columns = [
    'Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
    'Выручка, ₽', '% прироста выручки', 'Средний чек, ₽',
    'Оборачиваемость за неделю, дни', 'Процент выкупа'
]

default_values = {
    'Продавцы': 0,
    'Продавцы с заказами': 0,
    'Монополизация, %': 0,
    'Выручка, ₽': 0,
    '% прироста выручки': 0,
    'Средний чек, ₽': 0,
    'Оборачиваемость за неделю, дни': 0,
    'Процент выкупа': 0
}

# Если market содержит несколько строк (по предметам) — get_columns сохранит длину
base = get_columns(market, expected_market_columns, default_values)

# Преобразуем числа
numeric_base_cols = ['Продавцы', 'Продавцы с заказами', 'Монополизация, %',
                    'Выручка, ₽', '% прироста выручки', 'Средний чек, ₽',
                    'Оборачиваемость за неделю, дни', 'Процент выкупа']
base = convert_to_numeric(base, numeric_base_cols)

# Объединяем с запросами по 'Предмет'
if 'Предмет' in base.columns and not queries_agg.empty:
    base = pd.merge(base, queries_agg, on='Предмет', how='left')
else:
    base['Количество_запросов'] = base.get('Количество_запросов', 0)

base['Количество_запросов'] = base['Количество_запросов'].fillna(0)

# -------------------------------
# НАСТРОЙКИ И ФИЛЬТРЫ
# -------------------------------
st.sidebar.title("⚙️ Настройки рекомендаций")
min_growth = st.sidebar.number_input("Мин. рост выручки (%)", value=20, step=5)
max_monopoly = st.sidebar.number_input("Макс. монополизация (%)", value=50, step=5)
min_queries = st.sidebar.number_input("Мин. запросов", value=100000, step=10000)
max_turnover = st.sidebar.number_input("Макс. оборачиваемость (дни)", value=30, step=5)
min_buyout = st.sidebar.number_input("Мин. выкуп (%)", value=70, step=5)

# Список юрлиц
if 'Юрлицо' in sales_agg.columns:
    legal_entities = ['Любое'] + sorted(sales_agg['Юрлицо'].dropna().unique())
else:
    legal_entities = ['Любое']
    sales_agg['Юрлицо'] = 'Не указано'

selected_legal = st.sidebar.selectbox("Юрлицо", legal_entities)

# -------------------------------
# Объединение продаж с базой
# -------------------------------
if selected_legal == "Любое":
    sales_agg['Мой_процент_выкупа'] = pd.to_numeric(sales_agg['Мой_процент_выкупа'], errors='coerce')
    agg_all = sales_agg.groupby('Предмет', as_index=False).agg(
        Мои_заказы=('Мои_заказы', 'sum'),
        Мои_выкупы=('Мои_выкупы', 'sum'),
        Мои_товары=('Мои_товары', 'sum'),
        Мой_процент_выкупа=('Мой_процент_выкупа', 'mean'),
        Юрлица=('Юрлицо', lambda x: ', '.join(sorted(str(v) for v in x.dropna().unique())))
    )
    if 'Предмет' in base.columns and 'Предмет' in agg_all.columns:
        result = pd.merge(base, agg_all, on='Предмет', how='left')
    else:
        result = base.copy()
        for c in ['Мои_заказы', 'Мои_выкупы', 'Мои_товары', 'Мой_процент_выкупа', 'Юрлица']:
            result[c] = 0 if c != 'Юрлица' else "—"
    result['Юрлица'] = result['Юрлица'].fillna("—")
else:
    # Исправлена опечатка: 'Юрлицо'
    filtered_sales = sales_agg[sales_agg['Юрлицо'] == selected_legal]
    if 'Предмет' in base.columns and 'Предмет' in filtered_sales.columns:
        result = pd.merge(base, filtered_sales, on='Предмет', how='left')
    else:
        result = base.copy()
    result['Юрлица'] = selected_legal

# Заполнение пропусков
for col in ['Мои_заказы', 'Мои_выкупы', 'Мой_процент_выкупа', 'Количество_запросов', 'Мои_товары']:
    if col in result.columns:
        result[col] = result[col].fillna(0)

# Приведение типов
numeric_cols = ['Выручка, ₽', '% прироста выручки', 'Монополизация, %', 
                'Оборачиваемость за неделю, дни', 'Процент выкупа',
                'Мои_заказы', 'Количество_запросов', 'Мой_процент_выкупа',
                'Мои_выкупы', 'Мои_товары']
result = convert_to_numeric(result, [col for col in numeric_cols if col in result.columns])

# Доля рынка
if 'Мои_заказы' in result.columns and 'Выручка, ₽' in result.columns:
    result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, np.nan) * 100).round(2)
    result['Моя_доля_рынка_%'] = result['Моя_доля_рынка_%'].fillna(0)
else:
    result['Моя_доля_рынка_%'] = 0

# -------------------------------
# РЕКОМЕНДАЦИИ (логика сохранена)
# -------------------------------
def get_rec(row):
    try:
        required_cols = ['Мои_заказы', 'Количество_запросов']
        for col in required_cols:
            if col not in row.index:
                return "❓ Нет данных"
        
        if row['Мои_заказы'] == 0:
            check_monopoly = ('Монополизация, %' in row.index and pd.notna(row['Монополизация, %']) and row['Монополизация, %'] <= max_monopoly)
            check_growth = ('% прироста выручки' in row.index and pd.notna(row['% прироста выручки']) and row['% прироста выручки'] >= min_growth)
            check_turnover = ('Оборачиваемость за неделю, дни' in row.index and pd.notna(row['Оборачиваемость за неделю, дни']) and row['Оборачиваемость за неделю, дни'] <= max_turnover)
            
            if (row['Количество_запросов'] >= min_queries and check_monopoly and check_growth and check_turnover):
                return "✅ Вход"
            else:
                return "⏸ Не сейчас"
        else:
            check_market_share = ('Моя_доля_рынка_%' in row.index and pd.notna(row['Моя_доля_рынка_%']) and row['Моя_доля_рынка_%'] < 5)
            check_growth = ('% прироста выручки' in row.index and pd.notna(row['% прироста выручки']) and row['% прироста выручки'] >= min_growth)
            check_buyout = ('Мой_процент_выкупа' in row.index and pd.notna(row['Мой_процент_выкупа']) and row['Мой_процент_выкупа'] >= min_buyout)
            
            if (check_market_share and check_growth and check_buyout):
                return "🚀 Усиление"
            elif ('Мой_процент_выкупа' in row.index and pd.notna(row['Мой_процент_выкупа']) and row['Мой_процент_выкупа'] < 70):
                return "⚠️ Выход / Анализ"
            else:
                return "📊 Мониторинг"
    except Exception:
        return "❓ Ошибка"

if not result.empty:
    result['Рекомендация'] = result.apply(get_rec, axis=1)
else:
    result['Рекомендация'] = "📊 Нет данных"

# Фильтр по рекомендациям
if not result.empty and 'Рекомендация' in result.columns:
    rec_options = sorted(result['Рекомендация'].unique())
    selected_recs = st.sidebar.multiselect("Рекомендация", rec_options, default=rec_options)
    result = result[result['Рекомендация'].isin(selected_recs)].copy()

# -------------------------------
# СОРТИРОВКА (исправлена и усилена)
# -------------------------------
sorted_result = result.copy()
if not sorted_result.empty:
    sort_options = ['Выручка, ₽', 'Количество_запросов', 'Монополизация, %', 
                   'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_процент_выкупа',
                   '% прироста выручки', 'Оборачиваемость за неделю, дни']

    available_sort_cols = [col for col in sort_options if col in sorted_result.columns]

    if available_sort_cols:
        # добавим опцию "По умолчанию (Выручка)"
        ui_options = ['По умолчанию (Выручка)'] + available_sort_cols
        selected_sort = st.selectbox("Сортировать по:", ui_options, index=0)

        # если выбрана конкретная колонка — разрешаем выбрать направление
        if selected_sort != 'По умолчанию (Выручка)':
            sort_ascending = st.checkbox("По возрастанию", value=False)
            sort_col = selected_sort  # это название колонки в DF
            # Попытка привести колонку к числовому типу для корректной сортировки
            try:
                sorted_result[sort_col] = pd.to_numeric(sorted_result[sort_col], errors='coerce')
                sorted_result = sorted_result.sort_values(by=sort_col, ascending=sort_ascending, na_position='last')
            except Exception:
                # безопасный fallback — лексикографическая сортировка
                sorted_result = sorted_result.sort_values(by=sort_col, ascending=sort_ascending, na_position='last')
        else:
            # По умолчанию — сортируем по 'Выручка, ₽' убыванию, если есть
            if 'Выручка, ₽' in sorted_result.columns:
                sorted_result['Выручка, ₽'] = pd.to_numeric(sorted_result['Выручка, ₽'], errors='coerce')
                sorted_result = sorted_result.sort_values(by='Выручка, ₽', ascending=False, na_position='last')

    sorted_result = sorted_result.reset_index(drop=True)

# -------------------------------
# ОТОБРАЖЕНИЕ
# -------------------------------
st.title("🔍 Анализ ниш Wildberries")

if result.empty:
    st.warning("⚠️ Нет данных для отображения")
else:
    display_df = sorted_result.copy()

    # Форматирование денежных значений
    money_cols = ['Выручка, ₽', 'Средний чек, ₽', 'Мои_заказы', 'Мои_выкупы']
    for col in money_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(format_number)

    # Форматирование количественных значений
    count_cols = ['Количество_запросов', 'Продавцы', 'Продавцы с заказами', 'Мои_товары']
    for col in count_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: format_number(x) if pd.notna(x) else "—")

    # Форматирование процентных значений
    percent_cols = ['Монополизация, %', 'Моя_доля_рынка_%', 'Мой_процент_выкупа', 
                    '% прироста выручки', 'Процент выкупа']
    for col in percent_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")

    # Форматирование дней
    day_cols = ['Оборачиваемость за неделю, дни']
    for col in day_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")

    possible_columns = ['Предмет', 'Юрлица', 'Выручка, ₽', 'Количество_запросов', 
                       'Монополизация, %', 'Продавцы с заказами', 'Мои_заказы', 
                       'Моя_доля_рынка_%', 'Мой_процент_выкупа', 'Рекомендация',
                       'Средний чек, ₽', 'Оборачиваемость за неделю, дни', 'Процент выкупа']

    existing_columns = [col for col in possible_columns if col in display_df.columns]

    st.dataframe(
        display_df[existing_columns],
        use_container_width=True,
        hide_index=True
    )

    # Запросы по предмету (не трогал логику, только исправил опечатку)
    st.subheader("🔎 Запросы по предмету")
    if 'Предмет' in sorted_result.columns and not sorted_result['Предмет'].empty:
        subjects = sorted(sorted_result['Предмет'].dropna().unique())
        if subjects:
            selected_subject = st.selectbox("Выберите предмет", subjects)
            if selected_subject and 'Предмет' in queries.columns:
                q = queries[queries['Предмет'] == selected_subject].copy()
                if not q.empty:
                    available_cols = []
                    for col in ['Поисковый запрос', 'Количество запросов', 
                               'Количество запросов (предыдущий период)',
                               'Заказали товаров', 'Заказали товаров (предыдущий период)']:
                        if col in q.columns:
                            available_cols.append(col)

                    if available_cols:
                        query_numeric_cols = ['Количество запросов', 'Количество запросов (предыдущий период)',
                                            'Заказали товаров', 'Заказали товаров (предыдущий период)']
                        q = convert_to_numeric(q, [col for col in query_numeric_cols if col in q.columns])

                        if 'Количество запросов' in q.columns and 'Количество запросов (предыдущий период)' in q.columns:
                            q['Δ Запросы, %'] = (
                                (q['Количество запросов'] - q['Количество запросов (предыдущий период)']) /
                                q['Количество запросов (предыдущий период)'].replace(0, np.nan) * 100
                            ).round(1).fillna(0)
                            available_cols.append('Δ Запросы, %')

                        if 'Заказали товаров' in q.columns and 'Заказали товаров (предыдущий период)' in q.columns:
                            q['Δ Заказы, %'] = (
                                (q['Заказали товаров'] - q['Заказали товаров (предыдущий период)']) /
                                q['Заказали товаров (предыдущий период)'].replace(0, np.nan) * 100
                            ).round(1).fillna(0)
                            available_cols.append('Δ Заказы, %')

                        display_q = q[available_cols].copy()

                        # Форматирование чисел (исправлена опечатка 'предходящий' -> 'предыдущий')
                        for col in ['Количество запросов', 'Количество запросов (предыдущий период)',
                                   'Заказали товаров', 'Заказали товаров (предыдущий период)']:
                            if col in display_q.columns:
                                display_q[col] = display_q[col].apply(format_number)

                        for col in ['Δ Запросы, %', 'Δ Заказы, %']:
                            if col in display_q.columns:
                                display_q[col] = display_q[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")

                        st.dataframe(display_q, use_container_width=True, hide_index=True)
                    else:
                        st.info("Нет доступных данных по запросам")
                else:
                    st.info("Нет данных по запросам для выбранного предмета")
            else:
                st.info("Выберите предмет для просмотра запросов")
        else:
            st.info("Нет доступных предметов")
    else:
        st.info("Нет данных о предметах")

# -------------------------------
# СТАТИСТИКА
# -------------------------------
st.sidebar.subheader("📊 Статистика")
if not result.empty and 'Рекомендация' in result.columns:
    total_categories = len(result)
    enter_categories = len(result[result['Рекомендация'] == "✅ Вход"])
    st.sidebar.metric("Всего категорий", total_categories)
    st.sidebar.metric("Для входа", enter_categories)
