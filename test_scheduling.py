import sqlite3
import sys
import openpyxl
from app import generate_schedule_for_target_api, get_db_connection

sys.stdout.reconfigure(encoding='utf-8')

def test_validation():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_targets ORDER BY id ASC")
    targets = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    print(f"=== Total Targets in DB: {len(targets)} ===")
    
    # 1. Domestic/Airport stations test (base_interval == 1)
    print("\n--- 1. Domestic & Airport Stations (Annual Direct ●) ---")
    domestic_found = 0
    for t in targets:
        if t["base_interval"] == 1:
            sched = generate_schedule_for_target_api(t["id"], 2026, 2030)
            symbols = [sched[y]["symbol"] if sched[y] else "None" for y in range(2026, 2031)]
            print(f"[{t['id']:3d}] {t['station_name']:20s} ({t['operation_status']}) | 2026~2030: {symbols}")
            domestic_found += 1
            if t["operation_status"] == "운항":
                assert symbols == ['●', '●', '●', '●', '●'], f"Failed for {t['station_name']}"
    print(f"Total base_interval == 1 targets tested: {domestic_found}")
    
    # 2. General Station 2-year Interval Test
    print("\n--- 2. General Stations (2-year Interval ● <-> ◎) ---")
    test_stations = ["GUM (괌)", "SPN (사이판)", "DAD(다낭)", "CXR (나트랑)", "SGN (호치민)", "VAECO (DAD 다낭)"]
    for t in targets:
        if any(ts in t["station_name"] for ts in test_stations):
            sched = generate_schedule_for_target_api(t["id"], 2026, 2030)
            sym_list = []
            for y in range(2026, 2031):
                s = sched.get(y)
                sym_list.append(f"{y}:{s['symbol']}({s['audit_type']})" if s else f"{y}:-")
            print(f"[{t['id']:3d}] {t['station_name']:20s} ({t['operation_status']}) | {', '.join(sym_list)}")
            
    # 3. Dynamic Roll-over Test (Anchor Reset)
    print("\n--- 3. Testing Dynamic Roll-over (Reset & Roll-over) ---")
    # Pick a general operating station, e.g. GUM (괌)
    gum = next(t for t in targets if "GUM" in t["station_name"])
    print(f"Initial GUM schedule 2026~2030:")
    sched_before = generate_schedule_for_target_api(gum["id"], 2026, 2030)
    for y in range(2026, 2031):
        print(f"  {y}: {sched_before[y]['symbol'] if sched_before[y] else '-'}")
        
    print("\nSimulating user changing 2026 to DIRECT (●) in audit_history:")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO audit_history (target_id, year, audit_type, status, scheduled_date) VALUES (?, 2026, '직접', '계획', '2026-05-10')", (gum["id"],))
    conn.commit()
    conn.close()
    
    sched_after = generate_schedule_for_target_api(gum["id"], 2026, 2030)
    print("New Rolled Schedule after 2026 DIRECT set:")
    for y in range(2026, 2031):
        print(f"  {y}: {sched_after[y]['symbol'] if sched_after[y] else '-'} ({sched_after[y]['audit_type'] if sched_after[y] else '없음'})")
        
    assert sched_after[2026]["symbol"] == "●"
    assert sched_after[2027] is None
    assert sched_after[2028]["symbol"] == "◎"
    assert sched_after[2029] is None
    assert sched_after[2030]["symbol"] == "●"
    print(">> Dynamic Roll-over Test PASSED! (2026:● -> 2027:- -> 2028:◎ -> 2029:- -> 2030:●)")
    
    # Clean up test insert
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM audit_history WHERE target_id = ? AND year = 2026", (gum["id"],))
    conn.commit()
    conn.close()
    print("Test record cleaned up.")
    
    # 4. Non-operating Station Schedule Test
    print("\n--- 4. Non-operating (비운항) Station Test ---")
    non_ops = [t for t in targets if t["operation_status"] == "비운항"]
    print(f"Total non-operating targets: {len(non_ops)}")
    for t in non_ops[:5]:
        sched = generate_schedule_for_target_api(t["id"], 2026, 2030)
        assert all(sched[y] is None for y in range(2026, 2031)), f"Non-op failed for {t['station_name']}"
    print(">> Non-operating stations correctly have 0 scheduled audits in 2026~2030!")

if __name__ == "__main__":
    test_validation()
