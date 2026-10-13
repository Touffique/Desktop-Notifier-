import sys
import sqlite3
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QDateTime
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDateTimeEdit,
    QComboBox, QFrame, QScrollArea, QSystemTrayIcon, QMenu,
    QMessageBox, QCheckBox
)

APP_NAME = "Desktop Notifier"
APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "focusbell.db"


def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                due_at TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Medium',
                completed INTEGER NOT NULL DEFAULT 0,
                notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)


def add_reminder(title, description, due_at, priority):
    with connect_db() as con:
        con.execute(
            """INSERT INTO reminders
               (title, description, due_at, priority, completed, notified, created_at)
               VALUES (?, ?, ?, ?, 0, 0, ?)""",
            (title, description, due_at, priority, datetime.now().isoformat(timespec="seconds"))
        )


def get_reminders(show_completed=False):
    with connect_db() as con:
        if show_completed:
            rows = con.execute(
                "SELECT * FROM reminders ORDER BY completed ASC, due_at ASC"
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM reminders WHERE completed = 0 ORDER BY due_at ASC"
            ).fetchall()
    return rows


def set_completed(reminder_id, completed=True):
    with connect_db() as con:
        con.execute(
            "UPDATE reminders SET completed = ?, notified = CASE WHEN ? = 1 THEN 1 ELSE notified END WHERE id = ?",
            (1 if completed else 0, 1 if completed else 0, reminder_id)
        )


def delete_reminder(reminder_id):
    with connect_db() as con:
        con.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


def due_reminders():
    now = datetime.now().isoformat(timespec="seconds")
    with connect_db() as con:
        rows = con.execute(
            """SELECT * FROM reminders
               WHERE completed = 0 AND notified = 0 AND due_at <= ?
               ORDER BY due_at ASC""", (now,)
        ).fetchall()
        if rows:
            con.executemany(
                "UPDATE reminders SET notified = 1 WHERE id = ?",
                [(row["id"],) for row in rows]
            )
    return rows


