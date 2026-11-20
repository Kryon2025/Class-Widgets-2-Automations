import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window as QQW
import RinUI

/*!
    确认 / 取消弹窗（RinUI）

    外观照搬主程序「重复打开 CW2」时弹的那个提示窗：
    全屏透明窗口 + 居中的 RinUI Dialog（图标 + 说明 + 底部两个整宽按钮）。
    额外加了一行「N 秒后自动…」的会话倒计时，能直接看出弹窗还剩多久消失。
*/
QQW.Window {
    id: root
    visible: false
    width: Screen.width
    height: Screen.height
    color: "transparent"
    flags: Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.WA_TranslucentBackground

    property string headline: ""
    property string bodyText: ""
    property string okText: "确认"
    property string cancelText: "取消"
    property int timeoutSeconds: 0
    property bool timeoutOk: true
    property int remain: 0
    property bool settled: false
    // Python 侧通过改这两个属性来驱动 QML（直接调 QML 函数在不同版本里不稳）
    property int showNonce: 0
    property int forceNonce: 0
    property bool forceOk: false

    function showDialog() {
        settled = false
        remain = Math.max(0, timeoutSeconds)
        dlg.title = headline.length ? headline : qsTr("自动化确认")
        dlg.open()
        root.show()
        root.raise()
        root.requestActivate()
        if (remain > 0)
            countdownTimer.start()
        else
            countdownTimer.stop()
    }

    function finish(ok) {
        if (settled)
            return
        settled = true
        countdownTimer.stop()
        dlg.close()
        root.hide()
        ConfirmBridge.result(ok)
    }

    onShowNonceChanged: if (showNonce > 0) showDialog()
    onForceNonceChanged: if (forceNonce > 0) finish(forceOk)

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.remain -= 1
            if (root.remain <= 0)
                root.finish(root.timeoutOk)
        }
    }

    // 键盘：Esc = 取消，Enter = 确认
    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: root.finish(false)
        Keys.onReturnPressed: root.finish(true)
        Keys.onEnterPressed: root.finish(true)
    }

    Dialog {
        id: dlg
        width: Math.min(Screen.width * 0.34, 520)
        modal: true
        closePolicy: Popup.NoAutoClose

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Icon {
                    Layout.alignment: Qt.AlignTop
                    size: 42
                    source: ConfirmIconPath
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: root.bodyText
                }
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                opacity: 0.72
                text: root.timeoutSeconds > 0
                    ? qsTr("%1 秒后自动「%2」").arg(Math.max(0, root.remain))
                          .arg(root.timeoutOk ? qsTr("确认") : qsTr("取消"))
                    : qsTr("不会自动关闭")
            }
        }

        footer: DialogButtonBox {
            Layout.fillWidth: true

            Button {
                Layout.preferredWidth: parent.width * 0.5
                text: root.cancelText.length ? root.cancelText : qsTr("取消")
                onClicked: root.finish(false)
            }

            Button {
                Layout.preferredWidth: parent.width * 0.5
                text: root.okText.length ? root.okText : qsTr("确认")
                highlighted: true
                onClicked: root.finish(true)
            }
        }
    }
}
