"""Qt client for the same translated-camera input regression as the GTK fixture."""
import os
import sys
from PySide6.QtCore import QEvent, QMimeData, Qt
from PySide6.QtGui import QColor, QDrag, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget


class ColourPanel(QWidget):
    def __init__(self, colour):
        super().__init__()
        self.colour = QColor(colour)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.colour)
        painter.end()


class Source(ColourPanel):
    def __init__(self):
        super().__init__("#00ee00")

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            print("MIDDLE_PRESSED", flush=True)
        self.origin = event.position().toPoint()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            print("MIDDLE_RELEASED", flush=True)
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "origin"):
            if (event.position().toPoint() - self.origin).manhattanLength() >= QApplication.startDragDistance():
                del self.origin
                print("PREPARE", flush=True)
                data = QMimeData()
                data.setText("hyprstack-test")
                drag = QDrag(self)
                drag.setMimeData(data)
                drag.exec(Qt.CopyAction)
        event.accept()


class Target(ColourPanel):
    def __init__(self):
        super().__init__("#ee0000")
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        print("DROP", event.mimeData().text(), round(event.position().x()), round(event.position().y()), flush=True)
        event.acceptProposedAction()


class Window(QWidget):
    def eventFilter(self, receiver, event):
        if event.type() == QEvent.MouseMove and isinstance(receiver, QWidget) and receiver.window() == self:
            local = receiver.mapTo(self, event.position().toPoint())
            print("MOTION", local.x(), local.y(), self.width(), self.height(), flush=True)
        return False


app = QApplication.instance() or QApplication(sys.argv)
window = Window()
window.setWindowTitle("Canvas Qt input regression")
window.resize(640, 400)
row = QHBoxLayout(window)
row.setContentsMargins(0, 0, 0, 0)
row.setSpacing(0)
source, target = Source(), Target()
for child in (source, target):
    child.setMouseTracking(True)
    row.addWidget(child, 1)
window.setMouseTracking(True)
app.installEventFilter(window)
if os.environ.get("HYPRSTACK_HIDE_CURSOR"):
    window.setCursor(Qt.BlankCursor)
window.show()
sys.exit(app.exec())
