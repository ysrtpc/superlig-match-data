# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import time
import html
import datetime
import subprocess
import urllib.request
import urllib.error

MACKOLIK_FIXTURES_URL = "https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-s%C3%BCper-lig/fikstur/482ofyysbdbeoxauk19yg7tdt"
MACKOLIK_STATS_2026_URL = "https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-trendyol-s%C3%BCper-lig/2026-2027/istatistik/482ofyysbdbeoxauk19yg7tdt"
MACKOLIK_STATS_2025_URL = "https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-trendyol-s%C3%BCper-lig/2025-2026/istatistik/482ofyysbdbeoxauk19yg7tdt"

FIXTURES_FILE = "fixtures_2026_2027.json"
STATS_2026_FILE = "stats_2026_2027.json"
STATS_2025_FILE = "stats_2025_2026.json"

TEAM_MAPPING = [
    (r"galata", "gs"),
    (r"fener", "fb"),
    (r"be.?ikta|besikt", "bjk"),
    (r"trabzon", "ts"),
    (r"ba.?ak.?eh|basak", "bsk"),
    (r"kas.?mpa.?a|kasim", "kas"),
    (r"g.?ztep|goztep", "goz"),
    (r"gaziantep", "gfk"),
    (r"rize", "rize"),
    (r"amed", "ame"),
    (r"konya", "kon"),
    (r"samsun", "sam"),
    (r"gen.?lerbirli|gencler", "gcl"),
    (r".?orum|corum", "cor"),
    (r"erzurum", "erz"),
    (r"alanya", "ala"),
    (r"ey.?p|eyup", "eyup"),
    (r"kocaeli", "koc"),
    (r"antalya", "ant"),
    (r"bodrum", "bod"),
    (r"hatay", "hat"),
    (r"sivas", "siv"),
    (r"adana", "ads"),
    (r"kayseri", "kys"),
    (r"karag.?mr.?k|karagumruk", "fkg"),
]

MONTHS_TR = {
    1: "Oca", 2: "Şub", 3: "Mar", 4: "Nis", 5: "May", 6: "Haz",
    7: "Tem", 8: "Ağu", 9: "Eyl", 10: "Eki", 11: "Kas", 12: "Ara"
}

