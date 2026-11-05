import sys
import os
import json
import re
import inspect
from importlib import reload
from pathlib import Path
import math

from maya import cmds, mel
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.api.OpenMaya as om

from ui.pyside_compat import (
    QtWidgets, QtCore, QtGui,
    QRegExp,
    QRegExpValidator,
    QAction,
    get_maya_main_window,
)

import scene_data
reload(scene_data)

class ComicNameDisplay(QtWidgets.QWidget):
    name_changed = QtCore.Signal(str)

    def __init__(self, line_data, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_data = line_data
        self.main_layout = QtWidgets.QStackedLayout()
        self.setLayout(self.main_layout)

        self.name_label = QtWidgets.QLabel(self)
        self.name_label.setText(self.line_data["name"])

        self.name_lineedit = QtWidgets.QLineEdit(self)
        self.name_lineedit.hide()

        self.main_layout.addWidget(self.name_label)
        self.main_layout.addWidget(self.name_lineedit)
        self.edit_state = False

        self.name_lineedit.editingFinished.connect(self.confirmChanges)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.switchMode()

    def switchMode(self):
        if not self.edit_state:
            self.name_lineedit.setText(self.name_label.text())
            self.main_layout.setCurrentWidget(self.name_lineedit)
            self.name_lineedit.setFocus()
            self.name_lineedit.selectAll()
            self.edit_state = True

    def confirmChanges(self):
        new_text = self.name_lineedit.text()
        if new_text == '':
            self.main_layout.setCurrentWidget(self.name_label)
            self.edit_state = False
            return
        else:
            self.name_label.setText(new_text)
            self.main_layout.setCurrentWidget(self.name_label)
            self.edit_state = False
            self.name_changed.emit(new_text)


CoolNameDisplay = ComicNameDisplay


comic_theme = """
    QWidget {
        background-color: #FBF6EE;
        color: #1A2230;
        font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
        font-size: 10pt;
    }
    QLabel {
        color: #1A2230;
        font-weight: bold;
    }
    QLineEdit {
        background-color: #FFFFFF;
        border: 2px solid #1A2230;
        border-radius: 5px;
        color: #1A2230;
        padding: 3px 6px;
        font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
        font-size: 10pt;
        selection-background-color: #DCCBB5;
    }
    QLineEdit:focus {
        border: 2px solid #000000;
        background-color: #FFFDF9;
    }
    QPushButton {
        background-color: #FFFFFF;
        border: 2px solid #1A2230;
        border-radius: 6px;
        color: #1A2230;
        padding: 4px 10px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #F0E7D8;
    }
    QPushButton:pressed {
        background-color: #DCCBB5;
    }
    QSlider::groove:horizontal {
        height: 6px;
        background: #EAE1D2;
        border: 1.5px solid #1A2230;
        border-radius: 3px;
    }
    QSlider::sub-page:horizontal {
        background: #1A2230;
        border-radius: 3px;
    }
    QSlider::handle:horizontal {
        background: #FFFFFF;
        border: 2px solid #1A2230;
        width: 14px;
        margin-top: -5px;
        margin-bottom: -5px;
        border-radius: 7px;
    }
    QSlider::handle:horizontal:hover {
        background: #F0E7D8;
    }
    QListWidget {
        background-color: #FFFFFF;
        border: 2px solid #1A2230;
        border-radius: 6px;
        padding: 2px;
    }
    QListWidget::item {
        border-bottom: 1px dashed #D5C8B5;
        padding: 3px;
    }
    QListWidget::item:selected {
        background-color: #EFE5D3;
        color: #1A2230;
        border-radius: 4px;
    }
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #D5C8B5;
        border: 1.5px solid #1A2230;
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #1A2230;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QToolTip {
        background-color: #FFFFFF;
        color: #1A2230;
        border: 1.5px solid #1A2230;
        border-radius: 4px;
        padding: 4px;
        font-size: 9pt;
    }
"""


class ComicTitleBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()

        # Title text: Cartoon Lineart
        font = QtGui.QFont("Segoe Print", 13, QtGui.QFont.Bold)
        if not font.exactMatch():
            font = QtGui.QFont("Ink Free", 13, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#1A2230"))
        painter.drawText(QtCore.QRect(0, 4, w, 28), QtCore.Qt.AlignCenter, "Cartoon Lineart")

        # Dynamic underline scribble ~
        cx = w // 2
        path = QtGui.QPainterPath()
        path.moveTo(cx - 30, 36)
        path.lineTo(cx + 10, 34)
        path.lineTo(cx - 15, 39)
        path.lineTo(cx + 25, 38)
        painter.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.strokePath(path, painter.pen())


class ComicSeparator(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()
        y = self.height() // 2

        pen = QtGui.QPen(QtGui.QColor("#1A2230"), 1.8, QtCore.Qt.DashLine, QtCore.Qt.RoundCap)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.drawLine(6, y, w - 6, y)


class ComicCollapsibleHeader(QtWidgets.QPushButton):
    toggled_collapse = QtCore.Signal(bool)

    def __init__(self, title="Content", parent=None):
        super().__init__(parent)
        self.title_text = title
        self.is_expanded = True
        self.setFixedHeight(28)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("QPushButton { border: none; background: transparent; text-align: left; padding: 2px 4px; }")
        self.clicked.connect(self.toggle)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.toggled_collapse.emit(self.is_expanded)
        self.update()

    def setExpanded(self, expanded):
        if self.is_expanded != expanded:
            self.is_expanded = expanded
            self.toggled_collapse.emit(self.is_expanded)
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Hover background
        if self.underMouse():
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#F0E6D5")))
            painter.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 1.2, QtCore.Qt.DashLine))
            painter.drawRoundedRect(1, 1, w - 2, h - 2, 5, 5)

        # Title text font
        font = QtGui.QFont("Segoe Print", 10, QtGui.QFont.Bold)
        if not font.exactMatch():
            font = QtGui.QFont("Ink Free", 10, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#1A2230"))
        painter.drawText(QtCore.QRect(6, 0, w - 30, h), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.title_text)

        # Draw comic arrow indicator on the right
        arrow_x = w - 16
        arrow_y = h // 2
        painter.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#1A2230")))

        if self.is_expanded:
            arrow = QtGui.QPolygonF([
                QtCore.QPointF(arrow_x - 5, arrow_y - 2),
                QtCore.QPointF(arrow_x, arrow_y + 3),
                QtCore.QPointF(arrow_x + 5, arrow_y - 2)
            ])
            painter.drawPolygon(arrow)
        else:
            arrow = QtGui.QPolygonF([
                QtCore.QPointF(arrow_x - 3, arrow_y - 5),
                QtCore.QPointF(arrow_x + 3, arrow_y),
                QtCore.QPointF(arrow_x - 3, arrow_y + 5)
            ])
            painter.drawPolygon(arrow)


class ComicBrushButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setFixedSize(62, 62)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Click to draw line on target mesh")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        is_active = self.isChecked()
        is_down = self.isDown() or is_active
        is_hover = self.underMouse()

        rect = QtCore.QRect(3, 3, 56, 56)
        if is_active:
            btn_rect = rect.translated(1, 1)
            bg_col = QtGui.QColor("#FFD99B") if is_hover else QtGui.QColor("#FFE4B8")
            border_col = QtGui.QColor("#D94A38")  # Highlight border in brush dip red
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(217, 74, 56, 35)))
            painter.drawRoundedRect(rect.translated(2, 2), 9, 9)
        elif is_down:
            btn_rect = rect.translated(1, 1)
            bg_col = QtGui.QColor("#FFE4B8")
            border_col = QtGui.QColor("#1A2230")
        elif is_hover:
            btn_rect = rect.translated(0, -1)
            bg_col = QtGui.QColor("#FFF6E8")
            border_col = QtGui.QColor("#2C3E50")
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 34, 48, 28)))
            painter.drawRoundedRect(rect.translated(2, 2), 9, 9)
        else:
            btn_rect = rect
            bg_col = QtGui.QColor("#FFFFFF")
            border_col = QtGui.QColor("#1A2230")
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 34, 48, 22)))
            painter.drawRoundedRect(rect.translated(2, 2), 9, 9)

        # Card body
        painter.setBrush(QtGui.QBrush(bg_col))
        painter.setPen(QtGui.QPen(border_col, 2.4 if is_active else 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawRoundedRect(btn_rect, 9, 9)

        # Draw brush & painted line inside btn_rect
        painter.save()
        painter.translate(btn_rect.topLeft())
        self._draw_brush_artwork(painter)
        painter.restore()

    def _draw_brush_artwork(self, p):
        tip = QtCore.QPointF(20, 43)

        # 1. Clean painted comic line in a smooth S-curve
        stroke = QtGui.QPainterPath()
        stroke.moveTo(tip)
        stroke.cubicTo(12, 42, 8, 33, 13, 25)
        stroke.cubicTo(17, 19, 17, 14, 12, 9)

        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 3.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        p.strokePath(stroke, p.pen())

        # 2. Paintbrush angled at -45 deg
        p.save()
        p.translate(tip)
        p.rotate(-45)

        ink_pen = QtGui.QPen(QtGui.QColor("#1A2230"), 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        p.setPen(ink_pen)

        # Wooden handle shaft
        wood_poly = QtGui.QPolygonF([
            QtCore.QPointF(19, -3.5),
            QtCore.QPointF(34, -2.4),
            QtCore.QPointF(34, 2.4),
            QtCore.QPointF(19, 3.5)
        ])
        p.setBrush(QtGui.QBrush(QtGui.QColor("#E5B074")))
        p.drawPolygon(wood_poly)

        # Red dipped tail (classic comic artist brush)
        tail_poly = QtGui.QPolygonF([
            QtCore.QPointF(34, -2.4),
            QtCore.QPointF(43, -1.6),
            QtCore.QPointF(43, 1.6),
            QtCore.QPointF(34, 2.4)
        ])
        p.setBrush(QtGui.QBrush(QtGui.QColor("#D94A38")))
        p.drawPolygon(tail_poly)
        p.drawEllipse(QtCore.QPointF(42.5, 0), 1.8, 1.8)

        # Silver Ferrule
        ferrule_poly = QtGui.QPolygonF([
            QtCore.QPointF(10, -4.0),
            QtCore.QPointF(19, -3.5),
            QtCore.QPointF(19, 3.5),
            QtCore.QPointF(10, 4.0)
        ])
        p.setBrush(QtGui.QBrush(QtGui.QColor("#D6DCE5")))
        p.drawPolygon(ferrule_poly)
        p.drawLine(QtCore.QPointF(14.5, -3.7), QtCore.QPointF(14.5, 3.7))

        # Bristles (dark ink, flexed tip touching paper)
        bristles = QtGui.QPainterPath()
        bristles.moveTo(10, -4.0)
        bristles.cubicTo(6, -4.2, 2, -2.5, 0, 0)
        bristles.cubicTo(2, 2.5, 6, 4.2, 10, 4.0)
        bristles.closeSubpath()
        p.setBrush(QtGui.QBrush(QtGui.QColor("#1A2230")))
        p.drawPath(bristles)

        p.restore()

class ComicCheckBox(QtWidgets.QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)

        bg = QtGui.QColor("#EFE5D3") if self.underMouse() else QtGui.QColor("#FFFFFF")
        painter.setBrush(QtGui.QBrush(bg))
        painter.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawRoundedRect(rect, 4, 4)

        if self.isChecked():
            pen = QtGui.QPen(QtGui.QColor("#1A2230"), 2.4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(5, 11, 9, 15)
            painter.drawLine(9, 15, 16, 6)

class ComicSettingCheckBox(QtWidgets.QCheckBox):
    """
    Comic-styled QCheckBox with custom indicator and Segoe Print text.
    Handles hover, checked, and disabled states.
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

    def sizeHint(self):
        fm = self.fontMetrics()
        txt = self.text()
        w = 26 + (fm.horizontalAdvance(txt) if hasattr(fm, 'horizontalAdvance') else fm.width(txt))
        h = max(22, fm.height() + 4)
        return QtCore.QSize(w, h)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        box_size = 18
        y_box = (self.height() - box_size) // 2
        rect = QtCore.QRect(2, y_box, box_size, box_size)

        is_enabled = self.isEnabled()
        border_col = QtGui.QColor("#1A2230") if is_enabled else QtGui.QColor("#A0A8B4")
        text_col = QtGui.QColor("#1A2230") if is_enabled else QtGui.QColor("#8A92A0")

        if not is_enabled:
            bg_col = QtGui.QColor("#E8E2D8")
        elif self.underMouse():
            bg_col = QtGui.QColor("#EFE5D3")
        else:
            bg_col = QtGui.QColor("#FFFFFF")

        painter.setBrush(QtGui.QBrush(bg_col))
        painter.setPen(QtGui.QPen(border_col, 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawRoundedRect(rect, 4, 4)

        if self.isChecked():
            pen = QtGui.QPen(border_col, 2.2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(rect.x() + 4, rect.y() + 9, rect.x() + 7, rect.y() + 13)
            painter.drawLine(rect.x() + 7, rect.y() + 13, rect.x() + 14, rect.y() + 5)

        if self.text():
            painter.setPen(text_col)
            font = self.font()
            painter.setFont(font)
            text_rect = QtCore.QRect(box_size + 8, 0, self.width() - (box_size + 8), self.height())
            painter.drawText(text_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, self.text())



class ComicTrashButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Delete this line")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        is_hover = self.underMouse()
        bg = QtGui.QColor("#FBE8E8") if is_hover else QtGui.QColor("#FFFFFF")
        pen_col = QtGui.QColor("#D93838") if is_hover else QtGui.QColor("#1A2230")

        painter.setBrush(QtGui.QBrush(bg))
        painter.setPen(QtGui.QPen(QtGui.QColor("#1A2230"), 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawRoundedRect(rect, 4, 4)

        p = QtGui.QPen(pen_col, 1.8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        painter.setPen(p)
        dx = (self.width() - 24) // 2
        dy = (self.height() - 24) // 2
        painter.drawLine(dx + 9, dy + 5, dx + 14, dy + 5)
        painter.drawLine(dx + 5, dy + 7, dx + 18, dy + 7)
        painter.drawLine(dx + 7, dy + 8, dx + 8, dy + 18)
        painter.drawLine(dx + 16, dy + 8, dx + 15, dy + 18)
        painter.drawLine(dx + 8, dy + 18, dx + 15, dy + 18)
        painter.drawLine(dx + 10, dy + 10, dx + 10, dy + 15)
        painter.drawLine(dx + 13, dy + 10, dx + 13, dy + 15)


class ComicFooterAccents(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        w = self.width()

        pen = QtGui.QPen(QtGui.QColor("#1A2230"), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(pen)

        # Bottom-left accent: ^ and ,
        painter.drawLine(8, 4, 12, 10)
        painter.drawLine(12, 10, 8, 14)
        painter.drawLine(14, 12, 17, 15)

        # Bottom-right accent: action marks ,,
        painter.drawLine(w - 14, 6, w - 8, 12)
        painter.drawLine(w - 10, 12, w - 6, 16)

        # Center underline squiggle
        cx = w // 2
        painter.drawLine(cx - 12, 8, cx + 12, 8)


class RebuildLineOptionsDialog(QtWidgets.QDialog):
    """
    Modal dialog to choose which subsets of properties to rebuild:
    - UI elements (Line width, Sweep shape, Smoothable, Displacement, Disp type, Color)
    - Custom attributes (Taper profile & points, Sides, cap, rotate_profile, noise parameters)
    - Follow method (switch or re-apply follow method to the currently active UI follow method)
    """
    def __init__(self, parent=None, initial_options=None):
        if parent is None:
            parent = get_maya_main_window()
        super().__init__(parent)
        self.setWindowTitle("Rebuild Line (wip)")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setFixedWidth(310)
        self.setStyleSheet("""
            QDialog {
                background-color: #FBF6EE;
            }
            QLabel {
                color: #1A2230;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel("Select properties to rebuild:", self)
        header.setStyleSheet("font-size: 10.5pt; font-weight: bold; color: #1A2230;")
        layout.addWidget(header)

        init_opts = initial_options or {"ui_elements": True, "custom_attrs": False, "follow_method": False}

        self.cb_ui_elements = ComicSettingCheckBox("UI elements", self)
        self.cb_ui_elements.setChecked(bool(init_opts.get("ui_elements", True)))
        self.cb_ui_elements.setToolTip("Apply basic UI settings:\nLine width, Sweep shape, Smoothable, Displacement, Disp type, Color.")
        layout.addWidget(self.cb_ui_elements)

        self.cb_custom_attrs = ComicSettingCheckBox("Custom attributes", self)
        self.cb_custom_attrs.setChecked(bool(init_opts.get("custom_attrs", False)))
        self.cb_custom_attrs.setToolTip("Apply custom line attributes:\nTaper profile & intermediate points, Sides, cap, noise/displacement parameters, etc.")
        layout.addWidget(self.cb_custom_attrs)

        self.cb_follow_method = ComicSettingCheckBox("Follow method", self)
        self.cb_follow_method.setChecked(bool(init_opts.get("follow_method", False)))
        self.cb_follow_method.setToolTip("Re-apply and update the line's follow method to the currently active UI follow method (Node, Wrap, or UV pin).")
        layout.addWidget(self.cb_follow_method)

        layout.addSpacing(6)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancel = QtWidgets.QPushButton("Cancel", self)
        self.btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #1A2230;
                border: 2px solid #1A2230;
                border-radius: 6px;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-weight: bold;
                font-size: 9.5pt;
                padding: 5px 14px;
            }
            QPushButton:hover {
                background-color: #EFE5D3;
            }
        """)

        self.btn_rebuild = QtWidgets.QPushButton("Rebuild", self)
        self.btn_rebuild.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_rebuild.setStyleSheet("""
            QPushButton {
                background-color: #1A2230;
                color: #FBF6EE;
                border: 2px solid #1A2230;
                border-radius: 6px;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-weight: bold;
                font-size: 9.5pt;
                padding: 5px 16px;
            }
            QPushButton:hover {
                background-color: #313B4D;
            }
        """)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_rebuild)
        layout.addLayout(btn_layout)

        self.btn_rebuild.clicked.connect(self.on_rebuild_clicked)
        self.btn_cancel.clicked.connect(self.reject)

    def on_rebuild_clicked(self):
        if not (self.cb_ui_elements.isChecked() or self.cb_custom_attrs.isChecked() or self.cb_follow_method.isChecked()):
            try:
                cmds.inViewMessage(amg="Please check at least one option to rebuild.", pos='topCenter', fade=True)
            except Exception:
                pass
            if not cmds.about(batch=True):
                QtWidgets.QMessageBox.information(self, "Rebuild line (wip)", "Please check at least one option to rebuild.")
            return
        self.accept()

    def rebuild_ui_elements(self):
        return self.cb_ui_elements.isChecked()

    def rebuild_custom_attrs(self):
        return self.cb_custom_attrs.isChecked()

    def rebuild_follow_method(self):
        return self.cb_follow_method.isChecked()

    def get_options(self):
        return {
            "ui_elements": self.rebuild_ui_elements(),
            "custom_attrs": self.rebuild_custom_attrs(),
            "follow_method": self.rebuild_follow_method()
        }

    def set_options(self, ui_elements=True, custom_attrs=True, follow_method=True):
        self.cb_ui_elements.setChecked(bool(ui_elements))
        self.cb_custom_attrs.setChecked(bool(custom_attrs))
        self.cb_follow_method.setChecked(bool(follow_method))


main_window_instance = None
paint_on_mesh = None
global_scene_data_obj = scene_data.GlobalSceneData()
cartoon_lineart_shader = None

line_default_scale = 0.1
line_subdiv_offset = 0.01
line_resolution = 5
curve_points = 4
smooth_curve = 1.0
brush_size = 1.0
current_follow_method = "Node based"
current_line_color = (0.0, 0.0, 0.0)
line_smoothable = False
line_displacement = False
line_add_noise = False
line_disp_type = "noise"
line_sweep_shape = 1.0

# Ensure sweep plugin is loaded
if not cmds.pluginInfo('sweep', q=True, loaded=True):
    try:
        cmds.loadPlugin('sweep')
    except Exception as e:
        print(f"Warning: could not load sweep plugin: {e}")

# Patch Maya's AEstrokeTemplate to avoid 'No object matches name: strokeShapeDefaultBrush1.useNormal' error
try:
    mel.eval('''
    global proc AEstrokeDimUseNormal( string $nodeName )
    {
        if (`objExists ($nodeName + ".useNormal")`) {
            int $n = `getAttr ($nodeName + ".useNormal")`;
            editorTemplate -dimControl $nodeName "normal" (!$n);
            editorTemplate -dimControl $nodeName "minimalTwist" ($n);
        }
    }
    ''')
except Exception:
    pass

# Installing script job to refresh file on scene opened
scene_event_catcher_num = cmds.scriptJob(event=["SceneOpened", global_scene_data_obj.detectSceneChange])


def findOrCreateShaderForColor(color=None):
    """
    Finds an existing surfaceShader with a color similar to `color` (tolerance < 0.02),
    or creates a new one and its shading group. Returns (shader, shading_engine).
    """
    if color is None:
        color = current_line_color
    r, g, b = float(color[0]), float(color[1]), float(color[2])

    all_shaders = cmds.ls(type='surfaceShader') or []
    best_shader = None
    best_dist = 0.02

    for s in all_shaders:
        if cmds.attributeQuery('outColor', node=s, exists=True):
            try:
                sc = cmds.getAttr(f"{s}.outColor")[0]
                dist = ((sc[0] - r) ** 2 + (sc[1] - g) ** 2 + (sc[2] - b) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_shader = s
            except Exception:
                pass

    if best_shader:
        sgs = cmds.listConnections(f"{best_shader}.outColor", type='shadingEngine') or []
        if not sgs:
            sgs = cmds.listConnections(best_shader, type='shadingEngine') or []
        if sgs:
            return best_shader, sgs[0]
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{best_shader}SG")
        cmds.connectAttr(f"{best_shader}.outColor", f"{sg}.surfaceShader")
        return best_shader, sg

    # Otherwise create a new shader
    hex_col = f"{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
    base_name = f"CartoonLineart_{hex_col}" if hex_col != "000000" else "CartoonLineartShader"
    sg_name = f"{base_name}SG"

    if not cmds.objExists(base_name):
        sh = cmds.createNode('surfaceShader', name=base_name, ss=True)
    else:
        sh = cmds.createNode('surfaceShader', name=f"{base_name}#", ss=True)
        sg_name = f"{sh}SG"

    cmds.setAttr(f"{sh}.outColor", r, g, b, type='double3')

    if not cmds.objExists(sg_name):
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
        cmds.connectAttr(f"{sh}.outColor", f"{sg}.surfaceShader")
    else:
        sg = sg_name

    return sh, sg


def getLineMeshColor(mesh_node):
    """
    Retrieves the RGB color of the shader currently assigned to `mesh_node`.
    """
    if not mesh_node or not cmds.objExists(mesh_node):
        return tuple(current_line_color)

    shapes = cmds.listRelatives(mesh_node, s=True, fullPath=True) or [mesh_node]
    for shape in shapes:
        sgs = cmds.listConnections(shape, type='shadingEngine') or []
        for sg in sgs:
            shaders = cmds.listConnections(f"{sg}.surfaceShader") or []
            if shaders:
                sh = shaders[0]
                if cmds.attributeQuery('outColor', node=sh, exists=True):
                    col = cmds.getAttr(f"{sh}.outColor")[0]
                    return (float(col[0]), float(col[1]), float(col[2]))
                elif cmds.attributeQuery('color', node=sh, exists=True):
                    col = cmds.getAttr(f"{sh}.color")[0]
                    return (float(col[0]), float(col[1]), float(col[2]))
    return tuple(current_line_color)


def detectOrCreateShader(color=None):
    sh, _ = findOrCreateShaderForColor(color)
    global cartoon_lineart_shader
    cartoon_lineart_shader = sh
    return sh


def assignLineShader(mesh_node, color=None):
    sh, sg = findOrCreateShaderForColor(color)
    if sg and cmds.objExists(sg):
        try:
            cmds.sets(mesh_node, forceElement=sg)
            return sh, sg
        except Exception:
            pass
    try:
        cmds.select(mesh_node, r=True)
        cmds.hyperShade(assign=sh)
        cmds.select(cl=True)
    except Exception:
        pass
    return sh, sg


DEFAULT_BASIC_PRESET = {
    "line_default_scale": 0.1,
    "scale_profile": 0.1,
    "line_resolution": 5,
    "line_subdiv_offset": 0.01,
    "curve_points": 4,
    "smooth_curve": 1.0,
    "line_sweep_shape": 1.0,
    "roundness": 1.0,
    "current_line_color": [0.0, 0.0, 0.0],
    "color": [0.0, 0.0, 0.0],
    "line_smoothable": False,
    "smoothable": False,
    "line_displacement": False,
    "displacement": False,
    "line_disp_type": "noise",
    "disp_type": "noise",
    "Sides": 6,
    "Start_value": 0.0,
    "End_value": 0.0,
    "Pt1_value": 0.3,
    "PtLast_value": 0.7,
    "smooth_method": 0,
    "smooth_divisions": 1,
    "disp_strength": 0.03,
    "disp_offset": 0.0,
    "noise_type": 1,
    "frequency": 12.0,
    "ratio": 0.7,
    "time": 0.0
}
DEFAULT_NEUTRAL_PRESET = DEFAULT_BASIC_PRESET

DEFAULT_INKBRUSH_PRESET = {
    "line_default_scale": 0.15,
    "scale_profile": 0.15,
    "line_resolution": 5,
    "line_subdiv_offset": 0.01,
    "curve_points": 4,
    "smooth_curve": 1.0,
    "line_sweep_shape": 0.85,
    "roundness": 0.85,
    "current_line_color": [0.0, 0.0, 0.0],
    "color": [0.0, 0.0, 0.0],
    "line_smoothable": True,
    "smoothable": True,
    "line_displacement": True,
    "displacement": True,
    "line_disp_type": "noise",
    "disp_type": "noise",
    "Sides": 8,
    "Start_value": 0.0,
    "End_value": 0.0,
    "Pt1_value": 0.35,
    "PtLast_value": 0.75,
    "smooth_method": 0,
    "smooth_divisions": 1,
    "disp_strength": 0.025,
    "disp_offset": 0.0,
    "noise_type": 1,
    "frequency": 14.0,
    "ratio": 0.7,
    "time": 0.0
}

active_preset_config = dict(DEFAULT_BASIC_PRESET)
_copied_line_attributes = None


def get_presets_file_path():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except (NameError, TypeError):
        script_dir = os.getcwd()
    local_path = os.path.join(script_dir, "presets.json")
    try:
        if not os.path.exists(local_path):
            with open(local_path, "w") as f:
                json.dump({"Basic": DEFAULT_BASIC_PRESET, "InkBrush": DEFAULT_INKBRUSH_PRESET}, f, indent=2)
        return local_path
    except Exception:
        pref_dir = cmds.internalVar(userPrefDir=True)
        fallback_path = os.path.join(pref_dir, "CartoonLineart_presets.json")
        if not os.path.exists(fallback_path):
            try:
                with open(fallback_path, "w") as f:
                    json.dump({"Basic": DEFAULT_BASIC_PRESET, "InkBrush": DEFAULT_INKBRUSH_PRESET}, f, indent=2)
            except Exception:
                pass
        return fallback_path


def load_all_presets():
    file_path = get_presets_file_path()
    presets = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                presets = json.load(f)
        except Exception:
            presets = {}
    if not isinstance(presets, dict):
        presets = {}

    # Migrate legacy names if present
    if "neutral" in presets:
        if "Basic" not in presets:
            presets["Basic"] = presets.pop("neutral")
        else:
            presets.pop("neutral")
    if "TestMangaStyle" in presets:
        if "InkBrush" not in presets:
            presets["InkBrush"] = presets.pop("TestMangaStyle")
        else:
            presets.pop("TestMangaStyle")
    if "custom" in presets:
        presets.pop("custom")

    if "Basic" not in presets:
        presets["Basic"] = dict(DEFAULT_BASIC_PRESET)
    return presets


def save_user_preset(name, data):
    file_path = get_presets_file_path()
    presets = load_all_presets()
    presets[name] = data
    try:
        with open(file_path, "w") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: could not save preset file: {e}")
        return False


def delete_user_preset(name):
    if not name or name in ["Basic", "neutral", "Custom", "custom"]:
        return False
    file_path = get_presets_file_path()
    presets = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                presets = json.load(f)
        except Exception:
            presets = {}
    if not isinstance(presets, dict):
        presets = {}
    if name in presets:
        presets.pop(name)
        try:
            with open(file_path, "w") as f:
                json.dump(presets, f, indent=2)
            return True
        except Exception as e:
            print(f"Warning: could not delete preset: {e}")
            return False
    return False


def extractLineAttributes(mesh_node, line_data=None):
    if not mesh_node or not cmds.objExists(mesh_node):
        return None

    data = {
        "color": getLineMeshColor(mesh_node)
    }

    # Profile attributes
    for a in ['scale_profile', 'roundness', 'rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
              'Start_position', 'Start_value', 'End_position', 'End_value']:
        if cmds.attributeQuery(a, node=mesh_node, exists=True):
            try:
                data[a] = cmds.getAttr(f"{mesh_node}.{a}")
            except Exception:
                pass

    # Intermediate taper points
    data["intermediate_points"] = []
    i = 1
    while cmds.attributeQuery(f"Pt{i}_position", node=mesh_node, exists=True):
        pt_entry = {
            "idx": i,
            "pos": cmds.getAttr(f"{mesh_node}.Pt{i}_position"),
            "val": cmds.getAttr(f"{mesh_node}.Pt{i}_value") if cmds.attributeQuery(f"Pt{i}_value", node=mesh_node, exists=True) else 1.0,
            "interp": cmds.getAttr(f"{mesh_node}.Pt{i}_interp") if cmds.attributeQuery(f"Pt{i}_interp", node=mesh_node, exists=True) else 1,
        }
        data["intermediate_points"].append(pt_entry)
        i += 1

    # Smooth
    has_smooth = bool(line_data.get("smoothable")) if line_data else False
    if not has_smooth:
        has_smooth = cmds.attributeQuery('divisions', node=mesh_node, exists=True)
    data["smoothable"] = has_smooth
    if has_smooth:
        if cmds.attributeQuery('method', node=mesh_node, exists=True):
            data["method"] = cmds.getAttr(f"{mesh_node}.method")
        if cmds.attributeQuery('divisions', node=mesh_node, exists=True):
            data["divisions"] = cmds.getAttr(f"{mesh_node}.divisions")

    # Displacement
    has_disp = bool(line_data.get("displacement")) if line_data else False
    if not has_disp:
        has_disp = cmds.attributeQuery('strength', node=mesh_node, exists=True)
    data["displacement"] = has_disp
    if has_disp:
        disp_type = "noise"
        if line_data and line_data.get("disp_type"):
            disp_type = line_data["disp_type"]
        elif line_data and line_data.get("noise_node") and cmds.objExists(line_data["noise_node"]):
            disp_type = cmds.nodeType(line_data["noise_node"])
        else:
            hist = cmds.listHistory(mesh_node) or []
            for h in hist:
                if cmds.nodeType(h) == "textureDeformer":
                    conn = cmds.listConnections(f"{h}.texture", s=True, d=False) or []
                    for c in conn:
                        nt = cmds.nodeType(c)
                        if nt in ["noise", "mountain", "fractal"]:
                            disp_type = nt
                            break
        data["disp_type"] = disp_type

        for a in ['strength', 'offset', 'noise_type', 'frequency', 'ratio', 'time',
                  'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
                  'amplitude', 'frequency_ratio']:
            if cmds.attributeQuery(a, node=mesh_node, exists=True):
                try:
                    data[a] = cmds.getAttr(f"{mesh_node}.{a}")
                except Exception:
                    pass

    return data


def removeSmoothFromStrokeMesh(stroke_mesh, line_data=None):
    if not stroke_mesh or not cmds.objExists(stroke_mesh):
        return
    hist = cmds.listHistory(stroke_mesh) or []
    for h in hist:
        if cmds.objExists(h) and cmds.nodeType(h) == "polySmoothFace":
            try:
                cmds.delete(h)
            except Exception:
                pass
    for attr in ['Smooth', 'method', 'divisions']:
        if cmds.attributeQuery(attr, node=stroke_mesh, exists=True):
            try:
                cmds.setAttr(f"{stroke_mesh}.{attr}", lock=False)
                cmds.deleteAttr(f"{stroke_mesh}.{attr}")
            except Exception:
                pass
    if line_data is not None:
        line_data["smooth_node"] = None
        line_data["smoothable"] = False


def removeDisplacementFromStrokeMesh(stroke_mesh, line_data=None):
    if not stroke_mesh or not cmds.objExists(stroke_mesh):
        return
    hist = cmds.listHistory(stroke_mesh) or []
    for h in hist:
        if cmds.objExists(h) and cmds.nodeType(h) == "textureDeformer":
            conn = cmds.listConnections(f"{h}.texture", s=True, d=False) or []
            for c in conn:
                if cmds.objExists(c) and cmds.nodeType(c) in ["noise", "mountain", "fractal"]:
                    try:
                        cmds.delete(c)
                    except Exception:
                        pass
            handle_conn = cmds.listConnections(f"{h}.handleMatrix", s=True, d=False) or []
            for hc in handle_conn:
                if cmds.objExists(hc):
                    try:
                        cmds.delete(hc)
                    except Exception:
                        pass
            if cmds.objExists(h):
                try:
                    cmds.delete(h)
                except Exception:
                    pass
    for attr in ['Displacement', 'Noise', 'strength', 'offset', 'noise_type', 'frequency', 'ratio', 'time',
                 'snow_roughness', 'rock_roughness', 'boundary', 'altitude', 'amplitude', 'frequency_ratio',
                 'noise_strength', 'noise_offset', 'noise_frequency', 'noise_ratio', 'noise_time']:
        if cmds.attributeQuery(attr, node=stroke_mesh, exists=True):
            try:
                cmds.setAttr(f"{stroke_mesh}.{attr}", lock=False)
                cmds.deleteAttr(f"{stroke_mesh}.{attr}")
            except Exception:
                pass
    if line_data is not None:
        line_data["tex_def_node"] = None
        line_data["noise_node"] = None
        line_data["tex_handle"] = None
        line_data["displacement"] = False
        line_data["add_noise"] = False


def rebuildLine(line_data, new_attrs=None, rebuild_ui_elements=True, rebuild_custom_attrs=True, rebuild_follow_method=False):
    """
    Rebuilds / adapts a cartoon line with given attributes (or active UI settings).
    Allows selective rebuilding of:
    - rebuild_ui_elements: Profile scale, roundness, smoothable toggle, displacement toggle, disp_type, color shader
    - rebuild_custom_attrs: Sides, rotate_profile, cap, precision, optimize_precision, taper points,
                            smooth divisions/method, displacement noise parameters
    - rebuild_follow_method: Switches or re-applies line follow method to the specified or active UI follow method
    """
    if not line_data:
        return False

    line_name = line_data.get("name", "line")
    mesh = line_data.get("mesh")
    if not mesh or not cmds.objExists(mesh):
        grp = line_data.get("group") or f"{line_name}_grp"
        if grp and cmds.objExists(grp):
            transforms = cmds.listRelatives(grp, allDescendents=True, type="transform") or []
            for tr in transforms:
                if tr.endswith("_msh") and cmds.objExists(tr):
                    mesh = tr
                    line_data["mesh"] = mesh
                    break
        elif cmds.objExists(f"{line_name}_msh"):
            mesh = f"{line_name}_msh"
            line_data["mesh"] = mesh

    if not mesh or not cmds.objExists(mesh):
        return False

    if new_attrs is None:
        if global_main_widget and hasattr(global_main_widget, "getCurrentUISettings"):
            new_attrs = global_main_widget.getCurrentUISettings()
        elif isinstance(active_preset_config, dict):
            new_attrs = dict(active_preset_config)
        else:
            new_attrs = {}

    line_group = line_data.get("group") or (cmds.listRelatives(mesh, p=True)[0] if cmds.listRelatives(mesh, p=True) else None)
    if line_group:
        line_data["group"] = line_group

    # 1. Sweep mesh node and profile wiring (structural wiring)
    sweep_mesh_node = line_data.get("sweep_mesh_node")
    if not sweep_mesh_node or not cmds.objExists(sweep_mesh_node):
        hist = cmds.listHistory(mesh) or []
        for h in hist:
            if cmds.nodeType(h) == "sweepMeshCreator":
                sweep_mesh_node = h
                line_data["sweep_mesh_node"] = sweep_mesh_node
                break

    # Ensure profile multDL exists for roundness (flat to round)
    if sweep_mesh_node and cmds.objExists(sweep_mesh_node):
        if not cmds.attributeQuery('roundness', node=mesh, exists=True):
            cmds.addAttr(mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=1.0, shortName='roundness')
            cmds.setAttr(f"{mesh}.roundness", 1.0)

        pm = line_data.get("profile_mult_node")
        if not pm or not cmds.objExists(pm):
            pm = f"{mesh}_profileY_mult"
            if not cmds.objExists(pm):
                pm = cmds.createNode('multDL', n=pm, ss=True)
            line_data["profile_mult_node"] = pm

        if cmds.attributeQuery('scale_profile', node=mesh, exists=True):
            if not cmds.isConnected(f"{mesh}.scale_profile", f"{pm}.input1"):
                cmds.connectAttr(f"{mesh}.scale_profile", f"{pm}.input1", force=True)
            if not cmds.isConnected(f"{mesh}.roundness", f"{pm}.input2"):
                cmds.connectAttr(f"{mesh}.roundness", f"{pm}.input2", force=True)
            if not cmds.isConnected(f"{pm}.output", f"{sweep_mesh_node}.scaleProfileY"):
                cmds.connectAttr(f"{pm}.output", f"{sweep_mesh_node}.scaleProfileY", force=True)
            if not cmds.isConnected(f"{mesh}.scale_profile", f"{sweep_mesh_node}.scaleProfileX"):
                cmds.connectAttr(f"{mesh}.scale_profile", f"{sweep_mesh_node}.scaleProfileX", force=True)

        if not cmds.attributeQuery('cap', node=mesh, exists=True):
            cmds.addAttr(mesh, at='bool', k=True, defaultValue=False, shortName='cap')
            cmds.setAttr(f"{mesh}.cap", 0)
        if not cmds.isConnected(f"{mesh}.cap", f"{sweep_mesh_node}.capsEnable"):
            try:
                cmds.connectAttr(f"{mesh}.cap", f"{sweep_mesh_node}.capsEnable", force=True)
            except Exception:
                pass

        if not cmds.attributeQuery('Sides', node=mesh, exists=True):
            cmds.addAttr(mesh, at='long', k=True, shortName='Sides', min=1, defaultValue=6)
            cmds.setAttr(f"{mesh}.Sides", 6)
        if not cmds.isConnected(f"{mesh}.Sides", f"{sweep_mesh_node}.profilePolySides"):
            try:
                cmds.connectAttr(f"{mesh}.Sides", f"{sweep_mesh_node}.profilePolySides", force=True)
            except Exception:
                pass

    # Ensure multDL node exists for visibility bypass
    mult_node = line_data.get("mult_dl_node") or (f"{line_name}_multDL" if line_name else None)
    if mult_node and cmds.objExists(mult_node):
        line_data["mult_dl_node"] = mult_node
    elif line_group and cmds.objExists(line_group) and sweep_mesh_node and cmds.objExists(sweep_mesh_node):
        mult_node = cmds.createNode('multDL', n=f"{line_name}_multDL", ss=True)
        cmds.setAttr(f"{mult_node}.input2", -1.0)
        cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1", force=True)
        cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState", force=True)
        line_data["mult_dl_node"] = mult_node

    # 2. Apply Profile attributes (UI elements vs Custom attributes)
    if rebuild_ui_elements:
        for a in ['scale_profile', 'roundness']:
            if a in new_attrs and cmds.attributeQuery(a, node=mesh, exists=True):
                try:
                    cmds.setAttr(f"{mesh}.{a}", new_attrs[a])
                except Exception:
                    pass

    if rebuild_custom_attrs:
        for a in ['rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
                  'Start_position', 'Start_value', 'End_position', 'End_value']:
            if a in new_attrs and cmds.attributeQuery(a, node=mesh, exists=True):
                try:
                    cmds.setAttr(f"{mesh}.{a}", new_attrs[a])
                except Exception:
                    pass

        # Intermediate taper points
        inter_points = new_attrs.get("intermediate_points", [])
        if inter_points:
            for pt in inter_points:
                i = pt.get("idx")
                if i is not None and cmds.attributeQuery(f"Pt{i}_position", node=mesh, exists=True):
                    try:
                        if "pos" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_position", pt["pos"])
                        if "val" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_value", pt["val"])
                        if "interp" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_interp", pt["interp"])
                    except Exception:
                        pass
        else:
            pts = []
            k = 1
            while cmds.attributeQuery(f"Pt{k}_value", node=mesh, exists=True):
                pts.append(k)
                k += 1
            if pts:
                if "Pt1_value" in new_attrs:
                    try:
                        cmds.setAttr(f"{mesh}.Pt{pts[0]}_value", new_attrs["Pt1_value"])
                    except Exception:
                        pass
                if "PtLast_value" in new_attrs and len(pts) > 1:
                    try:
                        cmds.setAttr(f"{mesh}.Pt{pts[-1]}_value", new_attrs["PtLast_value"])
                    except Exception:
                        pass

    # 3. Smoothable
    if rebuild_ui_elements:
        is_smooth = new_attrs.get("smoothable") if "smoothable" in new_attrs else new_attrs.get("line_smoothable")
        if is_smooth:
            smooth_node = applySmoothToStrokeMesh(mesh, line_name=line_name)
            if mult_node and cmds.objExists(mult_node) and smooth_node and cmds.objExists(smooth_node):
                try:
                    if not cmds.isConnected(f"{mult_node}.output", f"{smooth_node}.nodeState"):
                        cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState", force=True)
                except Exception:
                    pass
            line_data["smooth_node"] = smooth_node
            line_data["smoothable"] = True
        elif is_smooth is not None and not is_smooth:
            removeDisplacementFromStrokeMesh(mesh, line_data)
            removeSmoothFromStrokeMesh(mesh, line_data)
            line_data["smoothable"] = False
            line_data["smooth_node"] = None
            line_data["displacement"] = False
            line_data["tex_def_node"] = None
            line_data["noise_node"] = None
            line_data["tex_handle"] = None
            line_data["add_noise"] = False

    if rebuild_custom_attrs:
        method_val = new_attrs.get("method") if "method" in new_attrs else new_attrs.get("smooth_method")
        if method_val is not None and cmds.attributeQuery('method', node=mesh, exists=True):
            try:
                cmds.setAttr(f"{mesh}.method", method_val)
            except Exception:
                pass
        div_val = new_attrs.get("divisions") if "divisions" in new_attrs else new_attrs.get("smooth_divisions")
        if div_val is not None and cmds.attributeQuery('divisions', node=mesh, exists=True):
            try:
                cmds.setAttr(f"{mesh}.divisions", div_val)
            except Exception:
                pass

    # 4. Displacement
    if rebuild_ui_elements:
        is_disp = new_attrs.get("displacement") if "displacement" in new_attrs else new_attrs.get("line_displacement")
        can_disp = (new_attrs.get("smoothable") if "smoothable" in new_attrs else new_attrs.get("line_smoothable")) or line_data.get("smoothable") or cmds.attributeQuery("divisions", node=mesh, exists=True)
        if is_disp and can_disp:
            disp_type = new_attrs.get("disp_type", new_attrs.get("line_disp_type", "noise"))
            tex_def, tex_node, tex_handle = applyDisplacementToStrokeMesh(mesh, line_name=line_name, disp_type=disp_type)
            if tex_handle and cmds.objExists(tex_handle) and line_group and cmds.objExists(line_group):
                parent = cmds.listRelatives(tex_handle, parent=True) or []
                if not parent or parent[0] != line_group:
                    try:
                        cmds.parent(tex_handle, line_group)
                    except Exception:
                        pass

            if mult_node and cmds.objExists(mult_node) and tex_def and cmds.objExists(tex_def):
                try:
                    if not cmds.isConnected(f"{mult_node}.output", f"{tex_def}.nodeState"):
                        cmds.connectAttr(f"{mult_node}.output", f"{tex_def}.nodeState", force=True)
                except Exception:
                    pass

            line_data["tex_def_node"] = tex_def
            line_data["noise_node"] = tex_node
            line_data["tex_handle"] = tex_handle
            line_data["displacement"] = True
            line_data["disp_type"] = disp_type
            line_data["add_noise"] = True
        elif is_disp is not None and not is_disp:
            removeDisplacementFromStrokeMesh(mesh, line_data)
            line_data["displacement"] = False
            line_data["tex_def_node"] = None
            line_data["noise_node"] = None
            line_data["tex_handle"] = None
            line_data["add_noise"] = False

    if rebuild_custom_attrs:
        disp_param_map = {
            'strength': ['strength', 'disp_strength'],
            'offset': ['offset', 'disp_offset'],
            'noise_type': ['noise_type'],
            'frequency': ['frequency'],
            'ratio': ['ratio'],
            'time': ['time'],
            'snow_roughness': ['snow_roughness'],
            'rock_roughness': ['rock_roughness'],
            'boundary': ['boundary'],
            'altitude': ['altitude'],
            'amplitude': ['amplitude'],
            'frequency_ratio': ['frequency_ratio']
        }
        for attr, keys in disp_param_map.items():
            for k in keys:
                if k in new_attrs and cmds.attributeQuery(attr, node=mesh, exists=True):
                    try:
                        cmds.setAttr(f"{mesh}.{attr}", new_attrs[k])
                        break
                    except Exception:
                        pass

    # 5. Color / Shader
    if rebuild_ui_elements:
        color = new_attrs.get("color")
        if color is None:
            color = new_attrs.get("current_line_color")
        if color is not None:
            assignLineShader(mesh, color=color)
            line_data["color"] = tuple(color)

    # 6. Follow Method
    if rebuild_follow_method:
        target_follow_method = new_attrs.get("follow_method")
        if not target_follow_method:
            global current_follow_method
            target_follow_method = current_follow_method
        if target_follow_method:
            changeLineFollowMethod(line_data, target_follow_method)

    global_scene_data_obj.updateLineData(line_name, line_data)
    return True


def applyExtractedAttributes(tgt_mesh, tgt_line_data, attrs_dict):
    if not tgt_mesh or not cmds.objExists(tgt_mesh) or not attrs_dict:
        return
    if not tgt_line_data:
        all_lines = global_scene_data_obj.getAllLines()
        for name, data in all_lines.items():
            if data.get("mesh") == tgt_mesh:
                tgt_line_data = data
                break
        if not tgt_line_data:
            tgt_name = tgt_mesh.replace("_msh", "")
            tgt_group = cmds.listRelatives(tgt_mesh, p=True)[0] if cmds.listRelatives(tgt_mesh, p=True) else None
            tgt_line_data = {
                "name": tgt_name,
                "mesh": tgt_mesh,
                "group": tgt_group
            }
    return rebuildLine(tgt_line_data, new_attrs=attrs_dict)


def solve_param_pair(A1, B1, A2, B2, P):
    """
    Finds parameters u, v in [0, 1] along edges A1-B1 and A2-B2 such that their
    midpoint (average) minimizes the distance to point P.
    """
    v1 = [0.5 * (B1[k] - A1[k]) for k in range(3)]
    v2 = [0.5 * (B2[k] - A2[k]) for k in range(3)]
    w = [P[k] - 0.5 * (A1[k] + A2[k]) for k in range(3)]

    a = sum(v1[k] * v1[k] for k in range(3))
    b = sum(v1[k] * v2[k] for k in range(3))
    c = sum(v2[k] * v2[k] for k in range(3))
    d1 = sum(w[k] * v1[k] for k in range(3))
    d2 = sum(w[k] * v2[k] for k in range(3))

    det = a * c - b * b
    if abs(det) > 1e-9:
        u = (c * d1 - b * d2) / det
        v = (a * d2 - b * d1) / det
    else:
        u = d1 / a if a > 1e-9 else 0.5
        v = d2 / c if c > 1e-9 else 0.5

    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))

    mid = [0.5 * ((A1[k] + u * (B1[k] - A1[k])) + (A2[k] + v * (B2[k] - A2[k]))) for k in range(3)]
    dist = math.sqrt(sum((mid[k] - P[k]) ** 2 for k in range(3)))
    return u, v, dist, mid


def find_best_edge_pair_for_point(mfn_mesh, dag_mesh, P, poly_it=None, edge_it=None, all_points=None):
    """
    Finds the pair of edges in the closest polygon that forms the virtual triangle
    closest to point P, and computes parameters u, v and normal vector.
    Highly optimized: reuses iterators and pre-cached vertex positions when provided.
    """
    closest_pt, face_id = mfn_mesh.getClosestPoint(om.MPoint(P[0], P[1], P[2]), space=om.MSpace.kWorld)
    normal = mfn_mesh.getClosestNormal(closest_pt, space=om.MSpace.kWorld)[0]

    if poly_it is None:
        poly_it = om.MItMeshPolygon(dag_mesh)
    poly_it.setIndex(face_id)
    face_edges = poly_it.getEdges()
    n_edges = len(face_edges)

    if edge_it is None:
        edge_it = om.MItMeshEdge(dag_mesh)

    best_dist = float('inf')
    best_pair = (face_edges[0], face_edges[1] if n_edges > 1 else face_edges[0])
    best_uv = (0.5, 0.5)
    pt_coords = (closest_pt.x, closest_pt.y, closest_pt.z)

    # Pre-fetch edge vertex points and vertex sets
    edge_pts = []
    edge_verts = []
    for e in face_edges:
        edge_it.setIndex(e)
        v0 = edge_it.vertexId(0)
        v1 = edge_it.vertexId(1)
        if all_points is not None:
            p0 = all_points[v0]
            p1 = all_points[v1]
            edge_pts.append(((p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)))
        else:
            p0 = edge_it.point(0, om.MSpace.kWorld)
            p1 = edge_it.point(1, om.MSpace.kWorld)
            edge_pts.append(((p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)))
        edge_verts.append((v0, v1))

    for i in range(n_edges):
        A1, B1 = edge_pts[i]
        v1_0, v1_1 = edge_verts[i]
        for j in range(i + 1, n_edges):
            A2, B2 = edge_pts[j]
            v2_0, v2_1 = edge_verts[j]
            shares_vertex = (v1_0 == v2_0 or v1_0 == v2_1 or v1_1 == v2_0 or v1_1 == v2_1)

            u, v, dist, _ = solve_param_pair(A1, B1, A2, B2, pt_coords)

            # Prefer edges sharing a vertex to form the virtual triangle corner
            weight = 1.0 if shares_vertex else 1.3
            effective_dist = dist * weight

            if effective_dist < best_dist:
                best_dist = effective_dist
                best_pair = (face_edges[i], face_edges[j])
                best_uv = (u, v)

    return best_pair, best_uv, normal


def get_or_create_master_group():
    master_grp = "grp_lines"
    if not cmds.objExists(master_grp):
        master_grp = cmds.group(em=True, n=master_grp)
        cmds.xform(master_grp, os=True, pivots=(0, 0, 0))
    return master_grp


def get_next_line_id():
    existing_ids = set()
    # 1. Check in grp_lines
    if cmds.objExists("grp_lines"):
        children = cmds.listRelatives("grp_lines", children=True, type="transform") or []
        for ch in children:
            base = ch.split("|")[-1].lower()
            if base.startswith("line_"):
                try:
                    num_part = base.split("_")[1]
                    existing_ids.add(int(num_part))
                except Exception:
                    pass
    # 2. Check in global_scene_data_obj
    for k in global_scene_data_obj.getGlobalLinesData().keys():
        k_lower = k.lower()
        if k_lower.startswith("line_"):
            try:
                num_part = k_lower.split("_")[1]
                existing_ids.add(int(num_part))
            except Exception:
                pass
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
    return next_id


def reset_pivots_to_origin(*nodes):
    """
    Ensures that the given nodes (groups, meshes, curves) have their rotatePivot,
    scalePivot, and translate clean at the world origin (0, 0, 0), preventing offset pivots.
    """
    for node in nodes:
        if node and cmds.objExists(node):
            try:
                cmds.xform(node, ws=True, rp=(0.0, 0.0, 0.0), sp=(0.0, 0.0, 0.0))
                cmds.xform(node, zeroTransformPivots=True)
                for pivot_attr in ['rotatePivot', 'scalePivot', 'rotatePivotTranslate', 'scalePivotTranslate']:
                    if cmds.attributeQuery(pivot_attr, node=node, exists=True):
                        try:
                            cmds.setAttr(f"{node}.{pivot_attr}", 0.0, 0.0, 0.0)
                        except Exception:
                            pass
            except Exception:
                pass


def applyFollowMethod(follow_method, curve_transform, target_mesh, line_id, line_group, subdiv_offset):
    """
    Applies one of the three follow methods:
    1. 'Wrap deformer': Native Maya wrap deformer.
    2. 'UV pin': Maya 2026 native rivets snapped to closest UV, driving control points.
    3. 'Node based': 2 curveFromMeshEdge + 2 pointOnCurveInfo (turnOnPercentage) averaged via plusMinusAverage.
    """
    follow_nodes = []
    wrap_node = None
    curve_shapes = cmds.listRelatives(curve_transform, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
    if not curve_shapes:
        return {"wrap_node": None, "follow_nodes": []}
    curve_shape = curve_shapes[0]

    visible_shapes = cmds.listRelatives(target_mesh, s=True, noIntermediate=True, fullPath=True) or []
    if not visible_shapes:
        visible_shapes = cmds.listRelatives(target_mesh, s=True, fullPath=True) or []
    target_shape = visible_shapes[0] if visible_shapes else target_mesh

    if follow_method == "Wrap deformer":
        cmds.select([curve_transform, target_mesh], r=True, noExpand=True)
        cmds.CreateWrap()
        curve_shapes = cmds.listRelatives(curve_transform, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
        for s in curve_shapes:
            conns = cmds.listConnections(s + '.create', d=False, s=True)
            if conns:
                wrap_node = conns[0]
                break
        if not wrap_node:
            all_shapes = cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
            for s in all_shapes:
                conns = cmds.listConnections(s + '.create', d=False, s=True)
                if conns:
                    wrap_node = conns[0]
                    break
        if wrap_node:
            wrap_node = cmds.rename(wrap_node, f"{line_group}_wrap")
            follow_nodes.append(wrap_node)
        return {"wrap_node": wrap_node, "follow_nodes": follow_nodes}

    elif follow_method == "UV pin":
        import maya.internal.nodes.uvpin.node_interface as uvpin_if

        sel = om.MSelectionList()
        sel.add(target_shape)
        dag = sel.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag)
        poly_it = om.MItMeshPolygon(dag)

        num_cvs = len(cmds.ls(f"{curve_shape}.cv[*]", fl=True))
        rivets_grp = cmds.group(em=True, n=f"{line_group}_rivets_grp")
        cmds.parent(rivets_grp, line_group)
        cmds.setAttr(rivets_grp + '.v', 0)
        reset_pivots_to_origin(rivets_grp)
        follow_nodes.append(rivets_grp)

        for i in range(num_cvs):
            cv_pos = cmds.pointPosition(f"{curve_shape}.cv[{i}]", w=True)
            m_point = om.MPoint(cv_pos[0], cv_pos[1], cv_pos[2])
            closest_pt, face_id = mfn_mesh.getClosestPoint(m_point, space=om.MSpace.kWorld)
            u, v, _ = mfn_mesh.getUVAtPoint(closest_pt, space=om.MSpace.kWorld)
            normal = mfn_mesh.getClosestNormal(closest_pt, space=om.MSpace.kWorld)[0]

            cmds.select(f"{target_mesh}.f[{face_id}]", r=True)
            uvpin_if.createRivet()
            created = cmds.ls(sl=True)
            pin_node = cmds.rename(created[0], f"{line_group}_pin_{i}")
            loc = cmds.rename(created[1], f"{line_group}_rivet_{i}")
            cmds.parent(loc, rivets_grp)

            # Snap rivet to closest UV position
            cmds.setAttr(f"{pin_node}.coordinate[0].coordinateU", u)
            cmds.setAttr(f"{pin_node}.coordinate[0].coordinateV", v)

            decomp = cmds.createNode('decomposeMatrix', n=f"{line_group}_decomp_{i}")
            cmds.connectAttr(f"{pin_node}.outputMatrix[0]", f"{decomp}.inputMatrix")
            follow_nodes.extend([pin_node, loc, decomp])

            if subdiv_offset != 0:
                pma_off = cmds.createNode('plusMinusAverage', n=f"{line_group}_offset_{i}")
                cmds.setAttr(f"{pma_off}.operation", 1)  # Sum
                cmds.connectAttr(f"{decomp}.outputTranslate", f"{pma_off}.input3D[0]")
                cmds.setAttr(f"{pma_off}.input3D[1]", normal.x * subdiv_offset, normal.y * subdiv_offset, normal.z * subdiv_offset)
                cmds.connectAttr(f"{pma_off}.output3D", f"{curve_shape}.controlPoints[{i}]")
                follow_nodes.append(pma_off)
            else:
                cmds.connectAttr(f"{decomp}.outputTranslate", f"{curve_shape}.controlPoints[{i}]")

        cmds.select(cl=True)
        return {"wrap_node": None, "follow_nodes": follow_nodes}

    elif follow_method == "Node based":
        sel = om.MSelectionList()
        sel.add(target_shape)
        dag = sel.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag)
        all_points = mfn_mesh.getPoints(om.MSpace.kWorld)
        poly_it = om.MItMeshPolygon(dag)
        edge_it = om.MItMeshEdge(dag)

        curve_sel = om.MSelectionList()
        curve_sel.add(curve_shape)
        curve_dag = curve_sel.getDagPath(0)
        mfn_curve = om.MFnNurbsCurve(curve_dag)
        all_cvs = mfn_curve.cvPositions(om.MSpace.kWorld)
        num_cvs = len(all_cvs)

        for i in range(num_cvs):
            cv_pos = all_cvs[i]
            pair, uv, normal = find_best_edge_pair_for_point(mfn_mesh, dag, cv_pos, poly_it=poly_it, edge_it=edge_it, all_points=all_points)
            e1, e2 = pair
            u, v = uv

            cfme1 = cmds.createNode('curveFromMeshEdge', n=f"{line_group}_cfme_{i}_a")
            cmds.connectAttr(f"{target_shape}.worldMesh[0]", f"{cfme1}.inputMesh")
            cmds.setAttr(f"{cfme1}.edgeIndex[0]", e1)

            cfme2 = cmds.createNode('curveFromMeshEdge', n=f"{line_group}_cfme_{i}_b")
            cmds.connectAttr(f"{target_shape}.worldMesh[0]", f"{cfme2}.inputMesh")
            cmds.setAttr(f"{cfme2}.edgeIndex[0]", e2)

            poci1 = cmds.createNode('pointOnCurveInfo', n=f"{line_group}_poci_{i}_a")
            cmds.connectAttr(f"{cfme1}.outputCurve", f"{poci1}.inputCurve")
            cmds.setAttr(f"{poci1}.turnOnPercentage", 1)
            cmds.setAttr(f"{poci1}.parameter", u)

            poci2 = cmds.createNode('pointOnCurveInfo', n=f"{line_group}_poci_{i}_b")
            cmds.connectAttr(f"{cfme2}.outputCurve", f"{poci2}.inputCurve")
            cmds.setAttr(f"{poci2}.turnOnPercentage", 1)
            cmds.setAttr(f"{poci2}.parameter", v)

            pma_avg = cmds.createNode('plusMinusAverage', n=f"Line_{line_id}_avg_{i}")
            cmds.setAttr(f"{pma_avg}.operation", 3)  # Average
            cmds.connectAttr(f"{poci1}.position", f"{pma_avg}.input3D[0]")
            cmds.connectAttr(f"{poci2}.position", f"{pma_avg}.input3D[1]")

            follow_nodes.extend([cfme1, cfme2, poci1, poci2, pma_avg])

            if subdiv_offset != 0:
                pma_off = cmds.createNode('plusMinusAverage', n=f"{line_group}_offset_{i}")
                cmds.setAttr(f"{pma_off}.operation", 1)  # Sum
                cmds.connectAttr(f"{pma_avg}.output3D", f"{pma_off}.input3D[0]")
                cmds.setAttr(f"{pma_off}.input3D[1]", normal.x * subdiv_offset, normal.y * subdiv_offset, normal.z * subdiv_offset)
                cmds.connectAttr(f"{pma_off}.output3D", f"{curve_shape}.controlPoints[{i}]")
                follow_nodes.append(pma_off)
            else:
                cmds.connectAttr(f"{pma_avg}.output3D", f"{curve_shape}.controlPoints[{i}]")

        return {"wrap_node": None, "follow_nodes": follow_nodes}

    return {"wrap_node": None, "follow_nodes": []}


def removeFollowMethodFromLine(line_data):
    """
    Cleanly removes the follow deformer / rivets / nodes attached to the curve
    so that a new follow method can be attached cleanly without leftover connections.
    Preserves the exact current world-space position and shape of the curve.
    """
    if not line_data:
        return
    crv = line_data.get("curve")
    line_group = line_data.get("group")
    if (not crv or not cmds.objExists(crv)) and line_group and cmds.objExists(line_group):
        rel_crvs = cmds.listRelatives(line_group, allDescendents=True, type="nurbsCurve") or []
        if rel_crvs:
            crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
            line_data["curve"] = crv
    if not crv or not cmds.objExists(crv):
        return

    crv_shapes = cmds.listRelatives(crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(crv, s=True, fullPath=True) or []
    if not crv_shapes:
        return
    crv_shape = crv_shapes[0]
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))

    # Capture exact world-space position before disconnecting/deleting
    ws_positions = []
    if num_cvs > 0:
        try:
            ws_positions = [cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True) for i in range(num_cvs)]
        except Exception:
            ws_positions = []

    for i in range(num_cvs):
        conns = cmds.listConnections(f"{crv_shape}.controlPoints[{i}]", d=False, s=True, p=True) or []
        for src in conns:
            try:
                cmds.disconnectAttr(src, f"{crv_shape}.controlPoints[{i}]")
            except Exception:
                pass

    wn = line_data.get("wrap_node")
    if wn and cmds.objExists(wn):
        try:
            cmds.delete(wn)
        except Exception:
            pass
        for s in cmds.listRelatives(crv, s=True) or []:
            if 'Orig' in s and cmds.objExists(s):
                try:
                    cmds.delete(s)
                except Exception:
                    pass

    for fn in line_data.get("follow_nodes", []):
        if fn and cmds.objExists(fn):
            try:
                cmds.delete(fn)
            except Exception:
                pass

    # Re-assert world space positions so the curve permanently holds its exact evaluated shape
    if ws_positions and len(ws_positions) == num_cvs:
        for i, pos in enumerate(ws_positions):
            try:
                cmds.xform(f"{crv_shape}.cv[{i}]", ws=True, t=pos)
            except Exception:
                pass

    line_data["wrap_node"] = None
    line_data["follow_nodes"] = []


def changeLineFollowMethod(line_data, new_follow_method, subdiv_offset=None):
    """
    Switches or re-applies the follow method of a cartoon line (Node based, Wrap deformer, UV pin).
    Keeps all line nodes intact and only changes what is plugged into the curve.
    """
    if not line_data or not new_follow_method:
        return False
    line_group = line_data.get("group")
    crv = line_data.get("curve")
    if not crv or not cmds.objExists(crv):
        if line_group and cmds.objExists(line_group):
            rel_crvs = cmds.listRelatives(line_group, allDescendents=True, type="nurbsCurve") or []
            if rel_crvs:
                crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
                line_data["curve"] = crv
    if not crv or not cmds.objExists(crv):
        return False

    target_mesh = line_data.get("target_mesh") or get_target_mesh_for_line(line_data) or paint_on_mesh
    if not target_mesh or not cmds.objExists(target_mesh):
        return False

    if subdiv_offset is None:
        subdiv_offset = line_subdiv_offset

    crv_shapes = cmds.listRelatives(crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(crv, s=True, fullPath=True) or []
    if not crv_shapes:
        return False
    crv_shape = crv_shapes[0]

    current_method = line_data.get("follow_method")

    # If the line already has this follow method and its nodes are connected and valid,
    # keep all existing nodes intact and avoid re-projecting or accumulating drift.
    if current_method == new_follow_method:
        if new_follow_method == "Wrap deformer":
            wn = line_data.get("wrap_node")
            if wn and cmds.objExists(wn):
                return True
        elif new_follow_method in ("Node based", "UV pin"):
            fns = line_data.get("follow_nodes", [])
            has_valid_fn = any(cmds.objExists(fn) for fn in fns)
            conns = cmds.listConnections(f"{crv_shape}.controlPoints[0]", d=False, s=True) or []
            if has_valid_fn and conns:
                return True

    # 1. Capture exact world-space CV positions before modifying any connections
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))
    exact_ws = [cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True) for i in range(num_cvs)]

    # 2. Safely remove old follow method connections and nodes
    removeFollowMethodFromLine(line_data)

    # 3. Re-assert the exact world-space coordinates on the curve CVs so geometry is fixed
    for i, pos in enumerate(exact_ws):
        try:
            cmds.xform(f"{crv_shape}.cv[{i}]", ws=True, t=pos)
        except Exception:
            pass

    line_name = line_data.get("name", "line_1")
    line_id = line_name.replace("line_", "") if "line_" in line_name else "1"

    # 4. Plug in the new follow method at the exact CV positions
    follow_data = applyFollowMethod(
        follow_method=new_follow_method,
        curve_transform=crv,
        target_mesh=target_mesh,
        line_id=line_id,
        line_group=line_group,
        subdiv_offset=subdiv_offset
    )

    mult_node = line_data.get("mult_dl_node") or (f"{line_name}_multDL" if line_name else None)
    if mult_node and cmds.objExists(mult_node):
        if follow_data.get("wrap_node"):
            try:
                cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState", force=True)
            except Exception:
                pass
        for fn in follow_data.get("follow_nodes", []):
            if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState", force=True)
                except Exception:
                    pass

    line_data["follow_method"] = new_follow_method
    line_data["target_mesh"] = target_mesh
    line_data["wrap_node"] = follow_data.get("wrap_node")
    line_data["follow_nodes"] = follow_data.get("follow_nodes", [])
    line_data["baked"] = False
    return True


def applySmoothToStrokeMesh(result_mesh, line_name=None):
    """
    Applies a polySmoothFace node to the result mesh, adds a 'Smooth' Channel Box separator,
    and custom 'method' and 'divisions' attributes on the line's stroke mesh transform,
    connected to drive polySmoothFace.
    """
    if not result_mesh or not cmds.objExists(result_mesh):
        return None

    # Check if a polySmoothFace is already attached in history
    hist = cmds.listHistory(result_mesh) or []
    smooth_node = None
    for h in hist:
        if cmds.nodeType(h) == "polySmoothFace":
            smooth_node = h
            break
    else:
        smooth_nodes = cmds.polySmooth(result_mesh, mth=0, dv=1)
        if not smooth_nodes:
            return None
        smooth_node = smooth_nodes[0]

    # Add 'Smooth' Channel Box separator
    if not cmds.attributeQuery('Smooth', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', k=True, en='__________', shortName='Smooth', h=False)
        cmds.setAttr(f"{result_mesh}.Smooth", lock=True)

    # Add custom attributes method and divisions if not existing
    if not cmds.attributeQuery('method', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', en='Exponential:Linear', k=True, shortName='method')
        cmds.setAttr(f"{result_mesh}.method", 0)
    if not cmds.attributeQuery('divisions', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='long', k=True, min=0, max=4, defaultValue=1, shortName='divisions')
        cmds.setAttr(f"{result_mesh}.divisions", 1)

    # Ensure connections
    if not cmds.isConnected(f"{result_mesh}.method", f"{smooth_node}.method"):
        try:
            cmds.connectAttr(f"{result_mesh}.method", f"{smooth_node}.method", force=True)
        except Exception:
            pass
    if not cmds.isConnected(f"{result_mesh}.divisions", f"{smooth_node}.divisions"):
        try:
            cmds.connectAttr(f"{result_mesh}.divisions", f"{smooth_node}.divisions", force=True)
        except Exception:
            pass

    if line_name and smooth_node != f"{line_name}_smooth" and not cmds.objExists(f"{line_name}_smooth"):
        smooth_node = cmds.rename(smooth_node, f"{line_name}_smooth")

    mult_name = f"{line_name}_multDL" if line_name else None
    if mult_name and cmds.objExists(mult_name) and smooth_node and cmds.objExists(smooth_node):
        try:
            if not cmds.isConnected(f"{mult_name}.output", f"{smooth_node}.nodeState"):
                cmds.connectAttr(f"{mult_name}.output", f"{smooth_node}.nodeState", force=True)
        except Exception:
            pass

    return smooth_node


def applyDisplacementToStrokeMesh(result_mesh, line_name=None, disp_type=None):
    """
    Applies a textureDeformer node driven by a procedural texture node ('noise', 'mountain', or 'fractal')
    to the result mesh.
    Adds a 'Displacement' Channel Box separator and custom attributes on the line's stroke mesh transform:
    - Common: 'strength', 'offset'
    - noise: 'noise_type' (Billow by default), 'frequency', 'ratio', 'time'
    - mountain: 'snow_roughness', 'rock_roughness', 'boundary', 'altitude'
    - fractal: 'amplitude', 'ratio', 'frequency_ratio', 'time'
    """
    if not result_mesh or not cmds.objExists(result_mesh):
        return None, None, None

    global line_disp_type
    chosen_type = (disp_type or line_disp_type or "noise").lower().strip()
    if chosen_type not in ["noise", "mountain", "fractal"]:
        chosen_type = "noise"

    hist = cmds.listHistory(result_mesh) or []
    tex_def = None
    for h in hist:
        if cmds.nodeType(h) == "textureDeformer":
            tex_def = h
            break

    tex_handle = None
    tex_node = None

    if not tex_def:
        tex_name = f"{line_name}_texDef" if line_name else "line_texDef"
        tex_def_nodes = cmds.textureDeformer(result_mesh, name=tex_name)
        tex_def = tex_def_nodes[0]
        if len(tex_def_nodes) > 1:
            tex_handle = tex_def_nodes[1]
            if line_name and not tex_handle.startswith(line_name):
                try:
                    tex_handle = cmds.rename(tex_handle, f"{line_name}_texDefHandle")
                except Exception:
                    pass

        # Normal displacement along surface normals for subtle brush stroke irregularity
        try:
            cmds.setAttr(f"{tex_def}.direction", 0)  # 0 = Normal
        except Exception:
            pass

        # Hide deformer handle in viewport
        try:
            cmds.setAttr(f"{tex_def}.handleVisibility", 0)
        except Exception:
            pass

        # Create procedural texture node according to chosen_type
        tex_node_name = f"{line_name}_{chosen_type}" if line_name else f"line_{chosen_type}"
        tex_node = cmds.createNode(chosen_type, name=tex_node_name)
        cmds.connectAttr(f"{tex_node}.outColor", f"{tex_def}.texture", force=True)

        if chosen_type == "noise":
            try:
                cmds.setAttr(f"{tex_node}.noiseType", 1)  # 1 = Billow
                cmds.setAttr(f"{tex_node}.frequency", 12.0)
                cmds.setAttr(f"{tex_node}.ratio", 0.7)
            except Exception:
                pass
        elif chosen_type == "mountain":
            try:
                cmds.setAttr(f"{tex_node}.snowRoughness", 0.4)
                cmds.setAttr(f"{tex_node}.rockRoughness", 0.7)
                cmds.setAttr(f"{tex_node}.boundary", 1.0)
                cmds.setAttr(f"{tex_node}.snowAltitude", 0.5)
            except Exception:
                pass
        elif chosen_type == "fractal":
            try:
                cmds.setAttr(f"{tex_node}.amplitude", 1.0)
                cmds.setAttr(f"{tex_node}.ratio", 0.707)
                cmds.setAttr(f"{tex_node}.frequencyRatio", 2.0)
            except Exception:
                pass
    else:
        existing_tex_node = None
        conn = cmds.listConnections(f"{tex_def}.texture", s=True, d=False) or []
        for c in conn:
            nt = cmds.nodeType(c)
            if nt in ["noise", "mountain", "fractal"]:
                existing_tex_node = c
                break
        handle_conn = cmds.listConnections(f"{tex_def}.handleMatrix", s=True, d=False) or []
        if handle_conn:
            tex_handle = handle_conn[0]

        if existing_tex_node and cmds.nodeType(existing_tex_node) != chosen_type:
            # Different texture type requested! Delete old texture node and old type-specific attrs
            try:
                cmds.delete(existing_tex_node)
            except Exception:
                pass
            existing_tex_node = None

            type_specific_attrs = [
                'noise_type', 'frequency', 'ratio', 'time',
                'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
                'amplitude', 'frequency_ratio'
            ]
            for attr in type_specific_attrs:
                if cmds.attributeQuery(attr, node=result_mesh, exists=True):
                    try:
                        cmds.setAttr(f"{result_mesh}.{attr}", lock=False)
                        cmds.deleteAttr(f"{result_mesh}.{attr}")
                    except Exception:
                        pass

        if not existing_tex_node:
            tex_node_name = f"{line_name}_{chosen_type}" if line_name else f"line_{chosen_type}"
            tex_node = cmds.createNode(chosen_type, name=tex_node_name)
            cmds.connectAttr(f"{tex_node}.outColor", f"{tex_def}.texture", force=True)

            if chosen_type == "noise":
                try:
                    cmds.setAttr(f"{tex_node}.noiseType", 1)  # 1 = Billow
                    cmds.setAttr(f"{tex_node}.frequency", 12.0)
                    cmds.setAttr(f"{tex_node}.ratio", 0.7)
                except Exception:
                    pass
            elif chosen_type == "mountain":
                try:
                    cmds.setAttr(f"{tex_node}.snowRoughness", 0.4)
                    cmds.setAttr(f"{tex_node}.rockRoughness", 0.7)
                    cmds.setAttr(f"{tex_node}.boundary", 1.0)
                    cmds.setAttr(f"{tex_node}.snowAltitude", 0.5)
                except Exception:
                    pass
            elif chosen_type == "fractal":
                try:
                    cmds.setAttr(f"{tex_node}.amplitude", 1.0)
                    cmds.setAttr(f"{tex_node}.ratio", 0.707)
                    cmds.setAttr(f"{tex_node}.frequencyRatio", 2.0)
                except Exception:
                    pass
        else:
            tex_node = existing_tex_node

    # Add 'Displacement' Channel Box separator on result_mesh
    if not cmds.attributeQuery('Displacement', node=result_mesh, exists=True) and not cmds.attributeQuery('Noise', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', k=True, en='__________', shortName='Displacement', h=False)
        cmds.setAttr(f"{result_mesh}.Displacement", lock=True)

    # Common displacement attributes: strength and offset
    if not cmds.attributeQuery('strength', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.03, shortName='strength', niceName='Strength')
        cmds.setAttr(f"{result_mesh}.strength", 0.03)
        if cmds.attributeQuery('noise_strength', node=result_mesh, exists=True):
            try:
                cmds.setAttr(f"{result_mesh}.strength", cmds.getAttr(f"{result_mesh}.noise_strength"))
            except Exception:
                pass

    if not cmds.attributeQuery('offset', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='offset', niceName='Offset')
        cmds.setAttr(f"{result_mesh}.offset", 0.0)
        if cmds.attributeQuery('noise_offset', node=result_mesh, exists=True):
            try:
                cmds.setAttr(f"{result_mesh}.offset", cmds.getAttr(f"{result_mesh}.noise_offset"))
            except Exception:
                pass

    if tex_def and cmds.objExists(tex_def):
        if not cmds.isConnected(f"{result_mesh}.strength", f"{tex_def}.strength"):
            try:
                cmds.connectAttr(f"{result_mesh}.strength", f"{tex_def}.strength", force=True)
            except Exception:
                pass
        if not cmds.isConnected(f"{result_mesh}.offset", f"{tex_def}.offset"):
            try:
                cmds.connectAttr(f"{result_mesh}.offset", f"{tex_def}.offset", force=True)
            except Exception:
                pass

    # Type-specific custom attributes
    if chosen_type == "noise":
        if not cmds.attributeQuery('noise_type', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='enum', en='Perlin Noise:Billow:Wave:Wispy:SpaceTime', k=True, defaultValue=1, shortName='noise_type', niceName='Noise Type')
            cmds.setAttr(f"{result_mesh}.noise_type", 1)  # Billow by default

        if not cmds.attributeQuery('frequency', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.1, defaultValue=12.0, shortName='frequency', niceName='Frequency')
            cmds.setAttr(f"{result_mesh}.frequency", 12.0)
            if cmds.attributeQuery('noise_frequency', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.frequency", cmds.getAttr(f"{result_mesh}.noise_frequency"))
                except Exception:
                    pass

        if not cmds.attributeQuery('ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.7, shortName='ratio', niceName='Ratio')
            cmds.setAttr(f"{result_mesh}.ratio", 0.7)
            if cmds.attributeQuery('noise_ratio', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.ratio", cmds.getAttr(f"{result_mesh}.noise_ratio"))
                except Exception:
                    pass

        if not cmds.attributeQuery('time', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='time', niceName='Time')
            cmds.setAttr(f"{result_mesh}.time", 0.0)
            if cmds.attributeQuery('noise_time', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.time", cmds.getAttr(f"{result_mesh}.noise_time"))
                except Exception:
                    pass

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.noise_type", f"{tex_node}.noiseType"):
                try:
                    cmds.connectAttr(f"{result_mesh}.noise_type", f"{tex_node}.noiseType", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.frequency", f"{tex_node}.frequency"):
                try:
                    cmds.connectAttr(f"{result_mesh}.frequency", f"{tex_node}.frequency", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.ratio", f"{tex_node}.ratio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.ratio", f"{tex_node}.ratio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.time", f"{tex_node}.time"):
                try:
                    cmds.connectAttr(f"{result_mesh}.time", f"{tex_node}.time", force=True)
                except Exception:
                    pass

    elif chosen_type == "mountain":
        if not cmds.attributeQuery('snow_roughness', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.4, shortName='snow_roughness', niceName='Snow Roughness')
            cmds.setAttr(f"{result_mesh}.snow_roughness", 0.4)

        if not cmds.attributeQuery('rock_roughness', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.7, shortName='rock_roughness', niceName='Rock Roughness')
            cmds.setAttr(f"{result_mesh}.rock_roughness", 0.7)

        if not cmds.attributeQuery('boundary', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=1.0, shortName='boundary', niceName='Boundary')
            cmds.setAttr(f"{result_mesh}.boundary", 1.0)

        if not cmds.attributeQuery('altitude', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, defaultValue=0.5, shortName='altitude', niceName='Altitude')
            cmds.setAttr(f"{result_mesh}.altitude", 0.5)

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.snow_roughness", f"{tex_node}.snowRoughness"):
                try:
                    cmds.connectAttr(f"{result_mesh}.snow_roughness", f"{tex_node}.snowRoughness", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.rock_roughness", f"{tex_node}.rockRoughness"):
                try:
                    cmds.connectAttr(f"{result_mesh}.rock_roughness", f"{tex_node}.rockRoughness", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.boundary", f"{tex_node}.boundary"):
                try:
                    cmds.connectAttr(f"{result_mesh}.boundary", f"{tex_node}.boundary", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.altitude", f"{tex_node}.snowAltitude"):
                try:
                    cmds.connectAttr(f"{result_mesh}.altitude", f"{tex_node}.snowAltitude", force=True)
                except Exception:
                    pass

    elif chosen_type == "fractal":
        if not cmds.attributeQuery('amplitude', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, defaultValue=1.0, shortName='amplitude', niceName='Amplitude')
            cmds.setAttr(f"{result_mesh}.amplitude", 1.0)

        if not cmds.attributeQuery('ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.707, shortName='ratio', niceName='Ratio')
            cmds.setAttr(f"{result_mesh}.ratio", 0.707)

        if not cmds.attributeQuery('frequency_ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.1, defaultValue=2.0, shortName='frequency_ratio', niceName='Frequency Ratio')
            cmds.setAttr(f"{result_mesh}.frequency_ratio", 2.0)

        if not cmds.attributeQuery('time', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='time', niceName='Time')
            cmds.setAttr(f"{result_mesh}.time", 0.0)

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.amplitude", f"{tex_node}.amplitude"):
                try:
                    cmds.connectAttr(f"{result_mesh}.amplitude", f"{tex_node}.amplitude", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.ratio", f"{tex_node}.ratio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.ratio", f"{tex_node}.ratio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.frequency_ratio", f"{tex_node}.frequencyRatio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.frequency_ratio", f"{tex_node}.frequencyRatio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.time", f"{tex_node}.time"):
                try:
                    cmds.connectAttr(f"{result_mesh}.time", f"{tex_node}.time", force=True)
                except Exception:
                    pass

    mult_name = f"{line_name}_multDL" if line_name else None
    if mult_name and cmds.objExists(mult_name) and tex_def and cmds.objExists(tex_def):
        try:
            if not cmds.isConnected(f"{mult_name}.output", f"{tex_def}.nodeState"):
                cmds.connectAttr(f"{mult_name}.output", f"{tex_def}.nodeState", force=True)
        except Exception:
            pass

    line_group = f"{line_name}_grp" if line_name else None
    if line_group and cmds.objExists(line_group) and tex_handle and cmds.objExists(tex_handle):
        parent = cmds.listRelatives(tex_handle, parent=True) or []
        if not parent or parent[0] != line_group:
            try:
                cmds.parent(tex_handle, line_group)
            except Exception:
                pass

    return tex_def, tex_node, tex_handle


applyNoiseToStrokeMesh = applyDisplacementToStrokeMesh


def setupStrokeMeshAttributes(stroke_mesh, sweep_mesh_node, num_driver_points=4, start_scale_value=0.1, line_type="paint", sweep_shape=None):
    """
    Sets up custom cartoon line attributes directly on the stroke mesh transform
    instead of creating a separate network node.
    Locks and hides standard transform attributes (TRS + V) so that selecting the stroke mesh
    in the viewport directly presents the line parameters cleanly in Maya's Channel Box.
    """
    if sweep_shape is None:
        sweep_shape = line_sweep_shape

    # 1. Lock and hide standard transform attributes and visibility
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']:
        try:
            cmds.setAttr(f"{stroke_mesh}.{attr}", lock=True, keyable=False, channelBox=False)
        except Exception:
            pass

    # 2. General profile attributes
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, shortName='scale_profile')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=sweep_shape, shortName='roundness')
    cmds.setAttr(f"{stroke_mesh}.roundness", sweep_shape)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='rotate_profile')
    cmds.setAttr(stroke_mesh + '.rotate_profile', 0)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='Sides', min=1, defaultValue=6)
    cmds.setAttr(stroke_mesh + '.Sides', 6)
    cmds.addAttr(stroke_mesh, at='bool', k=True, defaultValue=False, shortName='cap')
    cmds.setAttr(f"{stroke_mesh}.cap", 0)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='precision')
    cmds.addAttr(stroke_mesh, at='bool', k=True, shortName='optimize_precision')

    cmds.setAttr(sweep_mesh_node + '.interpolationMode', 0)
    cmds.setAttr(sweep_mesh_node + '.scaleProfileUniform', False)
    default_interpolation_precision = 90  # Default precision set to 90

    cmds.setAttr(stroke_mesh + '.precision', default_interpolation_precision)
    cmds.setAttr(stroke_mesh + '.optimize_precision', 1)

    cmds.connectAttr(stroke_mesh + '.scale_profile', sweep_mesh_node + '.scaleProfileX')

    # Profile mult node so scaleProfileY = scale_profile * roundness (flat to circular sweep shape)
    profile_mult = cmds.createNode('multDL', n=f"{stroke_mesh}_profileY_mult", ss=True)
    cmds.connectAttr(f"{stroke_mesh}.scale_profile", f"{profile_mult}.input1", force=True)
    cmds.connectAttr(f"{stroke_mesh}.roundness", f"{profile_mult}.input2", force=True)
    cmds.connectAttr(f"{profile_mult}.output", f"{sweep_mesh_node}.scaleProfileY", force=True)

    cmds.connectAttr(f"{stroke_mesh}.cap", f"{sweep_mesh_node}.capsEnable", force=True)
    cmds.connectAttr(stroke_mesh + '.rotate_profile', sweep_mesh_node + '.rotateProfile')
    cmds.connectAttr(stroke_mesh + '.Sides', sweep_mesh_node + '.profilePolySides')
    cmds.connectAttr(stroke_mesh + '.precision', sweep_mesh_node + '.interpolationPrecision')
    cmds.connectAttr(stroke_mesh + '.optimize_precision', sweep_mesh_node + '.interpolationOptimize')

    # 3. Taper section (POINTS renamed to Taper, enum separator "__________")
    cmds.addAttr(stroke_mesh, at='enum', k=True, en='__________', shortName='Taper', h=False)
    cmds.setAttr(stroke_mesh + '.Taper', lock=True)
    cmds.addAttr(stroke_mesh, at='float', k=True, shortName='Start_position')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=0.0, shortName='Start_value')

    num_driver_points = max(2, int(num_driver_points))
    num_inter = num_driver_points - 2
    if num_driver_points == 4:
        default_positions = [0.2, 0.8]
    elif num_inter > 0:
        default_positions = [(k + 1) / float(num_driver_points - 1) for k in range(num_inter)]
    else:
        default_positions = []

    for idx, pos in enumerate(default_positions, 1):
        if len(default_positions) == 1:
            pt_val = 0.7
        elif idx == 1:
            pt_val = 0.3
        elif idx == len(default_positions):
            pt_val = 0.7
        else:
            pt_val = 1.0

        cmds.addAttr(stroke_mesh, at='float', k=True, shortName=f'Pt{idx}_position')
        cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=pt_val, shortName=f'Pt{idx}_value')
        cmds.addAttr(stroke_mesh, at='enum', k=True, en='None:Linear:Smooth:Spline', shortName=f'Pt{idx}_interp')
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_position', pos)
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_value', pt_val)
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_interp', 1)

    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, shortName='End_position')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=0.0, shortName='End_value')

    # Defaults: Start_value is 0.0, Pt1 is 0.3, last Pt is 0.7, End_value is 0.0
    cmds.setAttr(stroke_mesh + '.scale_profile', start_scale_value)
    cmds.setAttr(stroke_mesh + '.Start_position', 0.0)
    cmds.setAttr(stroke_mesh + '.Start_value', 0.0)
    cmds.setAttr(stroke_mesh + '.End_position', 1.0)
    cmds.setAttr(stroke_mesh + '.End_value', 0.0)

    try:
        cmds.setAttr(sweep_mesh_node + '.taperCurve[0].taperCurve_FloatValue', 0.0)
        cmds.setAttr(sweep_mesh_node + '.taperCurve[1].taperCurve_FloatValue', 0.0)
    except Exception:
        pass

    cmds.connectAttr(stroke_mesh + '.Start_position', sweep_mesh_node + '.taperCurve[0].taperCurve_Position')
    cmds.connectAttr(stroke_mesh + '.Start_value', sweep_mesh_node + '.taperCurve[0].taperCurve_FloatValue')

    cmds.connectAttr(stroke_mesh + '.End_position', sweep_mesh_node + '.taperCurve[1].taperCurve_Position')
    cmds.connectAttr(stroke_mesh + '.End_value', sweep_mesh_node + '.taperCurve[1].taperCurve_FloatValue')

    for idx in range(1, len(default_positions) + 1):
        target_idx = 1 + idx
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_position', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_Position')
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_interp', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_Interp')
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_value', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_FloatValue')

    return stroke_mesh, profile_mult


def generate_mirror_name(orig_name, direction):
    """
    Generates a mirrored line name based on direction ('L to R' or 'R to L').
    The mirrored line gets the base line's name with the suffix '_R' (for 'L to R')
    or '_L' (for 'R to L').
    Strips existing side indicators (_L, _R, .L, .R, -L, -R, _left, _right) from the base name.
    If the target name already exists in the scene, appends _1, _2, etc. (never generic line_X).
    """
    target_suffix = "_R" if direction == "L to R" else "_L"

    # Strip existing side suffix at the end (e.g., _L, _R, _Left, _Right, .L, .R, -L, -R)
    # optionally followed by digits (e.g. _L_1, _R_2)
    base_name = orig_name
    pat_suffix = r'([_\.-])(?:L|R|left|right|LEFT|RIGHT)(?:_\d+)?$'
    if re.search(pat_suffix, base_name, flags=re.IGNORECASE):
        base_name = re.sub(pat_suffix, '', base_name, flags=re.IGNORECASE)

    # Also strip prefix if present (e.g., L_brow -> brow)
    pat_prefix = r'^(?:L|R|left|right|LEFT|RIGHT)[_\.-]'
    if re.search(pat_prefix, base_name, flags=re.IGNORECASE):
        base_name = re.sub(pat_prefix, '', base_name, flags=re.IGNORECASE)

    if not base_name:
        base_name = orig_name

    candidate = f"{base_name}{target_suffix}"

    all_line_names = set(global_scene_data_obj.getAllLines().keys()) if 'global_scene_data_obj' in globals() else set()
    if not cmds.objExists(candidate) and candidate not in all_line_names:
        return candidate

    idx = 1
    new_name = f"{candidate}_{idx}"
    while cmds.objExists(new_name) or new_name in all_line_names:
        idx += 1
        new_name = f"{candidate}_{idx}"
    return new_name


def get_target_mesh_for_line(line_data):
    """
    Robustly determines the target character/object mesh for a cartoon line.
    Checks:
    1. 'target_mesh' in line_data
    2. Follow nodes in line_data (curveFromMeshEdge, uvPin, wrap) connections
    3. Global paint_on_mesh
    4. Active UI set_target_mesh_lineedit
    5. Scene mesh detection (excluding lineart groups)
    """
    if not line_data:
        return paint_on_mesh if paint_on_mesh and cmds.objExists(paint_on_mesh) else None

    # 1. Stored target_mesh
    tm = line_data.get("target_mesh")
    if tm and cmds.objExists(tm):
        return tm

    # 2. Inspect follow_nodes
    follow_nodes = line_data.get("follow_nodes", []) or []
    for fn in follow_nodes:
        if not cmds.objExists(fn):
            continue
        nt = cmds.nodeType(fn)
        if nt == "curveFromMeshEdge":
            conns = cmds.listConnections(f"{fn}.inputMesh", s=True, d=False) or []
            for c in conns:
                if cmds.nodeType(c) == "mesh":
                    p = cmds.listRelatives(c, p=True)
                    return p[0] if p else c
                elif cmds.objExists(c):
                    return c
        elif nt == "uvPin":
            for attr in ['deformedGeometry', 'originalGeometry']:
                if cmds.attributeQuery(attr, node=fn, exists=True):
                    conns = cmds.listConnections(f"{fn}.{attr}", s=True, d=False) or []
                    for c in conns:
                        if cmds.nodeType(c) == "mesh":
                            p = cmds.listRelatives(c, p=True)
                            return p[0] if p else c
                        elif cmds.objExists(c):
                            return c
        elif nt == "wrap":
            conns = cmds.listConnections(f"{fn}.driverPoints[0]", s=True, d=False) or []
            for c in conns:
                if cmds.nodeType(c) == "mesh":
                    p = cmds.listRelatives(c, p=True)
                    return p[0] if p else c
                elif cmds.objExists(c):
                    return c

    # 3. Inspect wrap_node
    wn = line_data.get("wrap_node")
    if wn and cmds.objExists(wn):
        conns = cmds.listConnections(f"{wn}.driverPoints[0]", s=True, d=False) or []
        for c in conns:
            if cmds.nodeType(c) == "mesh":
                p = cmds.listRelatives(c, p=True)
                return p[0] if p else c
            elif cmds.objExists(c):
                return c

    # 4. Global paint_on_mesh
    if paint_on_mesh and cmds.objExists(paint_on_mesh):
        return paint_on_mesh

    # 5. UI lineedit
    if global_main_widget and hasattr(global_main_widget, "set_target_mesh_lineedit"):
        txt = global_main_widget.set_target_mesh_lineedit.text().strip()
        if txt and cmds.objExists(txt):
            return txt

    # 6. Selected mesh
    detected = get_selected_mesh_from_scene()
    if detected:
        return detected

    return None


def mirrorSingleLine(orig_line_data, direction="L to R", target_mesh=None):
    """
    Mirrors a single cartoon line across the symmetry plane (X=0 in local target_mesh or world space).
    Duplicates the curve, mirrors its CVs, performs Sweep Mesh, copies all profile & taper attributes,
    applies the follow method, wires visibility multDL, and registers in GlobalSceneData.
    """
    orig_crv = orig_line_data.get("curve")
    if not orig_crv or not cmds.objExists(orig_crv):
        grp = orig_line_data.get("group")
        if grp and cmds.objExists(grp):
            rel_crvs = cmds.listRelatives(grp, allDescendents=True, type="nurbsCurve") or []
            if rel_crvs:
                orig_crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
                orig_line_data["curve"] = orig_crv
    if not orig_crv or not cmds.objExists(orig_crv):
        return None

    if cmds.nodeType(orig_crv) == "nurbsCurve":
        crv_shape = orig_crv
        p_crvs = cmds.listRelatives(orig_crv, p=True, fullPath=True) or []
        orig_crv = p_crvs[0] if p_crvs else orig_crv
    else:
        crv_shapes = cmds.listRelatives(orig_crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(orig_crv, s=True, fullPath=True) or []
        if not crv_shapes:
            return None
        crv_shape = crv_shapes[0]
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))
    if num_cvs < 2:
        return None

    # Determine target mesh
    if not target_mesh or not cmds.objExists(target_mesh):
        target_mesh = get_target_mesh_for_line(orig_line_data)
    if target_mesh and not orig_line_data.get("target_mesh"):
        orig_line_data["target_mesh"] = target_mesh

    # Query target mesh matrix for local symmetry plane if available
    has_matrix = False
    inv_matrix = None
    world_matrix = None
    if target_mesh and cmds.objExists(target_mesh):
        try:
            sel = om.MSelectionList()
            sel.add(target_mesh)
            dag = sel.getDagPath(0)
            if not dag.hasFn(om.MFn.kTransform):
                dag.pop()
            inv_matrix = dag.inclusiveMatrix().inverse()
            world_matrix = dag.inclusiveMatrix()
            has_matrix = True
        except Exception:
            has_matrix = False

    # Calculate mirrored CV positions
    mirrored_pts = []
    for i in range(num_cvs):
        p = cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True)
        if has_matrix:
            pt = om.MPoint(p[0], p[1], p[2])
            local_pt = pt * inv_matrix
            mirrored_local = om.MPoint(-local_pt.x, local_pt.y, local_pt.z)
            mirrored_world = mirrored_local * world_matrix
            mirrored_pts.append((mirrored_world.x, mirrored_world.y, mirrored_world.z))
        else:
            mirrored_pts.append((-p[0], p[1], p[2]))

    # Names and IDs
    master_grp = get_or_create_master_group()
    orig_name = orig_line_data.get("name", "line_1")
    new_line_name = generate_mirror_name(orig_name, direction)
    line_id = get_next_line_id()

    # Create fresh, clean curve directly from mirrored points at world origin
    new_crv = cmds.curve(p=mirrored_pts, d=1, n=f"{new_line_name}_crv")

    # Optional shrinkwrap if offset active
    if line_subdiv_offset != 0.0 and target_mesh and cmds.objExists(target_mesh):
        t_shapes = cmds.listRelatives(target_mesh, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(target_mesh, s=True, fullPath=True) or []
        if t_shapes:
            subdiv_lvl = cmds.getAttr(t_shapes[0] + '.displaySmoothMesh')
            if subdiv_lvl > 0:
                shrinkWrapItem(target_msh=target_mesh, wrapped_item=new_crv, target_subdiv_lvl=subdiv_lvl)
        cmds.delete(new_crv, ch=True)

    # Perform sweep mesh
    cmds.select(new_crv, r=True, noExpand=True)
    mel.eval('performSweepMesh 0;')
    sweep_mesh_node = cmds.listConnections(new_crv + '.worldSpace[0]', d=True, s=False)[0]
    result_mesh = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)[0]

    # Setup hierarchy
    first_group = cmds.group(new_crv, n=f"{new_line_name}_crv_grp")
    root_converted_curve_group = cmds.group(first_group, n=f"{new_line_name}_keep_grp")
    cmds.setAttr(root_converted_curve_group + '.v', 0)

    line_group = cmds.group(em=True, n=new_line_name)
    cmds.parent(result_mesh, line_group)
    cmds.parent(root_converted_curve_group, line_group)
    cmds.parent(line_group, master_grp)
    reset_pivots_to_origin(master_grp, line_group, result_mesh, new_crv, root_converted_curve_group, first_group)

    # Read original attributes from orig_mesh
    orig_mesh = orig_line_data.get("mesh")
    num_driver_points = 2
    idx = 1
    pt_data = []
    scale_val = line_default_scale
    if orig_mesh and cmds.objExists(orig_mesh):
        if cmds.attributeQuery('scale_profile', node=orig_mesh, exists=True):
            scale_val = cmds.getAttr(f"{orig_mesh}.scale_profile")
        while cmds.attributeQuery(f'Pt{idx}_position', node=orig_mesh, exists=True):
            p_pos = cmds.getAttr(f"{orig_mesh}.Pt{idx}_position")
            p_val = cmds.getAttr(f"{orig_mesh}.Pt{idx}_value")
            p_int = cmds.getAttr(f"{orig_mesh}.Pt{idx}_interp")
            pt_data.append((p_pos, p_val, p_int))
            num_driver_points += 1
            idx += 1

    _, profile_mult = setupStrokeMeshAttributes(result_mesh, sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=scale_val, line_type=orig_line_data.get("type", "paint"))
    if profile_mult and cmds.objExists(profile_mult):
        profile_mult = cmds.rename(profile_mult, f"{new_line_name}_profileY_mult")

    smooth_node = None
    is_smoothable = orig_line_data.get("smoothable", False) or bool(orig_line_data.get("smooth_node")) or (
        bool(orig_mesh) and cmds.attributeQuery('divisions', node=orig_mesh, exists=True)
    )
    if is_smoothable:
        smooth_node = applySmoothToStrokeMesh(result_mesh, line_name=new_line_name)

    tex_def_node = None
    noise_node = None
    tex_handle_node = None
    has_disp = orig_line_data.get("displacement", False) or orig_line_data.get("add_noise", False) or bool(orig_line_data.get("noise_node")) or (
        bool(orig_mesh) and (
            cmds.attributeQuery('strength', node=orig_mesh, exists=True) or
            cmds.attributeQuery('noise_strength', node=orig_mesh, exists=True)
        )
    )
    disp_type = orig_line_data.get("disp_type")
    if not disp_type and orig_line_data.get("noise_node") and cmds.objExists(orig_line_data.get("noise_node")):
        disp_type = cmds.nodeType(orig_line_data.get("noise_node"))
    if not disp_type:
        disp_type = line_disp_type

    if is_smoothable and has_disp:
        tex_def_node, noise_node, tex_handle_node = applyDisplacementToStrokeMesh(result_mesh, line_name=new_line_name, disp_type=disp_type)
        if tex_handle_node and cmds.objExists(tex_handle_node):
            try:
                cmds.parent(tex_handle_node, line_group)
            except Exception:
                pass

    # Copy all attribute values from orig_mesh
    if orig_mesh and cmds.objExists(orig_mesh):
        for attr in [
            'scale_profile', 'roundness', 'rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
            'Start_position', 'Start_value', 'End_position', 'End_value',
            'method', 'divisions',
            'strength', 'offset',
            'noise_type', 'frequency', 'ratio', 'time',
            'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
            'amplitude', 'frequency_ratio',
            'noise_strength', 'noise_frequency', 'noise_ratio', 'noise_offset', 'noise_time'
        ]:
            if cmds.attributeQuery(attr, node=orig_mesh, exists=True) and cmds.attributeQuery(attr, node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.{attr}", cmds.getAttr(f"{orig_mesh}.{attr}"))
                except Exception:
                    pass
        for i, (p_pos, p_val, p_int) in enumerate(pt_data, 1):
            if cmds.attributeQuery(f'Pt{i}_position', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.Pt{i}_position", p_pos)
                    cmds.setAttr(f"{result_mesh}.Pt{i}_value", p_val)
                    cmds.setAttr(f"{result_mesh}.Pt{i}_interp", p_int)
                except Exception:
                    pass

    # Apply follow method
    follow_method = orig_line_data.get("follow_method", current_follow_method)
    follow_data = {"wrap_node": None, "follow_nodes": []}
    if target_mesh and cmds.objExists(target_mesh):
        try:
            follow_data = applyFollowMethod(
                follow_method=follow_method,
                curve_transform=new_crv,
                target_mesh=target_mesh,
                line_id=line_id,
                line_group=line_group,
                subdiv_offset=line_subdiv_offset
            )
        except Exception as e:
            print(f"Warning: could not apply follow method to mirrored line: {e}")

    # Setup visibility multDL
    mult_node = cmds.createNode('multDL', n=f"{new_line_name}_multDL", ss=True)
    cmds.setAttr(f"{mult_node}.input2", -1.0)
    cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1")
    cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState")
    if follow_data.get("wrap_node"):
        try:
            if not cmds.isConnected(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState"):
                cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState")
        except Exception:
            pass
    for fn in follow_data.get("follow_nodes", []):
        if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
            try:
                if not cmds.isConnected(f"{mult_node}.output", f"{fn}.nodeState"):
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState")
            except Exception:
                pass

    # Rename nodes cleanly
    if smooth_node and cmds.objExists(smooth_node):
        smooth_node = cmds.rename(smooth_node, f"{new_line_name}_smooth")
        if mult_node and cmds.objExists(mult_node):
            try:
                cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState")
            except Exception:
                pass

    if tex_def_node and cmds.objExists(tex_def_node):
        if mult_node and cmds.objExists(mult_node):
            try:
                cmds.connectAttr(f"{mult_node}.output", f"{tex_def_node}.nodeState")
            except Exception:
                pass

    result_mesh = cmds.rename(result_mesh, f"{new_line_name}_msh")
    sweep_mesh_node = cmds.rename(sweep_mesh_node, f"{new_line_name}_sweep")
    if cmds.objExists(new_crv) and not new_crv.endswith(f"{new_line_name}_crv"):
        new_crv = cmds.rename(new_crv, f"{new_line_name}_crv")
    reset_pivots_to_origin(master_grp, line_group, result_mesh, new_crv, root_converted_curve_group, first_group)

    # Shading - inherit base line color
    orig_color = orig_line_data.get("color")
    if orig_color is None and orig_mesh and cmds.objExists(orig_mesh):
        orig_color = getLineMeshColor(orig_mesh)
    if orig_color is None:
        orig_color = tuple(current_line_color)

    assignLineShader(result_mesh, color=orig_color)

    new_line_data = {
        "name": new_line_name,
        "type": orig_line_data.get("type", "paint"),
        "follow_method": follow_method,
        "target_mesh": target_mesh,
        "color": tuple(orig_color),
        "group": line_group,
        "mesh": result_mesh,
        "curve": new_crv,
        "sweep_msh_node": sweep_mesh_node,
        "sweep_mesh_node": sweep_mesh_node,
        "taper_ctrl_node": result_mesh,
        "brush_node": None,
        "wrap_node": follow_data.get("wrap_node"),
        "smooth_node": smooth_node,
        "smoothable": is_smoothable,
        "tex_def_node": tex_def_node,
        "noise_node": noise_node,
        "tex_handle": tex_handle_node,
        "displacement": bool(is_smoothable and has_disp),
        "disp_type": disp_type,
        "add_noise": bool(is_smoothable and has_disp),
        "profile_mult_node": profile_mult,
        "follow_nodes": follow_data.get("follow_nodes", []),
        "root_convert_grp": root_converted_curve_group,
        "converted_curve_grp": first_group,
        "mult_dl_node": mult_node,
        "reverse_state_node": mult_node,
        "baked": False
    }
    global_scene_data_obj.addLineData(new_line_data)
    return new_line_data


def clean_orphaned_stroke_brushes():
    """
    Deletes any orphaned strokeDefaultBrush or stroke brush nodes not used by any stroke.
    Never deletes Maya's template 'defaultBrush'.
    """
    try:
        # Check specifically for 'strokeDefaultBrush'
        if cmds.objExists("strokeDefaultBrush"):
            strokes = cmds.listConnections("strokeDefaultBrush", type="stroke") or []
            if not strokes:
                try:
                    cmds.delete("strokeDefaultBrush")
                except Exception:
                    pass

        # Check for any other stroke brush patterns
        candidates = cmds.ls("strokeDefaultBrush*", "*DefaultBrush*", "*stroke*brush*", "*stroke*Brush*", type="brush") or []
        for b in candidates:
            if b == "defaultBrush":
                continue
            if cmds.objExists(b):
                strokes = cmds.listConnections(b, type="stroke") or []
                if not strokes:
                    try:
                        cmds.delete(b)
                    except Exception:
                        pass
    except Exception:
        pass


global_main_widget = None
selection_event_catcher_num = None
stroke_event_catcher_num = None
tool_event_catcher_num = None
_is_drawing_line = False


def setup_selection_listener(callback):
    """
    Registers a persistent SelectionChanged scriptJob to track active mesh selections.
    """
    global selection_event_catcher_num
    kill_selection_listener()
    try:
        selection_event_catcher_num = cmds.scriptJob(event=["SelectionChanged", callback])
    except Exception:
        selection_event_catcher_num = None


def kill_selection_listener():
    """
    Safely kills the selection scriptJob if active.
    """
    global selection_event_catcher_num
    if selection_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=selection_event_catcher_num, force=True)
        except Exception:
            pass
        selection_event_catcher_num = None


def arm_stroke_listener():
    """
    Registers a one-shot SelectionChanged scriptJob to trigger drawLine on stroke completion.
    """
    global stroke_event_catcher_num
    kill_stroke_listener()
    try:
        stroke_event_catcher_num = cmds.scriptJob(runOnce=True, event=["SelectionChanged", drawLine])
    except Exception:
        stroke_event_catcher_num = None


def kill_stroke_listener():
    """
    Safely kills the stroke scriptJob if active.
    """
    global stroke_event_catcher_num
    if stroke_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=stroke_event_catcher_num, force=True)
        except Exception:
            pass
        stroke_event_catcher_num = None


def setup_tool_listener(callback):
    """
    Registers a ToolChanged scriptJob to detect tool switches during painting session.
    """
    global tool_event_catcher_num
    kill_tool_listener()
    try:
        tool_event_catcher_num = cmds.scriptJob(event=["ToolChanged", callback])
    except Exception:
        tool_event_catcher_num = None


def kill_tool_listener():
    """
    Safely kills the tool change scriptJob if active.
    """
    global tool_event_catcher_num
    if tool_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=tool_event_catcher_num, force=True)
        except Exception:
            pass
        tool_event_catcher_num = None


def find_lines_for_maya_selection(selection_list, line_data_list):
    """
    Given a list of Maya selection strings (transforms, shapes, components, groups),
    identifies which line items match based on mesh, curve, group, or associated nodes.
    Returns the list of matching line entries.
    """
    if not selection_list:
        return []

    candidates = set()
    for s in selection_list:
        if not s:
            continue
        node = s.split(".")[0]
        short_name = node.split("|")[-1]
        candidates.add(node)
        candidates.add(short_name)

        if cmds.objExists(node):
            try:
                parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
                for p in parents:
                    candidates.add(p)
                    candidates.add(p.split("|")[-1])
                ancestors = cmds.listRelatives(node, allParents=True, fullPath=False) or []
                for a in ancestors:
                    candidates.add(a)
                    candidates.add(a.split("|")[-1])
                shapes = cmds.listRelatives(node, shapes=True, fullPath=False) or []
                for sh in shapes:
                    candidates.add(sh)
                    candidates.add(sh.split("|")[-1])
                children = cmds.listRelatives(node, children=True, fullPath=False) or []
                for ch in children:
                    candidates.add(ch)
                    candidates.add(ch.split("|")[-1])
            except Exception:
                pass

    matches = []
    for item in line_data_list:
        line_data = item[1] if isinstance(item, tuple) else item
        if not isinstance(line_data, dict):
            continue
        line_ids = {
            line_data.get("mesh"),
            line_data.get("curve"),
            line_data.get("group"),
            line_data.get("name"),
            line_data.get("root_convert_grp"),
            line_data.get("converted_curve_grp"),
            line_data.get("sweep_msh_node"),
            line_data.get("taper_ctrl_node"),
            line_data.get("smooth_node"),
            line_data.get("tex_def_node"),
        }
        line_ids = {v for v in line_ids if v}
        line_ids.update({v.split("|")[-1] for v in list(line_ids)})

        if candidates.intersection(line_ids):
            matches.append(item)

    return matches


def get_selected_mesh_from_scene():
    """
    Returns the transform name of the currently selected polygon mesh in Maya,
    or None if no valid mesh is selected (or if selected object is part of lineart).
    """
    try:
        sel = cmds.ls(sl=True)
        if not sel:
            return None

        for item in sel:
            node = item.split(".")[0] if "." in item else item
            if not cmds.objExists(node):
                continue
            if node == "grp_lines" or node.startswith("line_"):
                continue
            parents = cmds.listRelatives(node, allParents=True, fullPath=True) or []
            if any("grp_lines" in p for p in parents):
                continue

            # If it is a mesh shape node, get its parent transform
            if cmds.nodeType(node) == "mesh":
                parent = cmds.listRelatives(node, parent=True, fullPath=False)
                node = parent[0] if parent else node

            # Check if the node has at least one mesh shape
            shapes = cmds.listRelatives(node, shapes=True, type="mesh", fullPath=False) or []
            if shapes:
                if "|" in node:
                    short = node.split("|")[-1]
                    if len(cmds.ls(short)) == 1:
                        return short
                    return node
                return node
        return None
    except Exception:
        return None


class DockableWindow(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    WINDOW_OBJECT_NAME = "CartoonLineartWindow"
    WINDOW_TITLE = "Cartoon Lineart"

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)
        self.setObjectName(self.WINDOW_OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)

        self.setGeometry(200, 200, 280, 750)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # Main scroll area so everything (including Bake button) scrolls together if window is resized
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.main_widget = mainWidget()
        self.scroll_area.setWidget(self.main_widget)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)
        self.main_layout.addWidget(self.scroll_area)

        self.setStyleSheet(comic_theme)

        # Register selection listener to auto-populate target mesh on Maya selection
        setup_selection_listener(self.main_widget.onSceneSelectionChanged)

    def closeEvent(self, event: QtGui.QCloseEvent):
        global scene_event_catcher_num
        if scene_event_catcher_num is not None:
            print(f"Clearing scene event catcher: {scene_event_catcher_num}")
            try:
                cmds.scriptJob(kill=scene_event_catcher_num, force=True)
            except Exception:
                pass
            scene_event_catcher_num = None

        kill_selection_listener()
        kill_stroke_listener()
        kill_tool_listener()
        if hasattr(self, 'main_widget') and self.main_widget:
            try:
                self.main_widget.stopPaintingSession(switch_tool=False)
            except Exception:
                pass

        try:
            super().closeEvent(event)
        except Exception:
            pass
        if event:
            event.accept()

    def dockCloseEventTriggered(self):
        global scene_event_catcher_num
        if scene_event_catcher_num is not None:
            print(f"Clearing scene event catcher: {scene_event_catcher_num}")
            try:
                cmds.scriptJob(kill=scene_event_catcher_num, force=True)
            except Exception:
                pass
            scene_event_catcher_num = None

        kill_selection_listener()
        kill_stroke_listener()
        kill_tool_listener()
        if hasattr(self, 'main_widget') and self.main_widget:
            try:
                self.main_widget.stopPaintingSession(switch_tool=False)
            except Exception:
                pass

        try:
            super().dockCloseEventTriggered()
        except Exception:
            pass

    def fileChange(self):
        global_scene_data_obj.detectSceneChange()


class mainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global global_main_widget, brush_size
        global_main_widget = self
        self.brush_size = brush_size
        self._is_syncing_settings = False
        self._is_syncing_selection = False
        self._is_paint_mode_active = False

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(6)

        # 1. Title Banner
        self.title_banner = ComicTitleBanner(self)
        self.main_layout.addWidget(self.title_banner)

        # 2. Target Mesh Section
        self.set_target_mesh_hlayout = QtWidgets.QHBoxLayout()
        self.set_target_mesh_hlayout.setSpacing(4)
        self.set_target_mesh_lineedit = QtWidgets.QLineEdit(self)
        self.set_target_mesh_lineedit.setPlaceholderText("Select mesh and click <<")
        self.set_target_mesh_button = QtWidgets.QPushButton("<<", self)
        self.set_target_mesh_button.setFixedWidth(42)
        self.set_target_mesh_button.setToolTip("Set selected mesh as target")
        self.set_target_mesh_hlayout.addWidget(self.set_target_mesh_lineedit)
        self.set_target_mesh_hlayout.addWidget(self.set_target_mesh_button)
        self.main_layout.addLayout(self.set_target_mesh_hlayout)

        # 3. Brush Size Row
        self.paint_options_buttons_hlayout = QtWidgets.QHBoxLayout()
        self.paint_options_buttons_hlayout.setSpacing(8)

        self.create_paint_line_button = ComicBrushButton(self)

        brush_ctrl_col = QtWidgets.QVBoxLayout()
        brush_ctrl_col.setSpacing(2)
        self.brush_size_label = QtWidgets.QLabel("Brush size :", self)

        brush_slider_row = QtWidgets.QHBoxLayout()
        brush_slider_row.setSpacing(4)
        self.brush_size_lineedit = QtWidgets.QLineEdit(f"{self.brush_size:.1f}", self)
        self.brush_size_lineedit.setFixedWidth(46)
        self.brush_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.brush_slider.setRange(1, 100)
        self.brush_slider.setValue(int(round(self.brush_size * 10.0)))
        brush_slider_row.addWidget(self.brush_size_lineedit)
        brush_slider_row.addWidget(self.brush_slider)

        brush_ctrl_col.addWidget(self.brush_size_label)
        brush_ctrl_col.addLayout(brush_slider_row)

        self.paint_options_buttons_hlayout.addWidget(self.create_paint_line_button)
        self.paint_options_buttons_hlayout.addLayout(brush_ctrl_col)
        self.main_layout.addLayout(self.paint_options_buttons_hlayout)

        # 3b. Preset Row
        self.preset_layout = QtWidgets.QHBoxLayout()
        self.preset_layout.setSpacing(6)
        self.preset_label = QtWidgets.QLabel("Preset :", self)
        self.preset_label.setStyleSheet("font-weight: bold; font-size: 10pt; color: #1A2230;")

        self.preset_combo = QtWidgets.QComboBox(self)
        self.preset_combo.setToolTip("Select line preset ('neutral', user presets, or 'custom')")
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                color: #1A2230;
                font-weight: bold;
                font-size: 10pt;
                padding: 3px 8px;
            }
            QComboBox:hover {
                background-color: #FBF6EE;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                selection-background-color: #1A2230;
                selection-color: #FBF6EE;
                color: #1A2230;
            }
        """)

        self.add_preset_button = QtWidgets.QPushButton("+", self)
        self.add_preset_button.setFixedSize(28, 28)
        self.add_preset_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.add_preset_button.setToolTip("Create a new preset from the selected line")
        self.add_preset_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14pt;
                color: #1A2230;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #1A2230;
                color: #FBF6EE;
            }
            QPushButton:pressed {
                background-color: #333C4D;
                color: #FBF6EE;
            }
        """)

        self.delete_preset_button = ComicTrashButton(self)
        self.delete_preset_button.setFixedSize(28, 28)
        self.delete_preset_button.setToolTip("Delete selected preset (disabled for Basic and Custom)")

        self.preset_layout.addWidget(self.preset_label)
        self.preset_layout.addWidget(self.preset_combo, 1)
        self.preset_layout.addWidget(self.add_preset_button)
        self.preset_layout.addWidget(self.delete_preset_button)
        self.main_layout.addLayout(self.preset_layout)

        # 4. Settings Grid
        self.settings_layout = QtWidgets.QGridLayout()
        self.settings_layout.setVerticalSpacing(4)
        self.settings_layout.setHorizontalSpacing(6)

        val_validator = QRegExpValidator(QRegExp(r'[0-9]+(\.[0-9]+)?'))
        int_validator = QRegExpValidator(QRegExp(r'[1-9][0-9]*'))
        cv_validator = QRegExpValidator(QRegExp(r'[2-9]|[1-9][0-9]+'))

        # Line width (formerly Default scale)
        self.default_scale_title_label = QtWidgets.QLabel("Line width", self)
        self.default_scale_lineedit = QtWidgets.QLineEdit("0.1", self)
        self.default_scale_lineedit.setValidator(val_validator)
        self.default_scale_lineedit.setFixedWidth(52)
        self.settings_layout.addWidget(self.default_scale_title_label, 0, 0)
        self.settings_layout.addWidget(self.default_scale_lineedit, 0, 1, QtCore.Qt.AlignRight)

        # Simplify curve (formerly Line resolution)
        self.line_resolution_label = QtWidgets.QLabel("Simplify curve", self)
        self.line_resolution_label.setToolTip("Simplifies and reduces curve CVs & spans for lighter, cleaner lines (1 is no simplification/raw stroke, default is 5).")
        self.line_resolution_lineedit = QtWidgets.QLineEdit("5", self)
        self.line_resolution_lineedit.setValidator(int_validator)
        self.line_resolution_lineedit.setFixedWidth(52)
        self.line_resolution_lineedit.setToolTip("Simplifies and reduces curve CVs & spans for lighter, cleaner lines (1 is no simplification/raw stroke, default is 5).")
        self.settings_layout.addWidget(self.line_resolution_label, 1, 0)
        self.settings_layout.addWidget(self.line_resolution_lineedit, 1, 1, QtCore.Qt.AlignRight)

        # Offset (formerly Subdiv Offset)
        self.subdived_target_offset_label = QtWidgets.QLabel("Offset", self)
        self.subdived_target_offset_label.setToolTip("When drawing on subdived mesh, the line clips inside. Adjust it here.")
        self.subdived_target_offset_lineedit = QtWidgets.QLineEdit("0.01", self)
        self.subdived_target_offset_lineedit.setValidator(val_validator)
        self.subdived_target_offset_lineedit.setFixedWidth(52)
        self.settings_layout.addWidget(self.subdived_target_offset_label, 2, 0)
        self.settings_layout.addWidget(self.subdived_target_offset_lineedit, 2, 1, QtCore.Qt.AlignRight)

        # Curve points
        self.curve_points_label = QtWidgets.QLabel("Curve points", self)
        self.curve_points_label.setToolTip("Number of driver points for scale/profile in the taper controller (default: 4).")
        self.curve_points_lineedit = QtWidgets.QLineEdit("4", self)
        self.curve_points_lineedit.setValidator(cv_validator)
        self.curve_points_lineedit.setFixedWidth(52)
        self.settings_layout.addWidget(self.curve_points_label, 3, 0)
        self.settings_layout.addWidget(self.curve_points_lineedit, 3, 1, QtCore.Qt.AlignRight)

        # Smooth curve
        self.smooth_curve_label = QtWidgets.QLabel("Smooth curve", self)
        self.smooth_curve_label.setToolTip("Controls stroke smoothing (0 = no smoothing, 1 = current smooth). Default is 1.0.")
        smooth_row = QtWidgets.QHBoxLayout()
        smooth_row.setSpacing(4)
        self.smooth_curve_lineedit = QtWidgets.QLineEdit("1.00", self)
        self.smooth_curve_lineedit.setFixedWidth(52)
        self.smooth_curve_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.smooth_curve_slider.setRange(0, 100)
        self.smooth_curve_slider.setValue(100)
        smooth_row.addWidget(self.smooth_curve_lineedit)
        smooth_row.addWidget(self.smooth_curve_slider)
        self.settings_layout.addWidget(self.smooth_curve_label, 4, 0)
        self.settings_layout.addLayout(smooth_row, 4, 1)

        # Sweep shape (flat to circular)
        self.sweep_shape_label = QtWidgets.QLabel("Sweep shape", self)
        self.sweep_shape_label.setToolTip("Adjusts sweep profile from Flat (0%) to Round (100%).")
        sweep_shape_row = QtWidgets.QHBoxLayout()
        sweep_shape_row.setSpacing(4)
        self.lbl_flat = QtWidgets.QLabel("Flat", self)
        self.lbl_flat.setStyleSheet("font-size: 8pt; color: #555555;")
        self.lbl_flat.setToolTip("Plat (0%)")
        self.sweep_shape_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.sweep_shape_slider.setRange(0, 100)
        self.sweep_shape_slider.setValue(100)
        self.sweep_shape_slider.setToolTip("Sweep shape: 0% = Flat (plat), 100% = Round (circulaire)")
        self.lbl_round = QtWidgets.QLabel("Round", self)
        self.lbl_round.setStyleSheet("font-size: 8pt; color: #555555;")
        self.lbl_round.setToolTip("Circulaire (100%)")
        sweep_shape_row.addWidget(self.lbl_flat)
        sweep_shape_row.addWidget(self.sweep_shape_slider)
        sweep_shape_row.addWidget(self.lbl_round)
        self.settings_layout.addWidget(self.sweep_shape_label, 5, 0)
        self.settings_layout.addLayout(sweep_shape_row, 5, 1)

        # Line color
        self.line_color_label = QtWidgets.QLabel("Line color", self)
        self.line_color_label.setToolTip("Click to open Maya's native color picker and change line shader color.")
        self.line_color_button = QtWidgets.QPushButton(self)
        self.line_color_button.setFixedSize(52, 22)
        self.line_color_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.updateColorButtonStyle((0.0, 0.0, 0.0))
        self.settings_layout.addWidget(self.line_color_label, 6, 0)
        self.settings_layout.addWidget(self.line_color_button, 6, 1, QtCore.Qt.AlignRight)

        # Smoothable & Displacement Checkboxes
        self.checkboxes_hlayout = QtWidgets.QHBoxLayout()
        self.checkboxes_hlayout.setContentsMargins(0, 4, 0, 0)
        self.checkboxes_hlayout.setSpacing(12)

        self.smoothable_checkbox = ComicSettingCheckBox("Smoothable", self)
        self.smoothable_checkbox.setToolTip("Adds a polySmoothFace node driven by 'method' and 'divisions' on the line.")
        self.displacement_checkbox = ComicSettingCheckBox("Displacement", self)
        self.displacement_checkbox.setToolTip("Adds procedural displacement to the line (requires Smoothable).")
        self.displacement_checkbox.setEnabled(False)
        self.add_noise_checkbox = self.displacement_checkbox

        self.checkboxes_hlayout.addWidget(self.smoothable_checkbox)
        self.checkboxes_hlayout.addWidget(self.displacement_checkbox)
        self.checkboxes_hlayout.addStretch()

        self.settings_layout.addLayout(self.checkboxes_hlayout, 7, 0, 1, 2)

        # Disp type dropdown
        self.disp_type_label = QtWidgets.QLabel("Disp type", self)
        self.disp_type_label.setToolTip("Displacement texture type ('noise', 'mountain', 'fractal').")
        self.disp_type_label.setEnabled(False)
        self.disp_type_combo = QtWidgets.QComboBox(self)
        self.disp_type_combo.addItems(["noise", "mountain", "fractal"])
        self.disp_type_combo.setToolTip("Displacement texture type")
        self.disp_type_combo.setEnabled(False)
        self.disp_type_combo.setFixedWidth(105)
        disp_combo_font = QtGui.QFont("Segoe Print", 10, QtGui.QFont.Bold)
        self.disp_type_combo.setFont(disp_combo_font)
        if self.disp_type_combo.view():
            self.disp_type_combo.view().setFont(disp_combo_font)
        self.disp_type_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 4px;
                padding: 1px 6px;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-size: 10pt;
                font-weight: bold;
                color: #1A2230;
                min-width: 95px;
            }
            QComboBox:hover {
                background-color: #FBF6EE;
            }
            QComboBox:disabled {
                background-color: #E2E8F0;
                color: #A0AEC0;
                border-color: #CBD5E0;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                selection-background-color: #1A2230;
                selection-color: #FBF6EE;
                color: #1A2230;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-size: 10pt;
                font-weight: bold;
            }
        """)
        self.settings_layout.addWidget(self.disp_type_label, 8, 0)
        self.settings_layout.addWidget(self.disp_type_combo, 8, 1, QtCore.Qt.AlignRight)

        # Rebuild line button
        self.rebuild_line_button = QtWidgets.QPushButton("Rebuild line (wip)", self)
        self.rebuild_line_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.rebuild_line_button.setToolTip("Rebuild selected line(s) with current settings (wip)")
        self.rebuild_line_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                color: #1A2230;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-weight: bold;
                font-size: 10pt;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #1A2230;
                color: #FBF6EE;
            }
            QPushButton:pressed {
                background-color: #333C4D;
                color: #FBF6EE;
            }
        """)
        self.settings_layout.addWidget(self.rebuild_line_button, 9, 0, 1, 2)

        self.main_layout.addLayout(self.settings_layout)

        # 5. Separator
        self.main_layout.addWidget(ComicSeparator(self))

        # 6. Follow Method Section
        self.follow_method_title_label = QtWidgets.QLabel("Follow method", self)
        self.follow_method_title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.follow_method_title_label)

        self.follow_method_buttons_layout = QtWidgets.QHBoxLayout()
        self.follow_method_buttons_layout.setSpacing(4)

        self.follow_btn_group = QtWidgets.QButtonGroup(self)
        self.follow_btn_group.setExclusive(True)

        self.btn_node_based = QtWidgets.QPushButton("Node", self)
        self.btn_node_based.setCheckable(True)
        self.btn_node_based.setChecked(True)
        self.btn_node_based.setToolTip("Fast, recommanded. Uses a strong and light node network.")

        self.btn_wrap = QtWidgets.QPushButton("Wrap", self)
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.setToolTip("Reliable, but slow. Not recommended for multiple lines.")

        self.btn_uv_pin = QtWidgets.QPushButton("UV pin", self)
        self.btn_uv_pin.setCheckable(True)
        self.btn_uv_pin.setToolTip("Fastest, but willing to break if the UV mapping is not optimal.")

        self.follow_btn_group.addButton(self.btn_node_based)
        self.follow_btn_group.addButton(self.btn_wrap)
        self.follow_btn_group.addButton(self.btn_uv_pin)

        self.follow_method_buttons_layout.addWidget(self.btn_node_based)
        self.follow_method_buttons_layout.addWidget(self.btn_wrap)
        self.follow_method_buttons_layout.addWidget(self.btn_uv_pin)
        self.main_layout.addLayout(self.follow_method_buttons_layout)
        self.updateFollowMethodUI()

        # 7. Separator
        self.main_layout.addWidget(ComicSeparator(self))

        # 8. Content section (collapsible header with Show all / Hide all)
        self.content_header_layout = QtWidgets.QHBoxLayout()
        self.content_header_layout.setContentsMargins(0, 0, 0, 0)
        self.content_header_layout.setSpacing(4)

        self.content_header = ComicCollapsibleHeader("Content", self)

        btn_header_style = """
            QPushButton {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 4px;
                color: #1A2230;
                font-family: "Segoe Print", "Ink Free", "Comic Sans MS", "Segoe UI", sans-serif;
                font-weight: bold;
                font-size: 8pt;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #1A2230;
                color: #FBF6EE;
            }
            QPushButton:pressed {
                background-color: #333C4D;
                color: #FBF6EE;
            }
        """

        self.show_all_button = QtWidgets.QPushButton("Show all", self)
        self.show_all_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.show_all_button.setToolTip("Show all lines in scene")
        self.show_all_button.setStyleSheet(btn_header_style)

        self.hide_all_button = QtWidgets.QPushButton("Hide all", self)
        self.hide_all_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.hide_all_button.setToolTip("Hide all lines in scene")
        self.hide_all_button.setStyleSheet(btn_header_style)

        self.content_header_layout.addWidget(self.content_header, 1)
        self.content_header_layout.addWidget(self.show_all_button)
        self.content_header_layout.addWidget(self.hide_all_button)
        self.main_layout.addLayout(self.content_header_layout)

        self.lines_list_widget = QtWidgets.QListWidget(self)
        self.lines_list_widget.setFixedHeight(120)
        self.lines_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.lines_list_widget.setFocusPolicy(QtCore.Qt.NoFocus)
        self.lines_list_widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.lines_list_widget.viewport().installEventFilter(self)
        self.main_layout.addWidget(self.lines_list_widget)

        # Mirror Row (Button + Dropdown L to R / R to L)
        self.mirror_container = QtWidgets.QWidget(self)
        self.mirror_hlayout = QtWidgets.QHBoxLayout(self.mirror_container)
        self.mirror_hlayout.setContentsMargins(0, 2, 0, 0)
        self.mirror_hlayout.setSpacing(6)

        self.mirror_button = QtWidgets.QPushButton("Mirror", self.mirror_container)
        self.mirror_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.mirror_button.setToolTip("Mirror selected lines across symmetry plane")
        self.mirror_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                color: #1A2230;
                font-weight: bold;
                font-size: 10pt;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #1A2230;
                color: #FBF6EE;
            }
            QPushButton:pressed {
                background-color: #333C4D;
                color: #FBF6EE;
            }
        """)

        self.mirror_combo = QtWidgets.QComboBox(self.mirror_container)
        self.mirror_combo.addItems(["L to R", "R to L"])
        self.mirror_combo.setToolTip("Mirror direction")
        self.mirror_combo.setStyleSheet("""
            QComboBox {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                color: #1A2230;
                font-weight: bold;
                font-size: 9pt;
                padding: 3px 8px;
                min-width: 65px;
            }
            QComboBox:hover {
                background-color: #FBF6EE;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                selection-background-color: #1A2230;
                selection-color: #FBF6EE;
                color: #1A2230;
            }
        """)

        self.mirror_hlayout.addWidget(self.mirror_button, 1)
        self.mirror_hlayout.addWidget(self.mirror_combo, 0)
        self.main_layout.addWidget(self.mirror_container)

        def _on_content_collapse(visible):
            self.lines_list_widget.setVisible(visible)
            self.mirror_container.setVisible(visible)

        self.content_header.toggled_collapse.connect(_on_content_collapse)

        # 9. Bake Button (inside the layout so it scrolls!)
        self.bake_button = QtWidgets.QPushButton("Bake deformations", self)
        self.bake_button.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                color: #1A2230;
                font-weight: bold;
                font-size: 11pt;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #1A2230;
                color: #FBF6EE;
            }
            QPushButton:pressed {
                background-color: #333C4D;
            }
        """)
        self.bake_button.setToolTip("Bakes curve animation over time so it is no longer deformed by nodes/wrap/rivets, but animated vertices.")
        self.main_layout.addWidget(self.bake_button)

        # 10. Footer spacing
        self.main_layout.addSpacing(6)

        # Connections
        global_scene_data_obj.request_ui_sync.connect(self.refreshList)
        global_scene_data_obj.request_ui_clear.connect(self.lines_list_widget.clear)

        self.set_target_mesh_button.clicked.connect(self.setTargetMeshButtonClicked)
        self.create_paint_line_button.clicked.connect(self.paintLineOnMesh)

        self.lines_list_widget.itemSelectionChanged.connect(self.selectLinesInMaya)
        self.lines_list_widget.itemClicked.connect(self.selectLinesInMaya)
        self.mirror_button.clicked.connect(self.mirrorSelectedLines)
        self.rebuild_line_button.clicked.connect(self.onRebuildButtonClicked)
        self.show_all_button.clicked.connect(self.showAllLines)
        self.hide_all_button.clicked.connect(self.hideAllLines)

        self.brush_slider.valueChanged.connect(self.changeBrushSizeSlider)
        self.brush_size_lineedit.textChanged.connect(self.changeBrushSizeText)

        self.preset_combo.currentIndexChanged.connect(self.onPresetComboChanged)
        self.add_preset_button.clicked.connect(self.onAddPresetClicked)
        self.delete_preset_button.clicked.connect(self.onDeletePresetClicked)

        self.lines_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lines_list_widget.customContextMenuRequested.connect(self.onLineListContextMenu)

        # Value sync connections
        self.default_scale_lineedit.textChanged.connect(self.changeLineDefaultScale)
        self.subdived_target_offset_lineedit.textChanged.connect(self.changeLineSubdivOffset)
        self.line_resolution_lineedit.textChanged.connect(self.changeLineResolution)
        self.curve_points_lineedit.textChanged.connect(self.changeCurvePoints)
        self.smooth_curve_slider.valueChanged.connect(self.changeSmoothCurveSlider)
        self.smooth_curve_lineedit.textChanged.connect(self.changeSmoothCurveText)
        self.sweep_shape_slider.valueChanged.connect(self.changeSweepShapeSlider)
        self.line_color_button.clicked.connect(self.pickLineColor)

        self.smoothable_checkbox.toggled.connect(self.onSmoothableToggled)
        self.displacement_checkbox.toggled.connect(self.onDisplacementToggled)
        self.disp_type_combo.currentIndexChanged.connect(self.onDispTypeChanged)

        # USER INTERACTION signals: only user edits will mark the preset as Custom!
        self.default_scale_lineedit.textEdited.connect(self.onUserParameterEdited)
        self.subdived_target_offset_lineedit.textEdited.connect(self.onUserParameterEdited)
        self.line_resolution_lineedit.textEdited.connect(self.onUserParameterEdited)
        self.curve_points_lineedit.textEdited.connect(self.onUserParameterEdited)
        self.smooth_curve_lineedit.textEdited.connect(self.onUserParameterEdited)
        self.smooth_curve_slider.sliderMoved.connect(self.onUserParameterEdited)
        self.sweep_shape_slider.sliderMoved.connect(self.onUserParameterEdited)
        self.smoothable_checkbox.clicked.connect(self.onUserParameterEdited)
        self.displacement_checkbox.clicked.connect(self.onUserParameterEdited)
        self.disp_type_combo.activated.connect(self.onUserParameterEdited)

        self.btn_node_based.clicked.connect(self.updateFollowMethodUI)
        self.btn_wrap.clicked.connect(self.updateFollowMethodUI)
        self.btn_uv_pin.clicked.connect(self.updateFollowMethodUI)

        self.bake_button.clicked.connect(self.bakeLinesClicked)

        self.set_target_mesh_lineedit.textChanged.connect(self.onTargetMeshTextChanged)

        self._is_applying_preset = False
        self._is_syncing_settings = False
        self.populatePresetsCombo(select_name="Basic")

        self.refreshList()
        self.initShaderColor()

        # Auto-detect target mesh from scene if already selected
        detected_mesh = get_selected_mesh_from_scene()
        if detected_mesh:
            self.setTargetMesh(detected_mesh)
        elif paint_on_mesh and cmds.objExists(paint_on_mesh):
            self.set_target_mesh_lineedit.setText(paint_on_mesh)

    def initShaderColor(self):
        global current_line_color
        if cmds.objExists('CartoonLineartShader'):
            col = cmds.getAttr('CartoonLineartShader.outColor')[0]
            current_line_color = (col[0], col[1], col[2])
            self.updateColorButtonStyle(current_line_color)

    def updateColorButtonStyle(self, color_tuple):
        r, g, b = color_tuple
        hex_col = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
        self.line_color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_col};
                border: 2px solid #1A2230;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #C08020;
            }}
        """)

    def pickLineColor(self):
        global current_line_color
        cmds.colorEditor(rgbValue=current_line_color)
        if cmds.colorEditor(query=True, result=True):
            values = cmds.colorEditor(query=True, rgb=True)
            r, g, b = values[0], values[1], values[2]
            current_line_color = (r, g, b)
            self.updateColorButtonStyle(current_line_color)
            detectOrCreateShader(color=current_line_color)
            self.applyColorToSelectedLines(current_line_color)
            self.markPresetCustom()

    def applyColorToSelectedLines(self, color):
        target_lines = []
        selected_names = set()
        selected_items = self.lines_list_widget.selectedItems()
        if selected_items:
            for it in selected_items:
                ld = it.data(QtCore.Qt.UserRole)
                if ld:
                    target_lines.append(ld)
                    if ld.get("name"):
                        selected_names.add(ld["name"])
        else:
            sel = cmds.ls(sl=True) or []
            if sel:
                all_lines = global_scene_data_obj.getAllLines()
                item_data_pairs = [(None, ld) for ld in all_lines.values()]
                matched = find_lines_for_maya_selection(sel, item_data_pairs)
                for _, ld in matched:
                    target_lines.append(ld)
                    if ld.get("name"):
                        selected_names.add(ld["name"])

        for ld in target_lines:
            mesh = ld.get("mesh")
            if mesh and cmds.objExists(mesh):
                assignLineShader(mesh, color=color)
            ld["color"] = color
            line_name = ld.get("name")
            if line_name:
                global_scene_data_obj.updateLineData(line_name, ld)

        # Restore selection in list widget
        if selected_names:
            self.lines_list_widget.blockSignals(True)
            try:
                for i in range(self.lines_list_widget.count()):
                    it = self.lines_list_widget.item(i)
                    d = it.data(QtCore.Qt.UserRole)
                    if d and d.get("name") in selected_names:
                        it.setSelected(True)
            finally:
                self.lines_list_widget.blockSignals(False)

        if target_lines:
            try:
                cmds.refresh()
            except Exception:
                pass

    def updateFollowMethodUI(self):
        global current_follow_method
        active_style = "background-color: #1A2230; color: #FBF6EE; border: 2px solid #1A2230; border-radius: 6px; padding: 4px; font-weight: bold;"
        inactive_style = "background-color: #FFFFFF; color: #1A2230; border: 2px solid #1A2230; border-radius: 6px; padding: 4px;"

        if self.btn_node_based.isChecked():
            current_follow_method = "Node based"
            self.btn_node_based.setStyleSheet(active_style)
            self.btn_wrap.setStyleSheet(inactive_style)
            self.btn_uv_pin.setStyleSheet(inactive_style)
        elif self.btn_wrap.isChecked():
            current_follow_method = "Wrap deformer"
            self.btn_node_based.setStyleSheet(inactive_style)
            self.btn_wrap.setStyleSheet(active_style)
            self.btn_uv_pin.setStyleSheet(inactive_style)
        elif self.btn_uv_pin.isChecked():
            current_follow_method = "UV pin"
            self.btn_node_based.setStyleSheet(inactive_style)
            self.btn_wrap.setStyleSheet(inactive_style)
            self.btn_uv_pin.setStyleSheet(active_style)

    def changeBrushSizeSlider(self, val):
        self.brush_size = max(0.1, val / 10.0)
        self.brush_size_lineedit.blockSignals(True)
        self.brush_size_lineedit.setText(f"{self.brush_size:.1f}")
        self.brush_size_lineedit.blockSignals(False)
        self.syncMayaBrushSize()

    def changeBrushSizeText(self, text):
        try:
            val = float(text)
            self.brush_size = max(0.1, min(50.0, val))
            slider_val = int(round(self.brush_size * 10.0))
            self.brush_slider.blockSignals(True)
            self.brush_slider.setValue(max(1, min(100, slider_val)))
            self.brush_slider.blockSignals(False)
            self.syncMayaBrushSize()
        except ValueError:
            pass

    def syncMayaBrushSize(self):
        global brush_size
        brush_size = self.brush_size
        try:
            tb = mel.eval('getDefaultBrush;')
            if tb and cmds.objExists(tb):
                cmds.setAttr(f'{tb}.globalScale', float(self.brush_size))
        except Exception:
            pass

    def onUserParameterEdited(self, *args):
        if getattr(self, "_is_applying_preset", False) or getattr(self, "_is_syncing_settings", False):
            return
        self.markPresetCustom()

    def changeSmoothCurveSlider(self, val):
        global smooth_curve
        smooth_curve = val / 100.0
        self.smooth_curve_lineedit.blockSignals(True)
        self.smooth_curve_lineedit.setText(f"{smooth_curve:.2f}")
        self.smooth_curve_lineedit.blockSignals(False)

    def changeSmoothCurveText(self, text):
        global smooth_curve
        try:
            val = float(text)
            smooth_curve = max(0.0, min(1.0, val))
            slider_val = int(round(smooth_curve * 100.0))
            self.smooth_curve_slider.blockSignals(True)
            self.smooth_curve_slider.setValue(slider_val)
            self.smooth_curve_slider.blockSignals(False)
        except ValueError:
            pass

    def changeSweepShapeSlider(self, val):
        global line_sweep_shape
        line_sweep_shape = float(val) / 100.0

    def eventFilter(self, source, event):
        if source == self.lines_list_widget.viewport() and event.type() == QtCore.QEvent.MouseButtonPress:
            item = self.lines_list_widget.itemAt(event.pos())
            if not item:
                self.lines_list_widget.clearSelection()
        return super().eventFilter(source, event)

    def refreshList(self):
        list_scrollbar = self.lines_list_widget.verticalScrollBar()
        current_scroll_value = list_scrollbar.value()

        self.lines_list_widget.clear()
        global_scene_data = global_scene_data_obj.getGlobalLinesData()

        for current_line_name in list(global_scene_data.keys()):
            current_line_data = dict(global_scene_data[current_line_name])
            current_line_item = QtWidgets.QListWidgetItem()
            current_line_item.setData(QtCore.Qt.UserRole, current_line_data)

            current_line_item_widget = lineListDisplayWidget(current_line_data, current_line_item)
            current_line_item.setSizeHint(current_line_item_widget.sizeHint())

            self.lines_list_widget.addItem(current_line_item)
            self.lines_list_widget.setItemWidget(current_line_item, current_line_item_widget)
            current_line_item_widget.delete_line_item.connect(self.deleteLineItem)

        list_scrollbar.setValue(current_scroll_value)
        if not getattr(self, "_is_paint_mode_active", False):
            self.syncContentSelectionFromMaya()

    def onSmoothableToggled(self, checked):
        global line_smoothable, line_displacement, line_add_noise
        line_smoothable = bool(checked)
        self.displacement_checkbox.setEnabled(line_smoothable)
        if not line_smoothable:
            self.displacement_checkbox.setChecked(False)
            line_displacement = False
            line_add_noise = False
            self.disp_type_combo.setEnabled(False)
            self.disp_type_label.setEnabled(False)

    def onDisplacementToggled(self, checked):
        global line_displacement, line_add_noise
        if not self.smoothable_checkbox.isChecked():
            self.displacement_checkbox.setChecked(False)
            line_displacement = False
            line_add_noise = False
            self.disp_type_combo.setEnabled(False)
            self.disp_type_label.setEnabled(False)
        else:
            line_displacement = bool(checked)
            line_add_noise = line_displacement
            self.disp_type_combo.setEnabled(line_displacement)
            self.disp_type_label.setEnabled(line_displacement)

    def onDispTypeChanged(self, index):
        global line_disp_type
        line_disp_type = self.disp_type_combo.currentText()

    def onAddNoiseToggled(self, checked):
        self.onDisplacementToggled(checked)

    def deleteLineItem(self, current_widget):
        row = self.lines_list_widget.row(current_widget.list_item)
        if row >= 0:
            self.lines_list_widget.takeItem(row)
        global_scene_data_obj.removeLineData(current_widget.line_data["name"])
        self.deleteLineInMaya(current_widget.line_data)

    def changeLineDefaultScale(self):
        global line_default_scale
        user_input = self.default_scale_lineedit.text()
        if user_input == '':
            user_input = 0.01
        try:
            line_default_scale = float(user_input)
        except Exception:
            return

    def changeLineSubdivOffset(self):
        global line_subdiv_offset
        user_input = self.subdived_target_offset_lineedit.text()
        if user_input == '':
            user_input = 0.0
        try:
            line_subdiv_offset = float(user_input)
        except Exception:
            return

    def changeLineResolution(self):
        global line_resolution
        user_input = self.line_resolution_lineedit.text()
        if user_input == '' or int(user_input) < 1:
            line_resolution = 5
        else:
            line_resolution = int(user_input)

    def changeCurvePoints(self):
        global curve_points
        user_input = self.curve_points_lineedit.text()
        if user_input == '' or int(user_input) < 2:
            curve_points = 4
        else:
            curve_points = int(user_input)

    def deleteLineInMaya(self, line_data):
        grp = line_data.get("group")
        if grp and cmds.objExists(grp):
            try:
                cmds.delete(grp)
            except Exception:
                pass

        taper_node = line_data.get("taper_ctrl_node")
        if taper_node and taper_node != line_data.get("mesh") and cmds.objExists(taper_node):
            try:
                cmds.delete(taper_node)
            except Exception:
                pass

        mult_node = line_data.get("mult_dl_node")
        if mult_node and cmds.objExists(mult_node):
            try:
                cmds.delete(mult_node)
            except Exception:
                pass

        sweep_node = line_data.get("sweep_msh_node")
        if sweep_node and cmds.objExists(sweep_node):
            try:
                cmds.delete(sweep_node)
            except Exception:
                pass

        profile_mult = line_data.get("profile_mult_node")
        if profile_mult and cmds.objExists(profile_mult):
            try:
                cmds.delete(profile_mult)
            except Exception:
                pass

        brush_node = line_data.get("brush_node")
        if brush_node and brush_node != "defaultBrush" and cmds.objExists(brush_node):
            try:
                cmds.delete(brush_node)
            except Exception:
                pass

        smooth_node = line_data.get("smooth_node")
        if smooth_node and cmds.objExists(smooth_node):
            try:
                cmds.delete(smooth_node)
            except Exception:
                pass

        tex_def = line_data.get("tex_def_node")
        if tex_def and cmds.objExists(tex_def):
            try:
                cmds.delete(tex_def)
            except Exception:
                pass

        noise_node = line_data.get("noise_node")
        if noise_node and cmds.objExists(noise_node):
            try:
                cmds.delete(noise_node)
            except Exception:
                pass

        tex_handle = line_data.get("tex_handle")
        if tex_handle and cmds.objExists(tex_handle):
            try:
                cmds.delete(tex_handle)
            except Exception:
                pass

        # Clean up strokeDefaultBrush or any orphaned stroke brushes
        clean_orphaned_stroke_brushes()

    def populatePresetsCombo(self, select_name="Basic"):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("Basic")
        all_presets = load_all_presets()
        for name in sorted(all_presets.keys()):
            if name not in ["Basic", "neutral", "Custom", "custom"]:
                self.preset_combo.addItem(name)
        self.preset_combo.addItem("Custom")

        idx = self.preset_combo.findText(select_name)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        else:
            self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

    def onPresetComboChanged(self, index):
        preset_name = self.preset_combo.currentText()
        if preset_name in ["Custom", "custom"]:
            return
        all_presets = load_all_presets()
        if preset_name in ["Basic", "neutral"]:
            preset_data = dict(DEFAULT_BASIC_PRESET)
        elif preset_name in all_presets:
            preset_data = dict(all_presets[preset_name])
        else:
            return
        self.applyPresetToUI(preset_data)

    def applyPresetToUI(self, preset_data):
        self._is_applying_preset = True
        try:
            global line_default_scale, line_resolution, line_subdiv_offset, curve_points
            global smooth_curve, line_sweep_shape, current_line_color
            global line_smoothable, line_displacement, line_add_noise, line_disp_type
            global active_preset_config

            active_preset_config = dict(preset_data)

            # Line width
            scale_val = preset_data.get("line_default_scale", preset_data.get("scale_profile", 0.1))
            line_default_scale = float(scale_val)
            self.default_scale_lineedit.blockSignals(True)
            self.default_scale_lineedit.setText(f"{line_default_scale:.2f}".rstrip('0').rstrip('.'))
            self.default_scale_lineedit.blockSignals(False)

            # Line resolution
            res_val = preset_data.get("line_resolution", 5)
            line_resolution = int(res_val)
            self.line_resolution_lineedit.blockSignals(True)
            self.line_resolution_lineedit.setText(str(line_resolution))
            self.line_resolution_lineedit.blockSignals(False)

            # Offset
            off_val = preset_data.get("line_subdiv_offset", 0.01)
            line_subdiv_offset = float(off_val)
            self.subdived_target_offset_lineedit.blockSignals(True)
            self.subdived_target_offset_lineedit.setText(str(line_subdiv_offset))
            self.subdived_target_offset_lineedit.blockSignals(False)

            # Curve points
            pts_val = preset_data.get("curve_points", 4)
            curve_points = int(pts_val)
            self.curve_points_lineedit.blockSignals(True)
            self.curve_points_lineedit.setText(str(curve_points))
            self.curve_points_lineedit.blockSignals(False)

            # Smooth curve
            sc_val = preset_data.get("smooth_curve", 1.0)
            smooth_curve = float(sc_val)
            self.smooth_curve_slider.blockSignals(True)
            self.smooth_curve_slider.setValue(int(round(smooth_curve * 100.0)))
            self.smooth_curve_slider.blockSignals(False)
            self.smooth_curve_lineedit.blockSignals(True)
            self.smooth_curve_lineedit.setText(f"{smooth_curve:.2f}")
            self.smooth_curve_lineedit.blockSignals(False)

            # Sweep shape
            sw_val = preset_data.get("line_sweep_shape", preset_data.get("roundness", 1.0))
            line_sweep_shape = float(sw_val)
            self.sweep_shape_slider.blockSignals(True)
            self.sweep_shape_slider.setValue(int(round(line_sweep_shape * 100.0)))
            self.sweep_shape_slider.blockSignals(False)

            # Color
            col = preset_data.get("current_line_color", preset_data.get("color", [0.0, 0.0, 0.0]))
            current_line_color = (float(col[0]), float(col[1]), float(col[2]))
            self.updateColorButtonStyle(current_line_color)

            # Smoothable
            sm_val = bool(preset_data.get("line_smoothable", preset_data.get("smoothable", False)))
            line_smoothable = sm_val
            self.smoothable_checkbox.blockSignals(True)
            self.smoothable_checkbox.setChecked(line_smoothable)
            self.smoothable_checkbox.blockSignals(False)
            self.displacement_checkbox.setEnabled(line_smoothable)

            # Displacement
            disp_val = bool(preset_data.get("line_displacement", preset_data.get("displacement", False)))
            line_displacement = disp_val and line_smoothable
            line_add_noise = line_displacement
            self.displacement_checkbox.blockSignals(True)
            self.displacement_checkbox.setChecked(line_displacement)
            self.displacement_checkbox.blockSignals(False)

            # Disp type
            dt_val = preset_data.get("line_disp_type", preset_data.get("disp_type", "noise"))
            line_disp_type = str(dt_val)
            self.disp_type_combo.setEnabled(line_smoothable and line_displacement)
            self.disp_type_label.setEnabled(line_smoothable and line_displacement)
            self.disp_type_combo.blockSignals(True)
            idx = self.disp_type_combo.findText(line_disp_type)
            if idx >= 0:
                self.disp_type_combo.setCurrentIndex(idx)
            self.disp_type_combo.blockSignals(False)
        finally:
            self._is_applying_preset = False

    def onAddPresetClicked(self):
        selected_items = self.lines_list_widget.selectedItems()
        if not selected_items and self.lines_list_widget.currentItem():
            selected_items = [self.lines_list_widget.currentItem()]

        if not selected_items:
            QtWidgets.QMessageBox.warning(self, "Add Preset", "Please select a line in the Content list to create a preset.")
            return

        item = selected_items[0]
        line_data = item.data(QtCore.Qt.UserRole)
        if not line_data:
            return

        line_name = line_data.get("name", "line")
        mesh = line_data.get("mesh")
        if not mesh or not cmds.objExists(mesh):
            grp = line_data.get("group")
            if grp and cmds.objExists(grp):
                transforms = cmds.listRelatives(grp, allDescendents=True, type="transform") or []
                for tr in transforms:
                    if tr.endswith("_msh") and cmds.objExists(tr):
                        mesh = tr
                        break

        if not mesh or not cmds.objExists(mesh):
            QtWidgets.QMessageBox.warning(self, "Add Preset", f"Could not find mesh for line '{line_name}'.")
            return

        preset_name, ok = QtWidgets.QInputDialog.getText(
            self, "Add Preset", "Preset name:", QtWidgets.QLineEdit.Normal, line_name
        )
        if not ok or not preset_name.strip():
            return
        preset_name = preset_name.strip()

        attrs = extractLineAttributes(mesh, line_data)
        if not attrs:
            QtWidgets.QMessageBox.warning(self, "Add Preset", "Failed to extract attributes from line.")
            return

        preset_data = dict(attrs)
        preset_data["line_default_scale"] = attrs.get("scale_profile", 0.1)
        preset_data["line_sweep_shape"] = attrs.get("roundness", 1.0)
        preset_data["line_smoothable"] = attrs.get("smoothable", False)
        preset_data["line_displacement"] = attrs.get("displacement", False)
        preset_data["line_disp_type"] = attrs.get("disp_type", "noise")
        preset_data["current_line_color"] = list(attrs.get("color", [0.0, 0.0, 0.0]))
        preset_data["line_resolution"] = line_resolution
        preset_data["line_subdiv_offset"] = line_subdiv_offset
        preset_data["curve_points"] = curve_points
        preset_data["smooth_curve"] = smooth_curve

        saved = save_user_preset(preset_name, preset_data)
        if saved:
            self.populatePresetsCombo(select_name=preset_name)
            self.applyPresetToUI(preset_data)
            try:
                cmds.inViewMessage(amg=f"Created preset <hl>{preset_name}</hl>", pos='topCenter', fade=True)
            except Exception:
                pass
            print(f"Created preset '{preset_name}'")

    def onDeletePresetClicked(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name in ["Basic", "Custom", "basic", "custom", "neutral"]:
            return

        delete_user_preset(preset_name)
        self.populatePresetsCombo(select_name="Basic")
        self.onPresetComboChanged(self.preset_combo.currentIndex())

    def markPresetCustom(self):
        if getattr(self, "_is_applying_preset", False) or getattr(self, "_is_syncing_settings", False):
            return
        if self.preset_combo.currentText() != "Custom":
            self.preset_combo.blockSignals(True)
            idx = self.preset_combo.findText("Custom")
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self.preset_combo.blockSignals(False)

        global active_preset_config
        if not isinstance(active_preset_config, dict):
            active_preset_config = dict(DEFAULT_BASIC_PRESET)
        active_preset_config["line_default_scale"] = line_default_scale
        active_preset_config["scale_profile"] = line_default_scale
        active_preset_config["line_resolution"] = line_resolution
        active_preset_config["line_subdiv_offset"] = line_subdiv_offset
        active_preset_config["curve_points"] = curve_points
        active_preset_config["smooth_curve"] = smooth_curve
        active_preset_config["line_sweep_shape"] = line_sweep_shape
        active_preset_config["roundness"] = line_sweep_shape
        active_preset_config["current_line_color"] = list(current_line_color)
        active_preset_config["color"] = list(current_line_color)
        active_preset_config["line_smoothable"] = line_smoothable
        active_preset_config["smoothable"] = line_smoothable
        active_preset_config["line_displacement"] = line_displacement
        active_preset_config["displacement"] = line_displacement
        active_preset_config["line_disp_type"] = line_disp_type
        active_preset_config["disp_type"] = line_disp_type

    def onLineListContextMenu(self, pos):
        item = self.lines_list_widget.itemAt(pos)
        selected_items = [it for it in self.lines_list_widget.selectedItems() if it.isSelected()]
        if item and item not in selected_items:
            # If item right-clicked is not in selected_items, check if Maya has multiple lines selected
            maya_sel = cmds.ls(sl=True) or []
            all_lines = global_scene_data_obj.getAllLines()
            item_data_pairs = [(None, v) for v in all_lines.values()]
            matched = find_lines_for_maya_selection(maya_sel, item_data_pairs)
            if len(matched) <= 1:
                self.lines_list_widget.clearSelection()
                item.setSelected(True)
                self.lines_list_widget.setCurrentItem(item)
                self.selectLinesInMaya()
                selected_items = [item]

        if not selected_items and self.lines_list_widget.currentItem() and self.lines_list_widget.currentItem().isSelected():
            selected_items = [self.lines_list_widget.currentItem()]

        has_targets = bool(selected_items)
        if not has_targets:
            maya_sel = cmds.ls(sl=True) or []
            all_lines = global_scene_data_obj.getAllLines()
            item_data_pairs = [(None, v) for v in all_lines.values()]
            has_targets = bool(find_lines_for_maya_selection(maya_sel, item_data_pairs))

        menu = QtWidgets.QMenu(self.lines_list_widget)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 2px solid #1A2230;
                border-radius: 6px;
                padding: 4px;
                font-weight: bold;
                color: #1A2230;
            }
            QMenu::item {
                padding: 4px 18px 4px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #EFE5D3;
                color: #1A2230;
            }
            QMenu::item:disabled {
                color: #A0AEC0;
            }
        """)

        copy_action = menu.addAction("Copy attributes")
        paste_action = menu.addAction("Paste attributes")

        copy_action.setEnabled(has_targets)
        paste_action.setEnabled(bool(_copied_line_attributes is not None and has_targets))

        action = menu.exec_(self.lines_list_widget.viewport().mapToGlobal(pos))
        if action == copy_action:
            self.copySelectedLineAttributes()
        elif action == paste_action:
            self.pasteSelectedLineAttributes()

    def copySelectedLineAttributes(self):
        global _copied_line_attributes
        selected_items = [it for it in self.lines_list_widget.selectedItems() if it.isSelected()]

        line_data = None
        if selected_items:
            try:
                line_data = selected_items[0].data(QtCore.Qt.UserRole)
            except Exception:
                line_data = None

        if not line_data:
            maya_sel = cmds.ls(sl=True) or []
            if maya_sel:
                all_lines = global_scene_data_obj.getAllLines()
                item_data_pairs = [(None, v) for v in all_lines.values()]
                matched = find_lines_for_maya_selection(maya_sel, item_data_pairs)
                if matched and matched[0][1]:
                    line_data = matched[0][1]

        if not line_data and self.lines_list_widget.currentItem() and self.lines_list_widget.currentItem().isSelected():
            line_data = self.lines_list_widget.currentItem().data(QtCore.Qt.UserRole)

        if not line_data:
            return

        mesh = line_data.get("mesh")
        if not mesh or not cmds.objExists(mesh):
            grp = line_data.get("group")
            if grp and cmds.objExists(grp):
                transforms = cmds.listRelatives(grp, allDescendents=True, type="transform") or []
                for tr in transforms:
                    if tr.endswith("_msh") and cmds.objExists(tr):
                        mesh = tr
                        break
        if not mesh or not cmds.objExists(mesh):
            cmds.warning(f"Could not find mesh for line '{line_data.get('name')}'")
            return

        _copied_line_attributes = extractLineAttributes(mesh, line_data)
        line_name = line_data.get('name', 'line')
        try:
            cmds.inViewMessage(amg=f"Copied attributes from <hl>{line_name}</hl>", pos='topCenter', fade=True)
        except Exception:
            pass
        print(f"Copied attributes from {line_name}")

    def pasteSelectedLineAttributes(self):
        global _copied_line_attributes
        if not _copied_line_attributes:
            QtWidgets.QMessageBox.information(self, "Paste attributes", "No attributes copied yet.")
            return

        # 1. Gather all target line dicts upfront BEFORE any rebuilding
        selected_items = [it for it in self.lines_list_widget.selectedItems() if it.isSelected()]

        target_line_data_list = []
        target_names = set()

        if selected_items:
            for item in selected_items:
                try:
                    ld = item.data(QtCore.Qt.UserRole)
                    if ld and isinstance(ld, dict):
                        target_line_data_list.append(dict(ld))
                        if ld.get("name"):
                            target_names.add(ld.get("name"))
                except Exception:
                    pass

        # If list widget has no selection or only 1 item, check if Maya has a broader selection
        maya_sel = cmds.ls(sl=True) or []
        if maya_sel:
            all_lines = global_scene_data_obj.getAllLines()
            item_data_pairs = [(None, v) for v in all_lines.values()]
            matched = find_lines_for_maya_selection(maya_sel, item_data_pairs)
            maya_matched_lines = [dict(p[1]) for p in matched if p[1] and isinstance(p[1], dict)]
            if len(maya_matched_lines) > len(target_line_data_list):
                target_line_data_list = maya_matched_lines
                target_names = {ld.get("name") for ld in target_line_data_list if ld.get("name")}
            elif not target_line_data_list:
                target_line_data_list = maya_matched_lines
                target_names = {ld.get("name") for ld in target_line_data_list if ld.get("name")}

        if not target_line_data_list and self.lines_list_widget.currentItem() and self.lines_list_widget.currentItem().isSelected():
            ld = self.lines_list_widget.currentItem().data(QtCore.Qt.UserRole)
            if ld and isinstance(ld, dict):
                target_line_data_list.append(dict(ld))
                if ld.get("name"):
                    target_names.add(ld.get("name"))

        if not target_line_data_list:
            return

        # 2. Block UI sync signals during batch paste so refreshList is not called per line
        cmds.undoInfo(openChunk=True, chunkName="PasteLineAttributes")
        global_scene_data_obj.blockSignals(True)
        pasted_count = 0
        try:
            for line_data in target_line_data_list:
                mesh = line_data.get("mesh")
                if not mesh or not cmds.objExists(mesh):
                    grp = line_data.get("group")
                    if grp and cmds.objExists(grp):
                        transforms = cmds.listRelatives(grp, allDescendents=True, type="transform") or []
                        for tr in transforms:
                            if tr.endswith("_msh") and cmds.objExists(tr):
                                mesh = tr
                                break
                if mesh and cmds.objExists(mesh):
                    applyExtractedAttributes(mesh, line_data, _copied_line_attributes)
                    pasted_count += 1
        finally:
            global_scene_data_obj.blockSignals(False)
            cmds.undoInfo(closeChunk=True)

        # 3. Refresh UI once cleanly and restore selection on all target lines
        self.refreshList()
        self.lines_list_widget.blockSignals(True)
        meshes_to_select = []
        try:
            self.lines_list_widget.clearSelection()
            for i in range(self.lines_list_widget.count()):
                it = self.lines_list_widget.item(i)
                dt = it.data(QtCore.Qt.UserRole)
                if dt and dt.get("name") in target_names:
                    it.setSelected(True)
                    msh = dt.get("mesh")
                    if msh and cmds.objExists(msh):
                        meshes_to_select.append(msh)
        finally:
            self.lines_list_widget.blockSignals(False)

        if meshes_to_select:
            self._is_syncing_selection = True
            try:
                cmds.select(meshes_to_select, r=True)
            finally:
                self._is_syncing_selection = False

        msg = f"Pasted attributes to {pasted_count} line(s)"
        try:
            cmds.inViewMessage(amg=msg, pos='topCenter', fade=True)
        except Exception:
            pass
        print(msg)

    def getCurrentUISettings(self):
        """
        Collects all current UI parameter settings into an attribute dictionary.
        """
        global active_preset_config, line_default_scale, line_sweep_shape, line_smoothable, line_displacement, line_disp_type, current_line_color, current_follow_method
        settings = {}
        if isinstance(active_preset_config, dict):
            settings.update(active_preset_config)

        try:
            settings["scale_profile"] = float(self.default_scale_lineedit.text())
        except Exception:
            settings["scale_profile"] = line_default_scale
        settings["line_default_scale"] = settings["scale_profile"]

        try:
            settings["roundness"] = self.sweep_shape_slider.value() / 100.0
        except Exception:
            settings["roundness"] = line_sweep_shape
        settings["line_sweep_shape"] = settings["roundness"]

        settings["smoothable"] = self.smoothable_checkbox.isChecked()
        settings["line_smoothable"] = settings["smoothable"]

        settings["displacement"] = self.displacement_checkbox.isChecked()
        settings["line_displacement"] = settings["displacement"]
        settings["add_noise"] = settings["displacement"]

        settings["disp_type"] = self.disp_type_combo.currentText()
        settings["line_disp_type"] = settings["disp_type"]

        settings["color"] = list(current_line_color)
        settings["current_line_color"] = list(current_line_color)

        settings["follow_method"] = current_follow_method

        return settings

    def onRebuildButtonClicked(self):
        """
        Slot triggered when the 'Rebuild line' button is clicked.
        Opens the RebuildLineOptionsDialog to prompt user for options.
        """
        self.rebuildSelectedLines(show_dialog=True)

    def rebuildSelectedLines(self, *args, show_dialog=False, rebuild_ui_elements=None, rebuild_custom_attrs=None, rebuild_follow_method=None):
        """
        Rebuilds selected line(s) in the UI or Viewport with current UI settings.
        If show_dialog is True, presents a modal dialog with 3 checkable options:
        - "ui elements": Updates Line width, Sweep shape, Smoothable, Displacement, Disp type, Color
        - "custom attributes": Updates Sides, rotate_profile, cap, precision, taper, noise parameters
        - "follow method": Updates the line's follow method to the currently active UI follow method
        """
        selected_items = [it for it in self.lines_list_widget.selectedItems() if it.isSelected()]

        target_line_data_list = []
        target_names = set()
        if selected_items:
            for item in selected_items:
                try:
                    data = item.data(QtCore.Qt.UserRole)
                    if data and isinstance(data, dict):
                        target_line_data_list.append(dict(data))
                        if data.get("name"):
                            target_names.add(data.get("name"))
                except Exception:
                    pass

        maya_sel = cmds.ls(sl=True) or []
        if maya_sel:
            all_lines = global_scene_data_obj.getAllLines()
            item_data_pairs = [(None, v) for v in all_lines.values()]
            matched = find_lines_for_maya_selection(maya_sel, item_data_pairs)
            maya_matched = [dict(p[1]) for p in matched if p[1] and isinstance(p[1], dict)]
            if len(maya_matched) > len(target_line_data_list):
                target_line_data_list = maya_matched
                target_names = {ld.get("name") for ld in target_line_data_list if ld.get("name")}
            elif not target_line_data_list:
                target_line_data_list = maya_matched
                target_names = {ld.get("name") for ld in target_line_data_list if ld.get("name")}

        if not target_line_data_list and self.lines_list_widget.currentItem() and self.lines_list_widget.currentItem().isSelected():
            data = self.lines_list_widget.currentItem().data(QtCore.Qt.UserRole)
            if data and isinstance(data, dict):
                target_line_data_list.append(dict(data))
                if data.get("name"):
                    target_names.add(data.get("name"))

        if not target_line_data_list:
            try:
                cmds.inViewMessage(amg="Please select a line to rebuild.", pos='topCenter', fade=True)
            except Exception:
                pass
            return

        if show_dialog:
            if not hasattr(self, "_last_rebuild_options") or not isinstance(self._last_rebuild_options, dict):
                self._last_rebuild_options = {"ui_elements": True, "custom_attrs": False, "follow_method": False}

            dlg = RebuildLineOptionsDialog(parent=self, initial_options=self._last_rebuild_options)
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                return  # User canceled

            opts = dlg.get_options()
            self._last_rebuild_options = opts
            rebuild_ui_elements = opts["ui_elements"]
            rebuild_custom_attrs = opts["custom_attrs"]
            rebuild_follow_method = opts["follow_method"]
        else:
            if rebuild_ui_elements is None:
                rebuild_ui_elements = True
            if rebuild_custom_attrs is None:
                rebuild_custom_attrs = True
            if rebuild_follow_method is None:
                rebuild_follow_method = False

        ui_settings = self.getCurrentUISettings()

        cmds.undoInfo(openChunk=True, chunkName="RebuildLine")
        global_scene_data_obj.blockSignals(True)
        rebuilt_count = 0
        try:
            for ld in target_line_data_list:
                res = rebuildLine(
                    ld,
                    new_attrs=ui_settings,
                    rebuild_ui_elements=rebuild_ui_elements,
                    rebuild_custom_attrs=rebuild_custom_attrs,
                    rebuild_follow_method=rebuild_follow_method
                )
                if res:
                    rebuilt_count += 1
        finally:
            global_scene_data_obj.blockSignals(False)
            cmds.undoInfo(closeChunk=True)

        self.refreshList()
        self.lines_list_widget.blockSignals(True)
        meshes_to_select = []
        try:
            self.lines_list_widget.clearSelection()
            for i in range(self.lines_list_widget.count()):
                it = self.lines_list_widget.item(i)
                dt = it.data(QtCore.Qt.UserRole)
                if dt and dt.get("name") in target_names:
                    it.setSelected(True)
                    msh = dt.get("mesh")
                    if msh and cmds.objExists(msh):
                        meshes_to_select.append(msh)
        finally:
            self.lines_list_widget.blockSignals(False)

        if meshes_to_select:
            self._is_syncing_selection = True
            try:
                cmds.select(meshes_to_select, r=True)
            finally:
                self._is_syncing_selection = False

        options_summary = []
        if rebuild_ui_elements:
            options_summary.append("UI elements")
        if rebuild_custom_attrs:
            options_summary.append("Custom attributes")
        if rebuild_follow_method:
            options_summary.append("Follow method")
        summary_str = ", ".join(options_summary) if options_summary else "No changes"

        msg = f"Rebuilt {rebuilt_count} line(s) ({summary_str})"
        try:
            cmds.inViewMessage(amg=msg, pos='topCenter', fade=True)
        except Exception:
            pass
        print(msg)

    def showAllLines(self):
        """
        Shows all lines in the scene by setting .v to 1 on their root groups.
        """
        all_lines = global_scene_data_obj.getAllLines()
        if not all_lines:
            return
        cmds.undoInfo(openChunk=True, chunkName="ShowAllLines")
        try:
            for name, data in all_lines.items():
                grp = data.get("group") or f"{name}_grp"
                if grp and cmds.objExists(grp):
                    try:
                        cmds.setAttr(f"{grp}.v", 1)
                    except Exception:
                        pass
        finally:
            cmds.undoInfo(closeChunk=True)
        self.refreshList()
        try:
            cmds.inViewMessage(amg=f"Showed all lines ({len(all_lines)})", pos='topCenter', fade=True)
        except Exception:
            pass

    def hideAllLines(self):
        """
        Hides all lines in the scene by setting .v to 0 on their root groups.
        """
        all_lines = global_scene_data_obj.getAllLines()
        if not all_lines:
            return
        cmds.undoInfo(openChunk=True, chunkName="HideAllLines")
        try:
            for name, data in all_lines.items():
                grp = data.get("group") or f"{name}_grp"
                if grp and cmds.objExists(grp):
                    try:
                        cmds.setAttr(f"{grp}.v", 0)
                    except Exception:
                        pass
        finally:
            cmds.undoInfo(closeChunk=True)
        self.refreshList()
        try:
            cmds.inViewMessage(amg=f"Hid all lines ({len(all_lines)})", pos='topCenter', fade=True)
        except Exception:
            pass

    def selectLinesInMaya(self, *args):
        if getattr(self, "_is_syncing_selection", False):
            return
        self._is_syncing_selection = True
        try:
            selected_items = self.lines_list_widget.selectedItems()
            if not selected_items:
                return
            meshes_to_select = []
            for item in selected_items:
                line_data = item.data(QtCore.Qt.UserRole)
                if not line_data:
                    continue
                reset_pivots_to_origin(
                    line_data.get("group"),
                    line_data.get("mesh"),
                    line_data.get("curve"),
                    line_data.get("root_convert_grp"),
                    line_data.get("converted_curve_grp")
                )
                mesh = line_data.get("mesh")
                if mesh and cmds.objExists(mesh):
                    meshes_to_select.append(mesh)

            if meshes_to_select:
                cmds.select(meshes_to_select, r=True)
                try:
                    if len(meshes_to_select) == 1:
                        cmds.headsUpMessage('Selected !', object=meshes_to_select[0])
                    else:
                        cmds.headsUpMessage(f'{len(meshes_to_select)} lines selected !')
                except Exception:
                    pass

            # Smart mirror direction hint based on selected line naming
            if len(selected_items) == 1:
                item_data = selected_items[0].data(QtCore.Qt.UserRole)
                if item_data and isinstance(item_data, dict):
                    name = item_data.get("name", "")
                    if re.search(r'([_\.-])L(?:_\d+)?$', name, flags=re.IGNORECASE) or re.search(r'^(?:L|Left)[_\.-]', name, flags=re.IGNORECASE):
                        if hasattr(self, "mirror_combo"):
                            self.mirror_combo.setCurrentText("L to R")
                    elif re.search(r'([_\.-])R(?:_\d+)?$', name, flags=re.IGNORECASE) or re.search(r'^(?:R|Right)[_\.-]', name, flags=re.IGNORECASE):
                        if hasattr(self, "mirror_combo"):
                            self.mirror_combo.setCurrentText("R to L")
        finally:
            self._is_syncing_selection = False

    selectLineInMaya = selectLinesInMaya

    def mirrorSelectedLines(self):
        selected_items = [it for it in self.lines_list_widget.selectedItems() if it.isSelected()]

        target_lines = []
        target_names = set()

        if selected_items:
            for it in selected_items:
                try:
                    ld = it.data(QtCore.Qt.UserRole)
                    if ld and isinstance(ld, dict):
                        target_lines.append(dict(ld))
                        if ld.get("name"):
                            target_names.add(ld.get("name"))
                except Exception:
                    pass

        # Check Maya viewport selection
        maya_sel = cmds.ls(sl=True) or []
        if maya_sel:
            all_lines = global_scene_data_obj.getAllLines()
            item_data_pairs = [(None, v) for v in all_lines.values()]
            matched = find_lines_for_maya_selection(maya_sel, item_data_pairs)
            maya_matched_lines = [dict(p[1]) for p in matched if p[1] and isinstance(p[1], dict)]
            if len(maya_matched_lines) > len(target_lines):
                target_lines = maya_matched_lines
                target_names = {ld.get("name") for ld in target_lines if ld.get("name")}
            elif not target_lines:
                target_lines = maya_matched_lines
                target_names = {ld.get("name") for ld in target_lines if ld.get("name")}

        if not target_lines and self.lines_list_widget.currentItem() and self.lines_list_widget.currentItem().isSelected():
            ld = self.lines_list_widget.currentItem().data(QtCore.Qt.UserRole)
            if ld and isinstance(ld, dict):
                target_lines.append(dict(ld))
                if ld.get("name"):
                    target_names.add(ld.get("name"))

        if not target_lines:
            QtWidgets.QMessageBox.warning(self, "", "Please select one or more lines to mirror !")
            return

        direction = self.mirror_combo.currentText()

        # Check target mesh
        target_msh = paint_on_mesh
        if not target_msh or not cmds.objExists(target_msh):
            detected = get_selected_mesh_from_scene()
            if detected:
                self.setTargetMesh(detected)
                target_msh = detected
            elif self.set_target_mesh_lineedit.text().strip():
                typed = self.set_target_mesh_lineedit.text().strip()
                if cmds.objExists(typed):
                    self.setTargetMesh(typed)
                    target_msh = typed

        cmds.undoInfo(openChunk=True, chunkName="CartoonLineartMirror")
        global_scene_data_obj.blockSignals(True)
        mirrored_items = []
        try:
            for line_data in target_lines:
                line_target_mesh = get_target_mesh_for_line(line_data) or target_msh
                if line_target_mesh and (not paint_on_mesh or not cmds.objExists(paint_on_mesh)):
                    self.setTargetMesh(line_target_mesh)
                new_data = mirrorSingleLine(line_data, direction=direction, target_mesh=line_target_mesh)
                if new_data:
                    mirrored_items.append(new_data)
        finally:
            global_scene_data_obj.blockSignals(False)
            cmds.undoInfo(closeChunk=True)

        if mirrored_items:
            self.refreshList()
            new_names = {d["name"] for d in mirrored_items if "name" in d}
            new_meshes = [d["mesh"] for d in mirrored_items if "mesh" in d and cmds.objExists(d["mesh"])]

            self.lines_list_widget.blockSignals(True)
            try:
                self.lines_list_widget.clearSelection()
                for i in range(self.lines_list_widget.count()):
                    it = self.lines_list_widget.item(i)
                    dt = it.data(QtCore.Qt.UserRole)
                    if dt and dt.get("name") in new_names:
                        it.setSelected(True)
            finally:
                self.lines_list_widget.blockSignals(False)

            if new_meshes:
                self._is_syncing_selection = True
                try:
                    cmds.select(new_meshes, r=True)
                finally:
                    self._is_syncing_selection = False

            msg = f"{len(mirrored_items)} line(s) mirrored ({direction}) !"
            try:
                cmds.headsUpMessage(msg)
                cmds.inViewMessage(amg=msg, pos='topCenter', fade=True)
            except Exception:
                pass
            print(msg)

    def setTargetMesh(self, mesh_name: str):
        global paint_on_mesh
        if not mesh_name or not cmds.objExists(mesh_name):
            return
        paint_on_mesh = mesh_name
        if self.set_target_mesh_lineedit.text() != mesh_name:
            self.set_target_mesh_lineedit.blockSignals(True)
            self.set_target_mesh_lineedit.setText(mesh_name)
            self.set_target_mesh_lineedit.blockSignals(False)

    def onTargetMeshTextChanged(self, text: str):
        global paint_on_mesh
        name = text.strip()
        if name and cmds.objExists(name):
            paint_on_mesh = name
        elif not name:
            paint_on_mesh = None

    def onSceneSelectionChanged(self):
        if getattr(self, "_is_syncing_selection", False) or getattr(self, "_is_drawing_line", False) or getattr(self, "_is_paint_mode_active", False):
            return
        self._is_syncing_selection = True
        try:
            mesh_name = get_selected_mesh_from_scene()
            if mesh_name:
                self.setTargetMesh(mesh_name)

            self.syncContentSelectionFromMaya()
        except RuntimeError:
            kill_selection_listener()
        except Exception:
            pass
        finally:
            self._is_syncing_selection = False

    def syncContentSelectionFromMaya(self):
        if getattr(self, "_is_drawing_line", False) or getattr(self, "_is_paint_mode_active", False):
            return

        sel = cmds.ls(sl=True) or []
        if not sel:
            if self.lines_list_widget.selectedItems():
                self.lines_list_widget.blockSignals(True)
                try:
                    self.lines_list_widget.clearSelection()
                finally:
                    self.lines_list_widget.blockSignals(False)
            return

        item_data_pairs = []
        for i in range(self.lines_list_widget.count()):
            it = self.lines_list_widget.item(i)
            ld = it.data(QtCore.Qt.UserRole)
            if ld:
                item_data_pairs.append((it, ld))

        matched_pairs = find_lines_for_maya_selection(sel, item_data_pairs)
        items_to_select = [p[0] for p in matched_pairs]

        current_rows = {self.lines_list_widget.row(it) for it in self.lines_list_widget.selectedItems()}
        new_rows = {self.lines_list_widget.row(it) for it in items_to_select}

        if current_rows != new_rows:
            self.lines_list_widget.blockSignals(True)
            try:
                self.lines_list_widget.clearSelection()
                for it in items_to_select:
                    it.setSelected(True)
                if items_to_select:
                    self.lines_list_widget.setCurrentItem(items_to_select[-1])
                    self.lines_list_widget.scrollToItem(items_to_select[-1], QtWidgets.QAbstractItemView.EnsureVisible)
            finally:
                self.lines_list_widget.blockSignals(False)

    def setTargetMeshButtonClicked(self):
        sel_mesh = get_selected_mesh_from_scene()
        if not sel_mesh:
            QtWidgets.QMessageBox.warning(self, "", "There is no mesh to paint on !")
            return
        if "|" in sel_mesh:
            QtWidgets.QMessageBox.warning(self, "Can't paint :(", "This object's name is not unique !")
            return

        self.setTargetMesh(sel_mesh)

    def createLineFromEdge(self):
        if getattr(self, "_is_paint_mode_active", False):
            self.stopPaintingSession()

        self._is_syncing_settings = True
        try:
            self.changeLineDefaultScale()
            self.changeLineSubdivOffset()
            self.changeLineResolution()
            self.changeCurvePoints()
            self.changeSweepShapeSlider(self.sweep_shape_slider.value())
            self.onSmoothableToggled(self.smoothable_checkbox.isChecked())
            self.onDisplacementToggled(self.displacement_checkbox.isChecked())
            self.onDispTypeChanged(self.disp_type_combo.currentIndex())
        finally:
            self._is_syncing_settings = False

        user_selection = cmds.ls(sl=True)
        if not user_selection:
            QtWidgets.QMessageBox.warning(self, "Can't create line :(", "Please select edges of the target mesh !")
            return

        sel_mesh = get_selected_mesh_from_scene()
        if sel_mesh and not paint_on_mesh:
            self.setTargetMesh(sel_mesh)

        if not paint_on_mesh or not cmds.objExists(paint_on_mesh):
            QtWidgets.QMessageBox.warning(self, "", "There is no mesh to paint on !")
            return

        if '.' in paint_on_mesh:
            QtWidgets.QMessageBox.warning(self, "Can't create line :(", "Please provide a valid target mesh, not a component !")
            return

        if paint_on_mesh not in user_selection[0]:
            QtWidgets.QMessageBox.warning(self, "Can't create line :(", "The line you selected is not on the target mesh !")
            return

        master_grp = get_or_create_master_group()
        line_id = get_next_line_id()
        line_name = f"line_{line_id}"

        cmds.select(user_selection, r=True)
        polytocurve_result = cmds.polyToCurve(form=3, degree=1)
        polytocurve_curve = polytocurve_result[0]
        polytocurve_node = polytocurve_result[1]
        cmds.delete(polytocurve_node)
        cmds.delete(polytocurve_curve, ch=True)

        cmds.select(cl=True)
        cmds.select(polytocurve_curve)

        mel.eval('performSweepMesh 0;')

        sweep_mesh_node = cmds.listConnections(polytocurve_curve + '.worldSpace[0]', d=True, s=False)[0]
        result_mesh = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)[0]

        setup_res = setupStrokeMeshAttributes(result_mesh, sweep_mesh_node, num_driver_points=curve_points, start_scale_value=line_default_scale, line_type="edge", sweep_shape=line_sweep_shape)
        profile_mult = setup_res[1] if isinstance(setup_res, (tuple, list)) else None

        smooth_node = None
        if line_smoothable:
            smooth_node = applySmoothToStrokeMesh(result_mesh, line_name=line_name)

        tex_def_node = None
        noise_node = None
        tex_handle_node = None
        has_disp = line_smoothable and (line_displacement or line_add_noise)
        if has_disp:
            tex_def_node, noise_node, tex_handle_node = applyDisplacementToStrokeMesh(result_mesh, line_name=line_name, disp_type=line_disp_type)

        cmds.setAttr(polytocurve_curve + '.v', 0)
        line_group = cmds.group(em=True, n=line_name)
        cmds.parent(result_mesh, line_group)
        cmds.parent(polytocurve_curve, line_group)
        if tex_handle_node and cmds.objExists(tex_handle_node):
            try:
                cmds.parent(tex_handle_node, line_group)
            except Exception:
                pass
        cmds.parent(line_group, master_grp)
        reset_pivots_to_origin(master_grp, line_group, result_mesh, polytocurve_curve)

        # Apply chosen follow method!
        follow_data = applyFollowMethod(
            follow_method=current_follow_method,
            curve_transform=polytocurve_curve,
            target_mesh=paint_on_mesh,
            line_id=line_id,
            line_group=line_group,
            subdiv_offset=line_subdiv_offset
        )

        mult_node = cmds.createNode('multDL', n=f"{line_name}_multDL", ss=True)
        cmds.setAttr(f"{mult_node}.input2", -1.0)
        cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1")
        cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState")
        if follow_data.get("wrap_node"):
            cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState")
        for fn in follow_data.get("follow_nodes", []):
            if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState")
                except Exception:
                    pass

        if smooth_node and cmds.objExists(smooth_node):
            smooth_node = cmds.rename(smooth_node, f"{line_name}_smooth")
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState")
                except Exception:
                    pass

        if tex_def_node and cmds.objExists(tex_def_node):
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{tex_def_node}.nodeState")
                except Exception:
                    pass

        if profile_mult and cmds.objExists(profile_mult):
            profile_mult = cmds.rename(profile_mult, f"{line_name}_profileY_mult")

        result_mesh = cmds.rename(result_mesh, f"{line_name}_msh")
        sweep_mesh_node = cmds.rename(sweep_mesh_node, f"{line_name}_sweep")
        converted_curve_shape = cmds.rename(polytocurve_curve, f"{line_name}_crv")
        reset_pivots_to_origin(master_grp, line_group, result_mesh, converted_curve_shape)

        line_data = {
            "name": line_name,
            "type": "edge",
            "follow_method": current_follow_method,
            "target_mesh": paint_on_mesh,
            "color": tuple(current_line_color),
            "group": line_group,
            "mesh": result_mesh,
            "curve": converted_curve_shape,
            "sweep_msh_node": sweep_mesh_node,
            "taper_ctrl_node": result_mesh,
            "wrap_node": follow_data.get("wrap_node"),
            "follow_nodes": follow_data.get("follow_nodes", []),
            "root_convert_grp": None,
            "converted_curve_grp": None,
            "smooth_node": smooth_node,
            "smoothable": bool(line_smoothable),
            "tex_def_node": tex_def_node,
            "noise_node": noise_node,
            "tex_handle": tex_handle_node,
            "displacement": bool(has_disp),
            "disp_type": line_disp_type,
            "add_noise": bool(has_disp),
            "profile_mult_node": profile_mult,
            "mult_dl_node": mult_node,
            "reverse_state_node": mult_node,
            "baked": False
        }

        global_scene_data_obj.addLineData(line_data)

        if active_preset_config:
            applyExtractedAttributes(result_mesh, line_data, active_preset_config)
        else:
            assignLineShader(result_mesh, color=current_line_color)

    def paintLineOnMesh(self, *args):
        if getattr(self, "_is_paint_mode_active", False):
            self.stopPaintingSession()
        else:
            self.startPaintingSession()

    def startPaintingSession(self):
        global paint_on_mesh

        # If a mesh is currently selected in Maya, auto-target it!
        sel_mesh = get_selected_mesh_from_scene()
        if sel_mesh:
            self.setTargetMesh(sel_mesh)
        elif not paint_on_mesh and self.set_target_mesh_lineedit.text().strip():
            typed = self.set_target_mesh_lineedit.text().strip()
            if cmds.objExists(typed):
                self.setTargetMesh(typed)

        if not paint_on_mesh or not cmds.objExists(paint_on_mesh):
            QtWidgets.QMessageBox.warning(self, "", "There is no mesh to paint on !")
            self.create_paint_line_button.setChecked(False)
            return

        cmds.select(paint_on_mesh, noExpand=True)
        mel.eval("MakePaintable")
        cmds.select(cl=True)  # Deselect target mesh so wireframe does not obscure it while painting
        mel.eval("PaintEffectsTool")

        try:
            cmds.dynWireCtx("paintMesh")
        except RuntimeError:
            pass

        cmds.setToolTo("paintMesh")

        self._is_syncing_settings = True
        try:
            self.syncMayaBrushSize()
            self.changeLineDefaultScale()
            self.changeLineSubdivOffset()
            self.changeLineResolution()
            self.changeCurvePoints()
            self.changeSmoothCurveSlider(self.smooth_curve_slider.value())
            self.changeSweepShapeSlider(self.sweep_shape_slider.value())
            self.onSmoothableToggled(self.smoothable_checkbox.isChecked())
            self.onDisplacementToggled(self.displacement_checkbox.isChecked())
            self.onDispTypeChanged(self.disp_type_combo.currentIndex())
        finally:
            self._is_syncing_settings = False

        self._is_paint_mode_active = True
        self.create_paint_line_button.setChecked(True)
        self.create_paint_line_button.setToolTip("Drawing mode active - Click to stop drawing (or press Q / W)")

        arm_stroke_listener()
        setup_tool_listener(self.onToolChanged)

    def stopPaintingSession(self, switch_tool=True):
        self._is_paint_mode_active = False
        self.create_paint_line_button.setChecked(False)
        self.create_paint_line_button.setToolTip("Click to draw line on target mesh")
        kill_stroke_listener()
        kill_tool_listener()
        if switch_tool:
            try:
                cmds.setToolTo("selectSuperContext")
            except Exception:
                pass

    def onToolChanged(self):
        if getattr(self, "_is_drawing_line", False):
            return
        try:
            curr_tool = cmds.currentCtx()
            if curr_tool and "paint" not in curr_tool.lower() and "dynwire" not in curr_tool.lower():
                if self._is_paint_mode_active:
                    self.stopPaintingSession(switch_tool=False)
        except Exception:
            pass

    def assignPreviewShader(self):
        shader = detectOrCreateShader(color=current_line_color)
        user_selection = cmds.ls(sl=True)

        if not user_selection and self.lines_list_widget.currentItem():
            item_data = self.lines_list_widget.currentItem().data(QtCore.Qt.UserRole)
            if item_data and "mesh" in item_data and cmds.objExists(item_data["mesh"]):
                cmds.select(item_data["mesh"], r=True)

        cmds.hyperShade(assign=shader)

    def bakeLinesClicked(self):
        if getattr(self, "_is_paint_mode_active", False):
            self.stopPaintingSession()

        reply = QtWidgets.QMessageBox.question(
            self, "Bake deformations",
            "This will bake the curve animation into vertex motion across the playback range\n"
            "and remove deformation setups (wrap/rivets/nodes) to save memory.\n\n"
            "Proceed with baking?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes
        )
        if reply == QtWidgets.QMessageBox.Yes:
            bakeAllLines()


class lineListDisplayWidget(QtWidgets.QWidget):
    delete_line_item = QtCore.Signal(QtWidgets.QWidget)

    def contextMenuEvent(self, event):
        parent_widget = self.parent()
        while parent_widget and not isinstance(parent_widget, QtWidgets.QListWidget):
            parent_widget = parent_widget.parent()
        if parent_widget:
            vp_pos = parent_widget.viewport().mapFromGlobal(event.globalPos())
            parent_widget.customContextMenuRequested.emit(vp_pos)
            event.accept()
        else:
            super().contextMenuEvent(event)

    def __init__(self, line_data: dict, list_item: QtWidgets.QListWidgetItem, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.line_data = line_data
        self.list_item = list_item

        self.main_layout = QtWidgets.QHBoxLayout()
        self.main_layout.setContentsMargins(4, 2, 4, 2)
        self.main_layout.setSpacing(6)
        self.setLayout(self.main_layout)

        self.line_name_widget = CoolNameDisplay(line_data)

        # Visibility comic checkbox
        current_line_grp_vis = True
        if self.line_data.get("group") and cmds.objExists(self.line_data["group"]):
            current_line_grp_vis = bool(cmds.getAttr(self.line_data["group"] + '.v'))

        self.disable_line_checkbox = ComicCheckBox(self)
        self.disable_line_checkbox.setChecked(current_line_grp_vis)

        # Delete comic trash button
        self.delete_button = ComicTrashButton(self)

        # Method badge
        method_str = self.line_data.get("follow_method", "Node based")
        if self.line_data.get("baked"):
            badge_text = "Baked"
        elif "Node" in method_str:
            badge_text = "Node"
        elif "Wrap" in method_str:
            badge_text = "Wrap"
        elif "UV" in method_str:
            badge_text = "UV"
        else:
            badge_text = method_str
        self.line_type_label = QtWidgets.QLabel(f'[{badge_text}]', self)
        self.line_type_label.setStyleSheet('font-size: 8pt; font-weight: bold; color: #777777;')

        self.main_layout.addWidget(self.line_name_widget)
        self.main_layout.addStretch()
        self.main_layout.addWidget(self.disable_line_checkbox)
        self.main_layout.addWidget(self.delete_button)
        self.main_layout.addWidget(self.line_type_label)

        self.line_name_widget.name_changed.connect(self.changeLineNameWrapper)
        self.disable_line_checkbox.stateChanged.connect(self.toggleLineVisibility)
        self.delete_button.clicked.connect(self.requestDelete)

    def changeLineNameWrapper(self, new_name: str):
        if new_name == self.line_data["name"]:
            return

        line_key = self.line_data["name"]
        self.line_data["name"] = new_name

        stroke_group = self.line_data.get("group")
        if stroke_group and cmds.objExists(stroke_group):
            stroke_group = cmds.rename(stroke_group, new_name)
        self.line_data["group"] = stroke_group

        old_mesh_name = self.line_data.get("mesh")
        result_mesh = old_mesh_name
        if result_mesh and cmds.objExists(result_mesh):
            result_mesh = cmds.rename(result_mesh, f"{new_name}_msh")

        sweep_mesh_node = self.line_data.get("sweep_msh_node")
        if sweep_mesh_node and cmds.objExists(sweep_mesh_node):
            sweep_mesh_node = cmds.rename(sweep_mesh_node, f"{new_name}_sweep")

        wrap_node = self.line_data.get("wrap_node")
        if wrap_node and cmds.objExists(wrap_node):
            wrap_node = cmds.rename(wrap_node, f"{new_name}_wrap")

        converted_curve_shape_node = self.line_data.get("curve")
        if converted_curve_shape_node and cmds.objExists(converted_curve_shape_node):
            converted_curve_shape_node = cmds.rename(converted_curve_shape_node, f"{new_name}_crv")

        taper_control_node = self.line_data.get("taper_ctrl_node")
        if taper_control_node and taper_control_node != old_mesh_name and cmds.objExists(taper_control_node):
            taper_control_node = cmds.rename(taper_control_node, f"edit_{new_name}")
        else:
            taper_control_node = result_mesh

        mult_node = self.line_data.get("mult_dl_node") or self.line_data.get("reverse_state_node")
        if mult_node and cmds.objExists(mult_node):
            mult_node = cmds.rename(mult_node, f"{new_name}_multDL")

        smooth_node = self.line_data.get("smooth_node")
        if smooth_node and cmds.objExists(smooth_node):
            smooth_node = cmds.rename(smooth_node, f"{new_name}_smooth")

        tex_def = self.line_data.get("tex_def_node")
        if tex_def and cmds.objExists(tex_def):
            tex_def = cmds.rename(tex_def, f"{new_name}_texDef")

        noise_node = self.line_data.get("noise_node")
        if noise_node and cmds.objExists(noise_node):
            node_type = cmds.nodeType(noise_node)
            suffix = f"_{node_type}" if node_type in ["noise", "mountain", "fractal"] else "_disp"
            noise_node = cmds.rename(noise_node, f"{new_name}{suffix}")

        tex_handle = self.line_data.get("tex_handle")
        if tex_handle and cmds.objExists(tex_handle):
            tex_handle = cmds.rename(tex_handle, f"{new_name}_texDefHandle")

        profile_mult = self.line_data.get("profile_mult_node")
        if profile_mult and cmds.objExists(profile_mult):
            profile_mult = cmds.rename(profile_mult, f"{new_name}_profileY_mult")

        new_data = dict(self.line_data)
        new_data.update({
            "name": new_name,
            "group": stroke_group,
            "mesh": result_mesh,
            "curve": converted_curve_shape_node,
            "sweep_msh_node": sweep_mesh_node,
            "taper_ctrl_node": taper_control_node,
            "wrap_node": wrap_node,
            "smooth_node": smooth_node,
            "tex_def_node": tex_def,
            "noise_node": noise_node,
            "tex_handle": tex_handle,
            "profile_mult_node": profile_mult,
            "mult_dl_node": mult_node,
            "reverse_state_node": mult_node,
        })

        if self.line_data.get("type") == "paint":
            root_converted = self.line_data.get("root_convert_grp")
            if root_converted and cmds.objExists(root_converted):
                root_converted = cmds.rename(root_converted, f"{new_name}_keep_grp")
            conv_grp = self.line_data.get("converted_curve_grp")
            if conv_grp and cmds.objExists(conv_grp):
                conv_grp = cmds.rename(conv_grp, f"{new_name}_crv_grp")

            new_data.update({
                "converted_curve_grp": conv_grp,
                "root_convert_grp": root_converted,
            })

        global_scene_data_obj.updateLineData(line_key, dict(new_data), update_name=True)

    def toggleLineVisibility(self):
        grp = self.line_data.get("group")
        if grp and cmds.objExists(grp):
            current_vis = cmds.getAttr(grp + '.v')
            cmds.setAttr(grp + '.v', (not current_vis))

    def requestDelete(self):
        self.list_item.listWidget().setCurrentItem(self.list_item)
        self.delete_line_item.emit(self)

def drawLine():
    global _is_drawing_line, paint_on_mesh
    if _is_drawing_line:
        return

    if not paint_on_mesh or not cmds.objExists(paint_on_mesh):
        sel_mesh = get_selected_mesh_from_scene()
        if sel_mesh:
            paint_on_mesh = sel_mesh
        elif global_main_widget and hasattr(global_main_widget, "set_target_mesh_lineedit"):
            txt = global_main_widget.set_target_mesh_lineedit.text().strip()
            if txt and cmds.objExists(txt):
                paint_on_mesh = txt

    sl = cmds.ls(sl=True) or []
    if not sl:
        if global_main_widget and getattr(global_main_widget, "_is_paint_mode_active", False):
            arm_stroke_listener()
        return

    shapes = cmds.listRelatives(sl, fullPath=False, shapes=True) or []
    stroke_shape = None
    for s in shapes:
        if cmds.objectType(s) == 'stroke':
            stroke_shape = s
            break

    if not stroke_shape:
        if global_main_widget and getattr(global_main_widget, "_is_paint_mode_active", False):
            arm_stroke_listener()
        return

    _is_drawing_line = True
    eff_smoothing = float(smooth_curve * 100.0)
    cmds.setAttr(stroke_shape + '.smoothing', eff_smoothing)

    was_symmetry = False
    try:
        was_symmetry = bool(cmds.symmetricModelling(q=True, symmetry=True))
        if was_symmetry:
            cmds.symmetricModelling(symmetry=False)
    except Exception:
        pass

    # Suspend viewport refresh and open single undo chunk for ultra-fast creation
    cmds.refresh(suspend=True)
    cmds.undoInfo(openChunk=True, chunkName="CartoonLineartDraw")
    try:
        mel.eval("PaintEffectsToCurve;")
        start_scale = line_default_scale

        converted_curve_transform = cmds.listConnections(stroke_shape + '.outMainCurves[0]', d=True, s=False)[0]
        converted_curve_shape = cmds.listRelatives(converted_curve_transform, s=True)[0]

        # Query spans amount to perform reduction based on user curve res & smooth_curve
        converted_curve_spans = cmds.getAttr(converted_curve_shape + '.s')
        eff_divisor = 1.0 + (float(line_resolution) - 1.0) * smooth_curve
        spans = max(1, int(round(converted_curve_spans / max(1.0, eff_divisor))))

        cmds.select(converted_curve_transform, noExpand=True)
        mel.eval(f'rebuildCurve -ch 0 -rpo 1 -rt 0 -end 1 -kr 0 -kcp 0 -kep 1 -kt 0 -s {spans} -d 1 -tol 0.0001;')

        # Only apply shrinkWrap if offset != 0.0 and subdiv preview active (avoids heavy multi-second mesh freeze)
        if line_subdiv_offset != 0.0 and paint_on_mesh and cmds.objExists(paint_on_mesh):
            target_shapes = cmds.listRelatives(paint_on_mesh, s=True, noIntermediate=True) or cmds.listRelatives(paint_on_mesh, s=True) or []
            if target_shapes:
                target_subdiv = cmds.getAttr(target_shapes[0] + '.displaySmoothMesh')
                if target_subdiv > 0:
                    shrinkWrapItem(target_msh=paint_on_mesh, wrapped_item=converted_curve_transform, target_subdiv_lvl=target_subdiv)

        # Delete construction history on converted_curve_transform to ensure clean curve geometry
        cmds.delete(converted_curve_transform, ch=True)

        cmds.select(converted_curve_transform, r=True, noExpand=True)
        mel.eval('performSweepMesh 0;')

        sweep_mesh_node = cmds.listConnections(converted_curve_transform + '.worldSpace[0]', d=True, s=False)[0]
        result_mesh = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)[0]

        master_grp = get_or_create_master_group()
        line_id = get_next_line_id()
        line_name = f"line_{line_id}"

        # Setup custom line parameters directly on the stroke mesh (lock/hide TRS + V)
        setup_res = setupStrokeMeshAttributes(result_mesh, sweep_mesh_node, num_driver_points=curve_points, start_scale_value=start_scale, line_type="paint", sweep_shape=line_sweep_shape)
        profile_mult = setup_res[1] if isinstance(setup_res, (tuple, list)) else None

        smooth_node = None
        if line_smoothable:
            smooth_node = applySmoothToStrokeMesh(result_mesh, line_name=line_name)

        tex_def_node = None
        noise_node = None
        tex_handle_node = None
        has_disp = line_smoothable and (line_displacement or line_add_noise)
        if has_disp:
            tex_def_node, noise_node, tex_handle_node = applyDisplacementToStrokeMesh(result_mesh, line_name=line_name, disp_type=line_disp_type)

        fg = cmds.listRelatives(converted_curve_transform, p=True)
        first_group = fg[0] if fg else converted_curve_transform
        rg = cmds.listRelatives(first_group, p=True) if fg else None
        root_converted_curve_group = rg[0] if rg else first_group

        stroke_tf = cmds.listRelatives(stroke_shape, p=True)
        stroke_transform = stroke_tf[0] if stroke_tf else stroke_shape
        if stroke_transform and cmds.objExists(stroke_transform):
            cmds.setAttr(stroke_transform + '.v', 0)
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != converted_curve_transform:
            cmds.setAttr(root_converted_curve_group + '.v', 0)

        line_group = cmds.group(em=True, n=line_name)
        cmds.parent(result_mesh, line_group)
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != line_group:
            try:
                cmds.parent(root_converted_curve_group, line_group)
            except Exception:
                pass
        if tex_handle_node and cmds.objExists(tex_handle_node):
            try:
                cmds.parent(tex_handle_node, line_group)
            except Exception:
                pass
        cmds.parent(line_group, master_grp)
        reset_pivots_to_origin(master_grp, line_group, result_mesh, converted_curve_transform, root_converted_curve_group, first_group)

        # Query connected brush node before deleting stroke
        brush_nodes = []
        try:
            if cmds.attributeQuery('brush', node=stroke_shape, exists=True):
                brush_nodes = cmds.listConnections(stroke_shape + '.brush', type='brush') or []
            if not brush_nodes:
                brush_nodes = cmds.listConnections(stroke_shape, type='brush') or []
        except Exception:
            pass
        brush_node = brush_nodes[0] if brush_nodes else None

        # Clean up temporary stroke transform and its brush asynchronously so Maya's Attribute Editor doesn't query a deleted node
        def _deferred_stroke_cleanup(tf_name, brush_names=None):
            if tf_name and cmds.objExists(tf_name):
                try:
                    cmds.delete(tf_name)
                except Exception:
                    pass
            if brush_names:
                for b in brush_names:
                    if b and b != "defaultBrush" and cmds.objExists(b):
                        try:
                            cmds.delete(b)
                        except Exception:
                            pass
            clean_orphaned_stroke_brushes()

        cmds.evalDeferred(lambda tf=stroke_transform, bn=brush_nodes: _deferred_stroke_cleanup(tf, bn))

        # Apply chosen follow method!
        follow_data = applyFollowMethod(
            follow_method=current_follow_method,
            curve_transform=converted_curve_transform,
            target_mesh=paint_on_mesh,
            line_id=line_id,
            line_group=line_group,
            subdiv_offset=line_subdiv_offset
        )

        mult_node = cmds.createNode('multDL', n=f"{line_name}_multDL", ss=True)
        cmds.setAttr(f"{mult_node}.input2", -1.0)
        cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1")
        cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState")
        if follow_data.get("wrap_node"):
            cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState")
        for fn in follow_data.get("follow_nodes", []):
            if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState")
                except Exception:
                    pass

        ccg = cmds.listRelatives(converted_curve_transform, p=True)
        converted_curve_grp = ccg[0] if ccg else first_group

        if smooth_node and cmds.objExists(smooth_node):
            smooth_node = cmds.rename(smooth_node, f"{line_name}_smooth")
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState")
                except Exception:
                    pass

        if tex_def_node and cmds.objExists(tex_def_node):
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{tex_def_node}.nodeState")
                except Exception:
                    pass

        if profile_mult and cmds.objExists(profile_mult):
            profile_mult = cmds.rename(profile_mult, f"{line_name}_profileY_mult")

        def _safe_rename(node_path, new_name):
            if not node_path:
                return None
            short = node_path.split("|")[-1]
            if cmds.objExists(short) and len(cmds.ls(short)) == 1:
                return cmds.rename(short, new_name)
            if cmds.objExists(node_path):
                return cmds.rename(node_path, new_name)
            matches = cmds.ls(f"*{short}")
            if matches and cmds.objExists(matches[0]):
                return cmds.rename(matches[0], new_name)
            return node_path

        result_mesh = _safe_rename(result_mesh, f"{line_name}_msh")
        sweep_mesh_node = _safe_rename(sweep_mesh_node, f"{line_name}_sweep")
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != line_group and root_converted_curve_group != converted_curve_transform:
            root_converted_curve_group = _safe_rename(root_converted_curve_group, f"{line_name}_keep_grp")
        converted_curve_transform = _safe_rename(converted_curve_transform, f"{line_name}_crv")
        if converted_curve_grp and cmds.objExists(converted_curve_grp) and converted_curve_grp != line_group and converted_curve_grp != root_converted_curve_group and converted_curve_grp != converted_curve_transform:
            converted_curve_grp = _safe_rename(converted_curve_grp, f"{line_name}_crv_grp")
        reset_pivots_to_origin(master_grp, line_group, result_mesh, converted_curve_transform, root_converted_curve_group, converted_curve_grp)

        line_data = {
            "name": line_name,
            "type": "paint",
            "follow_method": current_follow_method,
            "target_mesh": paint_on_mesh,
            "color": tuple(current_line_color),
            "group": line_group,
            "mesh": result_mesh,
            "curve": converted_curve_transform,
            "sweep_msh_node": sweep_mesh_node,
            "taper_ctrl_node": result_mesh,
            "brush_node": brush_node,
            "smooth_node": smooth_node,
            "smoothable": bool(line_smoothable),
            "tex_def_node": tex_def_node,
            "noise_node": noise_node,
            "tex_handle": tex_handle_node,
            "displacement": bool(has_disp),
            "disp_type": line_disp_type,
            "add_noise": bool(has_disp),
            "profile_mult_node": profile_mult,
            "wrap_node": follow_data.get("wrap_node"),
            "follow_nodes": follow_data.get("follow_nodes", []),
            "root_convert_grp": root_converted_curve_group,
            "converted_curve_grp": converted_curve_grp,
            "mult_dl_node": mult_node,
            "reverse_state_node": mult_node,
            "baked": False
        }

        # Fast direct shading engine assignment (no Hypershade / no selection overhead)
        if active_preset_config:
            applyExtractedAttributes(result_mesh, line_data, active_preset_config)
        else:
            assignLineShader(result_mesh, color=current_line_color)

        global_scene_data_obj.addLineData(line_data)

    finally:
        cmds.undoInfo(closeChunk=True)
        cmds.refresh(suspend=False)
        _is_drawing_line = False
        if was_symmetry:
            try:
                cmds.symmetricModelling(symmetry=True)
            except Exception:
                pass

    # Clear selection so created mesh is not selected
    if global_main_widget:
        global_main_widget._is_syncing_selection = True
    try:
        cmds.select(cl=True)
    finally:
        if global_main_widget:
            global_main_widget._is_syncing_selection = False

    # Continue painting session if active
    if global_main_widget and getattr(global_main_widget, "_is_paint_mode_active", False):
        try:
            if paint_on_mesh and cmds.objExists(paint_on_mesh):
                cmds.select(paint_on_mesh, noExpand=True)
                mel.eval("MakePaintable")
                cmds.select(cl=True)
            cmds.setToolTo("paintMesh")
        except Exception:
            pass
        arm_stroke_listener()
    else:
        try:
            cmds.setToolTo('moveSuperContext')
        except Exception:
            pass


def createTaperController(sweep_mesh_node, line_type="paint", paint_mode=False, num_driver_points=4, start_scale_value=1.0):
    """
    Deprecated: Kept for backwards-compatibility.
    Redirects attribute setup to the sweep mesh's output mesh directly.
    """
    mesh_conns = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)
    if mesh_conns:
        res = setupStrokeMeshAttributes(mesh_conns[0], sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=start_scale_value, line_type=line_type)
        return res[0] if isinstance(res, (tuple, list)) else res
    res = setupStrokeMeshAttributes(sweep_mesh_node, sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=start_scale_value, line_type=line_type)
    return res[0] if isinstance(res, (tuple, list)) else res


def shrinkWrapItem(target_msh, wrapped_item, target_subdiv_lvl=0, offset=None):
    if target_subdiv_lvl <= 0 or not target_msh or not cmds.objExists(target_msh):
        return

    shapes = cmds.listRelatives(target_msh, s=True, noIntermediate=True) or []
    if not shapes:
        shapes = cmds.listRelatives(target_msh, s=True) or []
    if not shapes:
        return
    target_msh_shape = shapes[0]

    shrinkwrap_deformer = cmds.deformer(wrapped_item, type='shrinkWrap')[0]

    cmds.connectAttr(target_msh_shape + '.boundaryRule', shrinkwrap_deformer + '.boundaryRule')
    cmds.connectAttr(target_msh_shape + '.continuity', shrinkwrap_deformer + '.continuity')
    cmds.connectAttr(target_msh_shape + '.keepBorder', shrinkwrap_deformer + '.keepBorder')
    cmds.connectAttr(target_msh_shape + '.keepHardEdge', shrinkwrap_deformer + '.keepHardEdge')
    cmds.connectAttr(target_msh_shape + '.keepMapBorders', shrinkwrap_deformer + '.keepMapBorders')
    cmds.connectAttr(target_msh_shape + '.smoothUVs', shrinkwrap_deformer + '.smoothUVs')
    cmds.connectAttr(target_msh_shape + '.worldMesh[0]', shrinkwrap_deformer + '.targetGeom')

    eff_offset = line_subdiv_offset if offset is None else float(offset)
    cmds.setAttr(shrinkwrap_deformer + '.prj', 4)
    cmds.setAttr(shrinkwrap_deformer + '.bi', 0)  # Unidirectional (prevents piercing through thin features to opposite side)
    cmds.setAttr(shrinkwrap_deformer + '.offset', eff_offset)
    cmds.setAttr(shrinkwrap_deformer + '.targetSmoothLevel', 3)

    cmds.select(wrapped_item, r=True, noExpand=True)
    mel.eval("DeleteHistory;")


def bakeAllLines():
    """
    Bakes the curve animation over the playback range so that the curve is no longer
    dynamically deformed by nodes/wrap/rivets, but has animated vertices (control points).
    This frees deformation computation and saves memory.
    """
    global_line_data = global_scene_data_obj.getGlobalLinesData()
    if not global_line_data:
        cmds.warning("No cartoon lines to bake.")
        return

    start_frame = int(cmds.playbackOptions(q=True, min=True))
    end_frame = int(cmds.playbackOptions(q=True, max=True))
    current_time = cmds.currentTime(q=True)

    target_keys = list(global_line_data.keys())

    # Maya Progress bar
    total_steps = max(1, (end_frame - start_frame + 1) * len(target_keys))
    progress_bar = None
    try:
        progress_bar = mel.eval('global string $gMainProgressBar; $tmp = $gMainProgressBar;')
        if progress_bar:
            cmds.progressBar(progress_bar, edit=True, beginProgress=True, isInterruptable=True,
                             status='Baking curve animations...', maxValue=total_steps)
    except Exception:
        pass

    try:
        for line_key in target_keys:
            line_data = dict(global_line_data[line_key])
            curve_transform = line_data.get("curve")
            if not curve_transform or not cmds.objExists(curve_transform):
                continue

            curve_shapes = cmds.listRelatives(curve_transform, s=True)
            if not curve_shapes:
                continue
            curve_shape = curve_shapes[0]
            num_cvs = len(cmds.ls(f"{curve_shape}.cv[*]", fl=True))

            # 1. Sample local positions across playback range
            anim_data = {i: [] for i in range(num_cvs)}
            for t in range(start_frame, end_frame + 1):
                cmds.currentTime(t, edit=True)
                for i in range(num_cvs):
                    pos = cmds.pointPosition(f"{curve_shape}.cv[{i}]", local=True)
                    anim_data[i].append((t, pos))
                if progress_bar:
                    cmds.progressBar(progress_bar, edit=True, step=1)

            # 2. Delete/disconnect deformation setup
            wrap_node = line_data.get("wrap_node")
            if wrap_node and cmds.objExists(wrap_node):
                cmds.delete(wrap_node)
                for s in cmds.listRelatives(curve_transform, s=True):
                    if 'Orig' in s:
                        cmds.delete(s)

            follow_nodes = line_data.get("follow_nodes", [])
            for fn in follow_nodes:
                if fn and cmds.objExists(fn):
                    try:
                        cmds.delete(fn)
                    except Exception:
                        pass

            # Ensure all control points connections are disconnected
            for i in range(num_cvs):
                conns = cmds.listConnections(f"{curve_shape}.controlPoints[{i}]", d=False, s=True, p=True)
                if conns:
                    for src in conns:
                        try:
                            cmds.disconnectAttr(src, f"{curve_shape}.controlPoints[{i}]")
                        except Exception:
                            pass

            # 3. Apply keyframes to controlPoints
            for i in range(num_cvs):
                for t, pos in anim_data[i]:
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].xValue", t=t, v=pos[0])
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].yValue", t=t, v=pos[1])
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].zValue", t=t, v=pos[2])

            line_data["baked"] = True
            line_data["wrap_node"] = None
            line_data["follow_nodes"] = []
            global_scene_data_obj.updateLineData(line_key, line_data)

    finally:
        cmds.currentTime(current_time, edit=True)
        if progress_bar:
            try:
                cmds.progressBar(progress_bar, edit=True, endProgress=True)
            except Exception:
                pass

    cmds.headsUpMessage("Bake completed! Curve animations are now vertex animations.", time=4)


def close_existing_ui():
    """
    Verifies if a Cartoon Lineart window already exists, and closes it cleanly.
    Handles global instance, Maya workspace controls, Qt top-level widgets, and Maya window children.
    """
    global main_window_instance, scene_event_catcher_num

    # 1. Close through global Python instance
    if main_window_instance is not None:
        try:
            main_window_instance.close()
            main_window_instance.deleteLater()
        except Exception:
            pass
        main_window_instance = None

    # 2. Close and delete Maya workspace controls / windows
    target_names = [
        "CartoonLineartWindow",
        "CartoonLineartWindowWorkspaceControl",
        "DockableWindowWorkspaceControl",
        "DockableWindow",
    ]
    for ctrl_name in target_names:
        try:
            if cmds.workspaceControl(ctrl_name, exists=True):
                cmds.workspaceControl(ctrl_name, edit=True, close=True)
                cmds.deleteUI(ctrl_name, control=True)
        except Exception:
            pass
        try:
            if cmds.window(ctrl_name, exists=True):
                cmds.deleteUI(ctrl_name, window=True)
        except Exception:
            pass

    # 3. Clean up through Qt top-level widgets
    try:
        app = QtWidgets.QApplication.instance()
        if app:
            maya_main = get_maya_main_window()
            for widget in app.topLevelWidgets():
                if maya_main and widget == maya_main:
                    continue
                w_title = widget.windowTitle() if hasattr(widget, "windowTitle") else ""
                w_obj = widget.objectName() if hasattr(widget, "objectName") else ""
                if w_title == "Cartoon Lineart" or w_obj in target_names:
                    try:
                        widget.close()
                        widget.deleteLater()
                    except Exception:
                        pass
    except Exception:
        pass

    # 4. Clean up through Maya main window children
    try:
        maya_main = get_maya_main_window()
        if maya_main:
            for child in maya_main.children():
                if isinstance(child, QtWidgets.QWidget):
                    w_title = child.windowTitle() if hasattr(child, "windowTitle") else ""
                    w_obj = child.objectName() if hasattr(child, "objectName") else ""
                    if w_title == "Cartoon Lineart" or w_obj in target_names:
                        try:
                            child.close()
                            child.deleteLater()
                        except Exception:
                            pass
    except Exception:
        pass

    # 5. Clean up any leftover scriptJob
    if scene_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=scene_event_catcher_num, force=True)
        except Exception:
            pass
        scene_event_catcher_num = None

    kill_selection_listener()
    clean_orphaned_stroke_brushes()


def launch_ui():
    global main_window_instance
    close_existing_ui()
    detectOrCreateShader()
    main_window_instance = DockableWindow()
    main_window_instance.show(dockable=True)
    return main_window_instance


if __name__ == '__main__':
    launch_ui()


def _get_active_shelf_layout():
    import maya.mel as mel
    try:
        top_shelf = mel.eval('$tmp = $gShelfTopLevel;')
        if top_shelf and cmds.tabLayout(top_shelf, exists=True):
            current_tab = cmds.tabLayout(top_shelf, query=True, selectTab=True)
            if current_tab:
                full_path = f"{top_shelf}|{current_tab}"
                if cmds.shelfLayout(full_path, exists=True):
                    return full_path
                return current_tab
    except Exception:
        pass

    try:
        if cmds.tabLayout("ShelfLayout", exists=True):
            current_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
            if current_tab:
                if cmds.shelfLayout(f"ShelfLayout|{current_tab}", exists=True):
                    return f"ShelfLayout|{current_tab}"
                return current_tab
    except Exception:
        pass

    try:
        all_shelves = cmds.lsUI(type="shelfLayout") or []
        for sh in all_shelves:
            if cmds.shelfLayout(sh, query=True, visible=True):
                return sh
        if all_shelves:
            return all_shelves[0]
    except Exception:
        pass

    return None


def onMayaDroppedPythonFile(*args):
    """
    Called automatically when dragging and dropping this file into Maya viewport.
    Creates/updates shelf button and opens Cartoon Lineart.
    """
    install_folder = None
    if args and len(args) > 0 and args[0]:
        p = Path(args[0])
        install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
    elif '__file__' in globals() and globals()['__file__']:
        p = Path(globals()['__file__'])
        install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
    else:
        try:
            p = Path(inspect.getfile(inspect.currentframe()))
            install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
        except Exception:
            install_folder = Path.cwd().resolve().as_posix()

    shelf_payload = (
        "import sys\n"
        f"install_dir = r'{install_folder}'\n"
        "if install_dir not in sys.path:\n"
        "    sys.path.insert(0, install_dir)\n"
        "import cartoon_lineart\n"
        "from importlib import reload\n"
        "reload(cartoon_lineart)\n"
        "cartoon_lineart.launch_ui()\n"
    )

    # Resolve button icon (button.png)
    icon_path = Path(install_folder) / "ico" / "button.png"
    if not icon_path.exists():
        icon_path = Path(install_folder) / "button.png"
    icon_file = icon_path.as_posix() if icon_path.exists() else "button.png"

    active_shelf = _get_active_shelf_layout()
    if active_shelf:
        try:
            children = cmds.shelfLayout(active_shelf, query=True, childArray=True) or []
            for child in children:
                if cmds.shelfButton(child, exists=True):
                    lbl = cmds.shelfButton(child, query=True, imageOverlayLabel=True) or ""
                    cmd = cmds.shelfButton(child, query=True, command=True) or ""
                    img = cmds.shelfButton(child, query=True, image1=True) or ""
                    if lbl in ("Lineart", "Cartoon Lineart", "Cool Lines") or "cartoon_lineart" in cmd or "button.png" in img:
                        cmds.deleteUI(child)
        except Exception:
            pass

        try:
            cmds.shelfButton(
                parent=active_shelf,
                imageOverlayLabel="",
                annotation="Launch Cartoon Lineart :)",
                image1=icon_file,
                command=shelf_payload,
                sourceType="python"
            )
            print(f"[Cartoon Lineart] Shelf button created on: {active_shelf}")
            cmds.headsUpMessage("Cartoon Lineart shelf button created!", time=3.0)
        except Exception as e:
            print(f"[Cartoon Lineart] Warning creating shelf button: {e}")

    launch_ui()
