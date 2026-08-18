"""
Process tab — 6-parameter bio-optical inversion.
Threaded worker → 6-panel matplotlib grid (top) + scene summary table (bottom).
"""
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QCheckBox, QLabel,
    QSlider, QProgressBar, QTableWidget, QTableWidgetItem, QSplitter, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

from rivsat.app.state import state
from rivsat.app.qt.theme import COLORS, pill
from rivsat.app.qt.common import StepHeader, ConsoleLog, MplCanvas, make_button
from rivsat.app.qt.workers import Worker
from PyQt6.QtWidgets import QComboBox

try:
    import cmocean
    _CMAPS = {"turbidity": cmocean.cm.turbid, "tss": cmocean.cm.matter,
              "chlorophyll": cmocean.cm.algae, "cdom": cmocean.cm.dense,
              "salinity": cmocean.cm.haline, "secchi_depth": cmocean.cm.ice}
except ImportError:
    _CMAPS = {"turbidity": "turbo", "tss": "YlOrRd", "chlorophyll": "YlGn",
              "cdom": "Blues", "salinity": "YlGnBu", "secchi_depth": "Greys_r"}

_PARAMS = [
    ("turbidity",    "Turbidity",          "FNU",  500),
    ("tss",          "TSS",                "mg/L", 600),
    ("chlorophyll",  "Chlorophyll-a",      "µg/L", 150),
    ("cdom",         "CDOM a(440)",        "m⁻¹",   10),
    ("salinity",     "Estuarine Salinity", "PSU",   35),
    ("secchi_depth", "Secchi Depth",       "m",   None),
]
_COLS = ["Sensor", "Date", "Turb FNU", "TSS mg/L", "Chl µg/L", "CDOM m⁻¹", "Sal PSU", "SDD m"]


