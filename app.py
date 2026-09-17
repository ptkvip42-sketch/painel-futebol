import datetime
import pandas as pd
import requests
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Painel de Futebol", page_icon="⚽", layout="wide"
)

st.title("⚽ Painel de Análise de Jogos do Dia")

# Barra Lateral - Autenticação
st.sidebar.header("⚙️ Configurações")
api_key = st.sidebar.text_input(
    "Cole sua chave de API (football-data.org):", type="password"
)

if not api_key:
    st.info(
        "👈 Insira sua chave de API na barra lateral para carregar os jogos do dia."
    )
    st.stop()


# Função para buscar os jogos do dia na API
@st.cache_data(ttl=300)
def carregar_jogos(token):
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": token}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("matches", [])
        else:
            st.error(f"Erro na API ({response.status_code}): Chave inválida ou limite excedido.")
            return []
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return []


matches = carregar_jogos(api_key)

if matches:
    lista_jogos = []
    for match in matches:
        utc_date = match.get("utcDate")
        dt = pd.to_datetime(utc_date)

        # Converter para o fuso de Brasília (UTC-3)
        if dt.tzinfo is not None:
            dt_local = dt.tz_convert("America/Sao_Paulo")
        else:
            dt_local = dt

        hora = dt_local.strftime("%H:%M")
        hora_int = dt_local.hour

        liga = match.get("competition", {}).get("name", "Outras")
        time_casa = match.get("homeTeam", {}).get("name", "Time Casa")
        time_fora = match.get("awayTeam", {}).get("name", "Time Fora")
        status = match.get("status", "SCHEDULED")

        lista_jogos.append(
            {
                "Horário": hora,
                "Hora_Int": hora_int,
                "Liga": liga,
                "Confronto": f"{time_casa} x {time_fora}",
                "Status": status,
            }
        )

    df = pd.DataFrame(lista_jogos)

    # Barra Lateral - Filtros
    st.sidebar.header("🔍 Filtros de Análise")

    # Filtro por Liga
    ligas = ["Todas"] + sorted(list(df["Liga"].unique()))
    liga_selecionada = st.sidebar.selectbox("Filtrar por Liga:", ligas)

    # Filtro por Horário (Slider)
    intervalo_hora = st.sidebar.slider(
        "Janela de Horário (Horas):",
        min_value=0,
        max_value=23,
        value=(0, 23),
        format="%dh",
    )

    # Aplicação dos Filtros
    df_filtrado = df.copy()

    if liga_selecionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Liga"] == liga_selecionada]

    df_filtrado = df_filtrado[
        (df_filtrado["Hora_Int"] >= intervalo_hora[0])
        & (df_filtrado["Hora_Int"] <= intervalo_hora[1])
    ]

    # Exibição dos Dados
    st.subheader(f"📊 Jogos Encontrados: {len(df_filtrado)}")

    if not df_filtrado.empty:
        st.dataframe(
            df_filtrado[["Horário", "Liga", "Confronto", "Status"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "Nenhum jogo encontrado para os filtros de horário/liga selecionados."
        )
else:
    st.warning("Nenhum jogo disponível no momento para a data de hoje.")
