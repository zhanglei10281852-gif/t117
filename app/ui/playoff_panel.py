from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
    QScrollArea, QFrame, QDialog, QSpinBox, QFormLayout, QDialogButtonBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsSimpleTextItem, QGraphicsItem
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from app.models.models import (
    Tournament, Match, TournamentPhase, MatchStatus, BracketRound
)
from app.logic.tournament_manager import (
    TournamentManager, TournamentError, ScoreValidationError
)
from app.ui.signals import signals


class ScoreDialogPlayoff(QDialog):
    def __init__(self, parent=None, match: Optional[Match] = None,
                 match_format: str = "bo3"):
        super().__init__(parent)
        self.setWindowTitle("录入比分")
        self.setMinimumWidth(300)
        self._match = match
        self._match_format = match_format

        layout = QFormLayout(self)

        team1_name = parent.manager.get_team_name(match.team1_id) if match and match.team1_id else "待定"
        team2_name = parent.manager.get_team_name(match.team2_id) if match and match.team2_id else "待定"

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

        if match and (not match.team1_id or not match.team2_id):
            self.score1_spin.setEnabled(False)
            self.score2_spin.setEnabled(False)

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


class BracketMatchItem(QGraphicsRectItem):
    def __init__(self, x: float, y: float, width: float, height: float,
                 match: Optional[Match] = None, team1_name: str = "",
                 team2_name: str = "", parent=None):
        super().__init__(x, y, width, height, parent)
        self.match = match
        self.team1_name = team1_name
        self.team2_name = team2_name
        self._width = width
        self._height = height
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)

    def paint(self, painter: QPainter, option, widget):
        rect = self.rect()

        if self.match and self.match.status == MatchStatus.COMPLETED:
            painter.setBrush(QBrush(QColor(240, 248, 240)))
            pen = QPen(QColor(76, 175, 80))
        elif self.match and self.match.team1_id and self.match.team2_id:
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            pen = QPen(QColor(100, 100, 100))
        else:
            painter.setBrush(QBrush(QColor(245, 245, 245)))
            pen = QPen(QColor(200, 200, 200))

        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 4, 4)

        pen = QPen(QColor(50, 50, 50))
        painter.setPen(pen)
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        team1_y = rect.top() + self._height * 0.35
        team2_y = rect.top() + self._height * 0.7

        t1_color = QColor(50, 50, 50)
        t2_color = QColor(50, 50, 50)

        if self.match and self.match.status == MatchStatus.COMPLETED:
            if self.match.winner_id == self.match.team1_id:
                t1_color = QColor(27, 94, 32)
                t2_color = QColor(150, 150, 150)
                font.setBold(True)
                painter.setFont(font)
            else:
                t2_color = QColor(27, 94, 32)
                t1_color = QColor(150, 150, 150)

        painter.setPen(t1_color)
        painter.drawText(
            QRectF(rect.left() + 8, team1_y - 10, rect.width() - 60, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.team1_name or "待定"
        )

        painter.setPen(t2_color)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            QRectF(rect.left() + 8, team2_y - 10, rect.width() - 60, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.team2_name or "待定"
        )

        if self.match and self.match.status == MatchStatus.COMPLETED:
            score_font = QFont()
            score_font.setBold(True)
            score_font.setPointSize(10)
            painter.setFont(score_font)
            painter.setPen(QColor(33, 33, 33))

            painter.drawText(
                QRectF(rect.right() - 50, team1_y - 10, 40, 20),
                Qt.AlignRight | Qt.AlignVCenter,
                str(self.match.team1_score)
            )
            painter.drawText(
                QRectF(rect.right() - 50, team2_y - 10, 40, 20),
                Qt.AlignRight | Qt.AlignVCenter,
                str(self.match.team2_score)
            )

        pen = QPen(QColor(220, 220, 220))
        painter.setPen(pen)
        painter.drawLine(
            QPointF(rect.left() + 5, rect.top() + self._height / 2),
            QPointF(rect.right() - 5, rect.top() + self._height / 2)
        )

    def mousePressEvent(self, event):
        if self.match and self.match.status == MatchStatus.PENDING:
            if self.match.team1_id and self.match.team2_id:
                self.scene().parent().edit_match_requested.emit(self.match)
        super().mousePressEvent(event)


class BracketScene(QGraphicsScene):
    edit_match_requested = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_match_requested = parent.edit_match_requested if hasattr(parent, 'edit_match_requested') else None


class PlayoffPanel(QWidget):
    from PySide6.QtCore import Signal
    edit_match_requested = Signal(object)

    def __init__(self, manager: TournamentManager):
        super().__init__()
        self.manager = manager
        self._match_widgets: Dict[str, BracketMatchItem] = {}
        self._init_ui()
        self._connect_signals()
        self.edit_match_requested.connect(self._on_edit_match)
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("淘汰赛 - 双败对阵图")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.start_playoff_btn = QPushButton("生成淘汰赛对阵")
        self.start_playoff_btn.setMinimumHeight(35)
        header_layout.addWidget(self.start_playoff_btn)

        layout.addLayout(header_layout)

        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_layout = QHBoxLayout(info_frame)

        self.format_label = QLabel("赛制: Bo3")
        self.format_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.format_label)

        self.status_label = QLabel("状态: 未开始")
        self.status_label.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()
        layout.addWidget(info_frame)

        self.bracket_view = QGraphicsView()
        self.bracket_view.setRenderHints(QPainter.Antialiasing)
        self.bracket_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.bracket_scene = BracketScene(self)
        self.bracket_view.setScene(self.bracket_scene)
        self.bracket_view.setMinimumHeight(500)
        layout.addWidget(self.bracket_view, 1)

    def _connect_signals(self):
        self.start_playoff_btn.clicked.connect(self._start_playoff)
        signals.data_changed.connect(self.refresh)
        signals.matches_updated.connect(self.refresh)

    def refresh(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            self._clear_bracket()
            self._update_button_states()
            return

        if tournament.phase in [TournamentPhase.SETUP, TournamentPhase.SWISS]:
            self.status_label.setText("状态: 等待瑞士轮完成")
            self._clear_bracket()
            self._update_button_states()
            return

        if tournament.phase == TournamentPhase.PLAYOFF:
            self.status_label.setText("状态: 进行中")
            self.format_label.setText(f"赛制: {tournament.playoff_format.upper()}")
            self._draw_bracket()
        elif tournament.phase == TournamentPhase.COMPLETED:
            self.status_label.setText("状态: 已完成")
            self._draw_bracket()

        self._update_button_states()

    def _update_button_states(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            self.start_playoff_btn.setEnabled(False)
            return

        can_start = (
            tournament.phase in [TournamentPhase.SWISS]
            and self.manager.check_swiss_complete()
        )
        self.start_playoff_btn.setEnabled(can_start)

        if tournament.phase == TournamentPhase.SWISS:
            advanced = [t for t in self.manager.get_teams()
                       if t.status.value == "advanced"]
            needed = self.manager.get_playoff_team_count()
            if len(advanced) < needed:
                self.start_playoff_btn.setEnabled(False)

    def _clear_bracket(self):
        self.bracket_scene.clear()
        self._match_widgets.clear()

    def _draw_bracket(self):
        self._clear_bracket()

        round_names = self.manager.get_playoff_round_names()
        if not round_names:
            return

        upper_rounds = [r for r in round_names if r.startswith("upper")]
        lower_rounds = [r for r in round_names if r.startswith("lower")]
        final_rounds = [r for r in round_names if r.startswith("grand")]

        col_width = 200
        row_height = 70
        match_height = 55
        col_spacing = 60
        start_x = 20
        start_y = 20

        total_cols = len(upper_rounds) + len(lower_rounds) + len(final_rounds)
        total_width = start_x + total_cols * (col_width + col_spacing) + 50

        max_rows = max(
            len(upper_rounds) > 0 and len(self.manager.get_playoff_matches_by_round(upper_rounds[0])) or 0,
            len(lower_rounds) > 0 and len(self.manager.get_playoff_matches_by_round(lower_rounds[0])) or 0
        )
        total_height = start_y + max_rows * row_height * 2 + 100

        self.bracket_scene.setSceneRect(0, 0, total_width, total_height)

        x = start_x
        for col_idx, round_name in enumerate(upper_rounds):
            matches = self.manager.get_playoff_matches_by_round(round_name)
            display_name = self.manager.get_round_display_name(round_name)

            label = QGraphicsSimpleTextItem(display_name)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            label.setPos(x, start_y - 25)
            label.setBrush(QColor(33, 150, 243))
            self.bracket_scene.addItem(label)

            y_offset = (max_rows - len(matches)) * row_height / 2
            for row_idx, match in enumerate(matches):
                y = start_y + y_offset + row_idx * row_height * 2

                team1_name = self.manager.get_team_name(match.team1_id) if match.team1_id else "待定"
                team2_name = self.manager.get_team_name(match.team2_id) if match.team2_id else "待定"

                item = BracketMatchItem(
                    x, y, col_width, match_height,
                    match, team1_name, team2_name
                )
                self.bracket_scene.addItem(item)
                self._match_widgets[f"{round_name}_{row_idx}"] = item

        x += col_width + col_spacing
        lower_x = x

        for col_idx, round_name in enumerate(lower_rounds):
            matches = self.manager.get_playoff_matches_by_round(round_name)
            if not matches:
                continue

            display_name = self.manager.get_round_display_name(round_name)

            label = QGraphicsSimpleTextItem(display_name)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            label.setPos(x, start_y - 25)
            label.setBrush(QColor(255, 87, 34))
            self.bracket_scene.addItem(label)

            y_offset = (max_rows - len(matches)) * row_height / 2
            for row_idx, match in enumerate(matches):
                y = start_y + y_offset + row_idx * row_height * 2

                team1_name = self.manager.get_team_name(match.team1_id) if match.team1_id else "待定"
                team2_name = self.manager.get_team_name(match.team2_id) if match.team2_id else "待定"

                item = BracketMatchItem(
                    x, y, col_width, match_height,
                    match, team1_name, team2_name
                )
                self.bracket_scene.addItem(item)
                self._match_widgets[f"{round_name}_{row_idx}"] = item

        x += col_width + col_spacing

        for round_name in final_rounds:
            matches = self.manager.get_playoff_matches_by_round(round_name)
            if not matches:
                continue

            display_name = self.manager.get_round_display_name(round_name)

            label = QGraphicsSimpleTextItem(display_name)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            label.setPos(x, start_y - 25)
            label.setBrush(QColor(156, 39, 176))
            self.bracket_scene.addItem(label)

            for row_idx, match in enumerate(matches):
                y = start_y + max_rows * row_height - match_height

                team1_name = self.manager.get_team_name(match.team1_id) if match.team1_id else "待定"
                team2_name = self.manager.get_team_name(match.team2_id) if match.team2_id else "待定"

                item = BracketMatchItem(
                    x, y, col_width, match_height,
                    match, team1_name, team2_name
                )
                self.bracket_scene.addItem(item)
                self._match_widgets[f"{round_name}_{row_idx}"] = item

    def _start_playoff(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            return

        advanced = [t for t in self.manager.get_teams()
                   if t.status.value == "advanced"]
        needed = self.manager.get_playoff_team_count()

        if len(advanced) < needed:
            QMessageBox.warning(
                self, "提示",
                f"还需要 {needed - len(advanced)} 支队伍晋级才能开始淘汰赛")
            return

        reply = QMessageBox.question(
            self, "确认开始淘汰赛",
            f"将有 {needed} 支队伍进入淘汰赛，确定要开始吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.manager.start_playoff()
                signals.data_changed.emit()
                signals.phase_changed.emit("playoff")
                QMessageBox.information(self, "成功", "淘汰赛对阵已生成！")
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _on_edit_match(self, match: Match):
        tournament = self.manager.get_tournament()
        if not tournament:
            return

        dialog = ScoreDialogPlayoff(self, match, tournament.playoff_format)
        if dialog.exec() == QDialog.Accepted:
            score1, score2 = dialog.get_scores()
            try:
                self.manager.record_match_result(match.id, score1, score2)
                signals.data_changed.emit()
                signals.standings_updated.emit()
                signals.matches_updated.emit()

                if self.manager.check_playoff_complete():
                    reply = QMessageBox.question(
                        self, "赛事完成",
                        "淘汰赛已全部完成！是否结束赛事？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        try:
                            self.manager.complete_tournament()
                            signals.data_changed.emit()
                            signals.phase_changed.emit("completed")
                            winner = self.manager.get_winner()
                            if winner:
                                QMessageBox.information(
                                    self, "恭喜！",
                                    f"赛事冠军是: {winner.name}！")
                        except TournamentError as e:
                            QMessageBox.warning(self, "错误", str(e))

            except ScoreValidationError as e:
                QMessageBox.warning(self, "比分无效", str(e))
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))
