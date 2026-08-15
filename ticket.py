# ticket.py
"""
Geração do Bilhete do Dia e Montagens Inteligentes
"""

from typing import List, Dict, Optional

def gerar_bilhete(resultados: List[Dict], max_selecoes: int = 5, max_por_jogo: int = 2) -> Optional[Dict]:
    """
    Recebe a lista de análises (output do ai_engine) e gera um bilhete com as melhores seleções.
    """
    selecoes_candidatas = []
    for jogo in resultados:
        for previsao in jogo.get('previsoes', []):
            if previsao.get('pontuacao', 0) <= 0:
                continue
            selecoes_candidatas.append({
                'jogo': f"{jogo['home_team']} vs {jogo['away_team']}",
                'mercado': previsao['mercado'],
                'selecao': previsao['selecao'],
                'probabilidade': previsao['probabilidade'],
                'odd': previsao.get('odd'),
                'pontuacao': previsao['pontuacao'],
                'confianca_jogo': jogo.get('confianca_geral', 0)
            })

    if not selecoes_candidatas:
        return None

    selecoes_candidatas.sort(key=lambda x: x['pontuacao'], reverse=True)

    selecionadas = []
    contador_jogos = {}
    for sel in selecoes_candidatas:
        if len(selecionadas) >= max_selecoes:
            break
        jogo = sel['jogo']
        if contador_jogos.get(jogo, 0) < max_por_jogo:
            selecionadas.append(sel)
            contador_jogos[jogo] = contador_jogos.get(jogo, 0) + 1

    if not selecionadas:
        return None

    odd_total = 1.0
    tem_odds = True
    for sel in selecionadas:
        if sel['odd'] is None:
            tem_odds = False
            break
        odd_total *= sel['odd']

    return {
        'selecoes': selecionadas,
        'num_selecoes': len(selecionadas),
        'odd_total': round(odd_total, 2) if tem_odds else None,
        'confianca_media': round(sum(s['pontuacao'] for s in selecionadas) / len(selecionadas), 1)
    }


def gerar_montagens_inteligentes(resultados: List[Dict]) -> List[Dict]:
    """
    Gera vários bilhetes com diferentes níveis de risco:
    - Ultra Seguro: confiança >= 85, máx 2 seleções
    - Seguro: confiança >= 75, máx 3 seleções
    - Moderado: confiança >= 65, máx 4 seleções
    - Arriscado: confiança >= 55, máx 5 seleções
    - Super Arriscado: confiança >= 45, máx 6 seleções
    """
    configs = [
        {"nome": "Ultra Seguro", "min_conf": 85, "max_sel": 2, "max_por_jogo": 1},
        {"nome": "Seguro", "min_conf": 75, "max_sel": 3, "max_por_jogo": 1},
        {"nome": "Moderado", "min_conf": 65, "max_sel": 4, "max_por_jogo": 2},
        {"nome": "Arriscado", "min_conf": 55, "max_sel": 5, "max_por_jogo": 2},
        {"nome": "Super Arriscado", "min_conf": 45, "max_sel": 6, "max_por_jogo": 3},
    ]

    montagens = []
    for cfg in configs:
        filtradas = []
        for jogo in resultados:
            for previsao in jogo.get('previsoes', []):
                if previsao.get('pontuacao', 0) >= cfg["min_conf"]:
                    filtradas.append({
                        'jogo': f"{jogo['home_team']} vs {jogo['away_team']}",
                        'mercado': previsao['mercado'],
                        'selecao': previsao['selecao'],
                        'probabilidade': previsao['probabilidade'],
                        'odd': previsao.get('odd'),
                        'pontuacao': previsao['pontuacao'],
                        'confianca_jogo': jogo.get('confianca_geral', 0)
                    })

        if not filtradas:
            continue

        filtradas.sort(key=lambda x: x['pontuacao'], reverse=True)

        selecionadas = []
        contador_jogos = {}
        for sel in filtradas:
            if len(selecionadas) >= cfg["max_sel"]:
                break
            jogo = sel['jogo']
            if contador_jogos.get(jogo, 0) < cfg["max_por_jogo"]:
                selecionadas.append(sel)
                contador_jogos[jogo] = contador_jogos.get(jogo, 0) + 1

        if not selecionadas:
            continue

        odd_total = 1.0
        tem_odds = True
        for sel in selecionadas:
            if sel['odd'] is None:
                tem_odds = False
                break
            odd_total *= sel['odd']

        montagens.append({
            'nome': cfg["nome"],
            'selecoes': selecionadas,
            'num_selecoes': len(selecionadas),
            'odd_total': round(odd_total, 2) if tem_odds else None,
            'confianca_media': round(sum(s['pontuacao'] for s in selecionadas) / len(selecionadas), 1)
        })

    return montagens
