"""Modal dialogs for project lifecycle (New / Open).

Wraps ``rrational.gui.project.ProjectManager`` in a Qt-native UX:

- :class:`NewProjectDialog` — asks for name, parent folder, optional
  description / author / data-source checkboxes; on OK creates the
  project structure on disk and returns the ProjectManager instance.

The "Open project" path doesn't need a custom dialog — a plain
``QFileDialog.getExistingDirectory`` plus validation is enough.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from rrational.gui.project import ProjectManager


class NewProjectDialog(QDialog):
    """Collect the parameters for ``ProjectManager.create_project``."""

    def __init__(self, parent=None, default_parent_dir: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New project")
        self.setMinimumWidth(540)

        self._default_parent = default_parent_dir or Path.home()
        self._project_manager: ProjectManager | None = None

        outer = QVBoxLayout(self)

        # Metadata form
        meta_box = QGroupBox("Project metadata")
        form = QFormLayout(meta_box)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Music-Listening Pilot 2026")
        form.addRow("Name *:", self._name_edit)

        loc_row = QHBoxLayout()
        self._location_edit = QLineEdit(str(self._default_parent))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._on_browse)
        loc_row.addWidget(self._location_edit)
        loc_row.addWidget(browse)
        form.addRow("Parent folder *:", loc_row)

        self._description_edit = QLineEdit()
        self._description_edit.setPlaceholderText("One-line description (optional)")
        form.addRow("Description:", self._description_edit)

        self._author_edit = QLineEdit()
        form.addRow("Author:", self._author_edit)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText("Free-text notes (optional)")
        self._notes_edit.setMaximumHeight(90)
        form.addRow("Notes:", self._notes_edit)

        outer.addWidget(meta_box)

        # Data-source checkboxes — start with both off so nothing leaks
        # into a new project unless the user opts in.
        src_box = QGroupBox("Data sources (optional — folders created under data/raw/)")
        src_layout = QVBoxLayout(src_box)
        self._source_checks: dict[str, QCheckBox] = {}
        for source_id, display in ProjectManager.DATA_SOURCES.items():
            cb = QCheckBox(f"{display}  ({source_id}/)")
            src_layout.addWidget(cb)
            self._source_checks[source_id] = cb
        outer.addWidget(src_box)

        # Resolved-path preview line (live-updates as the user types).
        self._preview = QLabel()
        self._preview.setStyleSheet("color: #555; padding: 4px;")
        self._preview.setWordWrap(True)
        outer.addWidget(self._preview)
        self._name_edit.textChanged.connect(self._update_preview)
        self._location_edit.textChanged.connect(self._update_preview)
        self._update_preview()

        # OK / Cancel
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose parent folder", str(self._location_edit.text() or Path.home())
        )
        if chosen:
            self._location_edit.setText(chosen)

    def _update_preview(self) -> None:
        path = self._resolved_path()
        if path is None:
            self._preview.setText(
                "<i>Enter a name and parent folder to see the resolved path.</i>"
            )
        else:
            self._preview.setText(f"Will create: <code>{path}</code>")

    def _resolved_path(self) -> Path | None:
        parent = self._location_edit.text().strip()
        name = self._name_edit.text().strip()
        if not parent or not name:
            return None
        return Path(parent).expanduser() / name

    def _on_accept(self) -> None:
        path = self._resolved_path()
        if path is None:
            QMessageBox.warning(
                self,
                "Missing information",
                "Please provide a name AND a parent folder.",
            )
            return
        if path.exists() and any(path.iterdir()):
            QMessageBox.warning(
                self,
                "Folder is not empty",
                f"{path} already exists and contains files. "
                "Pick a different name or an empty folder.",
            )
            return
        sources = [sid for sid, cb in self._source_checks.items() if cb.isChecked()]
        try:
            pm = ProjectManager.create_project(
                path=path,
                name=self._name_edit.text().strip(),
                description=self._description_edit.text().strip(),
                author=self._author_edit.text().strip(),
                notes=self._notes_edit.toPlainText().strip(),
                data_sources=sources or None,  # None → hrv_logger default
            )
        except (FileExistsError, OSError) as e:
            QMessageBox.critical(
                self, "Could not create project", f"{type(e).__name__}: {e}"
            )
            return
        self._project_manager = pm
        self.accept()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    def project_manager(self) -> ProjectManager | None:
        return self._project_manager
