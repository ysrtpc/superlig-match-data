# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import time
import html
import datetime
import urllib.request
import urllib.error

MACKOLIK_URL = "https://www.mackolik.com/puan-durumu/t%C3%BCrkiye-s%C3%BCper-lig/fikstur/482ofyysbdbeoxauk19yg7tdt"
FIXTURES_FILE = "fixtures_2026_2027.json"

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
    (r"kayseri", "kay"),
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

def fetch_mackolik() -> str:
    req = urllib.request.Request(
        MACKOLIK_URL,
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
        print(f"[HATA] Mackolik cekilemedi: {e}")
        return ""

def load_fixtures() -> list:
    if os.path.exists(FIXTURES_FILE):
        try:
            with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[HATA] Fikstur dosyasi okunamadi: {e}")
    return []

def save_fixtures(fixtures_data: list):
    paths = [
        FIXTURES_FILE,
        os.path.join("superlig-app", "app", "src", "main", "assets", FIXTURES_FILE)
    ]
    json_str = json.dumps(fixtures_data, ensure_ascii=False, indent=2)
    for p in paths:
        if os.path.exists(p) or p == FIXTURES_FILE:
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
                with open(p, "w", encoding="utf-8") as f:
                    f.write(json_str)
            except Exception as e:
                print(f"[UYARI] Dosya kaydedilemedi ({p}): {e}")

def run_sync_cycle(clock_state: dict) -> tuple:
    html_content = fetch_mackolik()
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
                # Turkey is UTC+3
                dt_tr = dt_utc + datetime.timedelta(hours=3)
                new_date = f"{dt_tr.day} {MONTHS_TR[dt_tr.month]} {dt_tr.year}"
                new_time = dt_tr.strftime("%H:%M")

                date_diff = (our_match.get("date") != new_date)
                time_diff = (our_match.get("time") != new_time)

                if date_diff or time_diff:
                    # Update date & time
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
        save_fixtures(fixtures)
        parts = []
        if live_matches_summary:
            parts.append(" | ".join(live_matches_summary))
        if schedule_changes:
            parts.append(f"{len(schedule_changes)} maçın saati güncellendi")
        commit_msg = "Live match & schedule update: " + " - ".join(parts if parts else ["Data updated"])
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
    print(f" SÜPER LİG CANLI MAÇ & FİKSTÜR SAATLERİ BOTU")
    print(f" Calisma Suresi: {duration_min} dakika")
    print(f" Baslangic Saati: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")

    start_time = time.time()
    end_time = start_time + (duration_min * 60)
    clock_state = {}

    while time.time() < end_time:
        try:
            has_changes, live_list = run_sync_cycle(clock_state)
            cur_time = time.strftime("%H:%M:%S")
            if live_list:
                print(f"[{cur_time}] Canli Maclar Takipte: {' | '.join(live_list)}")
            else:
                print(f"[{cur_time}] Su an canli mac bulunmuyor. (20 sn sonra tekrar kontrol edilecek)")
        except Exception as e:
            print(f"[HATA] Dongu hatasi: {e}")

        time.sleep(20)

    print("Senkronizasyon turu tamamlandi.")

if __name__ == "__main__":
    main()
