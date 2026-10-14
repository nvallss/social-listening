import os

import altair as alt
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Natura Bissé · Social Listening",
    page_icon="🔎",
    layout="wide",
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
PAGE_SIZE = 1000


@st.cache_data(ttl=300, show_spinner="Cargando menciones…")
def load_data() -> pd.DataFrame:
    """Lee toda la tabla `menciones` paginando de 1000 en 1000."""
    headers = {"apikey": SUPABASE_KEY}
    rows, offset = [], 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/menciones",
            headers=headers,
            params={"select": "*", "order": "fecha.desc", "limit": PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return pd.DataFrame(rows)


# ---------- Comprobaciones iniciales ----------
st.title("🔎 Natura Bissé · Social Listening")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Faltan las variables de entorno **SUPABASE_URL** y **SUPABASE_KEY**. "
        "Defínelas en Render → Environment."
    )
    st.stop()

try:
    df = load_data()
except requests.HTTPError as e:
    st.error(f"Error al leer Supabase ({e.response.status_code}): {e.response.text}")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudo conectar con Supabase: {e}")
    st.stop()

if df.empty:
    st.info(
        "La tabla `menciones` está vacía (o la política RLS de lectura no está creada). "
        "Ejecuta el workflow de n8n y revisa la tabla en Supabase."
    )
    st.stop()

# ---------- Limpieza ----------
df["fecha"] = pd.to_datetime(df["fecha"], utc=True, errors="coerce").dt.tz_localize(None)
df = df.dropna(subset=["fecha"])
for col in ["likes", "comentarios", "plays", "score"]:
    if col not in df.columns:
        df[col] = pd.NA
    df[col] = pd.to_numeric(df[col], errors="coerce")
df.loc[df["likes"] < 0, "likes"] = pd.NA  # Instagram devuelve -1 cuando oculta los likes
df["interacciones"] = (
    df[["likes", "comentarios", "score"]].fillna(0).sum(axis=1)
)

# ---------- Filtros ----------
with st.sidebar:
    st.header("Filtros")
    fuentes = sorted(df["fuente"].dropna().unique())
    sel_fuentes = st.multiselect("Fuente", fuentes, default=fuentes)

    fmin, fmax = df["fecha"].min().date(), df["fecha"].max().date()
    rango = st.date_input("Rango de fechas", value=(fmin, fmax), min_value=fmin, max_value=fmax)
    texto = st.text_input("Buscar en título / texto")

    if st.button("🔄 Recargar datos"):
        load_data.clear()
        st.rerun()

f = df[df["fuente"].isin(sel_fuentes)]
if isinstance(rango, tuple) and len(rango) == 2:
    f = f[(f["fecha"].dt.date >= rango[0]) & (f["fecha"].dt.date <= rango[1])]
if texto:
    mask = f["titulo"].fillna("").str.contains(texto, case=False, regex=False) | f[
        "snippet"
    ].fillna("").str.contains(texto, case=False, regex=False)
    f = f[mask]

if f.empty:
    st.warning("No hay menciones con esos filtros.")
    st.stop()

# ---------- KPIs ----------
hoy = pd.Timestamp.now().normalize()
ult7 = f[f["fecha"] >= hoy - pd.Timedelta(days=7)]
prev7 = f[(f["fecha"] >= hoy - pd.Timedelta(days=14)) & (f["fecha"] < hoy - pd.Timedelta(days=7))]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Menciones totales", f"{len(f):,}".replace(",", "."))
c2.metric("Últimos 7 días", len(ult7), delta=len(ult7) - len(prev7))
c3.metric("Fuentes activas", f["fuente"].nunique())
c4.metric("Interacciones (likes + comentarios + score)", f"{int(f['interacciones'].sum()):,}".replace(",", "."))

st.divider()

# ---------- Gráficos ----------
col_a, col_b = st.columns([2, 1])

f = f.assign(semana=f["fecha"].dt.to_period("W").dt.start_time)
por_semana = f.groupby(["semana", "fuente"]).size().reset_index(name="menciones")

with col_a:
    st.subheader("Menciones por semana")
    chart = (
        alt.Chart(por_semana)
        .mark_bar()
        .encode(
            x=alt.X("semana:T", title=None),
            y=alt.Y("menciones:Q", title="Menciones"),
            color=alt.Color("fuente:N", title="Fuente"),
            tooltip=["semana:T", "fuente:N", "menciones:Q"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

with col_b:
    st.subheader("Por fuente")
    por_fuente = f["fuente"].value_counts().reset_index()
    por_fuente.columns = ["fuente", "menciones"]
    chart2 = (
        alt.Chart(por_fuente)
        .mark_bar()
        .encode(
            x=alt.X("menciones:Q", title=None),
            y=alt.Y("fuente:N", sort="-x", title=None),
            color=alt.Color("fuente:N", legend=None),
            tooltip=["fuente", "menciones"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart2, use_container_width=True)

# ---------- Tablas ----------
config = {
    "url": st.column_config.LinkColumn("Enlace", display_text="Abrir"),
    "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
    "titulo": st.column_config.TextColumn("Título", width="large"),
    "interacciones": st.column_config.NumberColumn("Interacciones"),
}
cols = ["fecha", "fuente", "titulo", "interacciones", "likes", "comentarios", "plays", "score", "url"]

tab1, tab2 = st.tabs(["🔥 Más relevantes", "🕒 Más recientes"])
with tab1:
    top = f.sort_values("interacciones", ascending=False).head(20)
    st.dataframe(top[cols], column_config=config, hide_index=True, use_container_width=True)
with tab2:
    rec = f.sort_values("fecha", ascending=False).head(50)
    st.dataframe(rec[cols], column_config=config, hide_index=True, use_container_width=True)

st.caption(f"Datos de Supabase · caché de 5 min · {len(df):,} menciones en total".replace(",", "."))
