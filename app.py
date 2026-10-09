import io
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


THEME = {
    "navy": "#1E1F27",
    "blue": "#4F60D2",
    "pink": "#EB84CD",
    "cyan": "#4BDBC5",
    "red": "#E04232",
    "yellow": "#FCD200",
    "green": "#6EA514",
    "lime": "#BAD80A",
    "muted": "#5B5C64",
    "light": "#ECEFFC",
}
STATUS_COLORS = {
    "Pendente": THEME["pink"],
    "Em tratamento": THEME["blue"],
    "Concluído": THEME["green"],
}
DATA_PATH = Path(__file__).parent / "data" / "stock_08_10.csv"
REQUIRED_COLUMNS = ["Data entrada", "Descricao", "User", "Data tratamento"]


def _normalize_label(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.strip().casefold().replace("_", " ").split())


def normalize_columns(df):
    aliases = {
        "data entrada": "Data entrada",
        "data de entrada": "Data entrada",
        "descricao": "Descricao",
        "description": "Descricao",
        "tarefa": "Tarefa",
        "user": "User",
        "utilizador": "User",
        "responsavel": "User",
        "data tratamento": "Data tratamento",
        "data de tratamento": "Data tratamento",
        "data conclusao": "Data tratamento",
        "area": "Tarefa",
        "folha": "Tarefa",
    }
    rename_map = {}
    for column in df.columns:
        target = aliases.get(_normalize_label(column))
        if target:
            rename_map[column] = target
    return df.rename(columns=rename_map)


def normalize_user(value):
    normalized = unicodedata.normalize("NFKD", str(value).strip().casefold())
    return "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("M")
    )


@st.cache_data
def load_default_data():
    if not DATA_PATH.exists():
        return pd.DataFrame(columns=[*REQUIRED_COLUMNS, "Tarefa"])
    return pd.read_csv(DATA_PATH, sep=";", encoding="utf-8-sig")


@st.cache_data
def load_uploaded_data(filename, file_bytes):
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), sep=None, engine="python", encoding="utf-8-sig")
        return df, []

    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("Formato não suportado. Carrega um ficheiro CSV ou XLSX.")

    workbook = pd.ExcelFile(io.BytesIO(file_bytes))
    frames = []
    skipped_sheets = []
    for sheet_name in workbook.sheet_names:
        sheet = pd.read_excel(workbook, sheet_name=sheet_name)
        if sheet.dropna(how="all").empty:
            continue
        sheet = normalize_columns(sheet)
        if not set(REQUIRED_COLUMNS).issubset(sheet.columns):
            skipped_sheets.append(sheet_name)
            continue
        if "Tarefa" not in sheet.columns:
            sheet["Tarefa"] = sheet_name
        frames.append(sheet)

    if not frames:
        raise ValueError(
            "Não encontrei folhas com as colunas Data entrada, Descrição, User e Data tratamento."
        )
    return pd.concat(frames, ignore_index=True), skipped_sheets


def clean_dataframe(df):
    df = normalize_columns(df.copy())
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Colunas em falta: {', '.join(missing)}.")

    if "Tarefa" not in df.columns:
        df["Tarefa"] = "Tarefa desconhecida"
    df = df.dropna(how="all", subset=REQUIRED_COLUMNS)
    df["Descricao"] = df["Descricao"].fillna("Sem descrição").astype(str).str.strip()
    df["User"] = df["User"].fillna("").map(normalize_user)
    df["Tarefa"] = (
        df["Tarefa"]
        .fillna("Tarefa desconhecida")
        .astype(str)
        .str.strip()
        .str.replace(r"(?i)^DL\s+", "", regex=True)
        .replace(
            to_replace=r"(?i)^Pagamentos ilhas$",
            value="Pgto Ilhas - via ficheiro",
            regex=True,
        )
    )
    df["Data entrada"] = pd.to_datetime(df["Data entrada"], errors="coerce", dayfirst=True)
    df["Data tratamento"] = pd.to_datetime(df["Data tratamento"], errors="coerce", dayfirst=True)

    df["Estado"] = "Concluído"
    df.loc[df["Data tratamento"].isna() & df["User"].eq(""), "Estado"] = "Pendente"
    df.loc[df["Data tratamento"].isna() & df["User"].ne(""), "Estado"] = "Em tratamento"

    today = pd.Timestamp.today().normalize()
    waiting_days = (today - df["Data entrada"]).dt.days
    df["Dias em aberto"] = waiting_days.where(df["Data tratamento"].isna()).clip(lower=0)
    duration = (df["Data tratamento"] - df["Data entrada"]).dt.days
    df["Dias para concluir"] = duration.where(duration.ge(0))
    return df


