"""
Aura — Budget Page
Budget setup (SLA configuration) and live pacing monitor.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton,
    QFrame, QScrollArea, QProgressBar, QSizePolicy,
    QGridLayout
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard, StatCard
from ui.components.modern_button import ModernButton


class BudgetPage(QWidget):
    """Budget page — cost pacing setup and live monitoring."""

    pacing_start_requested = Signal(float, float, bool)   # budget, hours, eco_mode
    pacing_stop_requested = Signal()
    preflight_requested = Signal(int, int)                 # estimated_tasks, avg_tokens

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pacing_active = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("budgetScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # ─── Header ───────────────────────────────────────────────
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        title = QLabel("Budget & Pacing")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Cost-aware time pacing for guaranteed uptime")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        layout.addLayout(header_text)

        # ─── Section 1: Budget Configuration ──────────────────────
        setup_card = GlassCard()
        setup_card_layout = setup_card.get_layout()
        setup_hdr = QLabel("Budget Configuration")
        setup_hdr.setObjectName("cardHeader")
        setup_card_layout.addWidget(setup_hdr)
        setup_layout = QVBoxLayout()
        setup_layout.setSpacing(14)

        # Budget + Time row
        budget_row = QHBoxLayout()
        budget_row.setSpacing(10)

        budget_lbl = QLabel("Budget")
        budget_lbl.setObjectName("formLabel")
        budget_row.addWidget(budget_lbl)

        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setObjectName("budgetInput")
        self.budget_spin.setRange(0.50, 999.99)
        self.budget_spin.setValue(20.00)
        self.budget_spin.setPrefix("$")
        self.budget_spin.setDecimals(2)
        self.budget_spin.setSingleStep(1.0)
        self.budget_spin.setMinimumWidth(90)
        budget_row.addWidget(self.budget_spin)

        budget_row.addSpacing(10)

        time_lbl = QLabel("Window")
        time_lbl.setObjectName("formLabel")
        budget_row.addWidget(time_lbl)

        self.time_spin = QDoubleSpinBox()
        self.time_spin.setObjectName("budgetInput")
        self.time_spin.setRange(1.0, 720.0)
        self.time_spin.setValue(24.0)
        self.time_spin.setDecimals(1)
        self.time_spin.setSuffix(" hrs")
        self.time_spin.setSingleStep(1.0)
        self.time_spin.setMinimumWidth(90)
        self.time_spin.valueChanged.connect(self._update_time_display)
        budget_row.addWidget(self.time_spin)

        self.time_display = QLabel("= 1.0 days")
        self.time_display.setObjectName("mutedText")
        budget_row.addWidget(self.time_display)

        budget_row.addSpacing(10)

        tasks_lbl = QLabel("Tasks")
        tasks_lbl.setObjectName("formLabel")
        budget_row.addWidget(tasks_lbl)

        self.tasks_spin = QSpinBox()
        self.tasks_spin.setObjectName("budgetInput")
        self.tasks_spin.setRange(1, 100000)
        self.tasks_spin.setValue(200)
        self.tasks_spin.setMinimumWidth(80)
        budget_row.addWidget(self.tasks_spin)

        budget_row.addStretch()
        setup_layout.addLayout(budget_row)

        # Eco-mode row
        eco_row = QHBoxLayout()
        self.eco_check = QCheckBox("Eco-Mode (Dynamic Downgrading)")
        self.eco_check.setChecked(True)
        eco_row.addWidget(self.eco_check)
        eco_row.addStretch()
        setup_layout.addLayout(eco_row)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.preflight_btn = ModernButton("Pre-Flight Check", "secondary")
        self.preflight_btn.clicked.connect(self._on_preflight)
        btn_row.addWidget(self.preflight_btn)

        self.activate_btn = ModernButton("Activate Pacing", "primary")
        self.activate_btn.clicked.connect(self._on_toggle_pacing)
        btn_row.addWidget(self.activate_btn)

        btn_row.addStretch()
        setup_layout.addLayout(btn_row)

        # Pre-flight result area
        self.preflight_label = QLabel("")
        self.preflight_label.setObjectName("preflightResult")
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setVisible(False)
        setup_layout.addWidget(self.preflight_label)

        setup_card_layout.addLayout(setup_layout)
        layout.addWidget(setup_card)

        # ─── Section 2: Live Pacing Monitor ───────────────────────
        monitor_card = GlassCard()
        monitor_card_layout = monitor_card.get_layout()
        monitor_hdr = QLabel("Active Pacing Monitor")
        monitor_hdr.setObjectName("cardHeader")
        monitor_card_layout.addWidget(monitor_hdr)
        monitor_layout = QVBoxLayout()
        monitor_layout.setSpacing(14)

        # Stat cards grid (2×2)
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.remaining_card = StatCard("$0.00", "REMAINING", accent="blue")
        stats_grid.addWidget(self.remaining_card, 0, 0)

        self.burn_rate_card = StatCard("$0.00/hr", "BURN RATE", accent="purple")
        stats_grid.addWidget(self.burn_rate_card, 0, 1)

        self.runway_card = StatCard("0.0 hrs", "RUNWAY", accent="green")
        stats_grid.addWidget(self.runway_card, 1, 0)

        self.tier_card = StatCard("Sonnet", "CURRENT TIER", accent="orange")
        stats_grid.addWidget(self.tier_card, 1, 1)

        monitor_layout.addLayout(stats_grid)

        # Budget progress bar
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        progress_lbl = QLabel("Budget Usage")
        progress_lbl.setObjectName("formLabel")
        progress_row.addWidget(progress_lbl)

        self.budget_progress = QProgressBar()
        self.budget_progress.setObjectName("pacingProgressBar")
        self.budget_progress.setRange(0, 100)
        self.budget_progress.setValue(0)
        self.budget_progress.setTextVisible(True)
        self.budget_progress.setFormat("%p% spent")
        self.budget_progress.setFixedHeight(24)
        progress_row.addWidget(self.budget_progress, stretch=1)

        monitor_layout.addLayout(progress_row)

        # Rate comparison (2×2 grid)
        rate_grid = QGridLayout()
        rate_grid.setSpacing(10)

        self.actual_rate_lbl = QLabel("Actual: $0.00/hr")
        self.actual_rate_lbl.setObjectName("formLabel")
        rate_grid.addWidget(self.actual_rate_lbl, 0, 0)

        self.target_rate_lbl = QLabel("Target: $0.00/hr")
        self.target_rate_lbl.setObjectName("mutedText")
        rate_grid.addWidget(self.target_rate_lbl, 0, 1)

        self.elapsed_lbl = QLabel("Elapsed: 0.0 hrs")
        self.elapsed_lbl.setObjectName("mutedText")
        rate_grid.addWidget(self.elapsed_lbl, 1, 0)

        self.remaining_time_lbl = QLabel("Remaining: 0.0 hrs")
        self.remaining_time_lbl.setObjectName("mutedText")
        rate_grid.addWidget(self.remaining_time_lbl, 1, 1)

        monitor_layout.addLayout(rate_grid)

        # Status badge
        self.status_badge = QLabel("  Inactive  ")
        self.status_badge.setObjectName("badgeInfo")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedHeight(28)
        monitor_layout.addWidget(self.status_badge, alignment=Qt.AlignmentFlag.AlignLeft)

        monitor_card_layout.addLayout(monitor_layout)
        layout.addWidget(monitor_card)

        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── Slots ─────────────────────────────────────────────────────

    def _update_time_display(self, hours: float):
        days = hours / 24.0
        self.time_display.setText(f"= {days:.1f} days")

    def _on_preflight(self):
        self.preflight_label.setVisible(False)
        self.preflight_requested.emit(
            self.tasks_spin.value(),
            500,  # avg_tokens default
        )

    def _on_toggle_pacing(self):
        if self._pacing_active:
            self.pacing_stop_requested.emit()
        else:
            self.pacing_start_requested.emit(
                self.budget_spin.value(),
                self.time_spin.value(),
                self.eco_check.isChecked(),
            )

    # ─── Public slots (called by controller signals) ──────────────

    def update_pacing_status(self, status: dict):
        """Update all monitoring widgets with latest pacing data."""
        active = status.get("active", False)
        self._pacing_active = active

        # Toggle button text
        self.activate_btn.setText("Deactivate Pacing" if active else "Activate Pacing")

        # Stat cards
        remaining = status.get("remaining_usd", 0)
        self.remaining_card.set_value(f"${remaining:.2f}")

        burn = status.get("burn_rate_actual", 0)
        self.burn_rate_card.set_value(f"${burn:.4f}/hr")

        runway = status.get("projected_runway_hours", 0)
        self.runway_card.set_value(f"{runway:.1f} hrs")

        tier = status.get("current_max_tier", "sonnet").title()
        self.tier_card.set_value(tier)

        # Progress bar
        percent = status.get("percent_spent", 0)
        self.budget_progress.setValue(int(min(percent, 100)))

        # Rate labels
        self.actual_rate_lbl.setText(f"Actual: ${burn:.4f}/hr")
        target = status.get("burn_rate_target", 0)
        self.target_rate_lbl.setText(f"Target: ${target:.4f}/hr")
        elapsed = status.get("elapsed_hours", 0)
        self.elapsed_lbl.setText(f"Elapsed: {elapsed:.1f} hrs")
        rem_time = status.get("remaining_hours", 0)
        self.remaining_time_lbl.setText(f"Remaining: {rem_time:.1f} hrs")

        # Status badge
        st = status.get("status", "inactive")
        on_track = status.get("on_track", True)

        if st == "inactive":
            self.status_badge.setText("  Inactive  ")
            self.status_badge.setObjectName("badgeInfo")
        elif st == "paused":
            self.status_badge.setText("  Paused  ")
            self.status_badge.setObjectName("badgeWarning")
        elif st == "expired":
            self.status_badge.setText("  Expired  ")
            self.status_badge.setObjectName("badgeDanger")
        elif on_track:
            self.status_badge.setText("  On Track  ")
            self.status_badge.setObjectName("badgeSuccess")
        else:
            self.status_badge.setText("  Pacing Tight  ")
            self.status_badge.setObjectName("badgeWarning")

        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def show_preflight_result(self, result: dict):
        """Display pre-flight check result."""
        feasible = result.get("feasible", False)
        message = result.get("message", "")
        self.preflight_label.setText(message)
        self.preflight_label.setVisible(True)

        if feasible:
            self.preflight_label.setObjectName("preflightResultOk")
        else:
            self.preflight_label.setObjectName("preflightResultWarning")

        self.preflight_label.style().unpolish(self.preflight_label)
        self.preflight_label.style().polish(self.preflight_label)

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
