"""
Configuration dock — QGIS-style dockable panel on the left.

Holds all study-site settings and the GEE initialisation button.
Writes directly to the shared `state` object and emits signals so the
main window status bar and tabs can react.
"""
import os
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QCheckBox, QSlider, QLabel, QGroupBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS, section_label, pill
from rivsat.app.qt.common import make_button
from rivsat.app.qt.workers import Worker


class ConfigDock(QDockWidget):
    geeStatusChanged = pyqtSignal(bool)   # emitted after init attempt
    stateChanged     = pyqtSignal()       # emitted when any config value changes

    def __init__(self, parent=None):
        super().__init__("⚙  CONFIGURATION", parent)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._worker = None
        self._build()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build(self):
        container = QWidget()
        container.setFixedWidth(268)
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Study site group
        site_grp  = QGroupBox("Study Site")
        site_form = QFormLayout(site_grp)
        site_form.setSpacing(6)
        self.site_edit = QLineEdit(state.site_name)
        self.site_edit.setPlaceholderText("e.g. Karnaphuli_River")
        site_form.addRow("Site name", self.site_edit)
        root.addWidget(site_grp)

        # Date range group
        date_grp  = QGroupBox("Date Range")
        date_form = QFormLayout(date_grp)
        date_form.setSpacing(6)
        self.start_edit = QDateEdit(QDate(2023, 1, 1))
        self.end_edit   = QDateEdit(QDate(2023, 12, 31))
        for d in (self.start_edit, self.end_edit):
            d.setCalendarPopup(True)
            d.setDisplayFormat("yyyy-MM-dd")
        date_form.addRow("Start", self.start_edit)
        date_form.addRow("End",   self.end_edit)
        root.addWidget(date_grp)

        # Sensors group
        sensor_grp = QGroupBox("Sensors")
        sensor_lay = QVBoxLayout(sensor_grp)
        sensor_lay.setSpacing(4)
        self.cb_s2 = QCheckBox("Sentinel-2 MSI (S2)");  self.cb_s2.setChecked(True)
        self.cb_l8 = QCheckBox("Landsat 8 OLI (L8)");   self.cb_l8.setChecked(True)
        self.cb_l9 = QCheckBox("Landsat 9 OLI-2 (L9)")
        for cb in (self.cb_s2, self.cb_l8, self.cb_l9):
            sensor_lay.addWidget(cb)
        # cloud slider
        cloud_row = QHBoxLayout()
        self.cloud_lbl = QLabel("Max cloud: 20%")
        self.cloud_slider = QSlider(Qt.Orientation.Horizontal)
        self.cloud_slider.setRange(0, 100)
        self.cloud_slider.setValue(20)
        cloud_row.addWidget(self.cloud_slider)
        sensor_lay.addWidget(self.cloud_lbl)
        sensor_lay.addLayout(cloud_row)
        root.addWidget(sensor_grp)

        # Paths group
        path_grp  = QGroupBox("Paths")
        path_form = QFormLayout(path_grp)
        path_form.setSpacing(6)
        self.gee_proj_edit = QLineEdit();  self.gee_proj_edit.setPlaceholderText("optional")
        self.data_edit     = QLineEdit("./data")
        self.out_edit      = QLineEdit("./outputs")
        path_form.addRow("GEE project", self.gee_proj_edit)
        path_form.addRow("Data dir",    self.data_edit)
        path_form.addRow("Output dir",  self.out_edit)
        root.addWidget(path_grp)

        # GEE init
        gee_grp = QGroupBox("Google Earth Engine")
        gee_lay = QVBoxLayout(gee_grp)
        self.gee_btn = make_button("⚡  Initialize GEE", accent="primary")
        self.gee_status = QLabel(pill("● GEE not initialised", "red"))
        self.gee_status.setTextFormat(Qt.TextFormat.RichText)
        gee_lay.addWidget(self.gee_btn)
        gee_lay.addWidget(self.gee_status)
        root.addWidget(gee_grp)

        root.addStretch(1)
        self.setWidget(container)

        # ── Wiring ─────────────────────────────────────────────────────────────
        self.cloud_slider.valueChanged.connect(
            lambda v: self.cloud_lbl.setText(f"Max cloud: {v}%")
        )
        for w in (self.site_edit, self.gee_proj_edit, self.data_edit, self.out_edit):
            w.textChanged.connect(self._sync_state)
        self.start_edit.dateChanged.connect(self._sync_state)
        self.end_edit.dateChanged.connect(self._sync_state)
        self.cloud_slider.valueChanged.connect(self._sync_state)
        for cb in (self.cb_s2, self.cb_l8, self.cb_l9):
            cb.stateChanged.connect(self._sync_state)
        self.gee_btn.clicked.connect(self._init_gee)

        self._sync_state()

    # ── Apply loaded project state into widgets ────────────────────────────────
    def apply_from_state(self):
        """Push current state values into config widgets (blocks signals to avoid re-entrancy)."""
        widgets = [
            self.site_edit, self.start_edit, self.end_edit,
            self.cloud_slider, self.cb_s2, self.cb_l8, self.cb_l9,
            self.gee_proj_edit, self.data_edit, self.out_edit,
        ]
        for w in widgets:
            w.blockSignals(True)

        from PyQt6.QtCore import QDate
        self.site_edit.setText(state.site_name)
        try:
            self.start_edit.setDate(QDate.fromString(state.start_date, "yyyy-MM-dd"))
            self.end_edit.setDate(QDate.fromString(state.end_date, "yyyy-MM-dd"))
        except Exception:
            pass
        self.cloud_slider.setValue(int(state.max_cloud_cover))
        self.cloud_lbl.setText(f"Max cloud: {int(state.max_cloud_cover)}%")
        self.cb_s2.setChecked("S2" in state.sensors)
        self.cb_l8.setChecked("L8" in state.sensors)
        self.cb_l9.setChecked("L9" in state.sensors)
        self.gee_proj_edit.setText(state.gee_project_id)
        self.data_edit.setText(state.data_dir)
        self.out_edit.setText(state.output_dir)

        for w in widgets:
            w.blockSignals(False)

    # ── State sync ─────────────────────────────────────────────────────────────
    def _sync_state(self, *_):
        state.site_name       = self.site_edit.text().strip() or "My_River_Site"
        state.start_date      = self.start_edit.date().toString("yyyy-MM-dd")
        state.end_date        = self.end_edit.date().toString("yyyy-MM-dd")
        sensors = []
        if self.cb_s2.isChecked(): sensors.append("S2")
        if self.cb_l8.isChecked(): sensors.append("L8")
        if self.cb_l9.isChecked(): sensors.append("L9")
        state.sensors         = sensors
        state.max_cloud_cover = float(self.cloud_slider.value())
        state.gee_project_id  = self.gee_proj_edit.text().strip()
        state.data_dir        = self.data_edit.text().strip() or "./data"
        state.output_dir      = self.out_edit.text().strip()  or f"./outputs/{state.site_name}"
        try:
            os.makedirs(state.data_dir,   exist_ok=True)
            os.makedirs(state.output_dir, exist_ok=True)
        except Exception:
            pass
        self.stateChanged.emit()

    # ── GEE init (threaded) ────────────────────────────────────────────────────
    def _init_gee(self):
        self._sync_state()
        self.gee_btn.setEnabled(False)
        self.gee_status.setText(pill("● Initialising …", "orange"))

        def _do(log=None, progress=None):
            from rivsat import initialize_gee
            initialize_gee(project_id=state.gee_project_id or None)
            return True

        self._worker = Worker(_do)
        self._worker.signals.finished.connect(self._on_gee_ok)
        self._worker.signals.error.connect(self._on_gee_err)
        self._worker.start()

    def _on_gee_ok(self, _result):
        state.gee_ready = True
        self.gee_status.setText(pill("● GEE ready", "green"))
        self.gee_btn.setEnabled(True)
        self.geeStatusChanged.emit(True)

    def _on_gee_err(self, msg):
        state.gee_ready = False
        first = msg.splitlines()[0] if msg else "error"
        self.gee_status.setText(pill(f"● GEE error", "red"))
        self.gee_status.setToolTip(first)
        self.gee_btn.setEnabled(True)
        self.geeStatusChanged.emit(False)