def apply_filters(df, tasks, users, date_start, date_end, description_query):
    filtered = df[df["Tarefa"].isin(tasks)].copy()
    selected_assignees = [user for user in users if user != "(Sem responsável)"]
    user_mask = filtered["User"].isin(selected_assignees)
    if "(Sem responsável)" in users:
        user_mask |= filtered["User"].eq("")
    filtered = filtered[user_mask]
    if date_start:
        filtered = filtered[filtered["Data entrada"].ge(pd.Timestamp(date_start))]
    if date_end:
        filtered = filtered[filtered["Data entrada"].le(pd.Timestamp(date_end))]
    if description_query:
        filtered = filtered[
            filtered["Descricao"].str.contains(description_query, case=False, na=False, regex=False)
        ]
    return filtered


def style_dashboard():
    st.markdown(
        f"""
        <style>
        :root {{ --nos-pink: {THEME["pink"]}; --nos-blue: {THEME["blue"]}; }}
        [data-testid="stAppViewContainer"] {{ background: {THEME["light"]}; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stMainBlockContainer"] {{ max-width: 1500px; padding-top: 2rem; }}
        [data-testid="stMetric"] {{
            background: #ffffff; border: 1px solid #e1e8ed; border-radius: 14px;
            padding: 18px 20px; box-shadow: 0 2px 8px rgba(14, 40, 65, 0.04);
        }}
        [data-testid="stMetricLabel"] p {{ color: {THEME["muted"]}; font-size: 0.88rem; }}
        [data-testid="stMetricValue"] {{ color: {THEME["navy"]}; }}
        h1, h2, h3 {{ color: {THEME["navy"]}; }}
        .dashboard-eyebrow {{
            color: {THEME["blue"]}; font-size: 0.78rem; font-weight: 700;
            letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.35rem;
        }}
        .dashboard-subtitle {{ color: {THEME["muted"]}; margin-top: -0.5rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def export_csv(df):
    return df.to_csv(index=False, sep=";", date_format="%d-%m-%Y").encode("utf-8-sig")


st.set_page_config(
    page_title="Tarefas Recebimentos Contencioso",
    page_icon="📊",
    layout="wide",
)
style_dashboard()

st.markdown('<div class="dashboard-eyebrow">NOS · Operações</div>', unsafe_allow_html=True)
st.title("Tarefas Recebimentos Contencioso")
st.markdown(
    '<p class="dashboard-subtitle">Acompanha o volume de trabalho, o estado dos pedidos e os tempos de tratamento.</p>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Dados e filtros")
    uploaded_file = st.file_uploader(
        "Carregar outro ficheiro",
        type=["csv", "xlsx", "xlsm"],
        help="Os ficheiros Excel podem ter várias folhas; as folhas compatíveis são consolidadas.",
    )
    st.caption("Sem carregamento, é utilizado o ficheiro de stock local, se disponível.")

try:
    if uploaded_file:
        raw_data, skipped_sheets = load_uploaded_data(uploaded_file.name, uploaded_file.getvalue())
        source_label = uploaded_file.name
    else:
        raw_data = load_default_data()
        skipped_sheets = []
        source_label = "Quantidade_08.10.xlsx"
    data = clean_dataframe(raw_data)
except Exception as error:
    st.error(f"Não foi possível carregar os dados: {error}")
    st.stop()

if data.empty:
    st.info("Carrega o ficheiro de stock na barra lateral para visualizar o dashboard.")
    st.stop()
if skipped_sheets:
    st.sidebar.warning(
        "Folhas ignoradas por não terem as colunas esperadas: " + ", ".join(skipped_sheets)
    )

valid_dates = data["Data entrada"].dropna()
with st.sidebar:
    all_tasks = sorted(data["Tarefa"].dropna().unique().tolist())
    selected_tasks = st.multiselect("Tarefa", all_tasks, default=all_tasks)
    all_users = sorted(user for user in data["User"].unique().tolist() if user)
    user_options = ["(Sem responsável)", *all_users]
    selected_users = st.multiselect("Responsável", user_options, default=user_options)
    if not valid_dates.empty:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        selected_dates = st.date_input(
            "Data de entrada",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            date_start, date_end = selected_dates
        elif isinstance(selected_dates, tuple) and selected_dates:
            date_start, date_end = selected_dates[0], None
        else:
            date_start, date_end = None, None
    else:
        date_start, date_end = None, None
    description_query = st.text_input("Pesquisar descrição")

filtered = apply_filters(
    data, selected_tasks, selected_users, date_start, date_end, description_query
)
if filtered.empty:
    st.info("Não existem registos para os filtros selecionados.")
    st.stop()

total = len(filtered)
counts = filtered["Estado"].value_counts()
pending_count = int(counts.get("Pendente", 0))
in_progress_count = int(counts.get("Em tratamento", 0))
completed_count = int(counts.get("Concluído", 0))
completion_rate = completed_count / total * 100 if total else 0
average_days = filtered.loc[filtered["Estado"].eq("Concluído"), "Dias para concluir"].mean()

st.caption(f"Fonte: {source_label} · {total:,} registos no filtro".replace(",", " "))
kpis = st.columns(5)
kpis[0].metric("Total de registos", f"{total:,}".replace(",", " "))
kpis[1].metric("Concluídos", f"{completed_count:,}".replace(",", " "))
kpis[2].metric("Em tratamento", f"{in_progress_count:,}".replace(",", " "))
kpis[3].metric("Pendentes", f"{pending_count:,}".replace(",", " "))
kpis[4].metric("Taxa de conclusão", f"{completion_rate:.1f}%")
average_text = f"{average_days:.1f} dias" if pd.notna(average_days) else "—"
st.caption(
    f"Tempo médio até à conclusão: **{average_text}**. "
    "Pendente = sem responsável e sem data de tratamento; em tratamento = com responsável, ainda sem conclusão."
)

left_chart, right_chart = st.columns((1.4, 1))
with left_chart:
    st.subheader("Entradas e conclusões por mês")
    entries = (
        filtered.dropna(subset=["Data entrada"])
        .assign(
            Mês=lambda frame: frame["Data entrada"]
            .dt.to_period("M")
            .astype(str)
            .where(frame["Data entrada"].dt.year.ge(2026), "Antes de 2026")
        )
        .groupby("Mês")
        .size()
        .rename("Entradas")
    )
    completed = (
        filtered.dropna(subset=["Data tratamento"])
        .assign(
            Mês=lambda frame: frame["Data tratamento"]
            .dt.to_period("M")
            .astype(str)
            .where(frame["Data tratamento"].dt.year.ge(2026), "Antes de 2026")
        )
        .groupby("Mês")
        .size()
        .rename("Concluídos")
    )
    monthly = pd.concat([entries, completed], axis=1).fillna(0)
    monthly.index.name = "Mês"
    month_order = ["Antes de 2026", *sorted(month for month in monthly.index if month != "Antes de 2026")]
    monthly = monthly.reset_index().melt(
        id_vars="Mês", var_name="Indicador", value_name="Registos"
    )
    monthly_chart = px.bar(
        monthly,
        x="Mês",
        y="Registos",
        color="Indicador",
        barmode="group",
        color_discrete_map={"Entradas": THEME["blue"], "Concluídos": THEME["pink"]},
        category_orders={"Mês": month_order},
        labels={"Mês": "Mês", "Registos": "Número de registos"},
    )
    monthly_chart.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title_text="",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(monthly_chart, use_container_width=True)

with right_chart:
    st.subheader("Estado do stock")
    status_summary = (
        filtered["Estado"].value_counts().rename_axis("Estado").reset_index(name="Registos")
    )
    status_chart = px.pie(
        status_summary,
        names="Estado",
        values="Registos",
        hole=0.62,
        color="Estado",
        color_discrete_map=STATUS_COLORS,
    )
    status_chart.update_traces(textposition="inside", textinfo="percent+label")
    status_chart.update_layout(
        showlegend=False,
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(status_chart, use_container_width=True)

st.subheader("Trabalho por tarefa")
open_work = filtered[filtered["Estado"].ne("Concluído")]
if open_work.empty:
    st.success("Não há trabalho por concluir com os filtros selecionados.")
else:
    task_summary = (
        open_work.groupby(["Tarefa", "Estado"])
        .size()
        .rename("Registos")
        .reset_index()
        .sort_values("Registos", ascending=True)
    )
    task_chart = px.bar(
        task_summary,
        x="Registos",
        y="Tarefa",
        color="Estado",
        orientation="h",
        barmode="stack",
        color_discrete_map=STATUS_COLORS,
        labels={"Tarefa": "Tarefa", "Registos": "Registos em aberto"},
    )
    task_chart.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title_text="",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(task_chart, use_container_width=True)

st.subheader("Acompanhamento dos registos")
pending = filtered[filtered["Estado"].eq("Pendente")].sort_values(
    "Dias em aberto", ascending=False, na_position="last"
)
pending_task_board = (
    pending.groupby("Tarefa")
    .agg(
        Pendentes=("Tarefa", "size"),
        **{
            "Data mais antiga": ("Data entrada", "min"),
            "Dias do mais antigo": ("Dias em aberto", "max"),
        },
    )
    .reset_index()
    .sort_values(["Pendentes", "Dias do mais antigo"], ascending=[False, False])
)
if not pending_task_board.empty:
    pending_task_board["% dos pendentes"] = (
        pending_task_board["Pendentes"].div(pending_count).mul(100).round(1)
    )

pending_board_tab, pending_tab, in_progress_tab, all_tab, responsible_tab = st.tabs(
    [
        f"Quadro de pendentes ({len(pending_task_board)} tarefas)",
        f"Pendentes ({pending_count})",
        f"Em tratamento ({in_progress_count})",
        f"Todos ({total})",
        "Por responsável",
    ]
)
display_columns = [
    "Tarefa",
    "Descricao",
    "Data entrada",
    "User",
    "Data tratamento",
    "Dias em aberto",
    "Estado",
]

with pending_board_tab:
    st.caption("Resumo das tarefas com registos pendentes, ordenadas por volume.")
    if pending_task_board.empty:
        st.success("Não há tarefas pendentes com os filtros selecionados.")
    else:
        st.dataframe(
            pending_task_board,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Pendentes": st.column_config.NumberColumn("Pendentes", format="%d"),
                "% dos pendentes": st.column_config.NumberColumn(
                    "% dos pendentes", format="%.1f%%"
                ),
                "Data mais antiga": st.column_config.DateColumn(
                    "Data mais antiga", format="DD/MM/YYYY"
                ),
                "Dias do mais antigo": st.column_config.NumberColumn(
                    "Dias do mais antigo", format="%d"
                ),
            },
        )
        st.download_button(
            "Descarregar quadro de pendentes (CSV)",
            export_csv(pending_task_board),
            file_name="quadro_pendentes_por_tarefa.csv",
            mime="text/csv",
            key="download_pending_board",
        )

with pending_tab:
    if pending.empty:
        st.success("Não há registos pendentes.")
    else:
        st.dataframe(pending[display_columns], hide_index=True, use_container_width=True)
        st.download_button(
            "Descarregar pendentes (CSV)",
            export_csv(pending[display_columns]),
            file_name="pendentes_nos.csv",
            mime="text/csv",
            key="download_pending",
        )

with in_progress_tab:
    in_progress = filtered[filtered["Estado"].eq("Em tratamento")].sort_values(
        "Dias em aberto", ascending=False, na_position="last"
    )
    if in_progress.empty:
        st.success("Não há registos em tratamento.")
    else:
        st.dataframe(in_progress[display_columns], hide_index=True, use_container_width=True)
        st.download_button(
            "Descarregar em tratamento (CSV)",
            export_csv(in_progress[display_columns]),
            file_name="em_tratamento_nos.csv",
            mime="text/csv",
            key="download_in_progress",
        )

with all_tab:
    all_records = filtered.sort_values("Data entrada", ascending=False, na_position="last")
    st.dataframe(all_records[display_columns], hide_index=True, use_container_width=True)
    st.download_button(
        "Descarregar registos filtrados (CSV)",
        export_csv(all_records[display_columns]),
        file_name="stock_nos_filtrado.csv",
        mime="text/csv",
        key="download_all",
    )

with responsible_tab:
    st.caption(
        "Análise dos registos atribuídos, conforme os filtros selecionados. "
        "Os pendentes sem responsável são apresentados apenas no quadro de pendentes."
    )
    responsible_data = filtered[filtered["User"].ne("")].assign(
        Responsável=lambda frame: frame["User"]
    )
    responsible_summary = (
        responsible_data.pivot_table(
            index="Responsável",
            columns="Estado",
            values="Descricao",
            aggfunc="size",
            fill_value=0,
        )
        .reindex(columns=["Pendente", "Em tratamento", "Concluído"], fill_value=0)
        .rename(
            columns={
                "Pendente": "Pendentes",
                "Em tratamento": "Em tratamento",
                "Concluído": "Concluídos",
            }
        )
    )
    responsible_summary["Total"] = responsible_summary.sum(axis=1)
    responsible_summary["Taxa de conclusão"] = (
        responsible_summary["Concluídos"]
        .div(responsible_summary["Total"])
        .mul(100)
        .round(1)
    )
    responsible_summary["Tempo médio até à conclusão (dias)"] = (
        responsible_data[responsible_data["Estado"].eq("Concluído")]
        .groupby("Responsável")["Dias para concluir"]
        .mean()
        .round(1)
    )
    responsible_summary = (
        responsible_summary.reset_index()
        .sort_values(["Total", "Responsável"], ascending=[False, True])
    )
    responsible_chart_data = responsible_summary.melt(
        id_vars="Responsável",
        value_vars=["Pendentes", "Em tratamento", "Concluídos"],
        var_name="Estado",
        value_name="Registos",
    )
    responsible_chart = px.bar(
        responsible_chart_data,
        x="Registos",
        y="Responsável",
        color="Estado",
        orientation="h",
        barmode="stack",
        category_orders={
            "Responsável": responsible_summary["Responsável"].tolist(),
            "Estado": ["Pendentes", "Em tratamento", "Concluídos"],
        },
        color_discrete_map={
            "Pendentes": STATUS_COLORS["Pendente"],
            "Em tratamento": STATUS_COLORS["Em tratamento"],
            "Concluídos": STATUS_COLORS["Concluído"],
        },
        labels={"Responsável": "Responsável", "Registos": "Registos"},
    )
    responsible_chart.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title_text="",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(responsible_chart, use_container_width=True)
    st.dataframe(
        responsible_summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Taxa de conclusão": st.column_config.NumberColumn(
                "Taxa de conclusão", format="%.1f%%"
            ),
            "Tempo médio até à conclusão (dias)": st.column_config.NumberColumn(
                "Tempo médio até à conclusão (dias)", format="%.1f"
            ),
        },
    )
    st.download_button(
        "Descarregar análise por responsável (CSV)",
        export_csv(responsible_summary),
        file_name="analise_por_responsavel.csv",
        mime="text/csv",
        key="download_responsible_summary",
    )

st.caption("Paleta baseada nas cores oficiais da NOS.pt, com fundos neutros e suaves.")
