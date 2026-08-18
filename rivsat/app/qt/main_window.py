"""
RivSat main window — QMainWindow with tab canvas, config dock, menubar,
and a live status bar of pill indicators.
"""
import os
import datetime
import webbrowser

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QLabel, QFileDialog, QMessageBox,
    QWidget, QHBoxLayout, QMenu
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt, QUrl

from rivsat.app.state import state
from rivsat.app.project import ProjectManager
from rivsat.app.qt.theme import COLORS, pill
from rivsat.app.qt.config_dock import ConfigDock
from rivsat.app.qt.tabs import (
    MapTab, AcquireTab, ProcessTab, TimeSeriesTab, ProfilesTab, ExportTab
)

_DOCS_URL = "https://github.com/shovon/rivsat"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RivSat — Satellite Water Quality Platform")
        self.resize(1360, 860)

        self.pm = ProjectManager(self)

        # ── Config dock ────────────────────────────────────────────────────────
        self.config_dock = ConfigDock(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.config_dock)

        # ── Tabs ───────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.map_tab     = MapTab()
        self.acquire_tab = AcquireTab()
        self.process_tab = ProcessTab()
        self.ts_tab      = TimeSeriesTab()
        self.prof_tab    = ProfilesTab()
        self.export_tab  = ExportTab()
        self.tabs.addTab(self.map_tab,     "1. Map && Layers")
        self.tabs.addTab(self.acquire_tab, "2. Acquisition")
        self.tabs.addTab(self.process_tab, "3. Processing")
        self.tabs.addTab(self.ts_tab,      "4. Time-Series")
        self.tabs.addTab(self.prof_tab,    "5. Profiles")
        self.tabs.addTab(self.export_tab,  "6. Export")
        self.setCentralWidget(self.tabs)

        self._build_menubar()
        self._build_statusbar()
        self._wire_signals()
        self._refresh_status()
        self._refresh_title()
        self._check_autosave_recovery()

    # ── Title bar ──────────────────────────────────────────────────────────────
    def _refresh_title(self):
        base = "RivSat — Satellite Water Quality Platform"
        if state.project_path:
            name = os.path.basename(state.project_path)
            base = f"RivSat — {name}"
        if self.pm.dirty:
            base += " *"
        self.setWindowTitle(base)

    # ── Menubar ────────────────────────────────────────────────────────────────
    def _build_menubar(self):
        mb = self.menuBar()

        m_file = mb.addMenu("&File")

        act_new = QAction("New Project", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._new_project)
        m_file.addAction(act_new)

        act_open = QAction("Open Project…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_project)
        m_file.addAction(act_open)

        m_file.addSeparator()

        act_save = QAction("Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save_project)
        m_file.addAction(act_save)

        act_saveas = QAction("Save As…", self)
        act_saveas.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_saveas.triggered.connect(self._save_project_as)
        m_file.addAction(act_saveas)

        m_file.addSeparator()

        self.recent_menu = QMenu("Recent Projects", self)
        m_file.addMenu(self.recent_menu)
        self._rebuild_recent_menu()

        m_file.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        m_view = mb.addMenu("&View")
        act_dock = self.config_dock.toggleViewAction()
        act_dock.setText("Configuration Panel")
        m_view.addAction(act_dock)

        m_tools = mb.addMenu("&Tools")
        act_gee = QAction("Initialize GEE", self)
        act_gee.triggered.connect(self.config_dock._init_gee)
        act_refresh = QAction("Refresh Export List", self)
        act_refresh.triggered.connect(self.export_tab.refresh)
        m_tools.addAction(act_gee)
        m_tools.addAction(act_refresh)

        m_help = mb.addMenu("&Help")
        act_docs = QAction("Documentation", self)
        act_docs.triggered.connect(lambda: webbrowser.open(_DOCS_URL))
        act_about = QAction("About RivSat", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_docs)
        m_help.addAction(act_about)

    def _rebuild_recent_menu(self):
        self.recent_menu.clear()
        recent = ProjectManager.recent_projects()
        if not recent:
            self.recent_menu.addAction("(none)").setEnabled(False)
            return
        for path in recent:
            act = QAction(os.path.basename(path), self)
            act.setToolTip(path)
            act.triggered.connect(lambda _checked=False, p=path: self._open_project(p))
            self.recent_menu.addAction(act)
        self.recent_menu.addSeparator()
        act_clear = QAction("Clear Recent", self)
        act_clear.triggered.connect(self._clear_recent)
        self.recent_menu.addAction(act_clear)

    def _clear_recent(self):
        from PyQt6.QtCore import QSettings
        QSettings("RivSat", "RivSat").setValue("recent_projects", [])
        self._rebuild_recent_menu()

    # ── Status bar ─────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = self.statusBar()
        self.pill_gee    = QLabel(); self.pill_gee.setTextFormat(Qt.TextFormat.RichText)
        self.pill_site   = QLabel(); self.pill_site.setTextFormat(Qt.TextFormat.RichText)
        self.pill_scenes = QLabel(); self.pill_scenes.setTextFormat(Qt.TextFormat.RichText)
        self.pill_last   = QLabel(); self.pill_last.setTextFormat(Qt.TextFormat.RichText)
        for p in (self.pill_gee, self.pill_site, self.pill_scenes):
            sb.addWidget(p)
        sb.addPermanentWidget(self.pill_last)

    def _refresh_status(self):
        self.pill_gee.setText(
            pill("● GEE ready", "green") if state.gee_ready else pill("● GEE not ready", "red"))
        self.pill_site.setText(pill(f"📍 {state.site_name}", "blue"))
        n = len(state.processed_results) or len(state.scene_dirs)
        self.pill_scenes.setText(pill(f"🛰 Scenes: {n}", "blue" if n else "grey"))

    def _set_last(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.pill_last.setText(pill(f"✔ {msg} [{ts}]", "grey"))

    # ── Signal wiring ──────────────────────────────────────────────────────────
    def _wire_signals(self):
        # Dirty triggers
        self.config_dock.stateChanged.connect(self._on_state_changed)
        self.map_tab.featuresChanged.connect(self._on_map_changed)
        self.process_tab.processed.connect(self._on_processed)

        self.config_dock.geeStatusChanged.connect(lambda ok: (
            self._refresh_status(),
            self._set_last("GEE initialised" if ok else "GEE init failed"),
        ))
        self.acquire_tab.scenesReady.connect(lambda n: (
            self._refresh_status(), self._set_last(f"Downloaded {n} scenes"),
            self.tabs.setCurrentWidget(self.process_tab)))
        self.process_tab.overlaysReady.connect(self._on_overlays_ready)
        self.ts_tab.done.connect(lambda lbl: self._set_last(f"Time-series: {lbl}"))

        self.pm.dirtied.connect(self._refresh_title)
        self.pm.saved.connect(lambda p: (
            self._refresh_title(), self._set_last(f"Saved {os.path.basename(p)}")))

    def _on_state_changed(self):
        self._refresh_status()
        self.pm.mark_dirty()
        self._refresh_title()

    def _on_map_changed(self):
        self._refresh_status()
        self._set_last("Map layers updated")
        self.pm.mark_dirty()
        self._refresh_title()

    def _on_processed(self, n):
        self._refresh_status()
        self._set_last(f"Processed {n} scenes")
        self.export_tab.refresh()
        self.pm.mark_dirty()
        self._refresh_title()

    def _on_overlays_ready(self, overlays: dict):
        self.map_tab.clear_result_overlays()
        for key, meta in overlays.items():
            png_url = QUrl.fromLocalFile(meta["png"]).toString()
            self.map_tab.add_result_overlay(
                key, meta["label"], png_url, meta["bounds"], opacity=0.8)
        state.overlays = overlays
        self._set_last(f"{len(overlays)} map overlays added")

    # ── closeEvent ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.pm.dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                if not self._save_project():
                    event.ignore()
                    return
        ProjectManager.discard_autosave(self.pm.project_path)
        event.accept()

    # ── Autosave recovery ──────────────────────────────────────────────────────
    def _check_autosave_recovery(self):
        as_path = ProjectManager.check_autosave(None)
        if not as_path:
            return
        reply = QMessageBox.question(
            self, "Recover Autosave",
            f"An autosave was found:\n{as_path}\n\nRecover it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_project(as_path)

    # ── File menu actions ──────────────────────────────────────────────────────
    def _new_project(self):
        if self.pm.dirty:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save current project before creating a new one?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                if not self._save_project():
                    return
        self.pm.new_project()
        self.config_dock.apply_from_state()
        self.map_tab.map_view.load_features(
            {"aoi": [], "centerline": [], "transects": [], "stations": []})
        self.map_tab.layers.update_counts()
        self.map_tab.clear_result_overlays()
        self.process_tab.populate_scene_selector()
        self._refresh_status()
        self._refresh_title()
        self._set_last("New project")

    def _open_project(self, path: str = ""):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open RivSat Project", os.path.abspath("."),
                "RivSat Project (*.rivsat);;All (*)")
        if not path:
            return False
        if not os.path.exists(path):
            QMessageBox.warning(self, "Not found", f"File not found:\n{path}")
            return False
        try:
            warnings = self.pm.open(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open failed", str(exc))
            return False

        if warnings:
            QMessageBox.warning(self, "Missing files",
                                "Some result files are missing:\n" + "\n".join(warnings[:10]))

        # Apply config into widgets
        self.config_dock.apply_from_state()

        # Restore geometry on map
        payload = {
            "aoi": state.aoi_polygon,
            "centerline": [list(p) for p in state.centerline],
            "transects": [[list(p) for p in t] for t in state.transects],
            "stations": [
                {"name": s["name"], "lon": s["coords"][0], "lat": s["coords"][1],
                 "buffer": s.get("buffer_pixels", 2)}
                for s in state.stations
            ],
        }
        self.map_tab.map_view.load_features(payload)
        self.map_tab.layers.update_counts()

        # Reconstruct results in background-ish (blocking but fast — just reads TIFs)
        if self.pm.project_path:
            try:
                results = self.pm.reconstruct_results()
                if results:
                    self.process_tab.populate_scene_selector()
                    self.process_tab.show_scene(len(results) - 1)
                    # Rebuild overlays from latest result
                    try:
                        from rivsat.app.qt.overlays import build_overlays
                        ovs = build_overlays(results[-1], state.output_dir)
                        if ovs:
                            self._on_overlays_ready(ovs)
                    except Exception:
                        pass
            except Exception as exc:
                QMessageBox.warning(self, "Reconstruct warning",
                                    f"Could not reconstruct results:\n{exc}")

        self._rebuild_recent_menu()
        self._refresh_status()
        self._refresh_title()
        self._set_last(f"Opened {os.path.basename(path)}")
        return True

    def _save_project(self) -> bool:
        if not self.pm.project_path:
            return self._save_project_as()
        try:
            self.pm.save()
            self._rebuild_recent_menu()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False

    def _save_project_as(self) -> bool:
        default = os.path.abspath(f"./{state.site_name}.rivsat")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save RivSat Project", default,
            "RivSat Project (*.rivsat);;All (*)")
        if not path:
            return False
        if not path.endswith(".rivsat"):
            path += ".rivsat"
        try:
            self.pm.save(path)
            self._rebuild_recent_menu()
            self._refresh_title()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False

    def _about(self):
        QMessageBox.about(
            self, "About RivSat",
            "<h3>RivSat</h3>"
            "<p>Satellite-derived water quality platform for rivers, "
            "estuaries, and coasts.</p>"
            "<p>Sentinel-2 MSI · Landsat 8/9 OLI · Google Earth Engine</p>"
            "<p>6-parameter bio-optical suite: Turbidity, TSS, Chlorophyll-a, "
            "CDOM, Salinity, Secchi depth.</p>"
            f"<p style='color:{COLORS['muted']};'>Version 1.2.0</p>")
