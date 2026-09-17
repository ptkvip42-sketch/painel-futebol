import datetime
import json
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
lista_jogos = []

# --- 1. Football-Data.org ---
if fd_key:
    url_fd = f"https://api.football-data.org/v4/matches?dateFrom={hoje_str}&dateTo={hoje_str}"
    headers_fd = {"X-Auth-Token": fd_key}
    try:
        res_fd = requests.get(url_fd, headers=headers_fd)
        if res_fd.status_code == 200:
            matches_fd = res_fd.json().get("matches", [])
            for match in matches_fd:
                utc_date = match.get("utcDate")
                if utc_date:
                    dt = pd.to_datetime(utc_date)
                    dt_local = dt.tz_convert("America/Sao_Paulo") if dt.tzinfo else dt - pd.Timedelta(hours=3)
                    
                    # Nome da Liga
                    liga = match.get("competition", {}).get("name", "Outras Ligas")
                    
                    lista_jogos.append({
                        "Horário": dt_local.strftime("%H:%M"),
                        "Hora_Int": dt_local.hour,
                        "Liga": liga,
                        "Confronto": f"{match.get('homeTeam', {}).get('name')} x {match.get('awayTeam', {}).get('name')}",
                        "Status": match.get("status", "Agendado"),
                        "Fonte": "Football-Data"
                    })
    except Exception:
        pass

# --- 2. RapidAPI (Smart API) ---
if rapid_key:
    url_smart = "https://free-api-live-football-data.p.rapidapi.com/football-get-matches-by-date"
    headers_smart = {
        "x-rapidapi-key": rapid_key,
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
    }

    # Truque do Fuso: Busca hoje e amanhã para garantir os jogos da noite no Brasil
    data_seguinte = data_selecionada + datetime.timedelta(days=1)
    datas_para_buscar = [
        data_selecionada.strftime("%Y%m%d"),
        data_seguinte.strftime("%Y%m%d")
    ]

    raw_matches = []
    for data_api in datas_para_buscar:
        try:
            res_smart = requests.get(url_smart, headers=headers_smart, params={"date": data_api})
            if res_smart.status_code == 200:
                data = res_smart.json()
                resp = data.get("response", data)
                
                # Extração recursiva de ligas e torneios
                if isinstance(resp, dict) and "leagues" in resp:
                    for liga in resp["leagues"]:
                        nome_liga = liga.get("name") or liga.get("localizedName") or liga.get("leagueName") or "Outras Ligas"
                        pais = liga.get("cc", "")
                        if pais and pais.lower() != "intl":
                            nome_liga = f"{pais.upper()} - {nome_liga}"
                        for m in liga.get("matches", []):
                            if isinstance(m, dict):
                                m["_injected_league"] = nome_liga
                                raw_matches.append(m)
                elif isinstance(resp, list):
                    for item in resp:
                        if isinstance(item, dict):
                            if "matches" in item and isinstance(item["matches"], list):
                                nome_liga = item.get("name") or item.get("localizedName") or "Outras Ligas"
                                for m in item["matches"]:
                                    if isinstance(m, dict):
                                        m["_injected_league"] = nome_liga
                                        raw_matches.append(m)
                            else:
                                raw_matches.append(item)
        except Exception:
            pass

    for match in raw_matches:
        # Extração Segura de Hora/Data (UTC)
        utc_time_str = None
        status_raw = match.get("status")
        s_dict = {}
        
        if isinstance(status_raw, dict):
            s_dict = status_raw
            utc_time_str = s_dict.get("utcTime")
        elif isinstance(status_raw, str):
            try:
                parsed_json = json.loads(status_raw)
                if isinstance(parsed_json, dict):
                    s_dict = parsed_json
                    utc_time_str = s_dict.get("utcTime")
            except:
                pass
                
        if not utc_time_str:
            utc_time_str = match.get("time") or match.get("utcTime") or match.get("matchTime")

        if not utc_time_str:
            continue

        # Conversão estricta para o Horário de Brasília (BRT)
        try:
            dt = pd.to_datetime(utc_time_str)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            dt_local = dt.tz_convert("America/Sao_Paulo")
            
            # Filtro rigoroso: Apenas jogos do dia escolhido no Brasil
            if dt_local.strftime("%Y-%m-%d") != hoje_str:
                continue
                
            hora_str = dt_local.strftime("%H:%M")
            hora_int = dt_local.hour
        except Exception:
            continue

        # Status Limpo e Amigável (Placar + Estado)
        status_final = "Agendado"
        score = s_dict.get("scoreStr", "")
        reason = s_dict.get("reason", {}).get("short", "")
        
        if score and reason:
            status_final = f"{score} ({reason})"
        elif score:
            status_final = score
        elif reason:
            status_final = reason
        elif s_dict.get("finished"):
            status_final = "Encerrado"
        elif s_dict.get("started"):
            status_final = "Em Andamento"

        # Nome da Liga (Múltiplas tentativas para evitar "Outras Ligas")
        liga = match.get("_injected_league")
        if not liga or liga == "Outras Ligas":
            t = match.get("tournament") or match.get("league") or match.get("competition")
            if isinstance(t, dict):
                liga = t.get("name") or t.get("leagueName") or "Outras Ligas"
            elif isinstance(t, str):
                liga = t
            else:
                liga = match.get("leagueName") or match.get("categoryName") or "Outras Ligas"

        # Times
        time_casa = match.get("home", {}).get("name") or match.get("homeTeam", {}).get("name") or "Time Casa"
        time_fora = match.get("away", {}).get("name") or match.get("awayTeam", {}).get("name") or "Time Fora"

        lista_jogos.append({
            "Horário": hora_str,
            "Hora_Int": hora_int,
            "Liga": liga,
            "Confronto": f"{time_casa} x {time_fora}",
            "Status": status_final,
            "Fonte": "Smart API"
        })

# --- Renderização do Painel ---
if lista_jogos:
    df = pd.DataFrame(lista_jogos)
    df = df.sort_values(by=["Hora_Int", "Horário"]).drop_duplicates(subset=["Confronto"])

    st.sidebar.header("🔍 Filtros de Análise")
    ligas = ["Todas"] + sorted(list(df["Liga"].dropna().unique()))
    liga_sel = st.sidebar.selectbox("Filtrar por Liga:", ligas)

    # Janela padrão de 8h às 22h para cobrir todo o dia nobre
    intervalo_hora = st.sidebar.slider(
        "Janela de Horário (Horas):",
        min_value=0, max_value=23, value=(8, 22), format="%dh"
    )

    df_filtrado = df.copy()
    if liga_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_sel]

    df_filtrado = df_filtrado[
        (df_filtrado["Hora_Int"] >= intervalo_hora[0]) &
        (df_filtrado["Hora_Int"] <= intervalo_hora[1])
    ]

    st.subheader(f"📊 Jogos Encontrados ({data_selecionada.strftime('%d/%m/%Y')}): {len(df_filtrado)}")
    if not df_filtrado.empty:
        st.dataframe(df_filtrado[["Horário", "Liga", "Confronto", "Status", "Fonte"]], use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum jogo atende aos filtros de horário ou liga selecionados.")
else:
    st.warning("Nenhum jogo encontrado para esta data.")
