"""Shared table behavior for data grids shown in dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget


def configure_data_table(table: QTableWidget, accessible_name: str) -> None:
    """Apply reusable Query Results table behavior to app data grids."""
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setAccessibleName(accessible_name)

    horizontal_header = table.horizontalHeader()
    horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    horizontal_header.setStretchLastSection(False)
    horizontal_header.setMinimumSectionSize(48)

    table.verticalHeader().setVisible(False)


def autosize_data_table_columns(
    table: QTableWidget,
    max_initial_width: int = 260,
    sample_rows: int = 50,
) -> None:
    """Set a bounded initial width without measuring every cell."""
    font_metrics = table.fontMetrics()
    header_metrics = table.horizontalHeader().fontMetrics()
    visible_rows = min(table.rowCount(), max(0, sample_rows))
    for column in range(table.columnCount()):
        if table.isColumnHidden(column):
            continue
        header_item = table.horizontalHeaderItem(column)
        header_text = header_item.text() if header_item is not None else ""
        width = header_metrics.horizontalAdvance(header_text) + 36
        for row in range(visible_rows):
            item = table.item(row, column)
            if item is None:
                continue
            width = max(width, font_metrics.horizontalAdvance(item.text()) + 32)
            if width >= max_initial_width:
                width = max_initial_width
                break
        table.setColumnWidth(column, max(64, min(width, max_initial_width)))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
