# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import requests

# API Ayarları
API_KEY = os.environ.get("API_FOOTBALL_KEY")
if not API_KEY or API_KEY == "BURAYA_API_FOOTBALL_ANAHTARINIZI_YAZIN":
    print("HATA: API_FOOTBALL_KEY ortam değişkeni tanımlı değil!")
    sys.exit(1)

LEAGUE_ID = 203  # Trendyol Süper Lig
SEASON = "2026"  # 2026-2027 sezonu için
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY,
    "Accept": "application/json"
}

# Yerel Dosya Yolları
FIXTURE_PATH = "fixtures_2026_2027.json"
STATS_PATH = "stats_2026_2027.json"

# Takım adı eşleştirme (API adından yerel ID'ye)
def get_our_team_id(api_name):
    n = api_name.lower()
    if "galatasaray" in n: return "gs"
    if "fenerbahçe" in n or "fenerbahce" in n or "fenerbah" in n: return "fb"
    if "beşiktaş" in n or "besiktas" in n: return "bjk"
    if "trabzonspor" in n: return "ts"
    if "başakşehir" in n or "basaksehir" in n or "istanbul bb" in n: return "bsk"
    if "kasımpaşa" in n or "kasimpasa" in n: return "kas"
    if "antalyaspor" in n: return "ant"
    if "kayserispor" in n: return "kys"
    if "konyaspor" in n: return "kon"
    if "göztepe" in n or "goztepe" in n: return "goz"
    if "alanyaspor" in n: return "ala"
    if "rizespor" in n or "rize" in n: return "rize"
    if "kocaelispor" in n or "kocaeli" in n: return "koc"
    if "eyüpspor" in n or "eyupspor" in n: return "eyup"
    if "samsunspor" in n or "samsun" in n: return "sam"
    if "gaziantep" in n: return "gfk"
    if "gençlerbirliği" in n or "genclerbirligi" in n: return "gcl"
    if "karagümrük" in n or "karagumruk" in n or "fatih" in n: return "fkg"
    if "çorum" in n or "corum" in n: return "cor"
    if "amed" in n: return "ame"
    if "erzurum" in n or "erzurumspor" in n: return "erz"
    return None

def format_player_name(full_name):
    if not full_name: return ""
    parts = full_name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return full_name

def convert_event_type(api_type, detail):
    if api_type == "Goal": return "GOAL"
    if api_type == "Card":
        if "Red" in str(detail): return "RED_CARD"
        return "YELLOW_CARD"
    if api_type == "subst": return "SUBSTITUTION"
    return None

