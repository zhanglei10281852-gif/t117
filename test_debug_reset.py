import sys
import os
sys.path.insert(0, 'e:\\solo1\\projects\\t117')

from app.database import connection
from app.logic.tournament_manager import TournamentManager
from app.logic.double_elimination import BracketProgression
from app.models.models import TeamStatus, MatchStatus
from app.database import crud_match

def test_reset_progression():
    print("调试总决赛重赛推进问题")
    
    test_db = 'e:\\solo1\\projects\\t117\\data\\test_debug.db'
    original_db = connection.DB_PATH
    connection.DB_PATH = type(connection.DB_PATH)(test_db)
    
    if os.path.exists(test_db):
        os.remove(test_db)
    
    connection.init_database()
    
    mgr = TournamentManager()
    mgr.create_tournament("调试测试", playoff_teams=4)
    
    for i in range(1, 5):
        mgr.add_team(f"队伍{i}", i)
    
    mgr.start_playoff()
    
    print("\n--- 检查 bracket_structure 中的 grand_final ---")
    for info in mgr._bracket_structure:
        if info.bracket_round == "grand_final":
            print(f"  找到 grand_final info:")
            print(f"    bracket_side: {info.bracket_side}")
            print(f"    position: {info.position}")
            print(f"    winner_to_round: {info.winner_to_round}")
            print(f"    winner_to_position: {info.winner_to_position}")
            print(f"    winner_to_slot: {info.winner_to_slot}")
            print(f"    loser_to_round: {info.loser_to_round}")
            print(f"    loser_to_position: {info.loser_to_position}")
            print(f"    loser_to_slot: {info.loser_to_slot}")
    
    print("\n--- 打胜者组半决赛 ---")
    sf_matches = mgr.get_playoff_matches_by_round("upper_semi")
    for m in sf_matches:
        mgr.record_match_result(m.id, 2, 0)
        print(f"  场{m.match_number}: {mgr.get_team_name(m.winner_id)} 胜")
    
    print("\n--- 打胜者组决赛 ---")
    uf_matches = mgr.get_playoff_matches_by_round("upper_final")
    for m in uf_matches:
        mgr.record_match_result(m.id, 2, 1)
        print(f"  场{m.match_number}: {mgr.get_team_name(m.winner_id)} 胜")
    
    print("\n--- 打败者组半决赛 ---")
    ls_matches = mgr.get_playoff_matches_by_round("lower_semi")
    for m in ls_matches:
        if m.team1_id and m.team2_id:
            mgr.record_match_result(m.id, 2, 0)
            print(f"  场{m.match_number}: {mgr.get_team_name(m.winner_id)} 胜")
    
    print("\n--- 打败者组决赛 ---")
    lf_matches = mgr.get_playoff_matches_by_round("lower_final")
    for m in lf_matches:
        if m.team1_id and m.team2_id:
            mgr.record_match_result(m.id, 2, 0)
            print(f"  场{m.match_number}: {mgr.get_team_name(m.winner_id)} 胜")
    
    print("\n--- 总决赛前的重赛状态 ---")
    reset_matches = mgr.get_playoff_matches_by_round("grand_final_reset")
    if reset_matches:
        rm = reset_matches[0]
        print(f"  重赛 team1_id: {rm.team1_id} ({mgr.get_team_name(rm.team1_id)})")
        print(f"  重赛 team2_id: {rm.team2_id} ({mgr.get_team_name(rm.team2_id)})")
        print(f"  重赛 status: {rm.status.value}")
    
    print("\n--- 打总决赛 ---")
    gf_matches = mgr.get_playoff_matches_by_round("grand_final")
    gf = gf_matches[0]
    print(f"  总决赛: {mgr.get_team_name(gf.team1_id)} vs {mgr.get_team_name(gf.team2_id)}")
    print(f"  match.bracket_side: {gf.bracket_side}")
    print(f"  match.bracket_round: {gf.bracket_round}")
    print(f"  match.match_number: {gf.match_number}")
    
    all_matches_before = crud_match.get_matches_by_tournament(mgr.tournament_id)
    match_map_before = BracketProgression.get_bracket_match_map(all_matches_before)
    reset_key = f"grand_final_reset_0"
    reset_before = match_map_before.get(reset_key)
    print(f"\n  推进前重赛在 match_map 中: {reset_before is not None}")
    if reset_before:
        print(f"    status: {reset_before.status.value}")
        print(f"    team1_id: {reset_before.team1_id}")
        print(f"    team2_id: {reset_before.team2_id}")
    
    mgr.record_match_result(gf.id, 2, 1)
    gf = mgr.get_playoff_matches_by_round("grand_final")[0]
    print(f"  总决赛胜者: {mgr.get_team_name(gf.winner_id)}")
    
    print("\n--- 总决赛后的重赛状态 ---")
    reset_matches = mgr.get_playoff_matches_by_round("grand_final_reset")
    if reset_matches:
        rm = reset_matches[0]
        print(f"  重赛 team1_id (slot0): {rm.team1_id} ({mgr.get_team_name(rm.team1_id)})")
        print(f"  重赛 team2_id (slot1): {rm.team2_id} ({mgr.get_team_name(rm.team2_id)})")
        print(f"  重赛 status: {rm.status.value}")
    
    print("\n--- 手动测试 advance_winner ---")
    all_matches = crud_match.get_matches_by_tournament(mgr.tournament_id)
    match_map = BracketProgression.get_bracket_match_map(all_matches)
    
    gf_match = None
    for m in all_matches:
        if m.bracket_round == "grand_final":
            gf_match = m
            break
    
    if gf_match:
        print(f"  找到总决赛比赛")
        print(f"    bracket_side: {gf_match.bracket_side}")
        print(f"    bracket_round: {gf_match.bracket_round}")
        print(f"    match_number: {gf_match.match_number}")
        
        match_info = None
        for info in mgr._bracket_structure:
            if (info.bracket_round == gf_match.bracket_round
                and info.bracket_side == gf_match.bracket_side
                and info.position == gf_match.match_number):
                match_info = info
                break
        
        if match_info:
            print(f"  找到对应的 match_info")
            print(f"    winner_to_round: {match_info.winner_to_round}")
            print(f"    winner_to_position: {match_info.winner_to_position}")
            print(f"    winner_to_slot: {match_info.winner_to_slot}")
        else:
            print(f"  未找到对应的 match_info！")
    
    connection.DB_PATH = original_db

if __name__ == "__main__":
    test_reset_progression()
