import sys
import os
sys.path.insert(0, 'e:\\solo1\\projects\\t117')

from app.database import connection
from app.logic.tournament_manager import TournamentManager
from app.models.models import TeamStatus, TournamentPhase, MatchStatus

def print_all_matches(mgr, title="所有比赛"):
    print(f"\n--- {title} ---")
    for round_name in mgr.get_playoff_round_names():
        matches = mgr.get_playoff_matches_by_round(round_name)
        has_content = any(m.team1_id or m.team2_id for m in matches)
        if has_content:
            print(f"\n  {mgr.get_round_display_name(round_name)} ({round_name}):")
            for m in matches:
                t1 = mgr.get_team_name(m.team1_id) if m.team1_id else "?"
                t2 = mgr.get_team_name(m.team2_id) if m.team2_id else "?"
                status = m.status.value
                winner = mgr.get_team_name(m.winner_id) if m.winner_id else "-"
                print(f"    场{m.match_number}: {t1} vs {t2} [{status}] 胜者:{winner}")

def test_full_playoff(team_count: int):
    print(f"\n{'='*60}")
    print(f"  {team_count} 队完整淘汰赛流程测试")
    print(f"{'='*60}")
    
    test_db = f'e:\\solo1\\projects\\t117\\data\\test_playoff_{team_count}.db'
    original_db = connection.DB_PATH
    connection.DB_PATH = type(connection.DB_PATH)(test_db)
    
    if os.path.exists(test_db):
        os.remove(test_db)
    
    connection.init_database()
    
    mgr = TournamentManager()
    mgr.create_tournament(
        f"测试-{team_count}队", 
        playoff_teams=team_count
    )
    
    for i in range(1, team_count + 1):
        mgr.add_team(f"队伍{i}", i)
    
    mgr.start_playoff()
    
    print(f"\n初始状态:")
    print(f"  赛事阶段: {mgr._tournament.phase}")
    print(f"  晋级队伍数: {len(mgr.get_teams(TeamStatus.ADVANCED))}")
    
    def play_all_upper():
        print(f"\n=== 进行胜者组所有比赛 ===")
        round_names = [r for r in mgr.get_playoff_round_names() if r.startswith("upper_")]
        for rn in round_names:
            matches = mgr.get_playoff_matches_by_round(rn)
            played = 0
            for m in matches:
                if m.status == MatchStatus.COMPLETED:
                    continue
                if m.team1_id and m.team2_id:
                    mgr.record_match_result(m.id, 2, 1)
                    played += 1
            if played > 0:
                print(f"  {mgr.get_round_display_name(rn)}: 完成 {played} 场")
    
    def play_all_lower():
        print(f"\n=== 进行败者组所有比赛 ===")
        round_names = [r for r in mgr.get_playoff_round_names() if r.startswith("lower_")]
        total_played = 0
        for _ in range(len(round_names) * 2):
            played_this_pass = 0
            for rn in round_names:
                matches = mgr.get_playoff_matches_by_round(rn)
                for m in matches:
                    if m.status == MatchStatus.COMPLETED:
                        continue
                    if m.team1_id and m.team2_id:
                        mgr.record_match_result(m.id, 2, 0)
                        played_this_pass += 1
            total_played += played_this_pass
            if played_this_pass == 0:
                break
        print(f"  共完成 {total_played} 场败者组比赛")
    
    play_all_upper()
    print_all_matches(mgr, "胜者组打完后的所有比赛")
    
    play_all_lower()
    print_all_matches(mgr, "败者组打完后的所有比赛")
    
    gf_matches = mgr.get_playoff_matches_by_round("grand_final")
    if gf_matches:
        gf = gf_matches[0]
        print(f"\n=== 总决赛 ===")
        t1 = mgr.get_team_name(gf.team1_id)
        t2 = mgr.get_team_name(gf.team2_id)
        print(f"  对阵: {t1} vs {t2}")
        if gf.team1_id and gf.team2_id:
            mgr.record_match_result(gf.id, 2, 1)
            gf = mgr.get_playoff_matches_by_round("grand_final")[0]
            print(f"  结果: {mgr.get_team_name(gf.winner_id)} 胜")
        else:
            print(f"  队伍不全，无法进行")
    
    print(f"\n=== 尝试完成赛事 ===")
    complete = mgr.check_playoff_complete()
    print(f"  淘汰赛完成检查: {complete}")
    
    if complete:
        try:
            mgr.complete_tournament()
            print("  赛事完成成功")
        except Exception as e:
            print(f"  赛事完成失败: {e}")
    
    print(f"\n=== 最终结果 ===")
    winner = mgr.get_winner()
    if winner:
        print(f"  冠军: {winner.name}")
    else:
        print("  冠军: 未产生")
    
    print(f"  赛事阶段: {mgr._tournament.phase}")
    
    all_matches = []
    for rn in mgr.get_playoff_round_names():
        all_matches.extend(mgr.get_playoff_matches_by_round(rn))
    pending = [m for m in all_matches if m.status == MatchStatus.PENDING and not m.is_bye]
    print(f"  未完成非轮空比赛数: {len(pending)}")
    if pending:
        print("  未完成的比赛:")
        for m in pending:
            t1 = mgr.get_team_name(m.team1_id) if m.team1_id else "?"
            t2 = mgr.get_team_name(m.team2_id) if m.team2_id else "?"
            print(f"    {m.bracket_round} 场{m.match_number}: {t1} vs {t2}")
    
    print(f"\n  重赛详情:")
    reset_matches = mgr.get_playoff_matches_by_round("grand_final_reset")
    if reset_matches:
        rm = reset_matches[0]
        t1 = mgr.get_team_name(rm.team1_id) if rm.team1_id else "?"
        t2 = mgr.get_team_name(rm.team2_id) if rm.team2_id else "?"
        print(f"    队伍1(slot0): {t1}")
        print(f"    队伍2(slot1): {t2}")
        print(f"    状态: {rm.status.value}")
    
    connection.DB_PATH = original_db
    return mgr

if __name__ == "__main__":
    test_full_playoff(4)
    test_full_playoff(8)
