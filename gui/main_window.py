import re
from typing import Dict

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt
from worker import HoleheWorker
from export import export_json, export_csv

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Holehe GUI")
        self.resize(800, 600)
        self._worker = None
        self._results = []
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Email input row
        email_layout = QHBoxLayout()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter email address")
        self.email_input.returnPressed.connect(self.start_scan)
        email_layout.addWidget(self.email_input)
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_scan)
        email_layout.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan)
        email_layout.addWidget(self.stop_btn)
        main_layout.addLayout(email_layout)

        # Progress bar and status label
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # will be set when scan starts
        progress_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)
        main_layout.addLayout(progress_layout)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Site",
            "Exists",
            "Email Recovery",
            "Phone",
            "Rate Limited",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.table)

        # Bottom controls
        bottom_layout = QHBoxLayout()
        self.dark_mode_cb = QCheckBox("Dark mode")
        self.dark_mode_cb.stateChanged.connect(self.toggle_dark_mode)
        bottom_layout.addWidget(self.dark_mode_cb)
        bottom_layout.addStretch()
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.clicked.connect(self.export_json)
        bottom_layout.addWidget(self.export_json_btn)
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self.export_csv)
        bottom_layout.addWidget(self.export_csv_btn)
        main_layout.addLayout(bottom_layout)

    def start_scan(self):
        email = self.email_input.text().strip()
        if not EMAIL_REGEX.match(email):
            QMessageBox.warning(self, "Invalid email", "Please enter a valid email address.")
            return
        # Disable UI controls
        self.start_btn.setEnabled(False)
        self.email_input.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setRange(0, 0)  # indeterminate until we know total
        self.status_label.setText("Starting scan…")
        self._results.clear()
        self.table.setRowCount(0)
        self.export_json_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)

        self._worker = HoleheWorker(email)
        self._worker.resultReady.connect(self.handle_result)
        self._worker.progress.connect(self.update_progress)
        self._worker.finished_ok.connect(self.scan_finished)
        self._worker.failed.connect(self.scan_failed)
        self._worker.start()

    def stop_scan(self):
        if self._worker:
            self._worker.stop()
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Cancelling…")

    def handle_result(self, result: Dict):
        # Store result
        self._results.append(result)
        # Default: only show rows where exists is True
        if result.get("exists"):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(result.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(result.get("exists", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(result.get("emailrecovery") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(result.get("phoneNumber") or ""))
            self.table.setItem(row, 4, QTableWidgetItem(str(result.get("rateLimit", ""))))
        # Enable export once we have at least one result
        if not self.export_json_btn.isEnabled():
            self.export_json_btn.setEnabled(True)
            self.export_csv_btn.setEnabled(True)

    def update_progress(self, completed: int, total: int):
        # Switch progress bar to determinate mode once total is known
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)
        self.status_label.setText(f"Checked {completed}/{total} sites")

    def scan_finished(self, results: list, elapsed: float):
        self._worker = None
        self.start_btn.setEnabled(True)
        self.email_input.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(f"Finished in {elapsed:.1f}s – {len([r for r in results if r.get('exists')])} hits")
        # Store final results (already in self._results)
        # Export buttons already enabled

    def scan_failed(self, message: str):
        QMessageBox.critical(self, "Scan failed", message)
        self._worker = None
        self.start_btn.setEnabled(True)
        self.email_input.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Ready")

    def toggle_dark_mode(self, state: int):
        if state == Qt.CheckState.Checked.value:
            # Simple dark stylesheet – can be expanded
            self.setStyleSheet("""
                QWidget { background-color: #2b2b2b; color: #f0f0f0; }
                QLineEdit, QTableWidget { background-color: #3c3c3c; }
                QPushButton { background-color: #444444; }
            """)
        else:
            self.setStyleSheet("")

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON", "results.json", "JSON Files (*.json)")
        if path:
            export_json(self._results, path)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "results.csv", "CSV Files (*.csv)")
        if path:
            export_csv(self._results, path)
