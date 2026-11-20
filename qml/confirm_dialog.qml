import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window as QQW
import RinUI

/*!
    确认 / 取消弹窗（RinUI，多按钮版）

    外观照搬主程序「重复打开 CW2」时那个提示窗：全屏透明 + 居中 RinUI Dialog
    （信息图标 + 说明 + 底部整宽按钮），多一行「N 秒后自动按「…」」的会话倒计时。
    每个按钮可单独设背景色 / 文字色，留空就用主题色。
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
    property string buttonsJson: "[]"
    property var buttons: []
    property int timeoutSeconds: 0
    property int timeoutIndex: -1
    property int remain: 0
    property bool settled: false

    property int showNonce: 0
    property int forceNonce: 0
    property int forceIndex: -1

    function showDialog() {
        settled = false
        remain = Math.max(0, timeoutSeconds)
        try {
            buttons = JSON.parse(buttonsJson || "[]")
        } catch (e) {
            buttons = []
        }
        if (!buttons || buttons.length === 0)
            buttons = [{ "text": qsTr("确认"), "jump": -1, "bg": "", "fg": "" }]
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

    function finish(index) {
        if (settled)
            return
        settled = true
        countdownTimer.stop()
        dlg.close()
        root.hide()
        ConfirmBridge.result(index)
    }

    function timeoutText() {
        if (timeoutSeconds <= 0)
            return qsTr("不会自动关闭")
        var name = ""
        if (timeoutIndex >= 0 && timeoutIndex < buttons.length)
            name = buttons[timeoutIndex].text || ""
        if (!name)
            return qsTr("%1 秒后自动关闭").arg(Math.max(0, remain))
        return qsTr("%1 秒后自动按「%2」").arg(Math.max(0, remain)).arg(name)
    }

    onShowNonceChanged: if (showNonce > 0) showDialog()
    onForceNonceChanged: if (forceNonce > 0) finish(forceIndex)

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.remain -= 1
            if (root.remain <= 0)
                root.finish(root.timeoutIndex >= 0 ? root.timeoutIndex : -1)
        }
    }

    // 键盘：Esc = 关掉（-1），Enter = 第一个按钮
    Item {
        anchors.fill: parent
        focus: true
        Keys.onEscapePressed: root.finish(-1)
        Keys.onReturnPressed: root.finish(0)
        Keys.onEnterPressed: root.finish(0)
    }

    Dialog {
        id: dlg
        width: Math.min(Screen.width * 0.36, 560)
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
                text: root.timeoutText()
            }
        }

        footer: RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: root.buttons

                delegate: Button {
                    Layout.fillWidth: true
                    text: modelData.text || qsTr("按钮")
                    onClicked: root.finish(index)

                    background: Rectangle {
                        radius: Theme.currentTheme.appearance.buttonRadius
                        color: {
                            var custom = modelData.bg || ""
                            if (custom.length)
                                return custom
                            return index === 0
                                ? Theme.currentTheme.colors.primaryColor
                                : Theme.currentTheme.colors.controlFillColor
                        }
                        border.width: 1
                        border.color: Theme.currentTheme.colors.controlBorderColor
                    }

                    contentItem: Text {
                        text: modelData.text || qsTr("按钮")
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        color: {
                            var custom = modelData.fg || ""
                            if (custom.length)
                                return custom
                            return index === 0
                                ? Theme.currentTheme.colors.textOnAccentColor
                                : Theme.currentTheme.colors.textColor
                        }
                    }
                }
            }
        }
    }
}
