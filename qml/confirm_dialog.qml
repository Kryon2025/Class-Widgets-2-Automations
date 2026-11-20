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

        // 按钮放回 Dialog 的 footer（DialogButtonBox 负责官方内边距 / 间距）
        footer: DialogButtonBox {
            Layout.fillWidth: true

            Repeater {
                model: root.buttons

                delegate: Button {
                    id: btn
                    Layout.fillWidth: true
                    text: modelData.text || qsTr("按钮")

                    readonly property string customBg: modelData.bg || ""
                    readonly property string customFg: modelData.fg || ""

                    // 官方 Button 的外观全部保留，只把「强调色」换成用户选的颜色
                    highlighted: index === 0 || customBg.length > 0
                    primaryColor: customBg.length > 0
                        ? customBg
                        : Theme.currentTheme.colors.primaryColor

                    // 官方 contentItem 是「图标 + 文字」的 Row；这里没有图标，复制同样的排版
                    contentItem: Item {
                        clip: true
                        anchors.fill: parent

                        Text {
                            anchors.fill: parent
                            anchors.margins: 8
                            typography: Typography.Body
                            text: btn.text
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            color: btn.customFg.length > 0
                                ? btn.customFg
                                : (btn.highlighted
                                    ? Theme.currentTheme.colors.textOnAccentColor
                                    : Theme.currentTheme.colors.textColor)
                        }
                    }

                    onClicked: root.finish(index)
                }
            }
        }

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

    }
}
