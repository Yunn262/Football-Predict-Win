# app.py
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

from scraper import SofascoreAPI
from ai_engine import analisar_jogo
from ticket import gerar_bilhete, gerar_montagens_inteligentes
import database

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="⚽ FootballAI Bot",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Atualização automática a cada 5 minutos (300000 ms)
st_autorefresh(interval=300000, key="auto_refresh")

st.title("⚽ FootballAI Bot")
st.caption("Dados reais do Sofascore | Análise com IA simplificada | Bilhetes inteligentes")

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    data_selecionada = st.date_input(
        "Data dos jogos",
        value=datetime.now().date(),
        min_value=datetime.now().date() - timedelta(days=7),
        max_value=datetime.now().date() + timedelta(days=7)
    )
    st.divider()
    st.info("🔄 Atualização automática a cada 5 min")
    st.info("ℹ️ Dados obtidos via API interna do Sofascore (uso pessoal)")

# ============================================================
# FUNÇÃO DE ANÁLISE COM CACHE
# ============================================================
@st.cache_data(ttl=300)
def analisar_jogos_do_dia(date_str: str):
    """
    Busca jogos do dia e analisa cada um com o motor de IA.
    Retorna lista de dicionários com os resultados.
    """
    api = SofascoreAPI()
    jogos = api.get_scheduled_events(date_str)
    if not jogos:
        return []

    resultados = []
    for jogo in jogos:
        dados = api.prepare_match_data(jogo['event_id'])
        if not dados:
            continue
        try:
            analise = analisar_jogo(dados)
        except Exception as e:
            print(f"Erro ao analisar {jogo['home_team']} vs {jogo['away_team']}: {e}")
            continue

        analise['tournament'] = jogo.get('tournament', '')
        analise['start_time'] = jogo.get('start_time', '')
        analise['status'] = jogo.get('status', '')
        resultados.append(analise)

    # Ordenar por confiança (maior primeiro)
    resultados.sort(key=lambda x: x['confianca_geral'], reverse=True)
    return resultados

# ============================================================
# OBTER DADOS DO DIA
# ============================================================
date_str = data_selecionada.strftime("%Y-%m-%d")
resultados = analisar_jogos_do_dia(date_str)

if not resultados:
    st.warning("Nenhum jogo encontrado ou erro na recolha de dados.")
    st.stop()

# ============================================================
# GUARDAR PREVISÕES NA BASE DE DADOS
# ============================================================
for r in resultados:
    for p in r['previsoes']:
        database.salvar_previsao(
            data_jogo=date_str,
            jogo=f"{r['home_team']} vs {r['away_team']}",
            mercado=p['mercado'],
            selecao=p['selecao'],
            probabilidade=p['probabilidade'],
            odd=p.get('odd'),
            pontuacao=p['pontuacao'],
            confianca_jogo=r['confianca_geral']
        )

# ============================================================
# GERAR BILHETES
# ============================================================
bilhete_normal = gerar_bilhete(resultados)
if bilhete_normal:
    database.salvar_bilhete(
        data_bilhete=date_str,
        selecoes=bilhete_normal['selecoes'],
        odd_total=bilhete_normal.get('odd_total'),
        confianca_media=bilhete_normal['confianca_media'],
        tipo="normal"
    )

montagens = gerar_montagens_inteligentes(resultados)
for m in montagens:
    database.salvar_bilhete(
        data_bilhete=date_str,
        selecoes=m['selecoes'],
        odd_total=m.get('odd_total'),
        confianca_media=m['confianca_media'],
        tipo=m['nome']
    )

# ============================================================
# INTERFACE COM ABAS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Análise",
    "🎟️ Bilhete do Dia",
    "💎 Montagens Inteligentes",
    "📜 Histórico"
])

