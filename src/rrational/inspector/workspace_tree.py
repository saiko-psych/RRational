"""Tree-sidebar with status-pill badges (Cluster C6).

Extracted from the ad-hoc ``QTreeWidget`` instantiation in
``tabs/browse_tab.py``: keeps the widget self-contained so the
participant tab and (future) project-explorer can reuse the same
"file row + coloured badges" affordance without copy-pasting the item
construction code.

The badges live in a custom :class:`QStyledItemDelegate` so each pill
gets a rounded background tinted by its category (proc / window-count /
quality / kubios / bids). Tints are pulled from :mod:`theme.palette_tokens`
so they stay in lock-step with the rest of the dark/light theme.

The widget keeps no model of its own — callers push :class:`WorkspaceItem`
records and call :meth:`set_items` to rebuild the tree wholesale.
This mirrors how ``BrowseTab._add_dataset_to_tree`` was structured and
makes the widget trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from qtpy.QtCore import QRect, QSize, Qt
from qtpy.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from qtpy.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from rrational.inspector.style.theme import palette_tokens

# Custom item-data roles. Use values past Qt.UserRole so they don't
# collide with the built-in display / decoration / tooltip slots.
ROLE_DATASET_IDX = Qt.UserRole + 1
ROLE_SECTION_NAME = Qt.UserRole + 2
ROLE_BADGES = Qt.UserRole + 3  # list[str] of badge tags

# Badge taxonomy. The colour key indexes ``palette_tokens()`` directly
# so badge tinting tracks the active theme without a second mapping.
# "info" badges fall back to ``accent`` (warm amber) since the palette
# does not ship a standalone "info" colour.
_BADGE_COLORS: dict[str, str] = {
    "PROC": "success",
    "N-WIN": "accent",
    "BAD-Q": "danger",
    "KUBIOS": "warning",
    "BIDS": "accent",
}
_BADGE_TEXT_COLOR = "#ffffff"


@dataclass
class WorkspaceItem:
    """One row in the workspace tree.

    ``children`` carries SectionMeta-like rows (no badges by default,
    callers may attach them per-section if useful). ``badges`` is a
    list of tag strings — every tag is rendered as a coloured pill to
    the right of the label.
    """

    name: str
    dataset_idx: int
    badges: list[str] = field(default_factory=list)
    tooltip: str | None = None
    section_name: str | None = None  # set for child rows
    children: list["WorkspaceItem"] = field(default_factory=list)


class _BadgeDelegate(QStyledItemDelegate):
    """Paints rounded badge pills right-aligned next to the row text.

    The delegate respects normal QTreeWidget selection / hover painting
    (it calls the base ``paint`` first), then overlays the pills using
    the per-badge colour from :data:`_BADGE_COLORS`.
    """

    # Pixel geometry of one badge — kept small so the sidebar still
    # fits on narrow displays without horizontal scroll.
    _PAD_X = 6
    _PAD_Y = 1
    _GAP = 4
    _RADIUS = 6

    def __init__(self, parent=None, mode: str = "dark") -> None:
        super().__init__(parent)
        self._tokens = palette_tokens(mode)

    def set_theme_mode(self, mode: str) -> None:
        """Re-resolve palette tokens for a new theme without rebuilding."""
        self._tokens = palette_tokens(mode)

    # ------------------------------------------------------------------
    # Geometry helper — also used by sizeHint() so badges never clip.
    # ------------------------------------------------------------------
    def _badge_size(self, text: str, fm: QFontMetrics) -> QSize:
        return QSize(
            fm.horizontalAdvance(text) + 2 * self._PAD_X,
            fm.height() + 2 * self._PAD_Y,
        )

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802 - Qt API
        base = super().sizeHint(option, index)
        badges = index.data(ROLE_BADGES) or []
        if not badges:
            return base
        fm = QFontMetrics(option.font)
        # Reserve enough width: label + gap + sum(badges + gaps).
        extra = sum(self._badge_size(b, fm).width() + self._GAP for b in badges)
        return QSize(base.width() + extra + self._PAD_X, base.height())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: N802 - Qt API
        # Render the row's normal text + selection background first, but
        # squeeze the text rect so badges don't paint on top of long
        # labels. We re-do that by hand: paint the base widget *without*
        # text, then draw text in a reduced rect.
        badges = index.data(ROLE_BADGES) or []
        if not badges:
            super().paint(painter, option, index)
            return

        # 1. Draw the row chrome (selection band, hover tint, etc.)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""  # suppress default text so we can clip it
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        # 2. Compute the badge strip on the right.
        fm = QFontMetrics(option.font)
        rect = option.rect
        x_right = rect.right() - self._PAD_X
        badge_rects: list[tuple[QRect, str]] = []
        for badge in reversed(badges):
            size = self._badge_size(badge, fm)
            top = rect.top() + (rect.height() - size.height()) // 2
            x_left = x_right - size.width()
            badge_rects.append((QRect(x_left, top, size.width(), size.height()), badge))
            x_right = x_left - self._GAP
        # Put them back in original order so painting order matches the
        # input list (handy when stylesheets later care about z-order).
        badge_rects.reverse()

        # 3. Draw text in the remaining space.
        text_rect = QRect(rect)
        if badge_rects:
            text_rect.setRight(badge_rects[0][0].left() - self._GAP)
        painter.save()
        painter.setPen(QPen(option.palette.text().color()))
        painter.setFont(option.font)
        painter.drawText(
            text_rect.adjusted(self._PAD_X, 0, 0, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            fm.elidedText(text, Qt.ElideRight, text_rect.width() - self._PAD_X),
        )
        painter.restore()

        # 4. Draw each pill.
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        for badge_rect, badge in badge_rects:
            token = _BADGE_COLORS.get(badge, "accent")
            color = QColor(self._tokens.get(token, "#888888"))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(badge_rect, self._RADIUS, self._RADIUS)
            painter.setPen(QPen(QColor(_BADGE_TEXT_COLOR)))
            badge_font = QFont(option.font)
            badge_font.setPointSizeF(max(7.0, option.font.pointSizeF() - 1.0))
            badge_font.setBold(True)
            painter.setFont(badge_font)
            painter.drawText(badge_rect, Qt.AlignCenter, badge)
        painter.restore()


class WorkspaceTreeWidget(QTreeWidget):
    """Tree sidebar with rounded coloured badges per dataset row.

    The widget owns the delegate; callers push :class:`WorkspaceItem`
    records via :meth:`set_items` or :meth:`add_item`. Active-marker
    bolding is delegated to :meth:`set_active_index`, mirroring the
    behaviour the previous ad-hoc tree had inline in BrowseTab.
    """

    def __init__(self, parent=None, theme_mode: str = "dark") -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self._delegate = _BadgeDelegate(self, mode=theme_mode)
        self.setItemDelegate(self._delegate)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_theme_mode(self, mode: str) -> None:
        """Propagate a theme change to the delegate."""
        self._delegate.set_theme_mode(mode)
        self.viewport().update()

    def set_items(self, items: Iterable[WorkspaceItem]) -> None:
        """Replace every row with ``items`` (top-level + children)."""
        self.clear()
        for item in items:
            self.add_item(item)

    def add_item(self, item: WorkspaceItem) -> QTreeWidgetItem:
        """Append a single top-level item (with optional children)."""
        top = QTreeWidgetItem(self, [item.name])
        top.setData(0, ROLE_DATASET_IDX, item.dataset_idx)
        top.setData(0, ROLE_BADGES, list(item.badges))
        if item.tooltip:
            top.setToolTip(0, item.tooltip)
        for child in item.children:
            kid = QTreeWidgetItem(top, [child.name])
            kid.setData(0, ROLE_DATASET_IDX, child.dataset_idx)
            if child.section_name is not None:
                kid.setData(0, ROLE_SECTION_NAME, child.section_name)
            if child.badges:
                kid.setData(0, ROLE_BADGES, list(child.badges))
            if child.tooltip:
                kid.setToolTip(0, child.tooltip)
        top.setExpanded(True)
        return top

    def set_active_index(self, active_idx: int | None) -> None:
        """Bold the top-level row whose dataset index matches."""
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            idx = top.data(0, ROLE_DATASET_IDX)
            font = top.font(0)
            is_active = idx is not None and idx == active_idx
            font.setBold(is_active)
            font.setWeight(QFont.Bold if is_active else QFont.Normal)
            top.setFont(0, font)
