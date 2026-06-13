from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from app.models.models import TeamStanding, TournamentPhase
from app.logic.tournament_manager import TournamentManager
from app.ui.signals import signals


class StandingsPanel(QWidget):
    def __init__(self, manager: TournamentManager):
        super().__init__()
        self.manager = manager
        self._standings: List[TeamStanding] = []
        self._init_ui()
        self._connect_signals()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("实时积分榜")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.export_btn = QPushButton("刷新排名")
        self.export_btn.setMinimumHeight(30)
        header_layout.addWidget(self.export_btn)

        layout.addLayout(header_layout)

        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_layout = QHBoxLayout(info_frame)

        self.info_label = QLabel(
            "排名规则: 胜场 > Median-Buchholz > Buchholz > 相互胜负 > 对手胜率 > 得分")
        self.info_label.setStyleSheet("font-size: 12px; color: #666;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()

        layout.addWidget(info_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "排名", "种子", "队伍", "胜", "负", "战绩",
            "Median-Buchholz", "Buchholz", "相互胜负", "状态"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget::item { padding: 4px; }
            QHeaderView::section { padding: 6px; font-weight: bold; }
        """)

        layout.addWidget(self.table, 1)

        summary_layout = QHBoxLayout()
        self.summary_label = QLabel("共 0 支队伍")
        self.summary_label.setStyleSheet("font-size: 12px; color: #666;")
        summary_layout.addWidget(self.summary_label)

        self.advanced_label = QLabel("已晋级: 0")
        self.advanced_label.setStyleSheet("font-size: 12px; color: green;")
        summary_layout.addWidget(self.advanced_label)

        self.eliminated_label = QLabel("已淘汰: 0")
        self.eliminated_label.setStyleSheet("font-size: 12px; color: red;")
        summary_layout.addWidget(self.eliminated_label)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

    def _connect_signals(self):
        self.export_btn.clicked.connect(self.refresh)
        signals.data_changed.connect(self.refresh)
        signals.standings_updated.connect(self.refresh)

    def refresh(self):
        tournament = self.manager.get_tournament()
        if not tournament:
            self.table.setRowCount(0)
            self.summary_label.setText("共 0 支队伍")
            return

        self._standings = self.manager.calculate_standings()
        self.table.setRowCount(len(self._standings))

        advanced_count = 0
        eliminated_count = 0

        for row, standing in enumerate(self._standings):
            team = standing.team

            rank_item = QTableWidgetItem(str(standing.rank))
            rank_item.setTextAlignment(Qt.AlignCenter)

            seed_item = QTableWidgetItem(str(team.seed))
            seed_item.setTextAlignment(Qt.AlignCenter)

            name_item = QTableWidgetItem(team.name)

            wins_item = QTableWidgetItem(str(team.wins))
            wins_item.setTextAlignment(Qt.AlignCenter)

            losses_item = QTableWidgetItem(str(team.losses))
            losses_item.setTextAlignment(Qt.AlignCenter)

            record_text = f"{team.wins}-{team.losses}"
            record_item = QTableWidgetItem(record_text)
            record_item.setTextAlignment(Qt.AlignCenter)

            mb_item = QTableWidgetItem(str(int(standing.median_buchholz)))
            mb_item.setTextAlignment(Qt.AlignCenter)

            b_item = QTableWidgetItem(str(int(standing.buchholz)))
            b_item.setTextAlignment(Qt.AlignCenter)

            h2h_item = QTableWidgetItem(str(standing.head_to_head_wins))
            h2h_item.setTextAlignment(Qt.AlignCenter)

            status_text, status_color = self._get_status_info(team.status.value)
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row, 0, rank_item)
            self.table.setItem(row, 1, seed_item)
            self.table.setItem(row, 2, name_item)
            self.table.setItem(row, 3, wins_item)
            self.table.setItem(row, 4, losses_item)
            self.table.setItem(row, 5, record_item)
            self.table.setItem(row, 6, mb_item)
            self.table.setItem(row, 7, b_item)
            self.table.setItem(row, 8, h2h_item)
            self.table.setItem(row, 9, status_item)

            if team.status.value == "advanced":
                advanced_count += 1
                bg_color = QColor(232, 245, 233)
            elif team.status.value == "eliminated":
                eliminated_count += 1
                bg_color = QColor(255, 235, 238)
            else:
                bg_color = None

            if bg_color:
                for col in range(10):
                    self.table.item(row, col).setBackground(bg_color)

            if standing.rank == 1 and tournament.phase == TournamentPhase.COMPLETED:
                for col in range(10):
                    item = self.table.item(row, col)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(QColor(255, 248, 225))

        self.summary_label.setText(f"共 {len(self._standings)} 支队伍")
        self.advanced_label.setText(f"已晋级: {advanced_count}")
        self.eliminated_label.setText(f"已淘汰: {eliminated_count}")

    def _get_status_info(self, status: str):
        status_map = {
            "active": ("活跃", "#333"),
            "advanced": ("已晋级", "#2e7d32"),
            "eliminated": ("已淘汰", "#c62828")
        }
        return status_map.get(status, (status, "#333"))
