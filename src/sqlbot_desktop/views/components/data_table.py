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


def autosize_data_table_columns(table: QTableWidget, max_initial_width: int = 260) -> None:
    """Size columns to content once, while keeping user resizing interactive."""
    table.resizeColumnsToContents()
    for column in range(table.columnCount()):
        if not table.isColumnHidden(column) and table.columnWidth(column) > max_initial_width:
            table.setColumnWidth(column, max_initial_width)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