def get_team_id(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    for pattern, tid in TEAM_MAPPING:
        if re.search(pattern, n):
            return tid
    return ""

def fetch_url(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            content = html.unescape(content)
            try:
                content = content.encode('utf-8').decode('unicode_escape')
            except Exception:
                pass
            return content
    except Exception as e:
        print(f"[HATA] URL cekilemedi ({url}): {e}")
        return ""

def load_fixtures() -> list:
    if os.path.exists(FIXTURES_FILE):
        try:
            with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[HATA] Fikstur dosyasi okunamadi: {e}")
    return []

def git_commit_and_push(commit_msg: str):
    if not os.environ.get("GITHUB_ACTIONS"):
        print(f"[YEREL] Git push atlandi: {commit_msg}")
        return
    try:
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", "-A"], check=False)
        
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not res.stdout.strip():
            print("Git: Degisiklik yok.")
            return

        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        for attempt in range(3):
            push_res = subprocess.run(["git", "push"], capture_output=True, text=True)
            if push_res.returncode == 0:
                print(f"[OK] GitHub'a basariyla pushlandi: {commit_msg}")
                return
            else:
                print(f"[UYARI] Push denemesi {attempt+1} basarisiz, pull rebase yapiliyor...")
                subprocess.run(["git", "pull", "--rebase"], check=False)
                time.sleep(2)
    except Exception as e:
        print(f"[HATA] Git commit/push hatasi: {e}")

def save_json_file(filename: str, data, commit_msg: str = "") -> bool:
    paths = [
        filename,
        os.path.join("superlig-app", "app", "src", "main", "assets", filename)
    ]
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
            with open(p, "w", encoding="utf-8") as f:
                f.write(json_str)
        except Exception as e:
            print(f"[UYARI] Dosya kaydedilemedi ({p}): {e}")

    if commit_msg and os.environ.get("GITHUB_ACTIONS"):
        git_commit_and_push(commit_msg)
    return True

def sync_stats_for_season(season_name: str, target_url: str, target_filename: str, fixture_filename: str) -> bool:
    print(f"\n>>> {season_name} ISTATISTIKLERI CEKILIYOR...")
    clean_html = fetch_url(target_url)
    if not clean_html or len(clean_html) < 10000:
        print(f"[HATA] Mackolik istatistik sayfasi alinamadi: {target_url}")
        return False

    # 1. Map team GUIDs
    team_matches = re.findall(r'\{"id":"([0-9a-f\-]+)","uuid":"([^"]+)","n":"([^"]+)"', clean_html)
    guid_to_team_id = {}
    for guid, uuid, name in team_matches:
        tid = get_team_id(name)
        if tid:
            guid_to_team_id[guid] = tid

    print(f"Bulunan Takim Sayisi: {len(guid_to_team_id)}")

    # 2. Count played matches from fixtures
    team_played_counts = {}
    if os.path.exists(fixture_filename):
        try:
            with open(fixture_filename, "r", encoding="utf-8") as f:
                fix_list = json.load(f)
                for m in fix_list:
                    if m.get("status") in ["PLAYED", "LIVE", "HALF_TIME"]:
                        h = m.get("home")
                        a = m.get("away")
                        if h: team_played_counts[h] = team_played_counts.get(h, 0) + 1
                        if a: team_played_counts[a] = team_played_counts.get(a, 0) + 1
        except Exception:
            pass

    # 3. Helpers to get player stats
    def get_player_values_dict(key):
        d = {}
        m = re.search(r'\{"key":"' + key + r'","players":\[(.*?)\]\}', clean_html)
        if m:
            p_matches = re.findall(r'\{"uuid":"([^"]+)","i":(\d+),"team_id":"([^"]+)","n":"([^"]+)","v":"([^"]+)"\}', m.group(1))
            for uuid, pid, tguid, name, val in p_matches:
                v = int(re.sub(r'[^\d]', '', val) or 0)
                d[name] = v
        return d

    all_goals_dict = get_player_values_dict("ps_g")
    all_assists_dict = get_player_values_dict("ps_a")

    def parse_player_stats(key, pos_default):
        results = []
        m = re.search(r'\{"key":"' + key + r'","players":\[(.*?)\]\}', clean_html)
        if m:
            p_matches = re.findall(r'\{"uuid":"([^"]+)","i":(\d+),"team_id":"([^"]+)","n":"([^"]+)","v":"([^"]+)"\}', m.group(1))
            for uuid, pid, tguid, name, val in p_matches:
                tid = guid_to_team_id.get(tguid, "unknown")
                photo = f"https://secure.cache.images.core.optasports.com/soccer/players/150x150/uuid_{uuid}.png"
                if "Shomurodov" in name:
                    photo = "https://raw.githubusercontent.com/ysrtpc/superlig-match-data/main/players/shomurodov.png"
                elif "Traore" in name:
                    photo = "https://raw.githubusercontent.com/ysrtpc/superlig-match-data/main/players/traore.png"

                g = all_goals_dict.get(name, 0)
                a = all_assists_dict.get(name, 0)
                default_matches = 34 if "2025" in target_filename else 4
                matches = team_played_counts.get(tid, default_matches)

                results.append({
                    "photoUrl": photo,
                    "id": pid,
                    "uuid": uuid,
                    "teamId": tid,
                    "matches": matches,
                    "name": name,
                    "goals": g,
                    "assists": a,
                    "position": pos_default
                })
        return results

    top_scorers = parse_player_stats("ps_g", "Attacker")
    top_assists = parse_player_stats("ps_a", "Midfielder")

    print(f"=== {season_name} GOL KRALLIGI TOP 5 ===")
    for p in top_scorers[:5]:
        print(f"   {p['name']} [{p['teamId']}] - {p['goals']} Gol, {p['assists']} Asist")

    # 4. Extract Team Stats
    def parse_team_stats_cat(key):
        d = {}
        m = re.search(r'\{"key":"' + key + r'","teams":\[(.*?)\]\}', clean_html)
        if m:
            t_matches = re.findall(r'\{"id":"([^"]+)".*?"v":"([^"]+)"\}', m.group(1))
            for guid, val in t_matches:
                tid = guid_to_team_id.get(guid, "")
                if tid:
                    try:
                        d[tid] = float(val.replace(',', '.'))
                    except ValueError:
                        d[tid] = 0.0
        return d

    def parse_team_penalties():
        d = {}
        m = re.search(r'\{"key":"ts_pgp","teams":\[(.*?)\]\}', clean_html)
        if m:
            t_matches = re.findall(r'\{"id":"([^"]+)".*?"v":"([^"]+)"\}', m.group(1))
            for guid, val in t_matches:
                tid = guid_to_team_id.get(guid, "")
                if tid:
                    parts = val.split('/')
                    scored = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
                    total = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else scored
                    d[tid] = {"scored": scored, "total": total}

        m_pw = re.search(r'\{"key":"ts_pw","teams":\[(.*?)\]\}', clean_html)
        if m_pw:
            t_matches_pw = re.findall(r'\{"id":"([^"]+)".*?"v":"([^"]+)"\}', m_pw.group(1))
            for guid, val in t_matches_pw:
                tid = guid_to_team_id.get(guid, "")
                if tid:
                    pw_val = int(re.sub(r'[^\d]', '', val) or 0)
                    if tid not in d:
                        d[tid] = {"scored": pw_val, "total": pw_val}
                    elif d[tid]["total"] < pw_val:
                        d[tid]["total"] = pw_val
        return d

    ts_goals_scored   = parse_team_stats_cat("ts_g")
    ts_goals_conceded = parse_team_stats_cat("ts_gc")
    ts_yellow_cards   = parse_team_stats_cat("ts_yc")
    ts_red_cards      = parse_team_stats_cat("ts_rc")
    ts_npxg           = parse_team_stats_cat("ts_xgwp")
    ts_xg             = parse_team_stats_cat("ts_xg")
    ts_possession     = parse_team_stats_cat("ts_pppm")
    ts_shots_target   = parse_team_stats_cat("ts_sotpm")
    ts_total_shots    = parse_team_stats_cat("ts_spm")
    ts_clean_sheets   = parse_team_stats_cat("ts_cs")
    ts_woodwork       = parse_team_stats_cat("ts_hw")
    ts_fk_goals       = parse_team_stats_cat("ts_fkg")
    ts_hg_goals       = parse_team_stats_cat("ts_hg")
    ts_gfob_goals     = parse_team_stats_cat("ts_gfob")
    ts_corners        = parse_team_stats_cat("ts_crpm")
    ts_crosses_target = parse_team_stats_cat("ts_scpm")
    ts_passes_target  = parse_team_stats_cat("ts_sppm")
    ts_penalties      = parse_team_penalties()

    all_teams = list(set(guid_to_team_id.values()))
    if not all_teams:
        all_teams = ["gs", "fb", "bjk", "ts", "bsk", "kas", "goz", "gfk", "rize", "ame", "kon", "sam", "gcl", "cor", "erz", "ala", "eyup", "koc", "ant", "kys", "fkg"]

    team_stats_list = []
    for tid in all_teams:
        gs = int(ts_goals_scored.get(tid, 0))
        gc = int(ts_goals_conceded.get(tid, 0))
        yc = int(ts_yellow_cards.get(tid, 0))
        rc = int(ts_red_cards.get(tid, 0))
        npxg_val = ts_npxg.get(tid, ts_xg.get(tid, round(gs * 0.8, 1)))
        poss = ts_possession.get(tid, 50.0)
        sont = ts_shots_target.get(tid, 4.0)
        tot_shots = ts_total_shots.get(tid, 12.0)
        cs = int(ts_clean_sheets.get(tid, 0))
        hw = int(ts_woodwork.get(tid, 0))
        fkg = int(ts_fk_goals.get(tid, 0))
        hg = int(ts_hg_goals.get(tid, 0))
        gfob = int(ts_gfob_goals.get(tid, 0))
        c_avg = ts_corners.get(tid, 4.0)
        sc_avg = ts_crosses_target.get(tid, 4.0)
        sp_avg = ts_passes_target.get(tid, 350.0)
        pen_info = ts_penalties.get(tid, {"scored": 0, "total": 0})

        team_stats_list.append({
            "teamId": tid,
            "yellowCards": yc,
            "redCards": rc,
            "penaltiesWon": pen_info["scored"],
            "penaltiesTotal": pen_info["total"],
            "goalsScored": gs,
            "goalsConceded": gc,
            "cleanSheets": cs,
            "possessionAvg": poss,
            "shotsOnTargetAvg": sont,
            "totalShotsAvg": tot_shots,
            "hitWoodwork": hw,
            "saves": hw,
            "freeKickGoals": fkg,
            "headerGoals": hg,
            "outsideBoxGoals": gfob,
            "cornersAvg": c_avg,
            "successfulCrossesAvg": sc_avg,
            "successfulPassesAvg": sp_avg,
            "npxg": npxg_val
        })

    stats_data = {
        "topScorers": top_scorers,
        "topAssists": top_assists,
        "teamStats": team_stats_list
    }

    save_json_file(target_filename, stats_data, f"Mackolik resmi {season_name} istatistikleri ({target_filename}) guncellendi")
    print(f"[OK] {target_filename} basariyla kaydedildi.")
    return True

def run_sync_cycle(clock_state: dict) -> tuple:
    html_content = fetch_url(MACKOLIK_FIXTURES_URL)
    if not html_content or len(html_content) < 5000:
        return False, []

    fixtures = load_fixtures()
    if not fixtures:
        return False, []

    splits = html_content.split('{"match":{"id":')
    now_epoch = int(time.time())
    has_changes = False
    live_matches_summary = []
    schedule_changes = []

    for chunk in splits[1:]:
        m_name = re.search(r'"name":"(?P<home>[^"]+?)\s+vs\s+(?P<away>[^"]+?)"', chunk)
        if not m_name:
            m_team_a = re.search(r'"team_A":\{[^}]*?"name":"(?P<home>[^"]+?)"', chunk)
            m_team_b = re.search(r'"team_B":\{[^}]*?"name":"(?P<away>[^"]+?)"', chunk)
            if m_team_a and m_team_b:
                hname = m_team_a.group("home")
                aname = m_team_b.group("away")
            else:
                continue
        else:
            hname = m_name.group("home")
            aname = m_name.group("away")

        h_id = get_team_id(hname)
        a_id = get_team_id(aname)
        if not h_id or not a_id:
            continue

        our_match = next((m for m in fixtures if m.get("home") == h_id and m.get("away") == a_id), None)
        if not our_match:
            continue

        # 1. Update TFF Match Schedule (Date & Time)
        m_utc = re.search(r'"date_time_utc":"(?P<utc>[^"]+?)"', chunk)
        if m_utc:
            utc_str = m_utc.group("utc")
            try:
                dt_utc = datetime.datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
                dt_tr = dt_utc + datetime.timedelta(hours=3)
                new_date = f"{dt_tr.day} {MONTHS_TR[dt_tr.month]} {dt_tr.year}"
                new_time = dt_tr.strftime("%H:%M")

                date_diff = (our_match.get("date") != new_date)
                time_diff = (our_match.get("time") != new_time)

                if date_diff or time_diff:
                    schedule_changes.append(f"{our_match.get('homeName')} vs {our_match.get('awayName')} -> {new_date} {new_time}")
                    our_match["date"] = new_date
                    our_match["time"] = new_time
                    has_changes = True
            except Exception:
                pass

        # 2. Update Live / Match Status & Scores
        m_status = re.search(r'"status":"(?P<status>[^"]+?)"', chunk)
        st = m_status.group("status") if m_status else "Unknown"

        m_score = re.search(r'"fts_A":(\d+),"fts_B":(\d+)', chunk)
        sc_a = int(m_score.group(1)) if m_score else -1
        sc_b = int(m_score.group(2)) if m_score else -1

        m_min = re.search(r'"minute":(\d+)', chunk)
        min_val = int(m_min.group(1)) if m_min else -1

        m_period = re.search(r'"period":"([^"]+)"', chunk)
        period = m_period.group(1) if m_period else ""

        new_status = None
        new_elapsed = None
        new_hscore = None
        new_ascore = None

        if st in ["Playing", "Live"]:
            if "Half Time" in period or "Devre" in period:
                new_status = "HALF_TIME"
                new_elapsed = 45
            else:
                new_status = "LIVE"
                match_key = f"{h_id}_{a_id}"
                saved = clock_state.get(match_key)

                if not saved or min_val > saved.get("last_min", -1):
                    clock_state[match_key] = {
                        "last_min": min_val,
                        "epoch": now_epoch
                    }
                    new_elapsed = min_val
                else:
                    sec_passed = now_epoch - saved["epoch"]
                    adv_min = saved["last_min"] + (sec_passed // 60)
                    if "First" in period and adv_min > 45:
                        adv_min = 45
                    elif "Second" in period and adv_min > 90:
                        adv_min = 90
                    new_elapsed = max(min_val, adv_min)
            new_hscore = sc_a if sc_a >= 0 else 0
            new_ascore = sc_b if sc_b >= 0 else 0
        elif st == "HalfTime":
            new_status = "HALF_TIME"
            new_elapsed = 45
            new_hscore = sc_a if sc_a >= 0 else 0
            new_ascore = sc_b if sc_b >= 0 else 0
        elif st == "Played":
            new_status = "PLAYED"
            new_elapsed = 90
            new_hscore = sc_a if sc_a >= 0 else 0
            new_ascore = sc_b if sc_b >= 0 else 0

        if new_status:
            status_changed = (our_match.get("status") != new_status)
            score_changed = (our_match.get("homeScore") != new_hscore or our_match.get("awayScore") != new_ascore)
            minute_changed = (new_status == "LIVE" and our_match.get("elapsed") != new_elapsed)

            if new_status in ["LIVE", "HALF_TIME"]:
                live_matches_summary.append(
                    f"{our_match.get('homeName')} {new_hscore} - {new_ascore} {our_match.get('awayName')} [{new_status} - {new_elapsed}']"
                )

            if status_changed or score_changed or minute_changed:
                cur_time = time.strftime("%H:%M:%S")
                print(f"[{cur_time}] >>> CANLI GUNCELLEME: {our_match.get('homeName')} {new_hscore} - {new_ascore} {our_match.get('awayName')} [{new_status}] (Dk: {new_elapsed}')")
                our_match["status"] = new_status
                our_match["homeScore"] = new_hscore
                our_match["awayScore"] = new_ascore
                our_match["elapsed"] = new_elapsed
                has_changes = True

    if has_changes:
        parts = []
        if live_matches_summary:
            parts.append(" | ".join(live_matches_summary))
        if schedule_changes:
            parts.append(f"{len(schedule_changes)} macin saati guncellendi")
        commit_msg = "Live match & schedule update: " + " - ".join(parts if parts else ["Data updated"])
        save_json_file(FIXTURES_FILE, fixtures, commit_msg)
        print(f"[KAYDEDILDI] {commit_msg}")

    return has_changes, live_matches_summary

def main():
    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    duration_min = 15 if is_ci else 180
    if len(sys.argv) > 1:
        try:
            duration_min = int(sys.argv[1])
        except ValueError:
            pass

    print(f"==================================================")
    print(f" SÜPER LİG CANLI MAÇ, FİKSTÜR VE İSTATİSTİK BOTU")
    print(f" Calisma Suresi: {duration_min} dakika")
    print(f" Baslangic Saati: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")

    # 1. First sync official Mackolik Statistics
    try:
        sync_stats_for_season("2026/2027 Sezonu", MACKOLIK_STATS_2026_URL, STATS_2026_FILE, FIXTURES_FILE)
        sync_stats_for_season("2025/2026 Sezonu", MACKOLIK_STATS_2025_URL, STATS_2025_FILE, "fixtures_2025_2026.json")
    except Exception as e:
        print(f"[UYARI] Istatistik guncelleme hatasi: {e}")

    # 2. Start Live Match Polling
    start_time = time.time()
    end_time = start_time + (duration_min * 60)
    clock_state = {}
    last_stats_sync = time.time()

    while time.time() < end_time:
        try:
            has_changes, live_list = run_sync_cycle(clock_state)
            cur_time = time.strftime("%H:%M:%S")
            if live_list:
                print(f"[{cur_time}] Canli Maclar Takipte: {' | '.join(live_list)}")
            else:
                print(f"[{cur_time}] Su an canli mac bulunmuyor. (20 sn sonra tekrar kontrol edilecek)")

            # Periodic stats refresh every 5 minutes during live run
            if time.time() - last_stats_sync > 300:
                try:
                    sync_stats_for_season("2026/2027 Sezonu", MACKOLIK_STATS_2026_URL, STATS_2026_FILE, FIXTURES_FILE)
                    last_stats_sync = time.time()
                except Exception:
                    pass

        except Exception as e:
            print(f"[HATA] Dongu hatasi: {e}")

        time.sleep(20)

    print("Senkronizasyon turu tamamlandi.")

if __name__ == "__main__":
    main()