import datetime
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Painel de Futebol Multi-API", page_icon="⚽", layout="wide"
)

st.title("⚽ Painel de Análise de Jogos do Dia")

# Configuração de Chaves na Barra Lateral
st.sidebar.header("⚙️ Configurações das APIs")
fd_key = st.sidebar.text_input(
    "1. Chave Football-Data.org:", type="password"
)
rapid_key = st.sidebar.text_input(
    "2. Chave RapidAPI (Smart API):", type="password"
)

if not fd_key and not rapid_key:
    st.info(
        "👈 Insira ao menos uma chave de API na barra lateral para carregar os jogos de hoje."
    )
    st.stop()

# Data atual configurada para o dia de hoje
hoje_str = datetime.date.today().strftime("%Y-%m-%d")
lista_jogos = []


# 1. Busca Football-Data.org (Com filtro explícito de data)
@st.cache_data(ttl=300)
def buscar_football_data(token, data_str):
    url = f"https://api.football-data.org/v4/matches?dateFrom={data_str}&dateTo={data_str}"
    headers = {"X-Auth-Token": token}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.json().get("matches", [])
    except Exception:
        pass
    return []


# 2. Busca RapidAPI (Smart API)
@st.cache_data(ttl=300)
def buscar_smart_api(token, data_str):
    url = "https://free-api-live-football-data.p.rapidapi.com/football-get-matches-by-date"
    headers = {
        "x-rapidapi-key": token,
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
    }
    params = {"date": data_str}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json()
            return data.get("response", {}).get("matches", [])
    except Exception:
        pass
    return []


# Processar dados da Football-Data.org
if fd_key:
    matches_fd = buscar_football_data(fd_key, hoje_str)
    for match in matches_fd:
        utc_date = match.get("utcDate")
        dt = pd.to_datetime(utc_date)
        dt_local = (
            dt.tz_convert("America/Sao_Paulo")
            if dt.tzinfo
            else dt - pd.Timedelta(hours=3)
        )

        if dt_local.strftime("%Y-%m-%d") == hoje_str:
            lista_jogos.append(
                {
                    "Horário": dt_local.strftime("%H:%M"),
                    "Hora_Int": dt_local.hour,
                    "Liga": match.get("competition", {}).get("name", "Outras"),
                    "Confronto": f"{match.get('homeTeam', {}).get('name')} x {match.get('awayTeam', {}).get('name')}",
                    "Status": match.get("status", "SCHEDULED"),
                    "Fonte": "Football-Data",
                }
            )

# Processar dados da RapidAPI
if rapid_key:
    matches_rapid = buscar_smart_api(rapid_key, hoje_str)
    for match in matches_rapid:
        time_casa = (
            match.get("home", {}).get("name")
            or match.get("homeTeam", {}).get("name")
            or "Time Casa"
        )
        time_fora = (
            match.get("away", {}).get("name")
            or match.get("awayTeam", {}).get("name")
            or "Time Fora"
        )
        liga = match.get("league", {}).get("name", "Outras Ligas")
        hora_str = match.get("time", "00:00")

        try:
            hora_int = int(hora_str.split(":")[0])
        except Exception:
            hora_int = 12

        lista_jogos.append(
            {
                "Horário": hora_str,
                "Hora_Int": hora_int,
                "Liga": liga,
                "Confronto": f"{time_casa} x {time_fora}",
                "Status": match.get("status", "AGENDADO"),
                "Fonte": "RapidAPI",
            }
        )

# Renderização do Painel
if lista_jogos:
    df = pd.DataFrame(lista_jogos)
    df = df.drop_duplicates(subset=["Confronto"]).sort_values(by="Horário")

    st.sidebar.header("🔍 Filtros de Análise")
    ligas = ["Todas"] + sorted(list(df["Liga"].dropna().unique()))
    liga_sel = st.sidebar.selectbox("Filtrar por Liga:", ligas)

    intervalo_hora = st.sidebar.slider(
        "Janela de Horário (Horas):",
        min_value=0,
        max_value=23,
        value=(0, 23),
        format="%dh",
    )

    df_filtrado = df.copy()
    if liga_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_sel]

    df_filtrado = df_filtrado[
        (df_filtrado["Hora_Int"] >= intervalo_hora[0])
        & (df_filtrado["Hora_Int"] <= intervalo_hora[1])
    ]

    st.subheader(
        f"📊 Jogos de Hoje ({datetime.date.today().strftime('%d/%m/%Y')}): {len(df_filtrado)}"
    )
    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[["Horário", "Liga", "Confronto", "Status", "Fonte"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Nenhum jogo encontrado para os filtros selecionados hoje.")
else:
    st.warning("Nenhum jogo retornado pelas APIs para a data de hoje.")
