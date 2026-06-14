import os
import tempfile
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.database.connection import init_db, get_db
from app.logic.tournament_manager import TournamentManager
from app.models.models import TournamentPhase, MatchStatus


def test_bug1_8teams_8playoff():
    """Bug 1: 8支队伍+8个淘汰赛名额时，瑞士轮第一轮都生成不了"""
    print("\n" + "=" * 60)
    print("测试 Bug 1: 8队8名额瑞士轮能否生成对阵")
    print("=" * 60)

    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)
    db = next(get_db())

    mgr = TournamentManager(db)
    mgr.create_tournament("测试赛事", "swiss_elimination", playoff_team_count=8)

    for i in range(1, 9):
        mgr.add_team(f"队伍{i}", seed=i)

    mgr.start_swiss()

    try:
        mgr.generate_next_swiss_round()
        round_matches = mgr.get_current_round_matches()
        print(f"  ✅ 成功生成第一轮对阵，共 {len(round_matches)} 场比赛")
        for m in round_matches:
            t1 = mgr.get_team_name(m.team1_id) if m.team1_id else "轮空"
            t2 = mgr.get_team_name(m.team2_id) if m.team2_id else "轮空"
            print(f"    场{m.match_number}: {t1} vs {t2}")
        result = True
    except Exception as e:
        print(f"  ❌ 生成对阵失败: {e}")
        result = False

    db.close()
    os.unlink(db_file)
    return result


def test_bug2_playoff_team_count_persist():
    """Bug 2: 淘汰赛队伍数不持久化，重新加载赛事后变回默认值8"""
    print("\n" + "=" * 60)
    print("测试 Bug 2: 淘汰赛队伍数持久化")
    print("=" * 60)

    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)

    # 创建赛事，设置淘汰赛队伍数为4
    db = next(get_db())
    mgr = TournamentManager(db)
    mgr.create_tournament("测试赛事", "swiss_elimination", playoff_team_count=4)
    tid = mgr.tournament_id
    playoff_count_before = mgr._playoff_team_count
    print(f"  创建时设置: playoff_team_count = {playoff_count_before}")

    for i in range(1, 9):
        mgr.add_team(f"队伍{i}", seed=i)

    db.close()

    # 重新加载
    db2 = next(get_db())
    mgr2 = TournamentManager(db2)
    mgr2.load_tournament(tid)
    playoff_count_after = mgr2._playoff_team_count
    print(f"  重新加载后: playoff_team_count = {playoff_count_after}")

    if playoff_count_before == playoff_count_after == 4:
        print(f"  ✅ 淘汰赛队伍数持久化正确")
        result = True
    else:
        print(f"  ❌ 淘汰赛队伍数持久化失败: 创建时={playoff_count_before}, 加载后={playoff_count_after}")
        result = False

    db2.close()
    os.unlink(db_file)
    return result


def test_bug3_bye_counts_as_win():
    """Bug 3: 单数队伍时，轮空的队伍战绩不变，且轮空比赛不算完成"""
    print("\n" + "=" * 60)
    print("测试 Bug 3: 轮空算胜场、轮空比赛自动完成")
    print("=" * 60)

    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)
    db = next(get_db())

    mgr = TournamentManager(db)
    mgr.create_tournament("测试赛事", "swiss_elimination", playoff_team_count=4)

    # 添加7支队伍（单数）
    for i in range(1, 8):
        mgr.add_team(f"队伍{i}", seed=i)

    mgr.start_swiss()
    mgr.generate_next_swiss_round()

    round_matches = mgr.get_current_round_matches()
    bye_match = None
    for m in round_matches:
        if m.is_bye:
            bye_match = m
            break

    if not bye_match:
        print(f"  ❌ 没有找到轮空比赛")
        db.close()
        os.unlink(db_file)
        return False

    bye_team_id = bye_match.team1_id if bye_match.team1_id else bye_match.team2_id
    team_before = mgr.get_team(bye_team_id)
    print(f"  轮空队伍: {team_before.name}")
    print(f"  轮空比赛状态: {bye_match.status.value}")
    print(f"  轮空前战绩: {team_before.wins}胜 {team_before.losses}负")

    # 录入轮空比赛结果
    mgr.record_match_result(bye_match.id, 1, 0)

    team_after = mgr.get_team(bye_team_id)
    match_after = mgr._get_match(bye_match.id)

    print(f"  轮空后战绩: {team_after.wins}胜 {team_after.losses}负")
    print(f"  轮空后比赛状态: {match_after.status.value}")

    win_ok = team_after.wins == team_before.wins + 1
    status_ok = match_after.status.value == "completed"

    # 检查是否能生成下一轮
    # 需要先完成其他比赛
    for m in round_matches:
        if not m.is_bye and m.status.value == "pending":
            mgr.record_match_result(m.id, 2, 1)

    round_complete = mgr.check_round_complete()
    print(f"  本轮是否完成: {round_complete}")

    if win_ok and status_ok and round_complete:
        print(f"  ✅ 轮空算胜场、比赛标记完成、轮次可结束")
        result = True
    else:
        print(f"  ❌ 轮空逻辑有问题")
        result = False

    db.close()
    os.unlink(db_file)
    return result


