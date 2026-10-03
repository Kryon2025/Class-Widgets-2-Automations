import QtQuick
import QtQuick.Layouts
import RinUI
import ClassWidgets.Theme

// 自动化小组件
//   展示态：仅在有自动化正在执行时出现（执行结束后保留 EXEC_LINGER 秒便于看清）
//   编辑态：始终显示，否则在布局里找不到它
//   左侧空心圆环 = 执行进度；右侧第一行是自动化名，第二行是模块 + 行动步骤（从右至左轮播）
// backend / settings 由 WidgetLoader 注入；editMode 继承自 BaseWidget
Widget {
    id: root
    text: qsTr("自动化")

    property var stats: ({ "total": 0, "enabled": 0, "active": 0, "exec": null })

    readonly property var ex: (stats && stats.exec && stats.exec.name) ? stats.exec : null
    readonly property int stepIndex: ex ? (ex.index || 0) : 0
    readonly property int stepTotal: ex ? (ex.total || 0) : 0

    visible: editMode || root.ex !== null

    // 行动类型 → 简短说明
    function stepLabel(s) {
        if (!s)
            return ""
        var t = s.type
        var p1 = s.p1 === undefined || s.p1 === null ? "" : String(s.p1)
        var p2 = s.p2 === undefined || s.p2 === null ? "" : String(s.p2)
        switch (t) {
        case "run": return p1
        case "notify": return p1
        case "wait": return qsTr("等待 %1 秒").arg(p1 || "0")
        case "broadcast": return qsTr("广播 %1").arg(p1)
        case "set_flag": return qsTr("设标志 %1").arg(p1)
        case "set_config": return qsTr("设置 %1").arg(p1)
        case "lock": return qsTr("锁定 %1").arg(p1)
        case "restart": return qsTr("重启主程序")
        case "app": return (p2)
        case "open_settings": return qsTr("打开系统设置")
        case "set_theme": return qsTr("切换主题")
        case "power": return qsTr("电源 %1").arg(p1)
        case "volume": return qsTr("音量 %1").arg(p1)
        case "media": return qsTr("媒体 %1").arg(p1)
        case "sys_notify": return qsTr("发通知 %1").arg(p1)
        case "rollcall_roll": return qsTr("点名 %1 人").arg(p1 || "1")
        case "rollcall_set": return qsTr("设置点名 %1").arg(p1)
        case "rollcall_close": return qsTr("关闭点名窗口")
        default: return t ? String(t) : ""
        }
    }

    readonly property string stepText: {
        if (!root.ex || !root.ex.steps)
            return ""
        var cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        var out = []
        for (var i = 0; i < root.ex.steps.length; i++)
            out.push(qsTr("步骤%1：%2").arg(cn[i] || (i + 1)).arg(root.stepLabel(root.ex.steps[i])))
        return out.join("　")
    }

    function refresh() {
        if (!backend || !backend.statusJson)
            return
        try {
            root.stats = JSON.parse(backend.statusJson() || "{}")
        } catch (e) {
            // 引擎未就绪时保持上一次的值
        }
    }

    Component.onCompleted: refresh()

    Timer {
        interval: 250
        repeat: true
        running: true
        onTriggered: root.refresh()
    }

    RowLayout {
        anchors.centerIn: parent
        spacing: miniMode ? 8 : 12

        ProgressRing {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            Layout.alignment: Qt.AlignVCenter
            strokeWidth: 3
            backgroundColor: Qt.rgba(0.5, 0.5, 0.5, 0.22)
            primaryColor: "#2eaa76"
            // 执行中显示进度；空闲（编辑态预览）为满环
            value: root.stepTotal > 0 ? Math.min(1, root.stepIndex / root.stepTotal) : 1
        }

        ColumnLayout {
            spacing: 0
            Layout.alignment: Qt.AlignVCenter

            Title {
                text: root.ex ? root.ex.name : qsTr("自动化")
            }

            RowLayout {
                spacing: 6

                // 小字：当前执行到的模块
                Text {
                    opacity: 0.65
                    font.pixelSize: miniMode ? 9 : 11
                    text: qsTr("行动")
                }

                // 模块右侧：行动步骤，从右至左轮播
                MarqueeTitle {
                    Layout.preferredWidth: miniMode ? 140 : 220
                    font.pixelSize: miniMode ? 9 : 11
                    opacity: 0.85
                    text: root.stepText.length > 0 ? root.stepText : qsTr("无行动步骤")
                }
            }
        }
    }
}
