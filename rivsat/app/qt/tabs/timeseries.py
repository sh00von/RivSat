"""
Time-Series tab — station extraction + Mann-Kendall trend analysis.
"""
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QComboBox, QLabel,
    QGroupBox, QProgressBar, QTableWidget, QTableWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS, pill
from rivsat.app.qt.common import StepHeader, ConsoleLog, MplCanvas, make_button
from rivsat.app.qt.workers import Worker

_PARAMS = [
    ("turbidity", "Turbidity", "FNU"), ("tss", "TSS", "mg/L"),
    ("chlorophyll", "Chlorophyll-a", "µg/L"), ("cdom", "CDOM a(440)", "m⁻¹"),
    ("salinity", "Estuarine Salinity", "PSU"), ("secchi_depth", "Secchi Depth", "m"),
]
_TREND_COLS = ["Station", "N", "Mean", "M-K Z", "p-value", "Sen slope/yr", "Trend"]


class TimeSeriesTab(QWidget):
    done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._worker = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12); root.setSpacing(10)

        panel = QWidget(); panel.setFixedWidth(270)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0); pl.setSpacing(8)
        pl.addWidget(StepHeader(4, "Time-Series & Trends"))
        desc = QLabel("Extract water-quality dynamics at monitoring stations and "
                      "compute Mann-Kendall trend statistics with Sen's slope.")
        desc.setWordWrap(True); desc.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")
        pl.addWidget(desc)

        grp = QGroupBox("Parameters")
        form = QFormLayout(grp); form.setSpacing(6)
        self.param_cb = QComboBox()
        for k, lbl, _ in _PARAMS:
            self.param_cb.addItem(lbl, k)
        self.interp_cb = QComboBox(); self.interp_cb.addItems(["linear", "cubic", "none"])
        form.addRow("Parameter", self.param_cb)
        form.addRow("Gap-fill", self.interp_cb)
        pl.addWidget(grp)

        self.run_btn = make_button("▶  Extract Time-Series", accent="success")
        self.run_btn.clicked.connect(self._run)
        pl.addWidget(self.run_btn)
        self.progress = QProgressBar(); self.progress.hide()
        pl.addWidget(self.progress)
        self.status = QLabel(""); self.status.setTextFormat(Qt.TextFormat.RichText)
        pl.addWidget(self.status)
        self.log = ConsoleLog(height=120, placeholder="Log …")
        pl.addWidget(self.log)
        pl.addStretch(1)
        root.addWidget(panel)

        splitter = QSplitter(Qt.Orientation.Vertical)
        pw = QWidget(); pwl = QVBoxLayout(pw); pwl.setContentsMargins(0,0,0,0); pwl.setSpacing(4)
        ph = QLabel("TIME-SERIES PLOT"); ph.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        pwl.addWidget(ph)
        self.canvas = MplCanvas(figsize=(12, 5))
        pwl.addWidget(self.canvas)
        splitter.addWidget(pw)

        tw = QWidget(); twl = QVBoxLayout(tw); twl.setContentsMargins(0,6,0,0); twl.setSpacing(4)
        th = QLabel("MANN-KENDALL TREND SUMMARY"); th.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        twl.addWidget(th)
        self.table = QTableWidget(0, len(_TREND_COLS))
        self.table.setHorizontalHeaderLabels(_TREND_COLS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        twl.addWidget(self.table)
        splitter.addWidget(tw)
        splitter.setSizes([420, 180])
        root.addWidget(splitter, stretch=1)

    def _run(self):
        if not state.scene_dirs:
            self.log.line("ERROR  No scenes. Run Acquisition & Processing first.")
            self.status.setText(pill("✗ No scenes", "red")); return
        if not state.stations:
            self.log.line("ERROR  No stations. Go to Step 1 — AOI & Layers.")
            self.status.setText(pill("✗ No stations", "red")); return

        key    = self.param_cb.currentData()
        label  = self.param_cb.currentText()
        unit   = next(u for k, _, u in _PARAMS if k == key)
        interp = self.interp_cb.currentText()

        self.run_btn.setEnabled(False); self.progress.show(); self.progress.setValue(5)
        self.log.clear_log()

        def _do(log=None, progress=None):
            from rivsat import TimeSeriesEngine, calculate_temporal_trends, plot_station_timeseries
            log(f"START  Extracting {label} at {len(state.stations)} station(s)")
            progress(20)
            engine = TimeSeriesEngine(state.scene_dirs)
            ts_df = engine.extract_station_timeseries(state.stations, parameter=key)
            if ts_df.empty:
                return {"empty": True}
            progress(50)
            if interp != "none":
                ts_df = TimeSeriesEngine.interpolate_gaps(ts_df, parameter=key, method=interp)
                log(f"OK     Gap-filled ({interp})")
            csv = f"{state.output_dir}/{key}_timeseries.csv"
            ts_df.to_csv(csv, index=False)
            log(f"OK     CSV → {csv}")
            fig = plot_station_timeseries(ts_df, parameter=key, unit=unit,
                    title=f"{label} Dynamics — {state.site_name}",
                    save_path=f"{state.output_dir}/{key}_timeseries_plot.png")
            progress(80)
            trends = calculate_temporal_trends(ts_df, parameter=key)
            log("OK     Mann-Kendall complete")
            return {"empty": False, "fig": fig, "trends": trends, "label": label}

        self._worker = Worker(_do)
        self._worker.signals.log.connect(self.log.line)
        self._worker.signals.progress.connect(self.progress.setValue)
        self._worker.signals.finished.connect(self._on_done)
        self._worker.signals.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, payload):
        self.run_btn.setEnabled(True); self.progress.setValue(100)
        if payload.get("empty"):
            self.log.line("WARN   No data extracted.")
            self.status.setText(pill("⚠ No data", "orange")); return
        self.canvas.set_figure(payload["fig"])
        trends = payload["trends"]
        if "trends" in trends and not trends["trends"].empty:
            df = trends["trends"]
            cols = ["station_name", "N_observations", "mean_val",
                    "mann_kendall_z", "p_value", "sens_slope_annual", "trend_direction"]
            avail = [c for c in cols if c in df.columns]
            self.table.setRowCount(len(df))
            for r in range(len(df)):
                for c, col in enumerate(avail):
                    v = df.iloc[r][col]
                    v = f"{v:.4g}" if isinstance(v, float) else str(v)
                    self.table.setItem(r, c, QTableWidgetItem(v))
        self.status.setText(pill(f"✔ {payload['label']} extracted", "green"))
        self.done.emit(payload["label"])

    def _on_err(self, msg):
        self.log.line(f"ERROR  {msg.splitlines()[0]}")
        self.status.setText(pill("✗ Error", "red"))
        self.run_btn.setEnabled(True); self.progress.hide()
