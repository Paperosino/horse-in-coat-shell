"""Qt Quick scrolling, including XWayland and custom WheelHandler consumers."""
import os
import sys
from PySide6.QtCore import QUrl, QObject, QEvent, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
app = QGuiApplication(sys.argv)
class Observer(QObject):
    def eventFilter(self, receiver, event):
        if event.type() == QEvent.MouseMove:
            print("MOTION",event.position().x(),event.position().y(),event.globalPosition().x(),event.globalPosition().y(),flush=True)
        if event.type() == QEvent.Wheel:
            print("WHEEL", event.angleDelta().y(), event.pixelDelta().y(), flush=True)
        return False
observer = Observer()
app.installEventFilter(observer)
engine = QQmlApplicationEngine()
engine.loadData(b'''import QtQuick
import QtQuick.Controls
ApplicationWindow {
 visible:true; width:600; height:500; title:"Canvas scroll fixture"
 Flickable {
  id:view; objectName:"scrollView"; anchors.fill:parent; contentHeight:3000
  onContentYChanged:console.log("SCROLLED",contentY)
  Column {
   width:parent.width
   Repeater {model:60; Rectangle {required property int index; width:600;height:50;color:index%2?"#ee0022":"#0044dd"}}
  }
  WheelHandler {
   target:null
   onWheel:event=>{console.log("WHEEL",event.angleDelta.y,event.pixelDelta.y);view.contentY=Math.max(0,view.contentY+60)}
  }
 }
}''', QUrl('file:///canvas-scroll-fixture.qml'))
if not engine.rootObjects(): sys.exit(1)
root = engine.rootObjects()[0]
view = root.findChild(QQuickItem, "scrollView")
last = [view.property("contentY")]
def report():
    value = view.property("contentY")
    if value != last[0]:
        print("SCROLLED", value, flush=True)
        last[0] = value
timer = QTimer()
timer.timeout.connect(report)
timer.start(50)
print("STARTED", os.environ.get("QT_QPA_PLATFORM"), flush=True)
sys.exit(app.exec())