# ---------- ABA 1: ANÁLISE ----------
with tab1:
    st.subheader(f"Jogos de {date_str} (total: {len(resultados)})")

    # Tabela resumo
    rows = []
    for r in resultados:
        top3 = r['previsoes'][:3]
        texto_top = " | ".join([
            f"{p['mercado']}: {p['selecao']} ({p['probabilidade']:.0%})"
            for p in top3
        ])
        rows.append({
            "Jogo": f"{r['home_team']} vs {r['away_team']}",
            "Torneio": r.get('tournament', ''),
            "Hora": r.get('start_time', ''),
            "xG Casa": r['xg_casa'],
            "xG Fora": r['xg_fora'],
            "Confiança": f"{r['confianca_geral']}%",
            "Top 3 Palpites": texto_top
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # Detalhes expandidos por jogo
    for r in resultados:
        with st.expander(f"⚽ {r['home_team']} vs {r['away_team']} (Confiança: {r['confianca_geral']}%)"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Torneio:** {r.get('tournament', 'N/A')}")
                st.markdown(f"**Hora:** {r.get('start_time', 'N/A')}")
                st.markdown(f"**xG Casa:** {r['xg_casa']}")
                st.markdown(f"**xG Fora:** {r['xg_fora']}")
            with col2:
                st.markdown("**Palpites:**")
                for p in r['previsoes']:
                    odd_text = f" (Odd: {p['odd']})" if p.get('odd') else ""
                    st.markdown(
                        f"- {p['mercado']}: **{p['selecao']}** "
                        f"({p['probabilidade']:.0%}){odd_text} | Pontuação: {p['pontuacao']:.1f}"
                    )

# ---------- ABA 2: BILHETE DO DIA ----------
with tab2:
    st.subheader("🎟️ Bilhete do Dia (Normal)")
    if bilhete_normal:
        col1, col2 = st.columns([3, 1])
        with col1:
            for sel in bilhete_normal['selecoes']:
                odd_text = f" (Odd: {sel['odd']})" if sel.get('odd') else ""
                st.markdown(
                    f"**{sel['jogo']}** → {sel['mercado']}: {sel['selecao']} "
                    f"({sel['probabilidade']:.0%}){odd_text}"
                )
        with col2:
            st.metric("Confiança Média", f"{bilhete_normal['confianca_media']}%")
            if bilhete_normal.get('odd_total'):
                st.metric("Odd Total", f"{bilhete_normal['odd_total']:.2f}")
            else:
                st.info("Sem odds disponíveis")
    else:
        st.info("Não foi possível gerar um bilhete com os dados atuais.")

# ---------- ABA 3: MONTAGENS INTELIGENTES ----------
with tab3:
    st.subheader("💎 Montagens Inteligentes")
    if montagens:
        for m in montagens:
            with st.expander(f"{m['nome']} ({m['num_selecoes']} seleções, conf. média {m['confianca_media']}%)"):
                for sel in m['selecoes']:
                    odd_text = f" (Odd: {sel['odd']})" if sel.get('odd') else ""
                    st.markdown(
                        f"- {sel['jogo']} | {sel['mercado']}: {sel['selecao']} "
                        f"({sel['probabilidade']:.0%}){odd_text}"
                    )
                if m.get('odd_total'):
                    st.markdown(f"**Odd Total:** {m['odd_total']:.2f}")
                else:
                    st.markdown("**Odd Total:** indisponível")
    else:
        st.info("Sem montagens disponíveis com os critérios atuais.")

# ---------- ABA 4: HISTÓRICO ----------
with tab4:
    st.subheader("📜 Histórico de Previsões e Bilhetes")
    col_prev, col_bil = st.columns(2)

    with col_prev:
        st.markdown("### Previsões Recentes")
        previsoes = database.listar_previsoes(limit=50)
        if previsoes:
            df_prev = pd.DataFrame(previsoes)
            df_prev['criado_em'] = pd.to_datetime(df_prev['criado_em'])
            st.dataframe(df_prev, use_container_width=True, hide_index=True)
        else:
            st.info("Sem previsões guardadas.")

    with col_bil:
        st.markdown("### Bilhetes Gerados")
        bilhetes = database.listar_bilhetes(limit=20)
        if bilhetes:
            for b in bilhetes:
                with st.expander(f"{b['tipo']} - {b['data_bilhete']} (Conf: {b['confianca_media']}%)"):
                    st.markdown(f"**Status:** {b['status']}")
                    selecoes = json.loads(b['selecoes']) if isinstance(b['selecoes'], str) else b['selecoes']
                    for sel in selecoes:
                        st.markdown(f"- {sel['jogo']} | {sel['mercado']}: {sel['selecao']}")
                    if b['odd_total']:
                        st.markdown(f"**Odd Total:** {b['odd_total']:.2f}")

                    # Atualizar status do bilhete
                    opcoes_status = ["pendente", "ganho", "perdido"]
                    indice_atual = opcoes_status.index(b['status']) if b['status'] in opcoes_status else 0
                    novo_status = st.selectbox(
                        "Atualizar status",
                        options=opcoes_status,
                        index=indice_atual,
                        key=f"status_{b['id']}"
                    )
                    if novo_status != b['status'] and st.button("Salvar", key=f"save_{b['id']}"):
                        database.atualizar_status_bilhete(b['id'], novo_status)
                        st.success("Status atualizado!")
                        st.rerun()
        else:
            st.info("Sem bilhetes guardados.")