def test_bug4_edit_team_refresh():
    """Bug 4: 修改队伍名称或种子后界面无变化"""
    print("\n" + "=" * 60)
    print("测试 Bug 4: 编辑队伍后数据更新")
    print("=" * 60)

    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)
    db = next(get_db())

    mgr = TournamentManager(db)
    mgr.create_tournament("测试赛事", "swiss_elimination")

    team_id = mgr.add_team("原名字", seed=5)
    team_before = mgr.get_team(team_id)
    print(f"  修改前: {team_before.name}, 种子={team_before.seed}")

    mgr.update_team(team_id, "新名字", seed=10)
    team_after = mgr.get_team(team_id)
    print(f"  修改后: {team_after.name}, 种子={team_after.seed}")

    name_ok = team_after.name == "新名字"
    seed_ok = team_after.seed == 10

    if name_ok and seed_ok:
        print(f"  ✅ 队伍名称和种子都正确更新")
        result = True
    else:
        print(f"  ❌ 队伍编辑有问题")
        result = False

    db.close()
    os.unlink(db_file)
    return result


def test_bug5_double_elimination():
    """Bug 5: 淘汰赛胜者组打完后，败者组对阵一直是空的"""
    print("\n" + "=" * 60)
    print("测试 Bug 5: 双败淘汰赛败者组推进和冠军产生")
    print("=" * 60)

    db_file = tempfile.mktemp(suffix=".db")
    init_db(db_file)
    db = next(get_db())

    mgr = TournamentManager(db)
    mgr.create_tournament("测试赛事", "swiss_elimination", playoff_team_count=4)

    for i in range(1, 9):
        mgr.add_team(f"队伍{i}", seed=i)

    # 直接开始淘汰赛
    mgr._phase = TournamentPhase.PLAYOFF
    mgr._update_tournament_phase()
    from app.database.crud_team import get_teams
    teams = get_teams(db, mgr.tournament_id)
    mgr.start_playoffs([t.id for t in teams[:4]])

    # 打胜者组
    upper_rounds = ["upper_semi", "upper_final"]
    for round_name in upper_rounds:
        matches = [m for m in mgr.get_playoff_matches() if m.bracket_round == round_name]
        for m in matches:
            if m.team1_id and m.team2_id:
                mgr.record_match_result(m.id, 2, 1)

    # 检查败者组是否有队伍
    lower_rounds = ["lower_semi", "lower_final"]
    lower_filled = True
    for round_name in lower_rounds:
        matches = [m for m in mgr.get_playoff_matches() if m.bracket_round == round_name]
        for m in matches:
            if not m.team1_id:
                lower_filled = False
                print(f"  ❌ 败者组 {round_name} 场{m.match_number} team1 为空")

    if lower_filled:
        print(f"  ✅ 败者组比赛都有队伍填充")

    # 打败者组
    for round_name in lower_rounds:
        matches = [m for m in mgr.get_playoff_matches() if m.bracket_round == round_name]
        for m in matches:
            if m.team1_id and m.team2_id and m.status.value == "pending":
                mgr.record_match_result(m.id, 2, 1)

    # 检查总决赛
    grand_final = [m for m in mgr.get_playoff_matches() if m.bracket_round == "grand_final"][0]
    gf_ok = grand_final.team1_id is not None and grand_final.team2_id is not None
    if gf_ok:
        t1 = mgr.get_team_name(grand_final.team1_id)
        t2 = mgr.get_team_name(grand_final.team2_id)
        print(f"  ✅ 总决赛有对阵: {t1} vs {t2}")
    else:
        print(f"  ❌ 总决赛队伍不完整: team1={grand_final.team1_id}, team2={grand_final.team2_id}")

    # 打总决赛
    mgr.record_match_result(grand_final.id, 3, 2)

    # 检查冠军
    winner = mgr.get_playoff_winner()
    if winner:
        print(f"  ✅ 冠军已产生: {mgr.get_team_name(winner)}")
    else:
        print(f"  ❌ 冠军未产生")

    playoff_complete = mgr.check_playoff_complete()
    print(f"  淘汰赛是否完成: {playoff_complete}")

    result = lower_filled and gf_ok and winner is not None and playoff_complete

    db.close()
    os.unlink(db_file)
    return result


if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("#  所有 Bug 修复验证测试")
    print("#" * 60)

    results = []
    results.append(("Bug 1: 8队8名额瑞士轮", test_bug1_8teams_8playoff()))
    results.append(("Bug 2: 淘汰赛队伍数持久化", test_bug2_playoff_team_count_persist()))
    results.append(("Bug 3: 轮空算胜场", test_bug3_bye_counts_as_win()))
    results.append(("Bug 4: 编辑队伍刷新", test_bug4_edit_team_refresh()))
    results.append(("Bug 5: 败者组推进", test_bug5_double_elimination()))

    print("\n" + "#" * 60)
    print("#  测试结果汇总")
    print("#" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n  总计: {sum(1 for r in results if r[1])}/{len(results)} 项通过")
    if all_passed:
        print("  🎉 所有 Bug 都已修复！")
    else:
        print("  ⚠️  仍有 Bug 未修复")
