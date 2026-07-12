"""
Aura — Suppression List Page
Global email/domain suppression management with add, import, and delete.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QFrame,
    QHeaderView, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.icons import get_icon
from PySide6.QtCore import QSize
from utils.logger import get_logger

logger = get_logger("suppression_page")


class SuppressionPage(QWidget):
    """UI for managing the global suppression list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppression_engine = None
        self._build_ui()

    def set_engine(self, suppression_engine):
        """Set the suppression engine for data operations."""
        self._suppression_engine = suppression_engine
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(26)

        # ─── Header ───────────────────────────────────────────────
        header_layout = QHBoxLayout()

        header_left = QVBoxLayout()
        header_left.setSpacing(4)
        title = QLabel("Suppression List")
        title.setObjectName("sectionHeader")
        header_left.addWidget(title)

        subtitle = QLabel("Suppress emails to specific addresses or entire domains")
        subtitle.setObjectName("sectionSubheader")
        header_left.addWidget(subtitle)

        header_layout.addLayout(header_left)
        header_layout.addStretch()

        # Count badge
        self.count_label = QLabel("0 entries")
        self.count_label.setObjectName("badgeWarning")
        header_layout.addWidget(self.count_label)

        layout.addLayout(header_layout)

        # ─── Add Entry Card ───────────────────────────────────────
        add_card = GlassCard()
        add_layout = add_card.get_layout()  # Use the card's built-in layout
        add_layout.setSpacing(0)

        add_row = QHBoxLayout()
        add_row.setSpacing(12)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Email", "Domain"])
        self.type_combo.setFixedWidth(110)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Enter email or domain…")
        self.value_input.returnPressed.connect(self._add_entry)

        add_btn = ModernButton("+ Add", "primary")
        add_btn.setFixedWidth(90)
        add_btn.setFixedHeight(40)  # Match input height
        add_btn.clicked.connect(self._add_entry)

        import_btn = ModernButton("Import CSV", "secondary")
        import_btn.setIcon(get_icon("import_csv", "dark"))
        import_btn.setIconSize(QSize(16, 16))
        import_btn.setFixedHeight(40)  # Match input height
        import_btn.clicked.connect(self._import_csv)

        add_row.addWidget(self.type_combo)
        add_row.addWidget(self.value_input, 1)
        add_row.addWidget(add_btn)
        add_row.addWidget(import_btn)
        add_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Precision alignment

        add_layout.addLayout(add_row)

        layout.addWidget(add_card)

        # ─── Table ────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Email", "Domain", "Reason", "Added At"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 120)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        layout.addWidget(self.table)

        # ─── Bottom Actions ───────────────────────────────────────
        bottom_layout = QHBoxLayout()

        self.refresh_btn = ModernButton("Refresh", "secondary")
        self.refresh_btn.setIcon(get_icon("refresh", "dark"))
        self.refresh_btn.setIconSize(QSize(14, 14))
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self._refresh_table)

        self.delete_btn = ModernButton("Delete Selected", "danger")
        self.delete_btn.setIcon(get_icon("delete", "dark"))
        self.delete_btn.setIconSize(QSize(14, 14))
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.clicked.connect(self._delete_selected)

        bottom_layout.addWidget(self.refresh_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.delete_btn)

        layout.addLayout(bottom_layout)

    def _add_entry(self):
        """Add a single suppression entry."""
        if not self._suppression_engine:
            return

        value = self.value_input.text().strip()
        if not value:
            return

        entry_type = self.type_combo.currentText().lower()
        email = value if entry_type == "email" else None
        domain = value if entry_type == "domain" else None

        result = self._suppression_engine.add_suppression(
            email=email, domain=domain, reason="manual"
        )

        if result.get("success"):
            self.value_input.clear()
            self._refresh_table()
        else:
            QMessageBox.warning(self, "Error", result.get("error", "Failed to add entry"))

    def _import_csv(self):
        """Import entries from a CSV file."""
        if not self._suppression_engine:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Suppression CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        result = self._suppression_engine.bulk_import_from_csv(file_path)

        if result.get("success"):
            data = result.get("data", {})
            QMessageBox.information(
                self, "Import Complete",
                f"Imported: {data.get('imported', 0)}\n"
                f"Skipped: {data.get('skipped', 0)}"
            )
            self._refresh_table()
        else:
            QMessageBox.warning(self, "Import Failed", result.get("error", "Unknown error"))

    def _delete_selected(self):
        """Delete selected suppression entries."""
        if not self._suppression_engine:
            return

        selected = self.table.selectedItems()
        if not selected:
            return

        rows = set()
        for item in selected:
            rows.add(item.row())

        for row in rows:
            id_item = self.table.item(row, 0)
            if id_item:
                try:
                    entry_id = int(id_item.text())
                    self._suppression_engine.remove_suppression(entry_id)
                except (ValueError, AttributeError):
                    pass

        self._refresh_table()

    def _refresh_table(self):
        """Reload the table from the database."""
        if not self._suppression_engine:
            return

        entries = self._suppression_engine.get_all_entries()
        self.table.setRowCount(len(entries))
        self.count_label.setText(f"{len(entries)} entries")

        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("email", "") or ""))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("domain", "") or ""))
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("reason", "")))
            self.table.setItem(row, 4, QTableWidgetItem(entry.get("added_at", "")))

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