class ReminderCard(QFrame):
    def __init__(self, reminder, on_complete, on_delete, parent=None):
        super().__init__(parent)
        self.reminder = reminder
        self.setObjectName("ReminderCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(12)

        left = QVBoxLayout()
        title = QLabel(reminder["title"])
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        left.addWidget(title)

        due = datetime.fromisoformat(reminder["due_at"])
        due_label = QLabel("Due: " + due.strftime("%a, %d %b %Y · %I:%M %p"))
        due_label.setObjectName("Muted")
        left.addWidget(due_label)

        if reminder["description"]:
            desc = QLabel(reminder["description"])
            desc.setObjectName("Muted")
            desc.setWordWrap(True)
            left.addWidget(desc)

        priority = QLabel("Priority: " + reminder["priority"])
        priority.setObjectName("Priority")
        left.addWidget(priority)
        outer.addLayout(left, 1)

        actions = QVBoxLayout()
        complete_btn = QPushButton("✓ Done")
        complete_btn.setObjectName("SmallButton")
        complete_btn.clicked.connect(lambda: on_complete(reminder["id"]))
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(lambda: on_delete(reminder["id"]))
        actions.addWidget(complete_btn)
        actions.addWidget(delete_btn)
        actions.addStretch()
        outer.addLayout(actions)


class FocusBellWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FocusBell")
        self.resize(1000, 700)
        self.setMinimumSize(780, 560)
        self._quitting = False

        self.build_ui()
        self.setup_tray()
        self.refresh_reminders()

        self.scheduler = QTimer(self)
        self.scheduler.setInterval(5000)
        self.scheduler.timeout.connect(self.check_due_reminders)
        self.scheduler.start()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(225)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 24, 18, 22)
        side.setSpacing(14)

        brand = QLabel("◉  FocusBell")
        brand.setObjectName("Brand")
        side.addWidget(brand)

        tagline = QLabel("Make time count.")
        tagline.setObjectName("Muted")
        side.addWidget(tagline)
        side.addSpacing(22)

        nav = QLabel("WORKSPACE")
        nav.setObjectName("SectionLabel")
        side.addWidget(nav)
        current = QLabel("▣   My reminders")
        current.setObjectName("NavCurrent")
        side.addWidget(current)

        side.addStretch()
        tip = QLabel("TIP\nKeep reminders specific.\n“Practice linked lists for 30 min” beats “Study”.")
        tip.setObjectName("Tip")
        tip.setWordWrap(True)
        side.addWidget(tip)

        version = QLabel("MVP  ·  Local-only")
        version.setObjectName("Muted")
        side.addWidget(version)
        root.addWidget(sidebar)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(18)

        header = QHBoxLayout()
        heading_box = QVBoxLayout()
        heading = QLabel("My reminders")
        heading.setObjectName("PageTitle")
        subheading = QLabel("Your study sessions, coding goals and deadlines in one place.")
        subheading.setObjectName("Muted")
        heading_box.addWidget(heading)
        heading_box.addWidget(subheading)
        header.addLayout(heading_box, 1)

        self.hide_button = QPushButton("⌄  Minimize to tray")
        self.hide_button.setObjectName("SecondaryButton")
        self.hide_button.clicked.connect(self.hide)
        header.addWidget(self.hide_button)
        main.addLayout(header)

        form_card = QFrame()
        form_card.setObjectName("FormCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(10)

        form_title = QLabel("＋  Create a reminder")
        form_title.setObjectName("CardTitle")
        form_layout.addWidget(form_title)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("What do you need to do?  e.g. Revise binary trees")
        form_layout.addWidget(self.title_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional notes")
        self.description_input.setFixedHeight(58)
        form_layout.addWidget(self.description_input)

        row = QHBoxLayout()
        self.datetime_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.datetime_input.setCalendarPopup(True)
        self.datetime_input.setDisplayFormat("ddd, dd MMM yyyy   hh:mm AP")
        self.datetime_input.setMinimumDateTime(QDateTime.currentDateTime())
        row.addWidget(self.datetime_input, 2)

        self.priority_input = QComboBox()
        self.priority_input.addItems(["Low", "Medium", "High"])
        self.priority_input.setCurrentText("Medium")
        row.addWidget(self.priority_input, 1)

        self.add_button = QPushButton("Add reminder")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.clicked.connect(self.create_reminder)
        row.addWidget(self.add_button)
        form_layout.addLayout(row)
        main.addWidget(form_card)

        list_header = QHBoxLayout()
        list_title = QLabel("Upcoming and overdue")
        list_title.setObjectName("SectionTitle")
        list_header.addWidget(list_title)
        list_header.addStretch()
        self.show_completed = QCheckBox("Show completed")
        self.show_completed.stateChanged.connect(self.refresh_reminders)
        list_header.addWidget(self.show_completed)
        main.addLayout(list_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(2, 2, 6, 2)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_container)
        main.addWidget(self.scroll, 1)

        self.status_label = QLabel("Reminders are saved locally on this computer.")
        self.status_label.setObjectName("Muted")
        main.addWidget(self.status_label)

        root.addWidget(content, 1)
        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background: #11131a;
                color: #edf0f7;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            #Sidebar { background: #171a23; border-right: 1px solid #292d3a; }
            #Brand { font-size: 19pt; font-weight: 700; color: #b9a5ff; }
            #PageTitle { font-size: 23pt; font-weight: 700; }
            #SectionTitle { font-size: 13pt; font-weight: 650; }
            #SectionLabel { color: #858ba0; font-size: 8pt; font-weight: 700; }
            #NavCurrent { background: #2b2542; color: #d7cbff; padding: 10px; border-radius: 8px; }
            #Muted { color: #969caf; font-size: 9pt; }
            #Tip { background: #202330; color: #b7bdd0; padding: 12px; border-radius: 8px; }
            #FormCard, #ReminderCard { background: #1a1d27; border: 1px solid #2b3040; border-radius: 12px; }
            #CardTitle { font-size: 11pt; font-weight: 650; }
            #Priority { color: #b9a5ff; font-size: 9pt; }
            QLineEdit, QTextEdit, QDateTimeEdit, QComboBox {
                background: #10121a; border: 1px solid #353a4b; border-radius: 7px;
                padding: 9px; selection-background-color: #7056c9;
            }
            QLineEdit:focus, QTextEdit:focus, QDateTimeEdit:focus, QComboBox:focus { border: 1px solid #9b83ff; }
            QPushButton { border: 0; border-radius: 7px; padding: 9px 12px; font-weight: 600; }
            #PrimaryButton { background: #8b72ef; color: #ffffff; }
            #PrimaryButton:hover { background: #9a85f5; }
            #SecondaryButton, #SmallButton { background: #2b3040; color: #e7e9f2; }
            #SecondaryButton:hover, #SmallButton:hover { background: #383e52; }
            #DangerButton { background: #3b232b; color: #ffb5c0; }
            #DangerButton:hover { background: #55303b; }
            QCheckBox { color: #b4bacb; spacing: 7px; }
            QScrollArea { background: transparent; }
            QScrollBar:vertical { background: #151821; width: 9px; margin: 0; }
            QScrollBar::handle:vertical { background: #41465a; border-radius: 4px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QMenu { background: #202330; border: 1px solid #353a4b; padding: 5px; }
            QMenu::item { padding: 7px 24px; border-radius: 4px; }
            QMenu::item:selected { background: #3a3158; }
        """)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("FocusBell — reminders")
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation))
        menu = QMenu()
        show_action = QAction("Open FocusBell", self)
        show_action.triggered.connect(self.show_and_raise)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("Quit FocusBell", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_and_raise()

    def show_and_raise(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def create_reminder(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Title required", "Enter a title for your reminder.")
            self.title_input.setFocus()
            return

        due_qdt = self.datetime_input.dateTime()
        if due_qdt < QDateTime.currentDateTime():
            QMessageBox.warning(self, "Choose a future time", "The reminder time has already passed.")
            return

        due_at = due_qdt.toPython().isoformat(timespec="seconds")
        add_reminder(title, self.description_input.toPlainText().strip(),
                     due_at, self.priority_input.currentText())

        self.title_input.clear()
        self.description_input.clear()
        self.datetime_input.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.priority_input.setCurrentText("Medium")
        self.refresh_reminders()
        self.status_label.setText("Reminder saved successfully.")

    def refresh_reminders(self, *_):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        rows = get_reminders(self.show_completed.isChecked())
        now = datetime.now()
        if not rows:
            empty = QLabel("You're all clear. Add a reminder above to get started.")
            empty.setObjectName("Muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(110)
            self.cards_layout.addWidget(empty)
        else:
            for row in rows:
                card = ReminderCard(row, self.complete_reminder, self.remove_reminder)
                if not row["completed"] and datetime.fromisoformat(row["due_at"]) < now:
                    card.setStyleSheet("#ReminderCard { border: 1px solid #87505a; }")
                if row["completed"]:
                    card.setWindowOpacity(0.75)
                self.cards_layout.addWidget(card)
        self.cards_layout.addStretch()

        active = len([r for r in rows if not r["completed"]])
        self.status_label.setText(f"{active} active reminder(s) · Saved locally in focusbell.db")

    def complete_reminder(self, reminder_id):
        set_completed(reminder_id, True)
        self.refresh_reminders()

    def remove_reminder(self, reminder_id):
        answer = QMessageBox.question(
            self, "Delete reminder", "Delete this reminder permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_reminder(reminder_id)
            self.refresh_reminders()

    def check_due_reminders(self):
        rows = due_reminders()
        for row in rows:
            due = datetime.fromisoformat(row["due_at"])
            message = row["title"]
            if row["description"]:
                message += "\n" + row["description"]
            if self.tray.isVisible():
                self.tray.showMessage(
                    "FocusBell reminder",
                    message,
                    QSystemTrayIcon.MessageIcon.Information,
                    10000
                )
            else:
                QMessageBox.information(self, "FocusBell reminder", message)
        if rows:
            self.refresh_reminders()

    def closeEvent(self, event):
        if self._quitting:
            self.tray.hide()
            event.accept()
        else:
            event.ignore()
            self.hide()
            if self.tray.isVisible():
                self.tray.showMessage(
                    "FocusBell is still running",
                    "The window was hidden. Use the tray icon to reopen or quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3500
                )

    def quit_app(self):
        self._quitting = True
        self.scheduler.stop()
        self.tray.hide()
        QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    init_db()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(
            None, "System tray unavailable",
            "Windows system tray was not detected. The app can still run, but tray controls may not work."
        )

    window = FocusBellWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
