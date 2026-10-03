import QtQuick
import QtQuick.Layouts
import RinUI
import ClassWidgets.Theme

// 自动化小组件：左上角状态点 + 名称 + 「运行中 / 已启用」
// 由 WidgetLoader 注入 backend / settings（见 WidgetLoader.qml）
Widget {
    id: root
    text: qsTr("自动化")

    property var stats: ({ "total": 0, "enabled": 0, "active": 0 })

    readonly property int totalCount: stats.total || 0
    readonly property int enabledCount: stats.enabled || 0
    readonly property int activeCount: stats.active || 0

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

        Rectangle {
            Layout.preferredWidth: 10
            Layout.preferredHeight: 10
            Layout.alignment: Qt.AlignVCenter
            radius: 5
            color: root.activeCount > 0 ? "#43a047"
                 : (root.enabledCount > 0 ? "#1e88e5" : "#e53935")
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
                text: {
                    if (root.totalCount === 0)
                        return qsTr("未配置自动化")
                    return qsTr("%1 / %2 运行中").arg(root.activeCount).arg(root.enabledCount)
                }
            }
        }
    }
}
