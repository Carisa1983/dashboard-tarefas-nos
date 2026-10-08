import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


NOS_COLORS = {
    "navy": "#003B7A",
    "blue": "#00A7E1",
    "orange": "#FF6A1A",
    "dark": "#2F2F2F",
    "gray": "#7A7A7A",
    "light": "#E9EDF2",
    "white": "#FFFFFF",
}


@st.cache_data
def load_sample_data():
    sample_path = Path("data/dados_exemplo.csv")
    if sample_path.exists():
        return pd.read_csv(sample_path, sep=";", encoding="utf-8-sig")
    return pd.DataFrame(
        {
            "Data entrada": ["02-01-2026", "02-01-2026", "06-01-2026"],
            "Descricao": ["1.62631280_1", "1.59826266_1", "1.56476992_1"],
            "User": ["ofcação", "ofcação", ""],
            "Data tratamento": ["06-01-2026", "06-01-2026", ""],
        }
    )


@st.cache_data
def load_uploaded_data(uploaded_file):
    if uploaded_file is None:
        return load_sample_data()

    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file, sep=";", encoding="utf-8-sig")
        except Exception:
            return pd.read_csv(uploaded_file, encoding="utf-8-sig")

    if filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file)
        return df

    st.warning("Formato de ficheiro não suportado. Use CSV, XLSX ou XLS.")
    return pd.DataFrame()


def normalize_columns(df):
    if df.empty:
        return df

    rename_map = {}
    normalized = {str(col).strip().lower(): col for col in df.columns}

    for key, target in {
        "data entrada": "Data entrada",
        "data_entrada": "Data entrada",
        "data entrada ": "Data entrada",
        "descricao": "Descricao",
        "descrição": "Descricao",
        "description": "Descricao",
        "user": "User",
        "utilizador": "User",
        "data tratamento": "Data tratamento",
        "data_tratamento": "Data tratamento",
        "data tratamento ": "Data tratamento",
    }.items():
        if key in normalized:
            rename_map[normalized[key]] = target

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def clean_dataframe(df):
    df = df.copy()
    df = normalize_columns(df)

    required = ["Data entrada", "Descricao", "User", "Data tratamento"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.warning(f"Colunas em falta: {missing}. O dashboard assume estas colunas: {required}")

    for col in ["Data entrada", "Data tratamento"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    if "Descricao" not in df.columns:
        df["Descricao"] = "Sem descrição"

    if "User" not in df.columns:
        df["User"] = ""

    df["User"] = df["User"].fillna("").astype(str).str.strip()
    df["Descricao"] = df["Descricao"].fillna("Sem descrição").astype(str).str.strip()
    df["Data tratamento"] = pd.to_datetime(df["Data tratamento"], errors="coerce")
    df["Data entrada"] = pd.to_datetime(df["Data entrada"], errors="coerce")

    df["Estado"] = "Concluído"
    mask_pending = (df["User"].eq("") | df["User"].isna()) & (df["Data tratamento"].isna())
    df.loc[mask_pending, "Estado"] = "Pendente"

    df["Tarefa"] = df["Descricao"]
    return df


def apply_filters(df, task_filter, user_filter, date_start, date_end):
    filtered = df.copy()

    if task_filter != "Todos":
        filtered = filtered[filtered["Descricao"].str.contains(task_filter, case=False, na=False)]

    if user_filter != "Todos":
        filtered = filtered[filtered["User"].str.contains(user_filter, case=False, na=False)]

    if date_start:
        filtered = filtered[filtered["Data entrada"] >= pd.Timestamp(date_start)]
    if date_end:
        filtered = filtered[filtered["Data entrada"] <= pd.Timestamp(date_end)]

    return filtered


def kpi_cards(df):
    total = len(df)
    pendentes = int((df["Estado"] == "Pendente").sum())
    concluidos = int((df["Estado"] == "Concluído").sum())
    taxa = round((pendentes / total) * 100, 1) if total else 0

    cols = st.columns(4)
    metrics = [
        ("Total