class ProcessTab(QWidget):
    processed     = pyqtSignal(int)
    overlaysReady = pyqtSignal(dict)   # {key: {"png","bounds","label"}}

    def __init__(self):
        super().__init__()
        self._worker = None
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12); root.setSpacing(10)

        panel = QWidget(); panel.setFixedWidth(280)
        pl = QVBoxLayout(panel); pl.setContentsMargins(0, 0, 0, 0); pl.setSpacing(8)
        pl.addWidget(StepHeader(3, "Bio-Optical Processing"))
        desc = QLabel("Run the 6-parameter radiative transfer inversion on all "
                      "downloaded scenes. GeoTIFF rasters are exported automatically.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")
        pl.addWidget(desc)

        grp = QGroupBox("Processing Options")
        gl = QVBoxLayout(grp)
        wl = QFormLayout(); wl.setSpacing(4)
        self.workers_slider = QSlider(Qt.Orientation.Horizontal)
        self.workers_slider.setRange(1, 16); self.workers_slider.setValue(4)
        self.workers_lbl = QLabel("4")
        self.workers_slider.valueChanged.connect(lambda v: self.workers_lbl.setText(str(v)))
        row = QHBoxLayout(); row.addWidget(self.workers_slider); row.addWidget(self.workers_lbl)
        rw = QWidget(); rw.setLayout(row)
        wl.addRow("CPU workers", rw)
        gl.addLayout(wl)
        self.cb_sbaf    = QCheckBox("Apply SBAF correction"); self.cb_sbaf.setChecked(True)
        self.cb_rededge = QCheckBox("Use red-edge band (B5)"); self.cb_rededge.setChecked(True)
        self.cb_strict  = QCheckBox("Strict water mask (SCL)")
        for cb in (self.cb_sbaf, self.cb_rededge, self.cb_strict):
            gl.addWidget(cb)
        pl.addWidget(grp)

        self.run_btn = make_button("▶  Run Processing", accent="success")
        self.run_btn.clicked.connect(self._run)
        pl.addWidget(self.run_btn)

        self.progress = QProgressBar(); self.progress.hide()
        pl.addWidget(self.progress)
        self.status = QLabel(""); self.status.setTextFormat(Qt.TextFormat.RichText)
        pl.addWidget(self.status)

        loghdr = QLabel("PROCESSING LOG")
        loghdr.setStyleSheet(f"color:{COLORS['muted']};font-weight:700;font-size:10px;letter-spacing:0.8px;")
        pl.addWidget(loghdr)
        self.log = ConsoleLog(height=140, placeholder="Processing log …")
        pl.addWidget(self.log)
        pl.addStretch(1)
        root.addWidget(panel)

        # Right — grid over table
        splitter = QSplitter(Qt.Orientation.Vertical)
        grid_wrap = QWidget()
        gwl = QVBoxLayout(grid_wrap); gwl.setContentsMargins(0, 0, 0, 0); gwl.setSpacing(4)
        hdr_row = QHBoxLayout(); hdr_row.setContentsMargins(0, 0, 0, 0)
        gh = QLabel("SIX-PARAMETER PRODUCT GRID")
        gh.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        hdr_row.addWidget(gh)
        hdr_row.addStretch(1)
        scene_lbl = QLabel("Scene:")
        scene_lbl.setStyleSheet(f"color:{COLORS['muted']};font-size:11px;")
        hdr_row.addWidget(scene_lbl)
        self.scene_cb = QComboBox()
        self.scene_cb.setMinimumWidth(220)
        self.scene_cb.currentIndexChanged.connect(self.show_scene)
        hdr_row.addWidget(self.scene_cb)
        gwl.addLayout(hdr_row)
        self.canvas = MplCanvas(figsize=(14, 8), toolbar=True)
        gwl.addWidget(self.canvas)
        splitter.addWidget(grid_wrap)

        tbl_wrap = QWidget()
        twl = QVBoxLayout(tbl_wrap); twl.setContentsMargins(0, 6, 0, 0); twl.setSpacing(4)
        th = QLabel("SCENE SUMMARY TABLE")
        th.setStyleSheet(f"color:{COLORS['navy']};font-weight:700;font-size:11px;")
        twl.addWidget(th)
        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        twl.addWidget(self.table)
        splitter.addWidget(tbl_wrap)
        splitter.setSizes([560, 200])
        root.addWidget(splitter, stretch=1)

    # ── Scene selector ─────────────────────────────────────────────────────────
    def populate_scene_selector(self):
        self.scene_cb.blockSignals(True)
        self.scene_cb.clear()
        for res in state.processed_results:
            s = res.get("stats", {})
            label = f"{s.get('sensor', '?')}  ·  {s.get('date', '?')}"
            self.scene_cb.addItem(label)
        if self.scene_cb.count():
            self.scene_cb.setCurrentIndex(self.scene_cb.count() - 1)
        self.scene_cb.blockSignals(False)

    def show_scene(self, index: int):
        if index < 0 or index >= len(state.processed_results):
            return
        result = state.processed_results[index]
        self._draw_grid(result)
        self._fill_table(state.processed_results)

    # ── Grid rendering (on UI thread from worker result) ───────────────────────
    @staticmethod
    def _p95(arr, hard):
        v = float(np.nanpercentile(arr, 95))
        if hard is not None:
            return min(v * 1.1, hard) if v > 0 else hard
        return max(v * 1.1, 0.1)

    def _draw_grid(self, latest):
        import matplotlib.pyplot as plt
        fig = self.canvas.figure
        fig.clear()
        s = latest["stats"]
        fig.suptitle(f"{s['sensor']}  ·  {s['date']}  ·  {state.site_name}",
                     fontsize=12, fontweight="bold", color=COLORS["text"])
        axes = fig.subplots(2, 3)
        for ax, (key, title, unit, hard) in zip(axes.flat, _PARAMS):
            arr = latest.get(key)
            ax.set_facecolor("#e8ecf0")
            if arr is None:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        transform=ax.transAxes, color="#8a93a6")
                ax.set_title(f"{title} [{unit}]", fontsize=10)
                continue
            arr_ma = np.ma.masked_invalid(arr)
            vmax = self._p95(arr, hard)
            cmap = _CMAPS.get(key, "viridis")
            cobj = plt.get_cmap(cmap) if isinstance(cmap, str) else cmap
            try:
                cobj = cobj.copy(); cobj.set_bad("#c8ced6")
            except Exception:
                pass
            im = ax.imshow(arr_ma, cmap=cobj, vmin=0, vmax=vmax,
                           interpolation="nearest", aspect="auto")
            ax.set_title(f"{title} [{unit}]", fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=7)
            cb = fig.colorbar(im, ax=ax, fraction=0.044, pad=0.03)
            cb.ax.tick_params(labelsize=7)
            mv = float(np.nanmean(arr)); nw = int(np.sum(~np.isnan(arr)))
            ax.text(0.03, 0.97, f"Mean: {mv:.2f}\nPx: {nw:,}",
                    transform=ax.transAxes, fontsize=8, va="top",
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#d0d5dd", alpha=0.85))
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        self.canvas.canvas.draw_idle()

    def _fill_table(self, results):
        self.table.setRowCount(len(results))
        for r, res in enumerate(results):
            s = res["stats"]
            vals = [
                s.get("sensor", "—"), s.get("date", "—"),
                f"{s.get('turbidity_mean_fnu', 0):.1f}",
                f"{s.get('tss_mean_mg_l', 0):.1f}",
                f"{s.get('chlorophyll_mean_ug_l', 0):.1f}",
                f"{s.get('cdom_mean', 0):.3f}",
                f"{s.get('salinity_mean_psu', 0):.2f}",
                f"{s.get('secchi_depth_mean_m', 0):.3f}",
            ]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))

    # ── Run ────────────────────────────────────────────────────────────────────
    def _run(self):
        if not state.scene_dirs:
            self.log.line("ERROR  No scenes. Run Step 2 — Acquisition first.")
            self.status.setText(pill("✗ No scenes", "red"))
            return
        self.run_btn.setEnabled(False)
        self.progress.show(); self.progress.setValue(5)
        self.log.clear_log()

        workers  = int(self.workers_slider.value())
        sbaf     = self.cb_sbaf.isChecked()
        rededge  = self.cb_rededge.isChecked()
        strict   = self.cb_strict.isChecked()

        def _do(log=None, progress=None):
            from rivsat import process_batch_parallel
            log(f"START  {len(state.scene_dirs)} scene(s) | workers={workers}")
            log(f"       SBAF={sbaf} | red-edge={rededge} | strict={strict}")
            progress(15)
            results = process_batch_parallel(
                state.scene_dirs, max_workers=workers, apply_sbaf=sbaf,
                use_rededge=rededge, water_mask_strict=strict)
            progress(75)
            for res in results:
                s = res["stats"]
                log(f"OK     {s['sensor']} {s['date']}  "
                    f"Turb:{s.get('turbidity_mean_fnu',0):.1f}  "
                    f"TSS:{s.get('tss_mean_mg_l',0):.1f}  "
                    f"Chl:{s.get('chlorophyll_mean_ug_l',0):.1f}")
            return results

        self._worker = Worker(_do)
        self._worker.signals.log.connect(self.log.line)
        self._worker.signals.progress.connect(self.progress.setValue)
        self._worker.signals.finished.connect(self._on_done)
        self._worker.signals.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, results):
        state.processed_results = results
        self.populate_scene_selector()
        latest = results[-1]
        self._draw_grid(latest)
        self._fill_table(results)
        try:
            save_path = f"{state.output_dir}/multiparameter_grid.png"
            self.canvas.figure.savefig(save_path, dpi=150, bbox_inches="tight")
            self.log.line(f"DONE   Grid saved → {save_path}")
        except Exception as exc:
            self.log.line(f"WARN   Could not save grid PNG: {exc}")
        # Build georeferenced overlays for the latest scene → Map tab
        try:
            from rivsat.app.qt.overlays import build_overlays
            ovs = build_overlays(latest, state.output_dir)
            if ovs:
                self.overlaysReady.emit(ovs)
                self.log.line(f"OK     {len(ovs)} map overlay(s) generated")
        except Exception as exc:  # noqa: BLE001
            self.log.line(f"WARN   Overlay generation skipped: {exc}")

        n = len(results)
        self.status.setText(pill(f"✔ {n} scene(s) processed", "green"))
        self.run_btn.setEnabled(True)
        self.progress.setValue(100)
        self.processed.emit(n)

    def _on_err(self, msg):
        self.log.line(f"ERROR  {msg.splitlines()[0]}")
        self.status.setText(pill("✗ Processing failed", "red"))
        self.run_btn.setEnabled(True)
        self.progress.hide()
