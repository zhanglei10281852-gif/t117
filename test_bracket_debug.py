import sys
sys.path.insert(0, 'e:\\solo1\\projects\\t117')

from app.logic.double_elimination import DoubleEliminationBracket, BracketMatchInfo
from app.models.models import BracketRound

def print_bracket_structure(team_count: int):
    print(f"\n{'='*60}")
    print(f"  {team_count} 队双败淘汰赛结构分析")
    print(f"{'='*60}")
    
    bracket = DoubleEliminationBracket(team_count)
    structure = bracket.generate_bracket_structure()
    
    print(f"\n胜者组轮数: {bracket.upper_round_count}")
    print(f"败者组轮数: {bracket.lower_round_count}")
    
    print(f"\n--- 所有轮次名称 ---")
    for r in bracket.get_all_round_names():
        print(f"  {r} ({bracket.get_round_display_name(r)})")
    
    print(f"\n--- 详细比赛信息 ---")
    for info in structure:
        side = "胜者组" if info.bracket_side == "upper" else ("败者组" if info.bracket_side == "lower" else "总决赛")
        print(f"\n[{side}] {info.bracket_round} 位置{info.position}")
        if info.team1_seed or info.team2_seed:
            print(f"  初始队伍: seed{info.team1_seed} vs seed{info.team2_seed}")
        if info.source1_type:
            print(f"  来源1: {info.source1_type} from {info.source1_round} pos{info.source1_position}")
        if info.source2_type:
            print(f"  来源2: {info.source2_type} from {info.source2_round} pos{info.source2_position}")
        if info.winner_to_round:
            print(f"  胜者去: {info.winner_to_round} pos{info.winner_to_position} slot{info.winner_to_slot}")
        if info.loser_to_round:
            print(f"  败者去: {info.loser_to_round} pos{info.loser_to_position} slot{info.loser_to_slot}")

if __name__ == "__main__":
    print_bracket_structure(4)
    print_bracket_structure(8)
