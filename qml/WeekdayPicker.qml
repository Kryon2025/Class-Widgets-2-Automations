import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/*!
    星期选择：七个复选框（一 ~ 日）。

    写进触发器的 p2：
      - 七天全选 → 留空（引擎里「留空 = 每天」）
      - 全都不选 → "0"（永不触发）
      - 其余 → "1,3,5" 这种逗号列表
*/
RowLayout {
    id: weekRoot
    spacing: 2

    property var it: null
    property bool loading: false

    readonly property var dayNames: ["一", "二", "三", "四", "五", "六", "日"]

    function load(item) {
        it = item
        loading = true
        var spec = String((item && item.p2) || "").trim()
        var picked = spec ? spec.split(/[,，、\s]+/) : []
        for (var i = 0; i < 7; i++) {
            var cb = weekRep.itemAt(i)
            if (cb) cb.checked = spec ? (picked.indexOf(String(i + 1)) >= 0) : true
        }
        loading = false
    }

    function save() {
        if (loading || !it) return
        var picked = []
        for (var i = 0; i < 7; i++) {
            var cb = weekRep.itemAt(i)
            if (cb && cb.checked) picked.push(String(i + 1))
        }
        if (picked.length === 7) it.p2 = ""            // 全选 = 每天
        else if (picked.length === 0) it.p2 = "0"      // 全不选 = 不触发
        else it.p2 = picked.join(",")
    }

    Repeater {
        id: weekRep
        model: 7
        delegate: CheckBox {
            text: weekRoot.dayNames[index]
            onToggled: weekRoot.save()
        }
    }
}
