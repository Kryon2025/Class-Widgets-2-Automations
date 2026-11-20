import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/*!
    窗口规则调试（RinUI 窗口）

    实时显示当前前台窗口的句柄 / 类名 / 标题 / 状态 / 进程名 / 进程权限。
    「暂停获取」是开关（PillButton），会把数值冻住；
    「复制」「导出…」是一次性动作，用普通 Button。
*/
Window {
    id: root
    title: qsTr("窗口规则调试")
    width: 520
    height: Math.max(360, column.implicitHeight + titleBarHeight + 20)
    minimumWidth: 460
    minimizeVisible: false
    maximizeVisible: false
    // 与 RinUI Window 默认值一致，额外加置顶（不能用 Python 动态改 flags，会被 Qt 重建窗口、出现系统白边）
    flags: Qt.Window
        | Qt.WindowMinimizeButtonHint
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowCloseButtonHint
        | Qt.WindowStaysOnTopHint

    property var info: ({})
    property string toast: ""
    // 给 Python 侧用于自动定高（也方便测试断言）
    readonly property real contentHeight: column ? column.implicitHeight : 0
    readonly property real frameHeight: rowsLayout ? rowsLayout.implicitHeight : 0

    readonly property var rows: [
        { key: "title", label: qsTr("窗口标题"), copy: true },
        { key: "process", label: qsTr("进程名"), copy: true },
        { key: "cls", label: qsTr("窗口类名"), copy: false },
        { key: "pid", label: qsTr("进程 PID"), copy: false },
        { key: "state", label: qsTr("窗口状态"), copy: false },
        { key: "elevation", label: qsTr("进程权限"), copy: false },
        { key: "handle", label: qsTr("窗口句柄"), copy: false }
    ]

    function refreshInfo() {
        try {
            info = JSON.parse(WindowDebuggerBridge.infoJson() || "{}")
        } catch (e) {
            info = {}
        }
    }

    function valueOf(key) {
        var v = info[key]
        return (v === undefined || v === null || v === "") ? "—" : String(v)
    }

    function say(msg) {
        if (!msg) return
        toast = msg
        toastTimer.restart()
    }

    Component.onCompleted: refreshInfo()

    Connections {
        target: WindowDebuggerBridge
        function onInfoChanged() { root.refreshInfo() }
    }

    Timer {
        id: toastTimer
        interval: 3200
        onTriggered: root.toast = ""
    }

    ColumnLayout {
        id: column
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                typography: Typography.BodyStrong
                text: qsTr("窗口规则调试")
                Layout.fillWidth: true
            }
            PillButton {
                id: pauseBtn
                text: qsTr("暂停获取")
                onClicked: {
                    WindowDebuggerBridge.setPaused(checked)
                    text = checked ? qsTr("继续获取") : qsTr("暂停获取")
                    root.say(checked ? "已暂停：数值已冻结，可以放心复制"
                                     : "已继续获取")
                }
            }
            Button {
                text: qsTr("导出…")
                implicitHeight: 32
                onClicked: root.say(WindowDebuggerBridge.exportToFile())
            }
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.72
            font.pixelSize: 13
            text: qsTr("点击你要查询的窗口，这里就会显示它的信息。复制前先点「暂停获取」，数值就不会再变了。")
        }

        Frame {
            Layout.fillWidth: true
            // 让窗口高度跟着内容走：Frame 内部是“锚定”的 ColumnLayout，
            // 直接取它的 implicitHeight 才能算准（否则会算成 0 / 被裁剪）
            Layout.preferredHeight: rowsLayout.implicitHeight + 24
            radius: 10

            ColumnLayout {
                id: rowsLayout
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Repeater {
                    model: root.rows

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: modelData.label + "："
                            Layout.preferredWidth: 72
                            Layout.alignment: Qt.AlignTop
                            opacity: 0.72
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: root.valueOf(modelData.key)
                        }
                        Button {
                            text: qsTr("复制")
                            visible: modelData.copy
                            implicitHeight: 28
                            implicitWidth: 56
                            onClicked: root.say(WindowDebuggerBridge.copyField(modelData.key))
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.6
            font.pixelSize: 12
            text: qsTr("进程权限靠打开目标进程的令牌（TokenElevation）判断：普通权限读不到管理员进程的令牌时，会显示「未知（无权限读取令牌）」。")
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: root.toast
            visible: root.toast !== ""
            color: Theme.currentTheme.colors.primaryColor
        }

        Item { Layout.fillHeight: true }
    }
}