def main():
    print("Süper Lig Canlı Veri Güncelleme Botu Çalışıyor...")
    
    # 1. Yerel Fikstürü Yükle
    if not os.path.exists(FIXTURE_PATH):
        print(f"HATA: {FIXTURE_PATH} dosyası bulunamadı!")
        sys.exit(1)
        
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        local_fixtures = json.load(f)
    print(f"Yerel fikstür yüklendi: {len(local_fixtures)} maç.")

    # 2. API-Football'dan Canlı ve Bugün Oynanan Maçları Çek
    # 'live' veya bugün oynanan tüm maçları çekebilmek için Süper Lig fikstürlerini sorguluyoruz
    # Günlük limit tasarrufu için doğrudan o günkü maçları sorgulamak en iyisidir
    url = f"{BASE_URL}/fixtures?league={LEAGUE_ID}&season={SEASON}"
    # live=all parametresi sadece devam eden canlı maçları getirir
    # O gün oynanacak ve bitmiş maçları da görmek için league ve season filtresini kullanıyoruz
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"API HATA: HTTP {response.status_code}")
        sys.exit(1)
        
    data = response.json()
    if "response" not in data or len(data["response"]) == 0:
        print("API'dan Süper Lig verisi alınamadı!")
        sys.exit(0)
        
    print(f"API'dan {len(data['response'])} maç verisi alındı.")
    
    changed = False
    
    # Her bir API maç verisini kontrol et
    for match in data["response"]:
        api_fixture_id = match["fixture"]["id"]
        status_short = match["fixture"]["status"]["short"]
        
        # Sadece devam eden (canlı) veya bugün tamamlanmış/başlayacak maçları işleme alalım
        # FT = Finished, HT = Half Time, 1H/2H = Halves, NS = Not Started, PST = Postponed
        # Güncelleme yükünü azaltmak için sadece canlı durumdaki (1H, 2H, HT) ve yeni bitmiş (FT) maçlara odaklanalım.
        if status_short not in ["1H", "2H", "HT", "ET", "BT", "P", "FT", "LIVE"]:
            continue
            
        home_api = match["teams"]["home"]["name"]
        away_api = match["teams"]["away"]["name"]
        home_id = get_our_team_id(home_api)
        away_id = get_our_team_id(away_api)
        
        if not home_id or not away_id:
            print(f"Atlanıyor (ID eşleşmedi): {home_api} - {away_api}")
            continue
            
        # Yerel fikstürdeki eşleşen maçı bul
        local_match = None
        for f in local_fixtures:
            if f["home"] == home_id and f["away"] == away_id:
                local_match = f
                break
                
        if not local_match:
            print(f"Atlanıyor (Yerel fikstürde bulunamadı): {home_id} - {away_id}")
            continue
            
        our_fixture_id = local_match["id"]
        print(f"\nGüncelleniyor: {home_api} vs {away_api} ({our_fixture_id}) -> API Statü: {status_short}")
        
        # Skorları al
        home_score = match["goals"]["home"]
        away_score = match["goals"]["away"]
        
        # Eğer maç başladıysa skorları güncelle
        if home_score is not None and away_score is not None:
            if local_match["homeScore"] != home_score or local_match["awayScore"] != away_score:
                local_match["homeScore"] = home_score
                local_match["awayScore"] = away_score
                changed = True
                print(f" Skor güncellendi: {home_id} {home_score} - {away_score} {away_id}")
                
        # API verisinde canlı maç veya yeni bitmiş maç ise detayları (olay/kadro/istatistik) çekelim
        # 1. OLAYLAR
        events_url = f"{BASE_URL}/fixtures/events?fixture={api_fixture_id}"
        evt_resp = requests.get(events_url, headers=HEADERS)
        events_list = []
        if evt_resp.status_code == 200:
            evt_data = evt_resp.json()
            for e in evt_data.get("response", []):
                e_type = convert_event_type(e["type"], e.get("detail"))
                if not e_type: continue
                
                is_home = (e["team"]["id"] == match["teams"]["home"]["id"])
                player = format_player_name(e["player"]["name"])
                detail = format_player_name(e["assist"]["name"]) if e.get("assist") else ""
                
                events_list.append({
                    "minute": e["time"]["elapsed"],
                    "type": e_type,
                    "isHomeTeam": is_home,
                    "playerName": player,
                    "detail": detail
                })
        
        # 2. KADROLAR
        lineups_url = f"{BASE_URL}/fixtures/lineups?fixture={api_fixture_id}"
        lin_resp = requests.get(lineups_url, headers=HEADERS)
        home_lineup = {"starting11": [], "substitutes": []}
        away_lineup = {"starting11": [], "substitutes": []}
        
        if lin_resp.status_code == 200:
            lin_data = lin_resp.json()
            for team_lin in lin_data.get("response", []):
                is_home_team = (team_lin["team"]["id"] == match["teams"]["home"]["id"])
                starters = [format_player_name(p["player"]["name"]) for p in team_lin.get("startXI", [])]
                subs = [format_player_name(p["player"]["name"]) for p in team_lin.get("substitutes", [])]
                
                if is_home_team:
                    home_lineup["starting11"] = starters
                    home_lineup["substitutes"] = subs
                else:
                    away_lineup["starting11"] = starters
                    away_lineup["substitutes"] = subs
                    
        # 3. İSTATİSTİKLER
        stats_url = f"{BASE_URL}/fixtures/statistics?fixture={api_fixture_id}"
        stat_resp = requests.get(stats_url, headers=HEADERS)
        stats_dict = {
            "possessionHome": 50, "possessionAway": 50,
            "shotsHome": 0, "shotsAway": 0,
            "shotsOnTargetHome": 0, "shotsOnTargetAway": 0,
            "foulsHome": 0, "foulsAway": 0,
            "cornersHome": 0, "cornersAway": 0,
            "offsidesHome": 0, "offsidesAway": 0
        }
        
        if stat_resp.status_code == 200:
            stat_data = stat_resp.json()
            responses = stat_data.get("response", [])
            
            def get_stat_val(stats_array, stat_type):
                stat = next((item for item in stats_array if item["type"] == stat_type), None)
                if not stat or stat["value"] is None: return 0
                val = str(stat["value"])
                if "%" in val: return int(val.replace("%", ""))
                return int(val)
                
            if len(responses) >= 2:
                stats_dict["possessionHome"] = get_stat_val(responses[0]["statistics"], "Ball Possession")
                stats_dict["possessionAway"] = get_stat_val(responses[1]["statistics"], "Ball Possession")
                stats_dict["shotsHome"] = get_stat_val(responses[0]["statistics"], "Total Shots")
                stats_dict["shotsAway"] = get_stat_val(responses[1]["statistics"], "Total Shots")
                stats_dict["shotsOnTargetHome"] = get_stat_val(responses[0]["statistics"], "Shots on Goal")
                stats_dict["shotsOnTargetAway"] = get_stat_val(responses[1]["statistics"], "Shots on Goal")
                stats_dict["foulsHome"] = get_stat_val(responses[0]["statistics"], "Fouls")
                stats_dict["foulsAway"] = get_stat_val(responses[1]["statistics"], "Fouls")
                stats_dict["cornersHome"] = get_stat_val(responses[0]["statistics"], "Corner Kicks")
                stats_dict["cornersAway"] = get_stat_val(responses[1]["statistics"], "Corner Kicks")
                stats_dict["offsidesHome"] = get_stat_val(responses[0]["statistics"], "Offsides")
                stats_dict["offsidesAway"] = get_stat_val(responses[1]["statistics"], "Offsides")
                
        # Detay JSON dosyasını oluştur
        detail_data = {
            "stats": stats_dict,
            "homeLineups": home_lineup,
            "awayLineups": away_lineup,
            "events": events_list
        }
        
        # Dosyayı kaydet
        detail_filename = f"match_detail_{our_fixture_id}.json"
        with open(detail_filename, "w", encoding="utf-8") as df:
            json.dump(detail_data, df, ensure_ascii=False, indent=4)
        print(f"   -> {detail_filename} başarıyla güncellendi.")
        
        # API limitlerini korumak için kısa bekleme süresi
        time.sleep(0.5)

    # Değişiklik varsa fikstür dosyasını kaydet
    if changed:
        with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
            json.dump(local_fixtures, f, ensure_ascii=False, indent=4)
        print("\nFikstür dosyası (canlı skorlar dahil) güncellendi ve kaydedildi.")
    else:
        print("\nSkorlarda herhangi bir değişiklik olmadı.")

    # 3. İSTATİSTİKLERİ GÜNCELLE (Gol Krallığı, Asist Krallığı, Takım İstatistikleri)
    print("\n📊 Lig istatistikleri API-Football'dan güncelleniyor...")
    stats_data = {
        "topScorers": [],
        "topAssists": [],
        "teamStats": []
    }

    # 3a. Gol Krallığı
    print("⚽ Gol krallığı listesi çekiliyor...")
    scorers_url = f"{BASE_URL}/players/topscorers?league={LEAGUE_ID}&season={SEASON}"
    scorers_resp = requests.get(scorers_url, headers=HEADERS)
    if scorers_resp.status_code == 200:
        scorers_json = scorers_resp.json()
        for idx, item in enumerate(scorers_json.get("response", [])[:15]):
            player = item["player"]
            statistics = item["statistics"][0]
            team_api = statistics["team"]["name"]
            team_id = get_our_team_id(team_api) or "gs"
            
            # Pozisyon belirleme
            pos = player.get("position", "Forvet")
            if pos == "Attacker": pos = "Forvet"
            elif pos == "Midfielder": pos = "Orta Saha"
            elif pos == "Defender": pos = "Defans"
            elif pos == "Goalkeeper": pos = "Kaleci"

            stats_data["topScorers"].append({
                "id": f"26p{idx+1}",
                "name": format_player_name(player["name"]),
                "teamId": team_id,
                "goals": statistics["goals"].get("total") or 0,
                "assists": statistics["goals"].get("assists") or 0,
                "matches": statistics["games"].get("appearences") or 0,
                "position": pos
            })

    # 3b. Asist Krallığı
    print("🅰️  Asist krallığı listesi çekiliyor...")
    assists_url = f"{BASE_URL}/players/topassists?league={LEAGUE_ID}&season={SEASON}"
    assists_resp = requests.get(assists_url, headers=HEADERS)
    if assists_resp.status_code == 200:
        assists_json = assists_resp.json()
        for idx, item in enumerate(assists_json.get("response", [])[:15]):
            player = item["player"]
            statistics = item["statistics"][0]
            team_api = statistics["team"]["name"]
            team_id = get_our_team_id(team_api) or "gs"
            
            pos = player.get("position", "Orta Saha")
            if pos == "Attacker": pos = "Forvet"
            elif pos == "Midfielder": pos = "Orta Saha"
            elif pos == "Defender": pos = "Defans"
            elif pos == "Goalkeeper": pos = "Kaleci"

            stats_data["topAssists"].append({
                "id": f"26a{idx+1}",
                "name": format_player_name(player["name"]),
                "teamId": team_id,
                "goals": statistics["goals"].get("total") or 0,
                "assists": statistics["goals"].get("assists") or 0,
                "matches": statistics["games"].get("appearences") or 0,
                "position": pos
            })

    # 3c. Takım İstatistikleri (Sarı/Kırmızı Kartlar, Penaltılar vb.)
    print("🟨 Takım istatistikleri çekiliyor...")
    # API-Football'da ligdeki tüm takımların toplu kart/penaltı istatistikleri için her takımın detayına gitmek gerekir.
    # Alternatif olarak fikstür veya diğer toplu endpoint'lerden veya lig takımlarından alabiliriz.
    # En stabil yöntem ligdeki tüm takımları alıp her biri için istek atmaktır.
    teams_url = f"{BASE_URL}/teams?league={LEAGUE_ID}&season={SEASON}"
    teams_resp = requests.get(teams_url, headers=HEADERS)
    if teams_resp.status_code == 200:
        teams_json = teams_resp.json()
        for item in teams_json.get("response", []):
            team_info = item["team"]
            team_api = team_info["name"]
            team_id = get_our_team_id(team_api)
            if not team_id: continue
            
            # API limitlerini aşmamak için her takımın detay istatistiğini çekerken 0.2 saniye bekleyelim
            time.sleep(0.2)
            team_stats_url = f"{BASE_URL}/teams/statistics?league={LEAGUE_ID}&season={SEASON}&team={team_info['id']}"
            t_stats_resp = requests.get(team_stats_url, headers=HEADERS)
            
            yellow_cards = 0
            red_cards = 0
            penalties_won = 0
            penalties_total = 0
            goals_scored = 0
            goals_conceded = 0
            
            if t_stats_resp.status_code == 200:
                ts_json = t_stats_resp.json()
                ts_res = ts_json.get("response", {})
                
                # Kartlar
                cards = ts_res.get("cards", {})
                yellow_section = cards.get("yellow", {})
                for k, v in yellow_section.items():
                    if v and v.get("total"): yellow_cards += v["total"]
                    
                red_section = cards.get("red", {})
                for k, v in red_section.items():
                    if v and v.get("total"): red_cards += v["total"]
                
                # Penaltılar
                penalty = ts_res.get("penalty", {})
                penalties_won = penalty.get("scored", {}).get("total") or 0
                penalties_total = (penalty.get("scored", {}).get("total") or 0) + (penalty.get("missed", {}).get("total") or 0)
                
                # Goller
                goals = ts_res.get("goals", {})
                goals_scored = goals.get("for", {}).get("total", {}).get("home", 0) + goals.get("for", {}).get("total", {}).get("away", 0)
                goals_conceded = goals.get("against", {}).get("total", {}).get("home", 0) + goals.get("against", {}).get("total", {}).get("away", 0)

            stats_data["teamStats"].append({
                "teamId": team_id,
                "yellowCards": yellow_cards,
                "redCards": red_cards,
                "penaltiesWon": penalties_won,
                "penaltiesTotal": penalties_total,
                "goalsScored": goals_scored,
                "goalsConceded": goals_conceded,
                "npxg": round(float(goals_scored) * 0.9, 1) # Tahmini non-penalty xG
            })

    # Stats dosyasını kaydet
    with open(STATS_PATH, "w", encoding="utf-8") as sf:
        json.dump(stats_data, sf, ensure_ascii=False, indent=4)
    print("✅ stats_2026_2027.json başarıyla güncellendi.")

if __name__ == "__main__":
    main()
