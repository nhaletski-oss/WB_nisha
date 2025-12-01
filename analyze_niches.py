import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Анализ ниш Wildberries", layout="wide")

def format_number(x):
    if pd.isna(x) or x == 0:
        return "—"
    try:
        return f"{int(x):,}".replace(",", " ")
    except (ValueError, TypeError):
        return "—"

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
    return market, queries, sales

# ЗАГРУЗКА
try:
    market, queries, sales = load_data()
except Exception as e:
    st.error(f"❌ Ошибка загрузки данных: {e}")
    st.stop()

# ФУНКЦИЯ ДЛЯ КОНВЕРТАЦИИ В ЧИСЛА
def convert_to_numeric(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

# ФУНКЦИЯ ДЛЯ ПРОВЕРКИ И ВЫБОРА КОЛОНОК
def get_columns(df, preferred_columns, default_values=None):
    """Возвращает существующие колонки или создает их с значениями по умолчанию"""
    result = {}
    
    for col in preferred_columns:
        if col in df.columns:
            result[col] = df[col]
        elif default_values and col in default_values:
            result[col] = default_values[col]
        else:
            # Если колонки нет и нет значения по умолчанию, создаем пустую
            result[col] = np.nan
    
    return pd.DataFrame(result)

# КОНВЕРТАЦИЯ КОЛОНОК В ЧИСЛА ПЕРЕД АГРЕГАЦИЕЙ
numeric_sales_cols = ['Заказали на сумму, ₽', 'Выкупили на сумму, ₽']
sales = convert_to_numeric(sales, numeric_sales_cols)

# Агрегация продаж
# Проверяем, есть ли необходимая колонка для агрегации
if 'Артикул WB' not in sales.columns:
    # Если нет колонки 'Артикул WB', используем первую колонку для подсчета
    count_col = sales.columns[0] if len(sales.columns) > 0 else 'Артикул WB'
else:
    count_col = 'Артикул WB'

# ИСПРАВЛЕНА ОПЕЧАТКА: 'Юрлицo' -> 'Юрлицо'
sales_agg = sales.groupby(['Предмет', 'Юрлицо'], as_index=False).agg(
    Мои_заказы=('Заказали на сумму, ₽', 'sum'),
    Мои_выкупы=('Выкупили на сумму, ₽', 'sum'),
    Мои_товары=(count_col, 'count')
)

# ✅ КОРРЕКТНЫЙ РАСЧЁТ ВЫКУПА
sales_agg['Мои_заказы'] = pd.to_numeric(sales_agg['Мои_заказы'], errors='coerce').fillna(0)
sales_agg['Мои_выкупы'] = pd.to_numeric(sales_agg['Мои_выкупы'], errors='coerce').fillna(0)

sales_agg['Мой_процент_выкупа'] = (
    sales_agg['Мои_выкупы'] / sales_agg['Мои_заказы'].replace(0, np.nan) * 100
).round(2).fillna(0)

# Агрегация запросов
if 'Количество запросов' in queries.columns:
    queries = convert_to_numeric(queries, ['Количество запросов'])
    queries_agg = queries.groupby('Предмет', as_index=False).agg(
        Количество_запросов=('Количество запросов', 'sum')
    )
else:
    # Если нет колонки с запросами, создаем пустую
    queries_agg = pd.DataFrame({'Предмет': [], 'Количество_запросов': []})

# ОБЪЕДИНЕНИЕ РЫНКА
# Определяем ожидаемые колонки и их значения по умолчанию
expected_market_columns = [
    'Предмет', 'Продавцы', 'Продавцы с заказами', 'Монополизация, %',
    'Выручка, ₽', '% прироста выручки', 'Средний чек, ₽',
    'Оборачиваемость за неделю, дни', 'Процент выкупа'
]

# Значения по умолчанию для отсутствующих колонок
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

# Создаем base DataFrame с проверкой колонок
base = get_columns(market, expected_market_columns, default_values)

# Преобразуем числовые колонки
numeric_base_cols = ['Продавцы', 'Продавцы с заказами', 'Монополизация, %',
                    'Выручка, ₽', '% прироста выручки', 'Средний чек, ₽',
                    'Оборачиваемость за неделю, дни', 'Процент выкупа']

base = convert_to_numeric(base, numeric_base_cols)

# Объединяем с запросами
if not queries_agg.empty and 'Предмет' in queries_agg.columns and 'Предмет' in base.columns:
    base = pd.merge(base, queries_agg, on='Предмет', how='left')
else:
    base['Количество_запросов'] = 0

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

# Проверяем, есть ли колонка 'Юрлицо' в sales_agg
if 'Юрлицо' in sales_agg.columns:
    legal_entities = ['Любое'] + sorted(sales_agg['Юрлицо'].dropna().unique())
else:
    legal_entities = ['Любое']
    sales_agg['Юрлицо'] = 'Не указано'

selected_legal = st.sidebar.selectbox("Юрлицо", legal_entities)

if selected_legal == "Любое":
    # Преобразуем к числам перед агрегацией
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
        result['Мои_заказы'] = 0
        result['Мои_выкупы'] = 0
        result['Мои_товары'] = 0
        result['Мой_процент_выкупа'] = 0
        result['Юрлица'] = "—"
    
    result['Юрлица'] = result['Юрлица'].fillna("—")
else:
    filtered_sales = sales_agg[sales_agg['Юрлицо'] == selected_legal]
    
    if 'Предмет' in base.columns and 'Предмет' in filtered_sales.columns:
        result = pd.merge(base, filtered_sales, on='Предмет', how='left')
    else:
        result = base.copy()
    
    result['Юрлица'] = selected_legal

# Заполнение пропущенных значений
for col in ['Мои_заказы', 'Мои_выкупы', 'Мой_процент_выкупа', 'Количество_запросов']:
    if col in result.columns:
        result[col] = result[col].fillna(0)

# Приведение к числовым типам
numeric_cols = ['Выручка, ₽', '% прироста выручки', 'Монополизация, %', 
                'Оборачиваемость за неделю, дни', 'Процент выкупа',
                'Мои_заказы', 'Количество_запросов', 'Мой_процент_выкупа',
                'Мои_выкупы']

result = convert_to_numeric(result, [col for col in numeric_cols if col in result.columns])

# Доля рынка
if 'Мои_заказы' in result.columns and 'Выручка, ₽' in result.columns:
    result['Моя_доля_рынка_%'] = (result['Мои_заказы'] / result['Выручка, ₽'].replace(0, np.nan) * 100).round(2)
    result['Моя_доля_рынка_%'] = result['Моя_доля_рынка_%'].fillna(0)
else:
    result['Моя_доля_рынка_%'] = 0

# -------------------------------
# РЕКОМЕНДАЦИИ
# -------------------------------
def get_rec(row):
    try:
        # Проверяем наличие необходимых колонок
        required_cols = ['Мои_заказы', 'Количество_запросов']
        for col in required_cols:
            if col not in row.index:
                return "❓ Нет данных"
        
        if row['Мои_заказы'] == 0:
            # Проверяем наличие дополнительных колонок
            check_monopoly = 'Монополизация, %' in row.index and row['Монополизация, %'] <= max_monopoly
            check_growth = '% прироста выручки' in row.index and row['% прироста выручки'] >= min_growth
            check_turnover = 'Оборачиваемость за неделю, дни' in row.index and row['Оборачиваемость за неделю, дни'] <= max_turnover
            
            if (row['Количество_запросов'] >= min_queries and
                check_monopoly and
                check_growth and
                check_turnover):
                return "✅ Вход"
            else:
                return "⏸ Не сейчас"
        else:
            # Проверяем наличие колонок для существующих заказов
            check_market_share = 'Моя_доля_рынка_%' in row.index and row['Моя_доля_рынка_%'] < 5
            check_growth = '% прироста выручки' in row.index and row['% прироста выручки'] >= min_growth
            check_buyout = 'Мой_процент_выкупа' in row.index and row['Мой_процент_выкупа'] >= min_buyout
            
            if (check_market_share and
                check_growth and
                check_buyout):
                return "🚀 Усиление"
            elif 'Мой_процент_выкупа' in row.index and row['Мой_процент_выкупа'] < 70:
                return "⚠️ Выход / Анализ"
            else:
                return "📊 Мониторинг"
    except Exception as e:
        return f"❓ Ошибка"

if not result.empty:
    result['Рекомендация'] = result.apply(get_rec, axis=1)
else:
    result['Рекомендация'] = "📊 Нет данных"

# -------------------------------
# ФИЛЬТР ПО РЕКОМЕНДАЦИИ
# -------------------------------
if not result.empty and 'Рекомендация' in result.columns:
    rec_options = sorted(result['Рекомендация'].unique())
    selected_recs = st.sidebar.multiselect("Рекомендация", rec_options, default=rec_options)
    result = result[result['Рекомендация'].isin(selected_recs)].copy()

# -------------------------------
# СОРТИРОВКА
# -------------------------------
if not result.empty:
    sorted_result = result.copy()

    sort_options = ['Выручка, ₽', 'Количество_запросов', 'Монополизация, %',
                    'Мои_заказы', 'Моя_доля_рынка_%', 'Мой_процент_выкупа',
                    '% прироста выручки', 'Оборачиваемость за неделю, дни']

    available_sort_cols = [col for col in sort_options if col in sorted_result.columns]

    if available_sort_cols:
        available_sort_cols = ['По умолчанию (Выручка)'] + available_sort_cols

        selected_sort = st.selectbox("Сортировать по:", available_sort_cols)

        if selected_sort != 'По умолчанию (Выручка)':
            sort_ascending = st.checkbox("По возрастанию", value=False)
            sorted_result = sorted_result.sort_values(selected_sort, ascending=sort_ascending)
        else:
            if 'Выручка, ₽' in sorted_result.columns:
                sorted_result = sorted_result.sort_values('Выручка, ₽', ascending=False)

    sorted_result = sorted_result.reset_index(drop=True)

# -------------------------------
# ОТОБРАЖЕНИЕ (числа как числа, форматирование через форматтер)
# -------------------------------
st.title("🔍 Анализ ниш Wildberries")

if result.empty:
    st.warning("⚠️ Нет данных для отображения")
else:
    # Используем sorted_result напрямую (без форматирования в строки)
    display_df = sorted_result.copy()
    
    # Заменяем NaN и 0 на "—" только для отображения
    def format_for_display(df):
        # Копируем DataFrame
        formatted_df = df.copy()
        
        # Заменяем NaN и 0 на "—" для числовых колонок
        numeric_columns = formatted_df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_columns:
            if col in formatted_df.columns:
                formatted_df[col] = formatted_df[col].apply(
                    lambda x: "—" if pd.isna(x) or x == 0 else x
                )
        
        return formatted_df
    
    # Форматируем только для отображения
    display_df_formatted = format_for_display(display_df)

    # Определяем колонки для отображения
    possible_columns = ['Предмет', 'Юрлица', 'Выручка, ₽', 'Количество_запросов',
                       'Монополизация, %', 'Продавцы с заказами', 'Мои_заказы',
                       'Моя_доля_рынка_%', 'Мой_процент_выкупа', 'Рекомендация',
                       'Средний чек, ₽', 'Оборачиваемость за неделю, дни', 'Процент выкупа']

    existing_columns = [col for col in possible_columns if col in display_df_formatted.columns]
    
    # Создаем стилизованный DataFrame для отображения
    styled_df = display_df_formatted[existing_columns].style.format({
        # Денежные значения с разделителями тысяч
        'Выручка, ₽': lambda x: f"{x:,.0f} ₽".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Средний чек, ₽': lambda x: f"{x:,.0f} ₽".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Мои_заказы': lambda x: f"{x:,.0f} ₽".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Мои_выкупы': lambda x: f"{x:,.0f} ₽".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        
        # Количественные значения с разделителями тысяч
        'Количество_запросов': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Продавцы': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Продавцы с заказами': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        'Мои_товары': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) and x != "—" else x,
        
        # Процентные значения
        'Монополизация, %': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) and x != "—" else x,
        'Моя_доля_рынка_%': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) and x != "—" else x,
        'Мой_процент_выкупа': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) and x != "—" else x,
        '% прироста выручки': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) and x != "—" else x,
        'Процент выкупа': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) and x != "—" else x,
        
        # Дни
        'Оборачиваемость за неделю, дни': lambda x: f"{x:.0f}" if isinstance(x, (int, float)) and x != "—" else x,
    })

    # Используем st.dataframe для отображения с форматированием
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # -------------------------------
    # ЗАПРОСЫ ПО ПРЕДМЕТУ
    # -------------------------------
    st.subheader("🔎 Запросы по предмету")
    if 'Предмет' in sorted_result.columns and not sorted_result['Предмет'].empty:
        subjects = sorted(sorted_result['Предмет'].dropna().unique())
        
        if subjects:
            selected_subject = st.selectbox("Выберите предмет", subjects)

            if selected_subject and 'Предмет' in queries.columns:
                q = queries[queries['Предмет'] == selected_subject].copy()
                
                if not q.empty:
                    # Определяем, какие колонки есть в данных
                    available_cols = []
                    for col in ['Поисковый запрос', 'Количество запросов', 
                               'Количество запросов (предыдущий период)',
                               'Заказали товаров', 'Заказали товаров (предыдущий период)']:
                        if col in q.columns:
                            available_cols.append(col)
                    
                    if available_cols:
                        # Конвертируем числовые колонки
                        query_numeric_cols = ['Количество запросов', 'Количество запросов (предыдущий период)',
                                            'Заказали товаров', 'Заказали товаров (предыдущий период)']
                        q = convert_to_numeric(q, [col for col in query_numeric_cols if col in q.columns])
                        
                        # Рассчитываем проценты, если есть необходимые колонки
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
                        
                        # Форматирование для отображения
                        display_q = q[available_cols].copy()
                        
                        # Форматирование через стиль
                        styled_q = display_q.style.format({
                            'Количество запросов': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) else x,
                            'Количество запросов (предыдущий период)': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) else x,
                            'Заказали товаров': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) else x,
                            'Заказали товаров (предыдущий период)': lambda x: f"{x:,.0f}".replace(",", " ") if isinstance(x, (int, float)) else x,
                            'Δ Запросы, %': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x,
                            'Δ Заказы, %': lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x,
                        })
                        
                        st.dataframe(
                            styled_q,
                            use_container_width=True,
                            hide_index=True
                        )
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
if not result.empty and 'Рекомендация' в result.columns:
    total_categories = len(result)
    enter_categories = len(result[result['Рекомендация'] == "✅ Вход"])
    st.sidebar.metric("Всего категорий", total_categories)
    st.sidebar.metric("Для входа", enter_categories)