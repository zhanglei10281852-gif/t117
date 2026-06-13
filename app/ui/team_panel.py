from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QSpinBox, QLabel,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt
from app.models.models import Team, TournamentPhase
from app.logic.tournament_manager import TournamentManager, TournamentError
from app.ui.signals import signals


class TeamDialog(QDialog):
    def __init__(self, parent=None, team: Optional[Team] = None,
                 existing_seeds: Optional[list] = None):
        super().__init__(parent)
        self.setWindowTitle("编辑队伍" if team else "添加队伍")
        self.setMinimumWidth(300)
        self._existing_seeds = existing_seeds or []
        self._original_seed = team.seed if team else None

        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入队伍名称")
        if team:
            self.name_edit.setText(team.name)

        self.seed_spin = QSpinBox()
        self.seed_spin.setMinimum(1)
        self.seed_spin.setMaximum(999)
        if team:
            self.seed_spin.setValue(team.seed)

        layout.addRow("队伍名称:", self.name_edit)
        layout.addRow("种子排名:", self.seed_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        name = self.name_edit.text().strip()
        seed = self.seed_spin.value()
        return name, seed

    def accept(self):
        name, seed = self.get_data()
        if not name:
            QMessageBox.warning(self, "提示", "队伍名称不能为空")
            return
        if seed != self._original_seed and seed in self._existing_seeds:
            QMessageBox.warning(self, "提示", f"种子排名 {seed} 已存在")
            return
        super().accept()


class TeamPanel(QWidget):
    def __init__(self, manager: TournamentManager):
        super().__init__()
        self.manager = manager
        self._init_ui()
        self._connect_signals()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("队伍管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加队伍")
        self.edit_btn = QPushButton("编辑队伍")
        self.delete_btn = QPushButton("删除队伍")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "种子", "队伍名称", "胜场", "败场", "状态"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        info_layout = QHBoxLayout()
        self.count_label = QLabel("当前队伍数: 0")
        info_layout.addWidget(self.count_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

    def _connect_signals(self):
        self.add_btn.clicked.connect(self._add_team)
        self.edit_btn.clicked.connect(self._edit_team)
        self.delete_btn.clicked.connect(self._delete_team)
        self.table.doubleClicked.connect(self._edit_team)
        signals.data_changed.connect(self.refresh)

    def refresh(self):
        teams = self.manager.get_teams()
        self.table.setRowCount(len(teams))

        for row, team in enumerate(teams):
            seed_item = QTableWidgetItem(str(team.seed))
            seed_item.setTextAlignment(Qt.AlignCenter)
            seed_item.setData(Qt.UserRole, team.id)

            name_item = QTableWidgetItem(team.name)

            wins_item = QTableWidgetItem(str(team.wins))
            wins_item.setTextAlignment(Qt.AlignCenter)

            losses_item = QTableWidgetItem(str(team.losses))
            losses_item.setTextAlignment(Qt.AlignCenter)

            status_text = self._get_status_text(team.status.value)
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row, 0, seed_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, wins_item)
            self.table.setItem(row, 3, losses_item)
            self.table.setItem(row, 4, status_item)

            if team.status.value == "advanced":
                for col in range(5):
                    self.table.item(row, col).setBackground(Qt.green)
            elif team.status.value == "eliminated":
                for col in range(5):
                    self.table.item(row, col).setBackground(Qt.red)

        self.count_label.setText(f"当前队伍数: {len(teams)}")
        self._update_button_states()

    def _get_status_text(self, status: str) -> str:
        status_map = {
            "active": "活跃",
            "advanced": "已晋级",
            "eliminated": "已淘汰"
        }
        return status_map.get(status, status)

    def _update_button_states(self):
        tournament = self.manager.get_tournament()
        can_edit = (tournament is not None and
                    tournament.phase == TournamentPhase.SETUP)

        self.add_btn.setEnabled(can_edit)
        self.edit_btn.setEnabled(can_edit and self.table.currentRow() >= 0)
        self.delete_btn.setEnabled(can_edit and self.table.currentRow() >= 0)

    def _get_current_team_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        return None

    def _get_existing_seeds(self) -> list:
        teams = self.manager.get_teams()
        return [t.seed for t in teams]

    def _add_team(self):
        existing_seeds = self._get_existing_seeds()
        dialog = TeamDialog(self, existing_seeds=existing_seeds)
        if dialog.exec() == QDialog.Accepted:
            name, seed = dialog.get_data()
            try:
                self.manager.add_team(name, seed)
                signals.data_changed.emit()
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _edit_team(self):
        team_id = self._get_current_team_id()
        if not team_id:
            return

        from app.database.crud_team import get_team
        team = get_team(team_id)
        if not team:
            return

        existing_seeds = [s for s in self._get_existing_seeds() if s != team.seed]
        dialog = TeamDialog(self, team=team, existing_seeds=existing_seeds)
        if dialog.exec() == QDialog.Accepted:
            name, seed = dialog.get_data()
            try:
                self.manager.update_team(team_id, name, seed)
                signals.data_changed.emit()
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _delete_team(self):
        team_id = self._get_current_team_id()
        if not team_id:
            return

        from app.database.crud_team import get_team
        team = get_team(team_id)
        if not team:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除队伍「{team.name}」吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.manager.delete_team(team_id)
                signals.data_changed.emit()
            except TournamentError as e:
                QMessageBox.warning(self, "错误", str(e))
