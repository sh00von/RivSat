"""
Profiles tab — longitudinal gradients + cross-river transects with channel width.
"""
import matplotlib
matplotlib.use("QtAgg")

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QComboBox, QLabel,
    QGroupBox, QProgressBar, QSlider, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QSplitter
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
_W_COLS = ["Transect", "Chainage km", "Channel width m"]


class ProfilesTab(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12); root.setSpacing(10)

        panel = QWidget(); panel.setFixedWidth(270)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0); pl.setSpacing(8)
        pl.addWidget(StepHeader(5, "Profiles & Transects"))
        desc = QLabel("Extract along-river longitudinal gradients and perpendicular "
                      "cross-sectional transects with active channel width (W in m).")
        desc.setWordWrap(True); desc.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")
        pl.addWidget(desc)

        lg = QGroupBox("Longitudinal Profile")
        lf = QFormLayout(lg); lf.setSpacing(6)
        self.param_cb = QComboBox()
        for k, lbl, _ in _PARAMS:
            self.param_cb.addItem(lbl, k)
        self.samples_slider = QSlider(Qt.Orientation.Horizontal)
        self.samples_slider.setRange(20, 300); self.samples_slider.setValue(100)
        self.samples_lbl = QLabel("100")
        self.samples_slider.valueChanged.connect(lambda v: self.samples_lbl.setText(str(v)))
        sr = QHBoxLayout(); sr.addWidget(self.samples_slider); sr.addWidget(self.samples_lbl)
        srw = QWidget(); srw.setLayout(sr)
        lf.addRow("Parameter", self.param_cb)
        lf.addRow("Samples", srw)
        self.run_long_btn = make_button("▶  Longitudinal Profile", accent="primary")
        self.run_long_btn.clicked.connect(self._run_long)
        lf.addRow(self.run_long_btn)
        pl.addWidget(lg)

        cg = QGroupBox("Cross-River Transects")
        cf = QFormLayout(cg); cf.setSpacing(6)
        self.ntrans_slider = QSlider(Qt.Orientation.Horizontal)
        self.ntrans_slider.setRange(2, 20); self.ntrans_slider.setValue(4)
        self.ntrans_lbl = QLabel("4")
        self.ntrans_slider.valueChanged.connect(lambda v: self.ntrans_lbl.setText(str(v)))
        nr = QHBoxLayout(); nr.addWidget(self.ntrans_slider); nr.addWidget(self.ntrans_lbl)
        nrw = QWidget(); nrw.setLayout(nr)
        self.tlen_sb = QDoubleSpinBox(); self.tlen_sb.setRange(100, 10000)
        self.tlen_sb.setValue(1000); self.tlen_sb.setSuffix(" m"); self.tlen_sb.setSingleStep(100)
        cf.addRow("Transects", nrw)
        cf.addRow("Length", self.tlen_sb)
        self.run_cross_btn = make_button("▶  Cross Transects", accent="warning")
        self.run_cross_btn.clicked.connect(self._run_cross)
        cf.addRow(self.run_cross_btn)
        pl.addWidget(cg)

        self.progress = QProgressBar(); self.progress.hide()
        pl.addWidget(self.progress)
        self.status = QLabel(""); self.status.setTextFormat(Qt.TextFormat.RichText)
        pl.addWidget(self.status)
        self.log = ConsoleLog(height=100, placeholder="Log …")
        pl.addWidget(self.log)
        pl.addStretch(1)
        root.addWidget(panel)

        splitter = QSplitter(Qt.Orientation.Vertical)
        lw = QWidget(); lwl = QVBoxLayout(lw); lwl.setContentsMargins(0,0,0,0); lwl.setSpacing(4)
        lh = QLabel("LONGITUDINAL GRADIENT"); lh.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        lwl.addWidget(lh)
        self.long_canvas = MplCanvas(figsize=(12, 3.6))
        lwl.addWidget(self.long_canvas)
        splitter.addWidget(lw)

        cw = QWidget(); cwl = QVBoxLayout(cw); cwl.setContentsMargins(0,6,0,0); cwl.setSpacing(4)
        ch = QLabel("CROSS-SECTIONAL TRANSECTS"); ch.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        cwl.addWidget(ch)
        self.cross_canvas = MplCanvas(figsize=(12, 3.6))
        cwl.addWidget(self.cross_canvas)
        splitter.addWidget(cw)

        ww = QWidget(); wwl = QVBoxLayout(ww); wwl.setContentsMargins(0,6,0,0); wwl.setSpacing(4)
        wh = QLabel("ACTIVE CHANNEL WIDTH (W)"); wh.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        wwl.addWidget(wh)
        self.width_table = QTableWidget(0, len(_W_COLS))
        self.width_table.setHorizontalHeaderLabels(_W_COLS)
        self.width_table.horizontalHeader().setStretchLastSection(True)
        self.width_table.verticalHeader().setVisible(False)
        self.width_table.setMaximumHeight(150)
        wwl.addWidget(self.width_table)
        splitter.addWidget(ww)
        splitter.setSizes([280, 280, 150])
        root.addWidget(splitter, stretch=1)

    def _prereqs(self):
        if not state.processed_results:
            self.log.line("ERROR  No processed results. Run Step 3 first.")
            self.status.setText(pill("✗ No processed data", "red")); return False
        if not state.centerline:
            self.log.line("ERROR  No centerline. Go to Step 1.")
            self.status.setText(pill("✗ No centerline", "red")); return False
        return True

    def _run_long(self):
        if not self._prereqs():
            return
        key   = self.param_cb.currentData()
        label = self.param_cb.currentText()
        unit  = next(u for k, _, u in _PARAMS if k == key)
        nsamp = int(self.samples_slider.value())
        self.run_long_btn.setEnabled(False); self.progress.show(); self.progress.setValue(10)
        self.log.clear_log()

        def _do(log=None, progress=None):
            from rivsat import extract_longitudinal_profile, plot_longitudinal_gradient
            latest = state.processed_results[-1]
            arr = latest.get(key)
            if arr is None:
                return {"skip": True}
            log(f"START  Longitudinal {label} | {nsamp} samples")
            progress(40)
            df = extract_longitudinal_profile(raster_data=arr,
                    transform=latest["profile"]["transform"],
                    centerline_coords=state.centerline, num_samples=nsamp)
            fig = plot_longitudinal_gradient(df, param_name=label, unit=unit,
                    title=f"Longitudinal {label} — {state.site_name}",
                    save_path=f"{state.output_dir}/longitudinal_{key}_gradient.png")
            log("DONE")
            return {"skip": False, "fig": fig, "label": label}

        self._worker = Worker(_do)
        self._worker.signals.log.connect(self.log.line)
        self._worker.signals.progress.connect(self.progress.setValue)
        self._worker.signals.finished.connect(self._on_long_done)
        self._worker.signals.error.connect(self._on_err)
        self._worker.start()

    def _on_long_done(self, payload):
        self.run_long_btn.setEnabled(True); self.progress.setValue(100)
        if payload.get("skip"):
            self.log.line("WARN   Parameter not in last scene."); return
        self.long_canvas.set_figure(payload["fig"])
        self.status.setText(pill(f"✔ Profile: {payload['label']}", "green"))

    def _run_cross(self):
        if not self._prereqs():
            return
        ntrans = int(self.ntrans_slider.value())
        tlen   = float(self.tlen_sb.value())
        self.run_cross_btn.setEnabled(False); self.progress.show(); self.progress.setValue(10)
        self.log.clear_log()

        def _do(log=None, progress=None):
            from rivsat import extract_cross_transects, plot_cross_transects
            latest = state.processed_results[-1]
            arr = latest.get("turbidity")
            if arr is None:
                return {"skip": True}
            log(f"START  Cross transects | n={ntrans} | L={tlen} m")
            progress(35)
            df = extract_cross_transects(raster_data=arr,
                    transform=latest["profile"]["transform"],
                    centerline_coords=state.centerline, num_transects=ntrans,
                    transect_length_m=tlen, samples_per_transect=30)
            ws = df.groupby("transect_id")[["chainage_km", "channel_width_m"]].first().reset_index()
            log(f"OK     {len(ws)} transect(s). Width {ws['channel_width_m'].min():.0f}"
                f"–{ws['channel_width_m'].max():.0f} m")
            fig = plot_cross_transects(df, param_name="Turbidity", unit="FNU",
                    title=f"Cross-Transects — {state.site_name}",
                    save_path=f"{state.output_dir}/cross_transects.png")
            return {"skip": False, "fig": fig, "widths": ws}

        self._worker = Worker(_do)
        self._worker.signals.log.connect(self.log.line)
        self._worker.signals.progress.connect(self.progress.setValue)
        self._worker.signals.finished.connect(self._on_cross_done)
        self._worker.signals.error.connect(self._on_err)
        self._worker.start()

    def _on_cross_done(self, payload):
        self.run_cross_btn.setEnabled(True); self.progress.setValue(100)
        if payload.get("skip"):
            self.log.line("WARN   Turbidity array unavailable."); return
        self.cross_canvas.set_figure(payload["fig"])
        ws = payload["widths"]
        self.width_table.setRowCount(len(ws))
        for r in range(len(ws)):
            self.width_table.setItem(r, 0, QTableWidgetItem(str(int(ws.iloc[r]["transect_id"]))))
            self.width_table.setItem(r, 1, QTableWidgetItem(f"{ws.iloc[r]['chainage_km']:.3f}"))
            self.width_table.setItem(r, 2, QTableWidgetItem(f"{ws.iloc[r]['channel_width_m']:.1f}"))
        self.status.setText(pill("✔ Transects complete", "green"))

    def _on_err(self, msg):
        self.log.line(f"ERROR  {msg.splitlines()[0]}")
        self.status.setText(pill("✗ Failed", "red"))
        self.run_long_btn.setEnabled(True); self.run_cross_btn.setEnabled(True)
        self.progress.hide()
