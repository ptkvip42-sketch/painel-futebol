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
            st.sidebar.success(f"Football-Data: {len(matches_fd)} jogos encontrados")
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
    except Exception:
        pass

# --- 2. RapidAPI (Smart API) ---
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
            
            # Helper para extrair jogos quando estão aninhados dentro de ligas
            def extrair_de_ligas(lista_ligas):
                jogos = []
                for liga in lista_ligas:
                    nome_liga = liga.get("name") or liga.get("leagueName") or "Outras Ligas"
                    for m in liga.get("matches", []):
                        if isinstance(m, dict):
                            m["_injected_league"] = nome_liga
                            jogos.append(m)
                return jogos

            resp = data.get("response", data)
            raw_matches = []
            
            # Navegação na Estrutura da Smart API
            if isinstance(resp, list):
                if len(resp) > 0 and "matches" in resp[0]:
                    raw_matches = extrair_de_ligas(resp)
                else:
                    raw_matches = resp
            elif isinstance(resp, dict):
                if "leagues" in resp:
                    raw_matches = extrair_de_ligas(resp["leagues"])
                elif "matches" in resp:
                    raw_matches = resp["matches"]
                elif "list" in resp:
                    raw_matches = resp["list"]

            st.sidebar.success(f"Smart API: {len(raw_matches)} jogos processados")

            for match in raw_matches:
                # 1. Ajuste e Filtro Rigoroso de Data/Hora (UTC para BRT)
                status_dict = match.get("status", {})
                
                if isinstance(status_dict, dict) and "utcTime" in status_dict:
                    utc_time_str = status_dict.get("utcTime")
                else:
                    utc_time_str = match.get("time") or match.get("matchTime")
                
                try:
                    dt = pd.to_datetime(utc_time_str)
                    if dt.tzinfo is None:
                        dt = dt.tz_localize("UTC")
                    dt_local = dt.tz_convert("America/Sao_Paulo")
                    
                    # Filtro de Dia: Só aceita se for EXATAMENTE a data selecionada no fuso do Brasil
                    if dt_local.strftime("%Y-%m-%d") != hoje_str:
                        continue
                        
                    hora_str = dt_local.strftime("%H:%M")
                    hora_int = dt_local.hour
                except Exception:
                    # Fallback de emergência
                    raw_time = str(match.get("time", "00:00")).split(" ")
                    hora_str = raw_time[-1] if len(raw_time) > 1 else raw_time[0]
                    try:
                        hora_int = int(hora_str.split(":")[0])
                    except:
                        hora_int = 12

                # 2. Status Limpo (Extração de Placar e Tempo)
                status_final = "AGENDADO"
                if isinstance(status_dict, dict):
                    reason = status_dict.get("reason", {}).get("short", "")
                    score = status_dict.get("scoreStr", "")
                    
                    if score and reason:
                        status_final = f"{score} ({reason})"
                    elif score:
                        status_final = score
                    elif reason:
                        status_final = reason
                    elif status_dict.get("finished"):
                        status_final = "Encerrado"
                    elif status_dict.get("started"):
                        status_final = "Em Andamento"
                elif isinstance(status_dict, str):
                    status_final = status_dict

                # 3. Extração da Liga
                liga = match.get("_injected_league")
                if not liga:
                    t_info = match.get("tournament") or match.get("league")
                    if isinstance(t_info, dict):
                        liga = t_info.get("name", "Outras Ligas")
                    elif isinstance(t_info, str):
                        liga = t_info
                    else:
                        liga = match.get("leagueName", "Outras Ligas")

                # 4. Extração dos Times
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

                lista_jogos.append(
                    {
                        "Horário": hora_str,
                        "Hora_Int": hora_int,
                        "Liga": liga,
                        "Confronto": f"{time_casa} x {time_fora}",
                        "Status": status_final,
                        "Fonte": "Smart API",
                    }
                )
        else:
            st.sidebar.error(f"Erro Smart API: Status {res_smart.status_code}")
    except Exception:
        pass

# --- Renderização do Painel ---
if lista_jogos:
    # Ordenação Cronológica e Remoção de Duplicados
    df = pd.DataFrame(lista_jogos)
    df = df.sort_values(by=["Hora_Int", "Horário"]).drop_duplicates(subset=["Confronto"])

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
        st.warning("Nenhum jogo atende aos filtros selecionados.")
else:
    st.warning("Nenhum jogo formatado encontrado para esta data nas APIs.")
