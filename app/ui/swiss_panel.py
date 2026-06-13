from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QMessageBox,
    QDialog, QDialogButtonBox, QSpinBox, QFormLayout, QComboBox,
    QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from app.models.models import (
    Tournament, Match, Round, TournamentPhase, MatchStatus, RoundStatus
)
from app.logic.tournament_manager import (
    TournamentManager, TournamentError, ScoreValidationError, PhaseTransitionError
)
from app.database.crud_match import get_match
from app.ui.signals import signals


class ScoreDialog(QDialog):
    def __init__(self, parent=None, match: Optional[Match] = None,
                 match_format: str = "bo1"):
        super().__init__(parent)
        self.setWindowTitle("录入比分")
        self.setMinimumWidth(300)
        self._match = match
        self._match_format = match_format

        layout = QFormLayout(self)

        team1_name = parent.manager.get_team_name(match.team1_id) if match and match.team1_id else "TBD"
        team2_name = parent.manager.get_team_name(match.team2_id) if match and match.team2_id else "TBD"

        wins_needed = self._get_wins_needed(match_format)
        hint = QLabel(f"请输入比分（{match_format.upper()} 赛制，需赢 {wins_needed} 场）")
        hint.setStyleSheet("color: #666;")
        layout.addRow(hint)

        self.team1_label = QLabel(f"<b>{team1_name}</b>")
        self.team1_label.setStyleSheet("font-size: 14px;")
        self.score1_spin = QSpinBox()
        self.score1_spin.setMinimum(0)
        self.score1_spin.setMaximum(99)

        self.team2_label = QLabel(f"<b>{team2_name}</b>")
        self.team2_label.setStyleSheet("font-size: 14px;")
        self.score2_spin = QSpinBox()
        self.score2_spin.setMinimum(0)
        self.score2_spin.setMaximum(99)

        if match and match.status == MatchStatus.COMPLETED:
            self.score1_spin.setValue(match.team1_score)
            self.score2_spin.setValue(match.team2_score)
            self.score1_spin.setEnabled(False)
            self.score2_spin.setEnabled(False)

        vs_label = QLabel("VS")
        vs_label.setAlignment(Qt.AlignCenter)
        vs_label.setStyleSheet("font-weight: bold; font-size: 16px;")

        layout.addRow(self.team1_label, self.team2_label)
        layout.addRow(self.score1_spin, self.score2_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        if match and match.status == MatchStatus.COMPLETED:
            buttons.button(QDialogButtonBox.Ok).setEnabled(False)

        layout.addRow(buttons)

    def _get_wins_needed(self, fmt: str) -> int:
        if fmt == "bo1":
            return 1
        elif fmt == "bo3":
            return 2
        elif fmt == "bo5":
            return 3
        return 1

    def get_scores(self):
        return self.score1_spin.value(), self.score2_spin.value()

    def accept(self):
        score1, score2 = self.get_scores()
        if score1 == score2:
            QMessageBox.warning(self, "提示", "比分不能平局")
            return
        super().accept()


class SwissPanel(QWidget):
    def __init__(self, manager: TournamentManager):
        super().__init__()
        self.manager = manager
        self._current_round: Optional[Round] = None
        self._init_ui()
        self._connect_signals()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("瑞士轮 - 当前轮次")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.generate_round_btn = QPushButton("生成下一轮对阵")
        self.generate_round_btn.setMinimumHeight(35)
        header_layout.addWidget(self.generate_round_btn)

        layout.addLayout(header_layout)

        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_layout = QHBoxLayout(info_frame)

        self.round_info_label = QLabel("当前轮次: 未开始")
        self.round_info_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.round_info_label)

        self.format_label = QLabel("赛制: Bo1")
        self.format_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.format_label)

        self.status_label = QLabel("状态: -")
        self.status_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()
        layout.addWidget(info_frame)

        self.matches_area = QScrollArea()
        self.matches_area.setWidgetResizable(True)
        self.matches_container = QWidget()
        self.matches_layout = QVBoxLayout(self.matches_container)
        self.matches_layout.setSpacing(10)
        self.matches_area.setWidget(self.matches_container)
        layout.addWidget(self.matches_area, 1)

        self._add_empty_state()

    def _add_empty_state(self):
        for i in reversed(range(self.matches_layout.count())):
            self.matches_layout.itemAt(i).widget().setParent(None)

        empty_label = QLabel("请点击「生成下一轮对阵」按钮开始")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #999; font-size: 14px; padding: 40px;")
        self.matches_layout.addWidget(empty_label)

    def _connect_signals(self):
        self.generate_round_btn.clicked.connect(self._generate_next_round)
        signals.data_changed.connect(self.refresh)
        signals.matches_updated.connect(self.refresh)

    def refresh(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            self._add_empty_state()
            self._update_button_states()
            return

        if tournament.phase not in [TournamentPhase.SWISS, TournamentPhase.PLAYOFF]:
            self._add_empty_state()
            self._update_button_states()
            return

        current_round = self.manager.get_current_swiss_round()
        self._current_round = current_round

        if current_round:
            self.round_info_label.setText(f"当前轮次: 第 {current_round.round_number} 轮")
            self.format_label.setText(f"赛制: {current_round.format.upper()}")
            self.status_label.setText(f"状态: {self._get_round_status_text(current_round.status.value)}")
            self._load_matches(current_round)
        else:
            self.round_info_label.setText("当前轮次: 等待开始")
            self._add_empty_state()

        self._update_button_states()

    def _get_round_status_text(self, status: str) -> str:
        status_map = {
            "pending": "待开始",
            "in_progress": "进行中",
            "completed": "已完成"
        }
        return status_map.get(status, status)

    def _update_button_states(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            self.generate_round_btn.setEnabled(False)
            return

        can_generate = (
            tournament.phase == TournamentPhase.SWISS
        )
        self.generate_round_btn.setEnabled(can_generate)

    def _load_matches(self, round_obj: Round):
        matches = self.manager.get_round_matches(round_obj.id)

        for i in reversed(range(self.matches_layout.count())):
            self.matches_layout.itemAt(i).widget().setParent(None)

        if not matches:
            empty_label = QLabel("暂无对阵")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999;")
            self.matches_layout.addWidget(empty_label)
            return

        for match in matches:
            match_widget = self._create_match_widget(match, round_obj.format)
            self.matches_layout.addWidget(match_widget)

        self.matches_layout.addStretch()

    def _create_match_widget(self, match: Match, match_format: str) -> QWidget:
        widget = QFrame()
        widget.setFrameShape(QFrame.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 10px;
                background-color: white;
            }
            QFrame:hover {
                border-color: #999;
            }
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)

        if match.is_bye:
            team_name = self.manager.get_team_name(match.team1_id)
            bye_label = QLabel(f"🏆 轮空: <b>{team_name}</b> 自动获胜")
            bye_label.setStyleSheet("font-size: 14px;")
            bye_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(bye_label)
            return widget

        team1_name = self.manager.get_team_name(match.team1_id)
        team2_name = self.manager.get_team_name(match.team2_id)

        team1_label = QLabel(f"<b>{team1_name}</b>")
        team1_label.setStyleSheet("font-size: 14px;")
        team1_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        team1_label.setMinimumWidth(150)

        score_label = QLabel()
        score_label.setAlignment(Qt.AlignCenter)
        score_label.setMinimumWidth(80)

        if match.status == MatchStatus.COMPLETED:
            if match.winner_id == match.team1_id:
                team1_label.setStyleSheet("font-size: 14px; color: green; font-weight: bold;")
                team2_label_style = "font-size: 14px; color: #999;"
            else:
                team2_label_style = "font-size: 14px; color: green; font-weight: bold;"
                team1_label.setStyleSheet("font-size: 14px; color: #999;")
            score_label.setText(
                f'<span style="font-size: 18px; font-weight: bold;">'
                f'{match.team1_score} - {match.team2_score}</span>')
            score_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        else:
            score_label.setText(
                f'<span style="font-size: 16px; color: #666;">VS</span>')
            score_label.setStyleSheet("font-size: 16px; color: #666;")
            team2_label_style = "font-size: 14px;"

        team2_label = QLabel(f"<b>{team2_name}</b>")
        team2_label.setStyleSheet(team2_label_style)
        team2_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        team2_label.setMinimumWidth(150)

        vs_text = QLabel()
        vs_text.setAlignment(Qt.AlignCenter)

        edit_btn = QPushButton("录入比分")
        edit_btn.setMinimumHeight(30)
        edit_btn.setMinimumWidth(100)

        if match.status == MatchStatus.COMPLETED:
            edit_btn.setText("已完成")
            edit_btn.setEnabled(False)
            edit_btn.setStyleSheet("background-color: #e8f5e9; color: #2e7d32;")

        edit_btn.clicked.connect(
            lambda m=match, fmt=match_format: self._edit_match_score(m, fmt))

        layout.addWidget(team1_label)
        layout.addWidget(score_label)
        layout.addWidget(team2_label)
        layout.addStretch()
        layout.addWidget(edit_btn)

        return widget

    def _generate_next_round(self):
        try:
            round_obj = self.manager.generate_next_swiss_round()
            signals.data_changed.emit()
            signals.matches_updated.emit()
            QMessageBox.information(
                self, "成功",
                f"第 {round_obj.round_number} 轮对阵已生成！")
        except PhaseTransitionError as e:
            QMessageBox.warning(self, "提示", str(e))
        except TournamentError as e:
            QMessageBox.critical(self, "错误", str(e))

    def _edit_match_score(self, match: Match, match_format: str):
        if match.status == MatchStatus.COMPLETED:
            return

        dialog = ScoreDialog(self, match, match_format)
        if dialog.exec() == QDialog.Accepted:
            score1, score2 = dialog.get_scores()
            try:
                self.manager.record_match_result(match.id, score1, score2)
                signals.data_changed.emit()
                signals.standings_updated.emit()
                signals.matches_updated.emit()
            except ScoreValidationError as e:
                QMessageBox.warning(self, "比分无效", str(e))
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))
