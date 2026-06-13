from PySide6.QtCore import QObject, Signal


class TournamentSignals(QObject):
    data_changed = Signal()
    tournament_changed = Signal(int)
    standings_updated = Signal()
    matches_updated = Signal()
    phase_changed = Signal(str)

    def __init__(self):
        super().__init__()


signals = TournamentSignals()
