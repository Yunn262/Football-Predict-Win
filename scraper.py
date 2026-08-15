# scraper.py
"""
Módulo de recolha de dados do Sofascore (API interna não oficial).
Substitui a RapidAPI para obter jogos, estatísticas e odds.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE_URL = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def _get(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Faz GET request à API interna e devolve JSON."""
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None

def _safe_get(data: Dict, *keys, default=None):
    """Acede a chaves aninhadas com segurança."""
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data

# ============================================================
# CLASSE PRINCIPAL
# ============================================================
class SofascoreAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ---------- JOGOS DO DIA ----------
    def get_scheduled_events(self, date_str: str, sport: str = "football") -> List[Dict]:
        """
        Obtém todos os jogos agendados para uma data.
        Formato date_str: 'YYYY-MM-DD'
        Retorna lista de eventos com informações básicas.
        """
        endpoint = f"/sport/{sport}/scheduled-events/{date_str}"
        data = _get(endpoint)
        if not data:
            return []

        events = []
        for event in _safe_get(data, "events", default=[]):
            tournament = _safe_get(event, "tournament", "name", default="")
            home_team = _safe_get(event, "homeTeam", "name", default="?")
            away_team = _safe_get(event, "awayTeam", "name", default="?")
            event_id = event.get("id")
            start_timestamp = event.get("startTimestamp")
            status = _safe_get(event, "status", "description", default="")

            events.append({
                "event_id": event_id,
                "home_team": home_team,
                "away_team": away_team,
                "tournament": tournament,
                "start_time": datetime.fromtimestamp(start_timestamp).strftime("%Y-%m-%d %H:%M") if start_timestamp else "",
                "status": status,
            })
        return events

    # ---------- DETALHES DO EVENTO ----------
    def get_event_details(self, event_id: int) -> Optional[Dict]:
        """Obtém detalhes completos de um evento."""
        endpoint = f"/event/{event_id}"
        return _get(endpoint)

    # ---------- ESTATÍSTICAS ----------
    def get_event_statistics(self, event_id: int) -> Optional[Dict]:
        """Obtém estatísticas do jogo (posse, remates, cantos, cartões, etc.)."""
        endpoint = f"/event/{event_id}/statistics"
        return _get(endpoint)

    # ---------- ESCALAÇÕES ----------
    def get_event_lineups(self, event_id: int) -> Optional[Dict]:
        """Obtém escalações confirmadas."""
        endpoint = f"/event/{event_id}/lineups"
        return _get(endpoint)

    # ---------- ODDS ----------
    def get_event_odds(self, event_id: int) -> Optional[Dict]:
        """
        Obtém odds do jogo.
        Nota: o endpoint pode variar; este é o mais comum.
        """
        endpoint = f"/event/{event_id}/odds/1/all"  # provider 1 = bet365 (exemplo)
        return _get(endpoint)

    # ---------- CLASSIFICAÇÃO ----------
    def get_tournament_standings(self, tournament_id: int, season_id: int) -> Optional[Dict]:
        """Obtém a classificação de um torneio e época."""
        endpoint = f"/unique-tournament/{tournament_id}/season/{season_id}/standings/total"
        return _get(endpoint)

    # ---------- FORMA RECENTE ----------
    def get_team_recent_matches(self, team_id: int, num_matches: int = 5) -> List[Dict]:
        """
        Busca os últimos jogos de uma equipa (endpoint não oficial).
        Retorna uma lista com dicionários:
        {
            'golos_marcados': int,
            'golos_sofridos': int,
            'adversario': str,
            'data': str
        }
        """
        all_matches = []
        page = 0
        while len(all_matches) < num_matches and page < 5:
            endpoint = f"/team/{team_id}/events/last/{page}"
            data = _get(endpoint)
            if not data or "events" not in data:
                break

            for event in data["events"]:
                home_id = _safe_get(event, "homeTeam", "id")
                away_id = _safe_get(event, "awayTeam", "id")
                home_score = _safe_get(event, "homeScore", "current", default=0)
                away_score = _safe_get(event, "awayScore", "current", default=0)

                if home_id == team_id:
                    golos_marcados = home_score or 0
                    golos_sofridos = away_score or 0
                    adversario = _safe_get(event, "awayTeam", "name", default="?")
                elif away_id == team_id:
                    golos_marcados = away_score or 0
                    golos_sofridos = home_score or 0
                    adversario = _safe_get(event, "homeTeam", "name", default="?")
                else:
                    continue

                start_ts = event.get("startTimestamp")
                data_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d") if start_ts else ""

                all_matches.append({
                    "golos_marcados": int(golos_marcados),
                    "golos_sofridos": int(golos_sofridos),
                    "adversario": adversario,
                    "data": data_str
                })

                if len(all_matches) >= num_matches:
                    break

            page += 1
            time.sleep(0.5)  # pausa para evitar bloqueios

        return all_matches[:num_matches]

    # ---------- DADOS PARA O MOTOR DE IA ----------
    def prepare_match_data(self, event_id: int, include_stats: bool = True) -> Optional[Dict]:
        """
        Monta um dicionário no formato que o ai_engine.analisar_jogo espera.
        Inclui forma recente, golos, cantos, cartões e posições (se disponíveis).
        """
        details = self.get_event_details(event_id)
        if not details:
            return None

        home_id = _safe_get(details, "homeTeam", "id")
        away_id = _safe_get(details, "awayTeam", "id")
        home_name = _safe_get(details, "homeTeam", "name", default="?")
        away_name = _safe_get(details, "awayTeam", "name", default="?")
        tournament_id = _safe_get(details, "tournament", "uniqueTournament", "id")
        season_id = _safe_get(details, "season", "id")

        match_data = {
            "event_id": event_id,
            "home_team": home_name,
            "away_team": away_name,
            "data": datetime.now().strftime("%Y-%m-%d"),
            "forma_casa": [],
            "forma_fora": [],
            "golos_casa": [],
            "golos_fora": [],
            "golos_sofridos_casa": [],
            "golos_sofridos_fora": [],
            "posicao_casa": None,
            "posicao_fora": None,
            "media_cantos_casa": 4.5,
            "media_cantos_fora": 4.0,
            "media_cartoes_casa": 2.0,
            "media_cartoes_fora": 2.0,
            "odds": {}
        }

        # Forma recente
        if home_id:
            try:
                ultimos_casa = self.get_team_recent_matches(home_id, num_matches=5)
                match_data["forma_casa"] = ultimos_casa
                match_data["golos_casa"] = [j["golos_marcados"] for j in ultimos_casa]
                match_data["golos_sofridos_casa"] = [j["golos_sofridos"] for j in ultimos_casa]
            except Exception as e:
                print(f"Erro ao buscar forma da casa: {e}")

        if away_id:
            try:
                ultimos_fora = self.get_team_recent_matches(away_id, num_matches=5)
                match_data["forma_fora"] = ultimos_fora
                match_data["golos_fora"] = [j["golos_marcados"] for j in ultimos_fora]
                match_data["golos_sofridos_fora"] = [j["golos_sofridos"] for j in ultimos_fora]
            except Exception as e:
                print(f"Erro ao buscar forma da fora: {e}")

        # Estatísticas do jogo (cantos, cartões)
        if include_stats:
            stats = self.get_event_statistics(event_id)
            if stats:
                for group in _safe_get(stats, "statistics", default=[]):
                    for item in group.get("groups", []):
                        for stat in item.get("statisticsItems", []):
                            name = stat.get("name", "").lower()
                            if "corner" in name or "canto" in name:
                                home_val = stat.get("home")
                                away_val = stat.get("away")
                                if home_val is not None:
                                    match_data["media_cantos_casa"] = float(home_val)
                                if away_val is not None:
                                    match_data["media_cantos_fora"] = float(away_val)
                            elif "yellow" in name or "cartão" in name:
                                home_val = stat.get("home")
                                away_val = stat.get("away")
                                if home_val is not None:
                                    match_data["media_cartoes_casa"] = float(home_val)
                                if away_val is not None:
                                    match_data["media_cartoes_fora"] = float(away_val)

        # Classificação
        if tournament_id and season_id:
            standings = self.get_tournament_standings(tournament_id, season_id)
            if standings:
                for row in _safe_get(standings, "standings", default=[]):
                    for team in row.get("rows", []):
                        team_id = _safe_get(team, "team", "id")
                        position = team.get("position")
                        if team_id == home_id:
                            match_data["posicao_casa"] = position
                        elif team_id == away_id:
                            match_data["posicao_fora"] = position

        # Odds (mapeamento básico, pode ser adaptado)
        odds = self.get_event_odds(event_id)
        if odds:
            # O mapeamento exato depende da estrutura retornada; deixamos para ajuste futuro
            pass

        return match_data

# ============================================================
# TESTE RÁPIDO
# ============================================================
if __name__ == "__main__":
    api = SofascoreAPI()
    date_str = "2026-08-15"
    print(f"Buscando jogos de {date_str}...")
    events = api.get_scheduled_events(date_str)
    if not events:
        print("Nenhum jogo encontrado.")
    else:
        print(f"Encontrados {len(events)} jogos.")
        for ev in events[:5]:
            print(f"- {ev['home_team']} vs {ev['away_team']} ({ev['tournament']}) ID: {ev['event_id']}")
        if events:
            first_id = events[0]['event_id']
            print(f"\nPreparando dados do evento {first_id}...")
            data = api.prepare_match_data(first_id)
            if data:
                print(json.dumps(data, indent=2))
