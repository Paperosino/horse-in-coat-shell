//@ pragma AppId org.hics.Shell
//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io

// Deliberately independent of Config, extensions and the normal services graph.
ShellRoot {
 id: root
 property var data: ({})
 IpcHandler {
  target: "sessionControl"
  function transition(mode: string): bool {
   if (!["on", "resume"].includes(mode)) return false;
   Qt.exit(mode === "on" ? 75 : 76);
   return true;
  }
 }
 property list<string> helperCommand: ["python3", Quickshell.shellDir + "/../assets/shell_recovery.py"]
 property string error: ""
 property bool receivedReply: false
 property bool confirmation: false
 property real now: Date.now()
 readonly property int remaining: Math.max(0,Math.ceil(((data.pending?.deadline??0)*1000-now)/1000))
 Timer { interval:1000;repeat:true;running:!!root.data.pending?.token;onTriggered:{root.now=Date.now();if(root.remaining===0&&!worker.running)root.invoke("status");} }
 readonly property bool ru: Qt.locale().name.startsWith("ru")
 function tr(en, ruText) { return ru ? ruText : en; }
 function invoke(action) {
  if (worker.running) return;
  error = ""; receivedReply = false; worker.command = [...root.helperCommand, action]; worker.running = true;
 }
 Component.onCompleted: invoke("status")
 Process {
  id: worker
  stdout: StdioCollector { onStreamFinished: {
   if (!text.trim()) return;
   try {
    const value=JSON.parse(text);
    if (!value || typeof value!=="object" || Array.isArray(value)) throw new Error("Expected recovery object");
    root.receivedReply=true;
    if(value.error)root.error=String(value.error);else {root.now=Date.now();root.data=value;}
   } catch(e) {root.error=root.tr("Recovery service returned an invalid response.","Служба восстановления вернула некорректный ответ.");}
  } }
  stderr: StdioCollector { onStreamFinished: {if(text.trim())root.error=text.trim().slice(0,2048);} }
  onExited: (code,status) => {if(!root.error&&(code||status||!root.receivedReply))root.error=root.tr("Recovery operation failed. Check that the HICS package is installed completely.","Операция восстановления не выполнена. Проверьте полноту установки пакета HICS.");}

 }
 FloatingWindow {
  id: window
  visible: true
  title: "hics — " + root.tr("Safe mode", "Безопасный режим")
  implicitWidth: 840; implicitHeight: 650
  color: "#1c1b22"
  onVisibleChanged: if (!visible) Qt.callLater(() => window.visible = true)
  ScrollView {
   anchors.fill: parent; anchors.margins: 28
   contentWidth: availableWidth
   ColumnLayout {
    id: recoveryContent
    width: parent.width; spacing: 18
    Text { text:"hics";color:"#d0bcff";font.pixelSize:20;renderType:Text.QtRendering }
    Text { Layout.fillWidth:true;text:root.tr("Your desktop can recover", "Рабочий стол можно восстановить");color:"#e6e1e5";font.pixelSize:30;wrapMode:Text.WordWrap;renderType:Text.QtRendering }
    Text { Layout.fillWidth:true;text:root.tr("The shell is running with a minimal interface. Your applications and files are preserved. Extensions remain disabled until you enable them again.","Оболочка запущена с минимальным интерфейсом. Приложения и файлы сохранены. Расширения останутся отключены, пока вы не включите их снова.");color:"#cac4d0";font.pixelSize:16;wrapMode:Text.WordWrap;renderType:Text.QtRendering }
    Rectangle {
     Layout.fillWidth:true;implicitHeight:content.implicitHeight+36;radius:24;color:"#28252f";border.color:"#494451"
     ColumnLayout {
      id: content;anchors {left:parent.left;right:parent.right;top:parent.top;margins:18}
      spacing:14
      Text { Layout.fillWidth:true;text:root.tr("Working startup configuration", "Рабочая конфигурация запуска");font.pixelSize:20;color:"#e6e1e5";wrapMode:Text.WordWrap;renderType:Text.QtRendering }
      Text {Layout.fillWidth:true;text:root.data.startupCheckpoint?.available ? root.tr("A checkpoint is available. Restoring it changes only shell appearance and panel settings. Screen layouts, passwords and system settings are not changed.","Точка возврата доступна. Восстанавливаются только оформление оболочки и панели. Экраны, пароли и системные настройки не меняются.") : root.tr("No startup checkpoint is available yet. You can retry normal startup or inspect the configuration folder.","Точки возврата пока нет. Можно повторить обычный запуск или проверить папку конфигурации.");font.pixelSize:15;color:"#cac4d0";wrapMode:Text.WordWrap;renderType:Text.QtRendering}
      Button {
       implicitHeight:52
       objectName:"restoreStartup"
       Layout.fillWidth:true;enabled:!worker.running&&!!root.data.startupCheckpoint?.available&&!root.data.pending?.token
       text:root.confirmation?root.tr("Restore checkpoint", "Восстановить точку возврата"):root.tr("Review recovery", "Восстановление настроек")
       onClicked: {if(root.confirmation){root.confirmation=false;root.invoke("restore");}else root.confirmation=true;}
       background:Rectangle {radius:16;color:parent.enabled?"#d0bcff":"#494451"}
       contentItem:Text {text:parent.text;color:parent.enabled?"#251d35":"#e6e1e5";font.pixelSize:16;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;wrapMode:Text.WordWrap;renderType:Text.QtRendering}
      }
      Text {Layout.fillWidth:true;visible:!!root.data.pending?.token;text:root.tr("Trial: %1 seconds. Start the normal shell and confirm the appearance there, or the previous settings will return automatically.","Пробное восстановление: %1 с. Запустите обычную оболочку и подтвердите оформление в ней; без подтверждения прежние настройки вернутся автоматически.").arg(root.remaining);color:"#d0bcff";font.pixelSize:15;wrapMode:Text.WordWrap;renderType:Text.QtRendering}
     }
    }
    Button {
     implicitHeight:52
     objectName:"resumeStartup"
     Layout.fillWidth:true;enabled:!worker.running;text:root.tr("Try normal startup", "Попробовать обычный запуск");onClicked:root.invoke("resume")
     background:Rectangle {radius:16;color:parent.down?"#51475f":"#393240"}
     contentItem:Text {text:parent.text;color:"#e6e1e5";font.pixelSize:17;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;renderType:Text.QtRendering}
    }
    Button {
     implicitHeight:48
     Layout.fillWidth:true;enabled:!worker.running;text:root.tr("Refresh status", "Обновить состояние");onClicked:root.invoke("status")
     background:Rectangle {radius:16;color:parent.down?"#51475f":"#393240"}
     contentItem:Text {text:parent.text;color:"#e6e1e5";font.pixelSize:16;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;renderType:Text.QtRendering}
    }
    Text {Layout.fillWidth:true;visible:worker.running;text:root.tr("Working…", "Выполняется…");color:"#d0bcff";renderType:Text.QtRendering}
    Text {
     id: recoveryWarningText
     objectName: "recoveryWarning"
     Layout.fillWidth: true
     visible: !!root.data.recoveryWarning
     text: root.tr("Some settings could not be restored. Details:", "Часть настроек не удалось восстановить. Подробности:") + "\n" + (root.data.recoveryWarning || "")
     color: "#ffb4ab";font.pixelSize:15;wrapMode:Text.WordWrap;textFormat:Text.PlainText;renderType:Text.QtRendering
    }
    Text {Layout.fillWidth:true;visible:!!root.error;text:root.error;color:"#ffb4ab";wrapMode:Text.WordWrap;textFormat:Text.PlainText;renderType:Text.QtRendering}
   }
  }
 }
}
