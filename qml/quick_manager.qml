import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/*!
    快捷管理自动化（托盘快捷面板入口）

    与主程序其它窗口一致的 RinUI 窗口：列出全部自动化，
    每行右侧两个勾选框，分别控制「恢复」与「启用」，勾选立即保存。
    数据与保存都在 Python 侧的 QuickRuleBridge 里，QML 只负责显示。
*/
Window {
    id: root
    title: qsTr("快捷管理自动化")
    width: 520
    height: 640
    minimumWidth: 460
    minimumHeight: 420
    minimizeVisible: false
    maximizeVisible: false

    property var rules: []
    property string emptyText: "还没有自动化规则，先在「设置 → 自动化」里新建一条。"

    function reload() {
        var list = []
        try {
            list = JSON.parse(QuickRuleBridge.rulesJson() || "[]")
        } catch (e) {
            list = []
        }
        rules = list
    }

    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                typography: Typography.Subtitle
                text: qsTr("快捷管理自动化")
                Layout.fillWidth: true
            }
            Button {
                text: qsTr("刷新")
                onClicked: root.reload()
            }
            Button {
                text: qsTr("关闭")
                onClicked: root.close()
            }
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.72
            text: qsTr("勾选立即生效并保存：左边是「恢复」，右边是「启用」。")
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            visible: root.rules.length === 0
            opacity: 0.72
            text: root.emptyText
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: root.rules
            ScrollBar.vertical: ScrollBar { }

            delegate: SettingCard {
                width: ListView.view.width
                height: 76
                title: modelData.name || qsTr("未命名自动化")
                description: modelData.enabled ? qsTr("已启用") : qsTr("已停用")

                RowLayout {
                    spacing: 14

                    CheckBox {
                        text: qsTr("恢复")
                        checked: modelData.revert
                        onToggled: {
                            QuickRuleBridge.setRule(modelData.uid, !!modelData.enabled, checked)
                            root.reload()
                        }
                    }
                    CheckBox {
                        text: qsTr("启用")
                        checked: modelData.enabled
                        onToggled: {
                            QuickRuleBridge.setRule(modelData.uid, checked, !!modelData.revert)
                            root.reload()
                        }
                    }
                }
            }
        }
    }
}