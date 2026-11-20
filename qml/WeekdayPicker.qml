import QtQuick
import QtQuick.Layouts
import RinUI

/*!
    星期选择：七个 RinUI PillButton（一 ~ 日）。

    写进触发器的字段（默认 p2）：
      - 七天全选 → 留空（引擎里「留空 = 每天」）
      - 全都不选 → "0"（永不触发）
      - 其余 → "1,3,5" 这种逗号列表

    PillButton 自带选中态（checked），点击既切换又写回，不需要额外状态管理。
*/
RowLayout {
    id: weekRoot
    spacing: 4

    property var it: null
    property bool loading: false
    // 写入触发器的哪个字段：定时 / 闹钟 / 时间段触发器都用默认 p2（时间段触发器传 p3）
    property string field: "p2"

    readonly property var dayNames: ["一", "二", "三", "四", "五", "六", "日"]

    function load(item) {
        it = item
        loading = true
        var spec = String((item && item[weekRoot.field]) || "").trim()
        var picked = spec ? spec.split(/[,，、\s]+/) : []
        for (var i = 0; i < 7; i++) {
            var btn = weekRep.itemAt(i)
            if (btn) btn.checked = spec ? (picked.indexOf(String(i + 1)) >= 0) : true
        }
        loading = false
    }

    function save() {
        if (loading || !it) return
        var picked = []
        for (var i = 0; i < 7; i++) {
            var btn = weekRep.itemAt(i)
            if (btn && btn.checked) picked.push(String(i + 1))
        }
        if (picked.length === 7) it[weekRoot.field] = ""            // 全选 = 每天
        else if (picked.length === 0) it[weekRoot.field] = "0"      // 全不选 = 不触发
        else it[weekRoot.field] = picked.join(",")
    }

    Repeater {
        id: weekRep
        model: 7
        delegate: PillButton {
            text: weekRoot.dayNames[index]
            onClicked: weekRoot.save()
        }
    }
}
