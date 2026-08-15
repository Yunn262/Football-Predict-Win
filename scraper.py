# scraper.py
"""
Módulo de recolha de dados da AllSportsAPI (API oficial de futebol).
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ============================================================
# CONFIGURAÇÃO
# ============================================================
API_KEY = "97136b858bff84845d6e6f2bad6a75679eb11e657682e951af497bd3434640a6"  # ← SUBSTITUIR PELA CHAVE REAL
BASE_URL = "https://apiv2.allsportsapi.com/football/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def _get(params: Dict) -> Optional[Dict]:
    """Faz GET request à AllSportsAPI."""
    params["APIkey"] = API_KEY
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") != 1:
            print(f"Erro da API: {data.get('message', 'sucesso=0')}")
            return None
        return data
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

class AllSportsAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_events = []

    # ---------- JOGOS DO DIA ----------
    def get_scheduled_events(self, date_str: str) -> List[Dict]:
        """Obtém jogos de uma data (formato 'YYYY-MM-DD')."""
        params = {
            "met": "Fixtures",
            "from": date_str,
            "to": date_str,
        }
        data = _get(params)
        if not data:
            self.last_events = []
            return []

        events = []
        for fixture in _safe_get(data, "result", default=[]):
            event = {
                "event_id": fixture.get("event_key"),
                "home_team": fixture.get("event_home_team", "?"),
                "away_team": fixture.get("event_away_team", "?"),
                "tournament": fixture.get("league_name", ""),
                "start_time": fixture.get("event_date", ""),
                "status": fixture.get("event_status", ""),
                "home_team_id": fixture.get("home_team_key"),
                "away_team_id": fixture.get("away_team_key"),
                "league_id": fixture.get("league_key"),
                "raw": fixture
            }
            events.append(event)

        self.last_events = events
        return events

    # ---------- DETALHES DO EVENTO ----------
    def get_event_details(self, event_id: str) -> Optional[Dict]:
        for ev in self.last_events:
            if str(ev["event_id"]) == str(event_id):
                return ev["raw"]
        return None

    # ---------- ESTATÍSTICAS (não suportado) ----------
    def get_event_statistics(self, event_id: str) -> Optional[Dict]:
        return None

    # ---------- ESCALAÇÕES (não suportado) ----------
    def get_event_lineups(self, event_id: str) -> Optional[Dict]:
        return None

    # ---------- ODDS (não implementado) ----------
    def get_event_odds(self, event_id: str) -> Optional[Dict]:
        return None

    # ---------- CLASSIFICAÇÃO ----------
    def get_tournament_standings(self, league_id: str) -> Optional[Dict]:
        params = {
            "met": "Standings",
            "leagueId": league_id,
        }
        return _get(params)

    # ---------- FORMA RECENTE ----------
    def get_team_recent_matches(self, team_id: str, num_matches: int = 5) -> List[Dict]:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        params = {
            "met": "Fixtures",
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "teamId": team_id,
        }
        data = _get(params)
        if not data:
            return []

        fixtures = _safe_get(data, "result", default=[])
        played = []
        for fx in fixtures:
            final_result = fx.get("event_final_result", "")
            if final_result:
                try:
                    home_goals, away_goals = map(int, final_result.split("-"))
                except:
                    continue
                if str(fx.get("home_team_key")) == str(team_id):
                    golos_marcados = home_goals
                    golos_sofridos = away_goals
                    adversario = fx.get("event_away_team", "?")
                else:
                    golos_marcados = away_goals
                    golos_sofridos = home_goals
                    adversario = fx.get("event_home_team", "?")
                played.append({
                    "golos_marcados": golos_marcados,
                    "golos_sofridos": golos_sofridos,
                    "adversario": adversario,
                    "data": fx.get("event_date", "")
                })
        played.sort(key=lambda x: x["data"], reverse=True)
        return played[:num_matches]

    # ---------- PREPARAR DADOS PARA O MOTOR DE IA ----------
    def prepare_match_data(self, event_id: str) -> Optional[Dict]:
        evento = None
        for ev in self.last_events:
            if str(ev["event_id"]) == str(event_id):
                evento = ev
                break

        if not evento:
            print(f"Evento {event_id} não encontrado.")
            return None

        match_data = {
            "event_id": event_id,
            "home_team": evento["home_team"],
            "away_team": evento["away_team"],
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

        home_id = evento.get("home_team_id")
        away_id = evento.get("away_team_id")
        league_id = evento.get("league_id")

        if home_id:
            try:
                ultimos_casa = self.get_team_recent_matches(home_id, 5)
                match_data["forma_casa"] = ultimos_casa
                match_data["golos_casa"] = [j["golos_marcados"] for j in ultimos_casa]
                match_data["golos_sofridos_casa"] = [j["golos_sofridos"] for j in ultimos_casa]
            except Exception as e:
                print(f"Erro forma casa: {e}")

        if away_id:
            try:
                ultimos_fora = self.get_team_recent_matches(away_id, 5)
                match_data["forma_fora"] = ultimos_fora
                match_data["golos_fora"] = [j["golos_marcados"] for j in ultimos_fora]
                match_data["golos_sofridos_fora"] = [j["golos_sofridos"] for j in ultimos_fora]
            except Exception as e:
                print(f"Erro forma fora: {e}")

        if league_id:
            try:
                standings = self.get_tournament_standings(league_id)
                if standings:
                    for row in _safe_get(standings, "result", default=[]):
                        team_key = str(row.get("team_key"))
                        position = row.get("standing_place")
                        if team_key == str(home_id):
                            match_data["posicao_casa"] = int(position) if position else None
                        elif team_key == str(away_id):
                            match_data["posicao_fora"] = int(position) if position else None
            except Exception as e:
                print(f"Erro classificação: {e}")

        return match_data

# ============================================================
# TESTE RÁPIDO
# ============================================================
if __name__ == "__main__":
    api = AllSportsAPI()
    date_str = "2026-08-15"
    print(f"Buscando jogos de {date_str}...")
    events = api.get_scheduled_events(date_str)
    if not events:
        print("Nenhum jogo encontrado.")
    else:
        print(f"Encontrados {len(events)} jogos.")
        for ev in events[:5]:
            print(f"- {ev['home_team']} vs {ev['away_team']} | ID: {ev['event_id']}")
