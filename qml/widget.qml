import QtQuick
import QtQuick.Layouts
import RinUI
import ClassWidgets.Theme

// 自动化小组件：**仅当有自动化正在执行时才显示**。
// 左侧是空心圆环（进度 = 运行中 / 已启用），右侧是名称与条数。
// 由 WidgetLoader 注入 backend / settings（见 WidgetLoader.qml）
Widget {
    id: root
    text: qsTr("自动化")

    property var stats: ({ "total": 0, "enabled": 0, "active": 0 })

    readonly property int totalCount: stats.total || 0
    readonly property int enabledCount: stats.enabled || 0
    readonly property int activeCount: stats.active || 0

    // 没有任何自动化在执行时，整个小组件不出现
    visible: root.activeCount > 0

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
        interval: 1000
        repeat: true
        running: true
        onTriggered: root.refresh()
    }

    RowLayout {
        anchors.centerIn: parent
        spacing: miniMode ? 8 : 12

        // 空心圆环：轨道 + 进度弧，形如事件倒计时那条进度条卷成的环
        ProgressRing {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            Layout.alignment: Qt.AlignVCenter
            value: root.enabledCount > 0 ? (root.activeCount / root.enabledCount) : 0
            strokeWidth: 3
            backgroundColor: Qt.rgba(0.5, 0.5, 0.5, 0.22)
            primaryColor: "#2eaa76"
        }

        ColumnLayout {
            spacing: 0
            Layout.alignment: Qt.AlignVCenter

            Title {
                text: qsTr("自动化")
            }

            Text {
                opacity: 0.75
                font.pixelSize: miniMode ? 10 : 12
                text: qsTr("%1 / %2 运行中").arg(root.activeCount).arg(root.enabledCount)
            }
        }
    }
}
