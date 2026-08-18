"""
Acquire tab — GEE download with threaded worker, live console, progress bar.
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox,
    QLabel, QGroupBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS, pill
from rivsat.app.qt.common import StepHeader, ConsoleLog, make_button
from rivsat.app.qt.workers import Worker


class AcquireTab(QWidget):
    scenesReady = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._worker = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        panel = QWidget(); panel.setFixedWidth(280)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0); pl.setSpacing(8)

        pl.addWidget(StepHeader(2, "Satellite Acquisition"))
        desc = QLabel("Query Google Earth Engine for cloud-free composites. "
                      "Site, dates, sensors, and cloud threshold come from the "
                      "Configuration dock.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")
        pl.addWidget(desc)

        grp = QGroupBox("Query Parameters")
        form = QFormLayout(grp); form.setSpacing(6)
        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["annual", "seasonal", "monthly", "daily_overpass"])
        self.mode_cb.setCurrentText("seasonal")
        self.reducer_cb = QComboBox()
        self.reducer_cb.addItems(["median", "mean", "min", "max"])
        self.scale_sb = QDoubleSpinBox()
        self.scale_sb.setRange(10, 100); self.scale_sb.setValue(20); self.scale_sb.setSuffix(" m")
        form.addRow("Mode",    self.mode_cb)
        form.addRow("Reducer", self.reducer_cb)
        form.addRow("Scale",   self.scale_sb)
        pl.addWidget(grp)

        self.run_btn = make_button("▶  Download Imagery", accent="success")
        self.run_btn.clicked.connect(self._run)
        pl.addWidget(self.run_btn)

        self.progress = QProgressBar(); self.progress.setValue(0); self.progress.hide()
        pl.addWidget(self.progress)

        self.status = QLabel(""); self.status.setTextFormat(Qt.TextFormat.RichText)
        pl.addWidget(self.status)

        pl.addStretch(1)
        root.addWidget(panel)

        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)
        hdr = QLabel("DOWNLOAD LOG")
        hdr.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;letter-spacing:0.3px;")
        rl.addWidget(hdr)
        self.log = ConsoleLog(placeholder="Download log will appear here …")
        rl.addWidget(self.log)
        root.addWidget(right, stretch=1)

    def _run(self):
        if not state.gee_ready:
            self.log.line("ERROR  GEE not initialised. Use the Configuration dock first.")
            self.status.setText(pill("✗ GEE not ready", "red"))
            return
        if not state.aoi_polygon:
            self.log.line("ERROR  No AOI polygon. Go to Step 1 — AOI & Layers.")
            self.status.setText(pill("✗ No AOI", "red"))
            return

        self.run_btn.setEnabled(False)
        self.progress.show(); self.progress.setValue(5)
        self.log.clear_log()

        mode    = self.mode_cb.currentText()
        reducer = self.reducer_cb.currentText()
        scale   = float(self.scale_sb.value())

        def _do(log=None, progress=None):
            from rivsat import GEEDownloader
            geojson_path = f"{state.data_dir}/user_roi.geojson"
            log(f"START  Site: {state.site_name}")
            log(f"       Sensors: {state.sensors}")
            log(f"       Period : {state.start_date} → {state.end_date}")
            log(f"       Mode: {mode} | Scale: {scale} m | Reducer: {reducer}")
            log(f"       Cloud: ≤ {state.max_cloud_cover:.0f}%")
            progress(20)
            downloader = GEEDownloader(
                aoi_polygon=geojson_path, site_name=state.site_name,
                output_dir=state.data_dir, gee_project=state.gee_project_id or None,
            )
            scene_dirs = downloader.download_imagery(
                start_date=state.start_date, end_date=state.end_date, mode=mode,
                reducer=reducer, sensors=state.sensors,
                max_cloud_cover=state.max_cloud_cover, scale=scale,
            )
            progress(95)
            return scene_dirs

        self._worker = Worker(_do)
        self._worker.signals.log.connect(self.log.line)
        self._worker.signals.progress.connect(self.progress.setValue)
        self._worker.signals.finished.connect(self._on_done)
        self._worker.signals.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, scene_dirs):
        state.scene_dirs = scene_dirs
        n = len(scene_dirs)
        self.log.line(f"OK     Downloaded {n} scene(s):")
        for d in scene_dirs:
            self.log.line(f"       → {d}")
        self.status.setText(pill(f"🛰 {n} scene(s) ready", "blue"))
        self.run_btn.setEnabled(True)
        self.progress.setValue(100)
        self.scenesReady.emit(n)

    def _on_err(self, msg):
        self.log.line(f"ERROR  {msg.splitlines()[0]}")
        self.status.setText(pill("✗ Download failed", "red"))
        self.run_btn.setEnabled(True)
        self.progress.hide()
