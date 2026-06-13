import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTabWidget, QMessageBox, QDialog, QLineEdit, QComboBox, QSpinBox,
    QFormLayout, QDialogButtonBox, QFileDialog, QToolBar, QStatusBar,
    QSplitter
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from app.database.connection import init_database
from app.models.models import TournamentPhase
from app.logic.tournament_manager import TournamentManager, TournamentError
from app.database import crud_tournament
from app.ui.team_panel import TeamPanel
from app.ui.swiss_panel import SwissPanel
from app.ui.standings_panel import StandingsPanel
from app.ui.playoff_panel import PlayoffPanel
from app.ui.signals import signals


class NewTournamentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建新赛事")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入赛事名称")
        self.name_edit.setText(f"电竞赛事_{datetime.now().strftime('%Y%m%d')}")

        self.swiss_format_combo = QComboBox()
        self.swiss_format_combo.addItems(["Bo1", "Bo3", "Bo5"])
        self.swiss_format_combo.setCurrentIndex(0)

        self.playoff_format_combo = QComboBox()
        self.playoff_format_combo.addItems(["Bo1", "Bo3", "Bo5"])
        self.playoff_format_combo.setCurrentIndex(1)

        self.advance_wins_spin = QSpinBox()
        self.advance_wins_spin.setRange(1, 10)
        self.advance_wins_spin.setValue(3)

        self.eliminate_losses_spin = QSpinBox()
        self.eliminate_losses_spin.setRange(1, 10)
        self.eliminate_losses_spin.setValue(3)

        self.playoff_teams_spin = QSpinBox()
        self.playoff_teams_spin.setRange(2, 64)
        self.playoff_teams_spin.setSingleStep(2)
        self.playoff_teams_spin.setValue(8)

        layout.addRow("赛事名称:", self.name_edit)
        layout.addRow("瑞士轮赛制:", self.swiss_format_combo)
        layout.addRow("淘汰赛赛制:", self.playoff_format_combo)
        layout.addRow("晋级胜场数:", self.advance_wins_spin)
        layout.addRow("淘汰败场数:", self.eliminate_losses_spin)
        layout.addRow("淘汰赛队伍数:", self.playoff_teams_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "swiss_format": self.swiss_format_combo.currentText().lower(),
            "playoff_format": self.playoff_format_combo.currentText().lower(),
            "advance_wins": self.advance_wins_spin.value(),
            "eliminate_losses": self.eliminate_losses_spin.value(),
            "playoff_teams": self.playoff_teams_spin.value()
        }

    def accept(self):
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "提示", "请输入赛事名称")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager: Optional[TournamentManager] = None
        self._init_database()
        self._init_ui()
        self._connect_signals()
        self._try_load_last_tournament()

    def _init_database(self):
        init_database()

    def _init_ui(self):
        self.setWindowTitle("电竞瑞士轮赛事管理器")
        self.setMinimumSize(1200, 800)

        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

    def _create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("新建赛事", self)
        new_action.triggered.connect(self._new_tournament)
        toolbar.addAction(new_action)

        open_action = QAction("加载赛事", self)
        open_action.triggered.connect(self._show_tournament_list)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        start_swiss_action = QAction("开始瑞士轮", self)
        start_swiss_action.triggered.connect(self._start_swiss)
        toolbar.addAction(start_swiss_action)

        self.start_swiss_action = start_swiss_action

        toolbar.addSeparator()

        export_json_action = QAction("导出JSON", self)
        export_json_action.triggered.connect(lambda: self._export_data("json"))
        toolbar.addAction(export_json_action)

        export_csv_action = QAction("导出CSV", self)
        export_csv_action.triggered.connect(lambda: self._export_data("csv"))
        toolbar.addAction(export_csv_action)

    def _create_central_widget(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = self._create_header()
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 20px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #2196F3;
                color: white;
            }
        """)

        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(15, 10, 15, 10)

        self.tournament_name_label = QLabel("请创建或加载赛事")
        self.tournament_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.phase_label = QLabel("")
        self.phase_label.setStyleSheet("""
            QLabel {
                padding: 4px 12px;
                background-color: #9E9E9E;
                color: white;
                border-radius: 10px;
                font-size: 12px;
            }
        """)

        layout.addWidget(self.tournament_name_label)
        layout.addSpacing(20)
        layout.addWidget(self.phase_label)
        layout.addStretch()

        return header

    def _create_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("就绪")
        status.addWidget(self.status_label)

    def _connect_signals(self):
        signals.data_changed.connect(self._update_header)
        signals.phase_changed.connect(self._update_phase_label)
        signals.tournament_changed.connect(self._on_tournament_changed)

    def _try_load_last_tournament(self):
        tournaments = crud_tournament.get_all_tournaments()
        if tournaments:
            self._load_tournament(tournaments[0].id)
        else:
            self._update_no_tournament_state()

    def _new_tournament(self):
        dialog = NewTournamentDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                manager = TournamentManager()
                manager.create_tournament(
                    name=data["name"],
                    swiss_format=data["swiss_format"],
                    playoff_format=data["playoff_format"],
                    advance_wins=data["advance_wins"],
                    eliminate_losses=data["eliminate_losses"],
                    playoff_teams=data["playoff_teams"]
                )
                manager.validate_and_set_playoff_count(data["playoff_teams"])
                self.manager = manager
                signals.tournament_changed.emit(manager.tournament_id)
                signals.data_changed.emit()
                self._setup_panels()
                self.status_label.setText(f"已创建赛事: {data['name']}")
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _show_tournament_list(self):
        tournaments = crud_tournament.get_all_tournaments()
        if not tournaments:
            QMessageBox.information(self, "提示", "暂无保存的赛事")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("选择赛事")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(300)

        layout = QVBoxLayout(dialog)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)

        for t in tournaments:
            btn = QPushButton(f"{t.name} - {self._get_phase_text(t.phase.value)}")
            btn.setStyleSheet("text-align: left; padding: 10px;")
            btn.clicked.connect(lambda checked=False, tid=t.id: (dialog.accept(), self._load_tournament(tid)))
            list_layout.addWidget(btn)

        list_layout.addStretch()
        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _get_phase_text(self, phase: str) -> str:
        phase_map = {
            "setup": "准备中",
            "swiss": "瑞士轮",
            "playoff": "淘汰赛",
            "completed": "已完成"
        }
        return phase_map.get(phase, phase)

    def _load_tournament(self, tournament_id: int):
        try:
            self.manager = TournamentManager(tournament_id)
            signals.tournament_changed.emit(tournament_id)
            signals.data_changed.emit()
            self._setup_panels()
            self.status_label.setText("已加载赛事")
        except TournamentError as e:
            QMessageBox.warning(self, "错误", str(e))

    def _on_tournament_changed(self, tournament_id: int):
        self._update_header()
        self._update_phase_label()
        self._update_actions_state()

    def _update_no_tournament_state(self):
        self.tournament_name_label.setText("请创建或加载赛事")
        self.phase_label.setText("")
        self.tabs.clear()
        self.start_swiss_action.setEnabled(False)

    def _setup_panels(self):
        if not self.manager:
            return

        self.tabs.clear()

        self.team_panel = TeamPanel(self.manager)
        self.swiss_panel = SwissPanel(self.manager)
        self.standings_panel = StandingsPanel(self.manager)
        self.playoff_panel = PlayoffPanel(self.manager)

        self.tabs.addTab(self.team_panel, "队伍管理")
        self.tabs.addTab(self.swiss_panel, "瑞士轮对阵")
        self.tabs.addTab(self.standings_panel, "积分榜")
        self.tabs.addTab(self.playoff_panel, "淘汰赛对阵图")

        self._update_header()
        self._update_phase_label()
        self._update_actions_state()

    def _update_header(self):
        if not self.manager:
            return
        tournament = self.manager.get_tournament()
        if tournament:
            self.tournament_name_label.setText(f"赛事: {tournament.name}")

    def _update_phase_label(self):
        if not self.manager:
            return
        tournament = self.manager.get_tournament()
        if not tournament:
            return

        phase = tournament.phase.value
        phase_text = self._get_phase_text(phase)

        colors = {
            "setup": "#9E9E9E",
            "swiss": "#2196F3",
            "playoff": "#FF9800",
            "completed": "#4CAF50"
        }

        color = colors.get(phase, "#9E9E9E")
        self.phase_label.setText(phase_text)
        self.phase_label.setStyleSheet(f"""
            QLabel {{
                padding: 4px 12px;
                background-color: {color};
                color: white;
                border-radius: 10px;
                font-size: 12px;
            }}
        """)

    def _update_actions_state(self):
        if not self.manager:
            self.start_swiss_action.setEnabled(False)
            return

        tournament = self.manager.get_tournament()
        if not tournament:
            return

        can_start_swiss = (
            tournament.phase == TournamentPhase.SETUP
            and len(self.manager.get_teams()) >= 2
        )
        self.start_swiss_action.setEnabled(can_start_swiss)

    def _start_swiss(self):
        if not self.manager:
            return

        tournament = self.manager.get_tournament()
        if tournament.phase != TournamentPhase.SETUP:
            QMessageBox.warning(self, "提示", "赛事已经开始了")
            return

        teams = self.manager.get_teams()
        if len(teams) < 2:
            QMessageBox.warning(self, "提示", "至少需要2支队伍才能开始比赛")
            return

        reply = QMessageBox.question(
            self, "确认开始",
            f"确定要开始瑞士轮吗？\n当前共有 {len(teams)} 支队伍",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.manager.start_swiss()
                signals.data_changed.emit()
                signals.phase_changed.emit("swiss")
                self.status_label.setText("瑞士轮已开始")
                QMessageBox.information(self, "成功", "瑞士轮阶段已开始！")
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _export_data(self, format_type: str):
        if not self.manager:
            QMessageBox.warning(self, "提示", "请先加载赛事")
            return

        data = self.manager.export_data()
        tournament = self.manager.get_tournament()

        default_name = f"{tournament.name}_赛事数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format_type == "json":
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出数据", default_name + ".json", "JSON文件 (*.json)")
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")

        elif format_type == "csv":
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出数据", default_name + ".csv", "CSV文件 (*.csv)")
            if file_path:
                self._export_to_csv(data, file_path)
                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")

    def _export_to_csv(self, data: dict, file_path: str):
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)

            writer.writerow(["=== 赛事信息 ==="])
            t = data["tournament"]
            writer.writerow(["赛事名称", t["name"]])
            writer.writerow(["阶段", t["phase"]])
            writer.writerow(["瑞士轮赛制", t["swiss_format"]])
            writer.writerow(["淘汰赛赛制", t["playoff_format"]])
            writer.writerow(["晋级胜场", t["advance_wins"]])
            writer.writerow(["淘汰败场", t["eliminate_losses"]])
            writer.writerow([])

            writer.writerow(["=== 积分榜 ==="])
            writer.writerow([
                "排名", "种子", "队伍", "胜", "负", "战绩",
                "Median-Buchholz", "Buchholz", "相互胜负", "状态"
            ])
            for s in data["standings"]:
                status_map = {"active": "活跃", "advanced": "已晋级", "eliminated": "已淘汰"}
                writer.writerow([
                    s["rank"], s["team_id"], s["team_name"],
                    s["wins"], s["losses"], f"{s['wins']}-{s['losses']}",
                    s["median_buchholz"], s["buchholz"], s["head_to_head_wins"],
                    status_map.get(s["team_name"], "")
                ])
            writer.writerow([])

            writer.writerow(["=== 比赛结果 ==="])
            writer.writerow([
                "轮次", "阶段", "场序", "队伍1", "比分", "队伍2", "胜者", "状态"
            ])
            for m in data["matches"]:
                status = "已完成" if m["status"] == "completed" else "待开始"
                if m["is_bye"]:
                    writer.writerow([
                        m["round_number"], m["phase"], m["match_number"],
                        m["team1_name"] or "", "轮空", "",
                        m["team1_name"] or "", status
                    ])
                else:
                    score = f"{m['team1_score']}-{m['team2_score']}" if m["status"] == "completed" else "VS"
                    writer.writerow([
                        m["round_number"], m["phase"], m["match_number"],
                        m["team1_name"] or "", score, m["team2_name"] or "",
                        m["winner_name"] or "", status
                    ])

    def closeEvent(self, event):
        event.accept()
