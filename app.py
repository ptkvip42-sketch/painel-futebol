import datetime
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Painel de Futebol Multi-API", page_icon="⚽", layout="wide"
)
st.title("⚽ Painel de Análise de Jogos")

# Sidebar - Chaves e Controles
st.sidebar.header("⚙️ Configurações das APIs")
fd_key = st.sidebar.text_input(
    "1. Chave Football-Data.org:", type="password"
)
rapid_key = st.sidebar.text_input(
    "2. Chave RapidAPI (Smart API):", type="password"
)

if not fd_key and not rapid_key:
    st.info("👈 Insira as chaves na barra lateral para carregar os jogos.")
    st.stop()

# Seletor de Data
st.sidebar.header("📅 Seleção de Data")
data_selecionada = st.sidebar.date_input("Escolha o dia:", datetime.date.today())

hoje_str = data_selecionada.strftime("%Y-%m-%d")
# Muitas APIs da Rapid exigem data sem traços, vamos testar YYYYMMDD
hoje_smart_str = data_selecionada.strftime("%Y%m%d") 
lista_jogos = []

# --- 1. Football-Data.org ---
if fd_key:
    url_fd = f"https://api.football-data.org/v4/matches?dateFrom={hoje_str}&dateTo={hoje_str}"
    headers_fd = {"X-Auth-Token": fd_key}
    try:
        res_fd = requests.get(url_fd, headers=headers_fd)
        if res_fd.status_code == 200:
            matches_fd = res_fd.json().get("matches", [])
            st.sidebar.success(f"Football-Data: {len(matches_fd)} jogos")
            for match in matches_fd:
                utc_date = match.get("utcDate")
                dt = pd.to_datetime(utc_date)
                dt_local = (
                    dt.tz_convert("America/Sao_Paulo")
                    if dt.tzinfo
                    else dt - pd.Timedelta(hours=3)
                )
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
        else:
            st.sidebar.error(f"Erro Football-Data: Status {res_fd.status_code}")
    except Exception as e:
        st.sidebar.error(f"Erro Local FD: {e}")

# --- 2. RapidAPI (Smart API) ---
debug_smart_data = None
if rapid_key:
    url_smart = "https://free-api-live-football-data.p.rapidapi.com/football-get-matches-by-date"
    headers_smart = {
        "x-rapidapi-key": rapid_key,
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
    }

    try:
        res_smart = requests.get(
            url_smart, headers=headers_smart, params={"date": hoje_smart_str}
        )

        if res_smart.status_code == 200:
            data = res_smart.json()
            debug_smart_data = data  # Salva o pacote puro para o modo de diagnóstico

            raw_matches = []
            if isinstance(data, list):
                raw_matches = data
            elif isinstance(data, dict):
                # Busca recursiva básica pelas chaves mais comuns de APIs
                if "response" in data and isinstance(data["response"], list):
                    raw_matches = data["response"]
                elif "response" in data and isinstance(data["response"], dict):
                    raw_matches = data["response"].get("matches", [])
                elif "matches" in data:
                    raw_matches = data["matches"]
                elif "data" in data:
                    raw_matches = data["data"]

            st.sidebar.success(f"Smart API: {len(raw_matches)} jogos encontrados")

            for match in raw_matches:
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
                    hora_int = int(str(hora_str).split(":")[0])
                except Exception:
                    hora_int = 12

                lista_jogos.append(
                    {
                        "Horário": str(hora_str),
                        "Hora_Int": hora_int,
                        "Liga": liga,
                        "Confronto": f"{time_casa} x {time_fora}",
                        "Status": match.get("status", "AGENDADO"),
                        "Fonte": "Smart API",
                    }
                )
        else:
            st.sidebar.error(f"Erro Smart API: Status {res_smart.status_code}")
    except Exception as e:
        st.sidebar.error(f"Erro Local Smart: {e}")

# --- Exibição ---
if lista_jogos:
    df = pd.DataFrame(lista_jogos).drop_duplicates(subset=["Confronto"])

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
        f"📊 Jogos Encontrados ({data_selecionada.strftime('%d/%m/%Y')}): {len(df_filtrado)}"
    )
    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[["Horário", "Liga", "Confronto", "Status", "Fonte"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Nenhum jogo atende aos filtros de liga/horário selecionados.")
else:
    st.warning("Nenhum jogo formatado encontrado para esta data.")
    
    # === GATILHO DE DIAGNÓSTICO ===
    if debug_smart_data:
        st.error("🚨 **Diagnóstico da Smart API** 🚨")
        st.write("A conexão está verde e funcionando (Status 200), mas a estrutura dos dados recebidos mudou. Copie o bloco abaixo para ajustarmos:")
        st.json(debug_smart_data)
