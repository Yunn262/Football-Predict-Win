# ai_engine.py
"""
FootballAI - Motor de Inteligência Artificial
Responsável por analisar dados de jogos e gerar palpites com pontuação.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np

# ============================================================
# FUNÇÕES AUXILIARES DE ANÁLISE
# ============================================================

def calcular_forma(partidas: List[Dict], num_jogos: int = 5) -> float:
    """
    Calcula a forma recente de uma equipa com base nos últimos jogos.
    Cada vitória = 3 pontos, empate = 1, derrota = 0.
    Retorna a média de pontos por jogo (0 a 3).
    """
    if not partidas:
        return 1.5

    ultimas = partidas[-num_jogos:] if len(partidas) >= num_jogos else partidas
    pontos = 0
    for jogo in ultimas:
        golos_marcados = jogo.get('golos_marcados', 0)
        golos_sofridos = jogo.get('golos_sofridos', 0)
        if golos_marcados > golos_sofridos:
            pontos += 3
        elif golos_marcados == golos_sofridos:
            pontos += 1
    return pontos / len(ultimas)


def media_golos(marcados: List[int], sofridos: List[int]) -> tuple:
    """Retorna (média marcados, média sofridos)."""
    if not marcados:
        media_marc = 1.2
    else:
        media_marc = sum(marcados) / len(marcados)

    if not sofridos:
        media_sofr = 1.2
    else:
        media_sofr = sum(sofridos) / len(sofridos)

    return media_marc, media_sofr


def calcular_expectativa_golos(media_marcados_casa: float,
                               media_sofridos_fora: float,
                               media_marcados_fora: float,
                               media_sofridos_casa: float) -> tuple:
    """Estima golos esperados (xG simples) para cada equipa."""
    xg_casa = (media_marcados_casa + media_sofridos_fora) / 2
    xg_fora = (media_marcados_fora + media_sofridos_casa) / 2
    return xg_casa, xg_fora


def prob_poisson(golos_esperados: float, max_golos: int = 6) -> List[float]:
    """Calcula a distribuição de Poisson para os golos esperados."""
    return [np.exp(-golos_esperados) * (golos_esperados ** k) / np.math.factorial(k)
            for k in range(max_golos + 1)]


# ============================================================
# FUNÇÕES DE MERCADO
# ============================================================

def avaliar_resultado_final(xg_casa: float, xg_fora: float) -> Dict:
    """Probabilidades de resultado final (casa, empate, fora) usando Poisson."""
    prob_casa = 0
    prob_empate = 0
    prob_fora = 0

    for i in range(7):
        for j in range(7):
            p = prob_poisson(xg_casa)[i] * prob_poisson(xg_fora)[j]
            if i > j:
                prob_casa += p
            elif i == j:
                prob_empate += p
            else:
                prob_fora += p

    return {
        'casa': round(prob_casa, 3),
        'empate': round(prob_empate, 3),
        'fora': round(prob_fora, 3)
    }


def avaliar_over_under(xg_casa: float, xg_fora: float, linha: float = 2.5) -> float:
    """Probabilidade de over X golos."""
    total_xg = xg_casa + xg_fora
    prob_over = 0
    for i in range(7):
        for j in range(7):
            if i + j > linha:
                prob_over += prob_poisson(xg_casa)[i] * prob_poisson(xg_fora)[j]
    return round(prob_over, 3)


def avaliar_btts(xg_casa: float, xg_fora: float) -> float:
    """Probabilidade de ambas marcarem (BTTS)."""
    prob_casa_marca = 1 - prob_poisson(xg_casa)[0]
    prob_fora_marca = 1 - prob_poisson(xg_fora)[0]
    return round(prob_casa_marca * prob_fora_marca, 3)


def avaliar_cantos(media_cantos_casa: float,
                   media_cantos_fora: float,
                   linha: float = 8.5) -> float:
    """Probabilidade de over em cantos (distribuição normal aproximada)."""
    total_esperado = media_cantos_casa + media_cantos_fora
    desvio_padrao = 3.0
    if total_esperado <= 0:
        return 0.0
    z = (linha - total_esperado) / desvio_padrao
    prob_over = 1 - 0.5 * (1 + np.math.erf(z / np.sqrt(2)))
    return round(prob_over, 3)


def avaliar_cartoes(media_cartoes_casa: float,
                    media_cartoes_fora: float,
                    linha: float = 3.5) -> float:
    """Probabilidade de over em cartões (distribuição normal)."""
    total_esperado = media_cartoes_casa + media_cartoes_fora
    desvio_padrao = 1.8
    if total_esperado <= 0:
        return 0.0
    z = (linha - total_esperado) / desvio_padrao
    prob_over = 1 - 0.5 * (1 + np.math.erf(z / np.sqrt(2)))
    return round(prob_over, 3)


# ============================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ============================================================

def analisar_jogo(dados_jogo: Dict) -> Dict:
    """
    Recebe um dicionário com dados do jogo e retorna palpites com pontuação.
    Estrutura esperada de dados_jogo:
    {
        'event_id': int,
        'home_team': str,
        'away_team': str,
        'data': 'YYYY-MM-DD',
        'forma_casa': [...],
        'forma_fora': [...],
        'golos_casa': [...],
        'golos_fora': [...],
        'golos_sofridos_casa': [...],
        'golos_sofridos_fora': [...],
        'posicao_casa': int,
        'posicao_fora': int,
        'media_cantos_casa': float,
        'media_cantos_fora': float,
        'media_cartoes_casa': float,
        'media_cartoes_fora': float,
        'odds': { ... } (opcional)
    }
    Retorna:
    {
        'event_id': int,
        'home_team': str,
        'away_team': str,
        'previsoes': [ ... ],
        'xg_casa': float,
        'xg_fora': float,
        'confianca_geral': int
    }
    """
    event_id = dados_jogo.get('event_id')
    home = dados_jogo.get('home_team', '?')
    away = dados_jogo.get('away_team', '?')

    # 1. Calcular forma
    forma_casa = calcular_forma(dados_jogo.get('forma_casa', []))
    forma_fora = calcular_forma(dados_jogo.get('forma_fora', []))

    # 2. Médias de golos
    media_golos_casa, media_sofridos_casa = media_golos(
        dados_jogo.get('golos_casa', []),
        dados_jogo.get('golos_sofridos_casa', [])
    )
    media_golos_fora, media_sofridos_fora = media_golos(
        dados_jogo.get('golos_fora', []),
        dados_jogo.get('golos_sofridos_fora', [])
    )

    # 3. Ajuste pela posição na tabela
    pos_casa = dados_jogo.get('posicao_casa', 10)
    pos_fora = dados_jogo.get('posicao_fora', 10)
    ajuste_posicao = (pos_fora - pos_casa) * 0.05
    xg_casa, xg_fora = calcular_expectativa_golos(
        media_golos_casa + max(0, ajuste_posicao),
        media_sofridos_fora,
        media_golos_fora + max(0, -ajuste_posicao),
        media_sofridos_casa
    )

    # 4. Ajuste pela forma
    xg_casa *= (0.9 + forma_casa * 0.2)
    xg_fora *= (0.9 + forma_fora * 0.2)

    # Garantir valores razoáveis
    xg_casa = max(0.3, min(4.5, xg_casa))
    xg_fora = max(0.3, min(4.5, xg_fora))

    # 5. Probabilidades dos mercados
    probs_resultado = avaliar_resultado_final(xg_casa, xg_fora)
    prob_over_15 = avaliar_over_under(xg_casa, xg_fora, linha=1.5)
    prob_over_25 = avaliar_over_under(xg_casa, xg_fora, linha=2.5)
    prob_btts = avaliar_btts(xg_casa, xg_fora)

    media_cantos_casa = dados_jogo.get('media_cantos_casa', 4.5)
    media_cantos_fora = dados_jogo.get('media_cantos_fora', 4.0)
    prob_over_7_cantos = avaliar_cantos(media_cantos_casa, media_cantos_fora, linha=7.0)
    prob_over_85_cantos = avaliar_cantos(media_cantos_casa, media_cantos_fora, linha=8.5)

    media_cartoes_casa = dados_jogo.get('media_cartoes_casa', 2.0)
    media_cartoes_fora = dados_jogo.get('media_cartoes_fora', 2.0)
    prob_over_2_cartoes = avaliar_cartoes(media_cartoes_casa, media_cartoes_fora, linha=2.0)
    prob_over_3_cartoes = avaliar_cartoes(media_cartoes_casa, media_cartoes_fora, linha=3.0)

    # 6. Odds (se disponíveis)
    odds = dados_jogo.get('odds', {})

    # 7. Construir lista de previsões com pontuação
    previsoes = []

    def adicionar_previsao(mercado, selecao, probabilidade, odd=None):
        if odd and odd > 1.0:
            valor = (probabilidade * odd - 1) * 100
            pontuacao = min(95, max(20, probabilidade * 80 + valor * 20))
        else:
            pontuacao = probabilidade * 80
        previsoes.append({
            'mercado': mercado,
            'selecao': selecao,
            'probabilidade': round(probabilidade, 3),
            'odd': odd,
            'pontuacao': round(pontuacao, 1)
        })

    # Resultado Final
    melhor_resultado = max(probs_resultado, key=probs_resultado.get)
    odd_resultado = None
    if '1x2' in odds:
        odd_resultado = odds['1x2'].get(melhor_resultado)
    adicionar_previsao('Resultado Final', melhor_resultado.capitalize(), probs_resultado[melhor_resultado], odd_resultado)

    # Dupla Hipótese
    prob_casa_empate = probs_resultado['casa'] + probs_resultado['empate']
    prob_fora_empate = probs_resultado['fora'] + probs_resultado['empate']
    if prob_casa_empate >= prob_fora_empate:
        adicionar_previsao('Dupla Hipótese', 'Casa ou Empate', prob_casa_empate, None)
    else:
        adicionar_previsao('Dupla Hipótese', 'Fora ou Empate', prob_fora_empate, None)

    # Over/Under
    adicionar_previsao('Over 1.5', 'Sim', prob_over_15, odds.get('over_1_5'))
    adicionar_previsao('Over 2.5', 'Sim', prob_over_25, odds.get('over_2_5'))
    adicionar_previsao('BTTS', 'Sim', prob_btts, odds.get('btts'))

    # Cantos
    adicionar_previsao('Over 7 Cantos', 'Sim', prob_over_7_cantos, odds.get('over_7_cantos'))
    adicionar_previsao('Over 8.5 Cantos', 'Sim', prob_over_85_cantos, odds.get('over_8_5_cantos'))

    # Cartões
    adicionar_previsao('Over 2 Cartões', 'Sim', prob_over_2_cartoes, odds.get('over_2_cartoes'))
    adicionar_previsao('Over 3 Cartões', 'Sim', prob_over_3_cartoes, odds.get('over_3_cartoes'))

    # Ordenar por pontuação
    previsoes.sort(key=lambda x: x['pontuacao'], reverse=True)

    # Confiança geral (média das 3 melhores pontuações)
    confianca = int(np.mean([p['pontuacao'] for p in previsoes[:3]]))

    return {
        'event_id': event_id,
        'home_team': home,
        'away_team': away,
        'xg_casa': round(xg_casa, 2),
        'xg_fora': round(xg_fora, 2),
        'previsoes': previsoes,
        'confianca_geral': confianca
    }
