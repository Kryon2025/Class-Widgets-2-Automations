import QtQuick
import QtQuick.Layouts
import RinUI
import ClassWidgets.Theme

// 自动化小组件
//   展示态：仅在有自动化正在执行时出现（执行结束后保留 EXEC_LINGER 秒便于看清）
//   编辑态：始终显示，否则在布局里找不到它
//   backend / settings 由 WidgetLoader 注入；editMode 继承自 BaseWidget
//
// 注：行动步骤的逐步展示（轮播）暂时去掉，后期再做。
//     引擎侧的 exec.steps / exec.index 仍在提供，接回来时直接用即可。
Widget {
    id: root
    text: qsTr("自动化")

    property var stats: ({ "total": 0, "enabled": 0, "active": 0, "exec": null })

    readonly property var ex: (stats && stats.exec && stats.exec.name) ? stats.exec : null
    readonly property int stepIndex: ex ? (ex.index || 0) : 0
    readonly property int stepTotal: ex ? (ex.total || 0) : 0

    visible: editMode || root.ex !== null

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

            Text {
                visible: root.ex !== null && root.stepTotal > 0
                opacity: 0.7
                font.pixelSize: miniMode ? 9 : 11
                text: qsTr("执行中 %1/%2").arg(root.stepIndex).arg(root.stepTotal)
            }
        }
    }
}
