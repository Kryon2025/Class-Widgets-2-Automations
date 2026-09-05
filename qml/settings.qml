import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import ClassWidgets.Plugins

/*!
    Kryon 自动化 —— 自动化规则编辑界面。

    模型：自动化 = 触发器列表（任一触发）+ 规则集（全部/任一满足，可取反）
           + 行动列表（顺序执行）+ 恢复开关。
    每种触发器 / 规则 / 行动都有专属字段（下拉 / 开关 / 数字 / 文本 / 时间），
    选择类型后自动显示对应选项，不再使用通用参数框。
*/

PluginPage {
    id: page
    pluginId: "com.kryon.automations"
    title: "自动化"

    extraHeaderItems: Button {
        text: "窗口调试"
        onClicked: if (backend) backend.openWindowDebugger()
    }

    // ── 类型清单（顺序 = 后端常量表）────────────────────────
    property var trigTypes: ["time", "interval", "class_start", "class_end", "break_start",
        "after_school", "status_change", "before_class", "app_start", "signal"]
    property var trigLabels: ["定时", "间隔触发", "上课时", "下课时", "课间休息时",
        "放学时", "时间状态变化时", "上课前", "应用启动时", "收到信号"]

    property var ruleTypes: ["always_true", "always_false", "today_is", "later_than",
        "current_subject", "next_subject", "prev_subject", "current_status",
        "foreground_window", "flag_is", "current_teacher", "next_teacher"]
    property var ruleLabels: ["总是为真", "总是为假", "今天是…", "时间晚于…", "当前科目是",
        "下节课科目是", "上节课科目是", "当前时间状态是", "前台窗口…", "读标志…",
        "当前教师是", "下节课教师是"]

    property var actTypes: ["run", "notify", "wait", "broadcast", "set_flag",
        "set_config", "lock", "restart"]
    property var actLabels: ["运行命令/程序", "显示提醒", "等待", "广播信号", "设标志",
        "设置配置项", "锁定配置项", "重启主程序"]

    // ── 下拉选项（值数组与后端约定一致）────────────────────
    property var statusLabels: ["上课", "课间休息", "放学后", "活动", "预备"]
    property var statusValues: ["class", "break", "free", "activity", "preparation"]

    property var weekLabels: ["周一", "周二", "周三", "周四", "周五", "周六", "周日", "周末", "工作日"]
    property var weekValues: ["1", "2", "3", "4", "5", "6", "7", "weekend", "weekday"]

    property var winStateLabels: ["任意", "最大化", "全屏"]
    property var winStateValues: ["", "maximized", "fullscreen"]

    property var matchLabels: ["包含", "等于"]
    property var matchValues: ["contains", "equals"]

    property var levelLabels: ["普通提示", "上下课/状态", "警告", "系统"]
    property var levelValues: ["0", "1", "2", "3"]

    property var anchorLabels: ["左上", "中上", "右上", "左下", "中下", "右下"]
    property var anchorValues: ["top_left", "top_center", "top_right",
        "bottom_left", "bottom_center", "bottom_right"]

    property var layerLabels: ["置顶", "置底", "普通"]
    property var layerValues: ["top", "bottom", "normal"]

    property var precisionLabels: ["秒", "分"]
    property var precisionValues: ["second", "minute"]

    property var tapLabels: ["隐藏", "切换迷你模式", "浮窗"]
    property var tapValues: ["hide", "mini_mode", "floating_widget"]

    property var lockLabels: ["锁定", "解锁"]
    property var lockValues: ["lock", "unlock"]

    // ── 配置键（设置配置项 / 锁定配置项）────────────────────
    property var configKeys: [
        {"key": "preferences.mini_mode", "label": "迷你模式", "kind": "bool"},
        {"key": "preferences.lighting_effect", "label": "光影效果", "kind": "bool"},
        {"key": "interactions.hide.state", "label": "隐藏小组件", "kind": "bool"},
        {"key": "interactions.hide.in_class", "label": "课堂中隐藏", "kind": "bool"},
        {"key": "interactions.hide.maximized", "label": "最大化时隐藏", "kind": "bool"},
        {"key": "interactions.hide.fullscreen", "label": "全屏时隐藏", "kind": "bool"},
        {"key": "interactions.hover_fade", "label": "悬停淡出", "kind": "bool"},
        {"key": "notifications.enabled", "label": "通知开关", "kind": "bool"},
        {"key": "preferences.current_theme", "label": "主题", "kind": "theme"},
        {"key": "preferences.widgets_anchor", "label": "停靠位置", "kind": "anchor"},
        {"key": "preferences.widgets_layer", "label": "层级", "kind": "layer"},
        {"key": "preferences.countdown_precision", "label": "倒计时精度", "kind": "precision"},
        {"key": "interactions.hide.action", "label": "隐藏行为", "kind": "tap"},
        {"key": "interactions.tapped_action", "label": "点击行为", "kind": "tap"},
        {"key": "preferences.current_preset", "label": "组件方案", "kind": "preset"},
        {"key": "preferences.opacity", "label": "不透明度", "kind": "float01"},
        {"key": "notifications.volume", "label": "通知音量", "kind": "float01"},
        {"key": "preferences.scale_factor", "label": "缩放", "kind": "floatScale"},
        {"key": "preferences.widgets_offset_x", "label": "水平偏移", "kind": "int"},
        {"key": "preferences.widgets_offset_y", "label": "垂直偏移", "kind": "int"}
    ]
    property var keyLabels: configKeys.map(function (e) { return e.label })

    // ── 数据 ────────────────────────────────────────────────
    property var rules: []
    property int current: -1
    property int trigVersion: 0
    property int ruleVersion: 0
    property int actVersion: 0
    property int trigCount: 0
    property int ruleCount: 0
    property int actCount: 0
    property string statusText: ""
    property var flags: ({})
    property var subjects: []
    property var teachers: []
    property var themeIds: []
    property var themeNames: []
    property var presets: []

    Component.onCompleted: Qt.callLater(reload)
    onBackendChanged: { if (backend) Qt.callLater(reload) }

    function cur() {
        return (page.current >= 0 && page.current < page.rules.length) ? page.rules[page.current] : null
    }

    function reload() {
        if (!backend) return
        var raw = backend.getRulesJson()
        page.rules = raw ? JSON.parse(raw) : []
        if (page.rules.length && page.current >= page.rules.length) page.current = page.rules.length - 1
        if (page.current < 0 && page.rules.length) page.current = 0
        try { page.flags = JSON.parse(backend.getFlagsJson() || "{}") } catch (e) { page.flags = ({}) }
        try { page.presets = JSON.parse(backend.getPresetsJson() || "[]") } catch (e) { page.presets = [] }
        try {
            var sub = JSON.parse(backend.getSubjectsJson() || "{}")
            page.subjects = sub.subjects || []
            page.teachers = sub.teachers || []
        } catch (e) { page.subjects = []; page.teachers = [] }
        try {
            var th = JSON.parse(backend.getThemesJson() || "[]")
            page.themeIds = th.map(function (e) { return e[0] })
            page.themeNames = th.map(function (e) { return e[1] || e[0] })
        } catch (e) { page.themeIds = []; page.themeNames = [] }
        refreshNames()
        if (page.rules.length) loadRule()
        statusText = page.rules.length ? "" : "暂无自动化规则"
        editor.visible = page.rules.length > 0
        emptyHint.visible = !editor.visible
    }

    function refreshNames() {
        var arr = []
        for (var i = 0; i < page.rules.length; i++) arr.push(page.rules[i].name || "未命名")
        ruleCombo.model = arr
        ruleCombo.currentIndex = page.current
    }

    function loadRule() {
        var r = page.cur()
        if (!r) return
        nameField.text = r.name || ""
        enabledSwitch.checked = !!r.enabled
        revertSwitch.checked = !!r.revert
        rsEnabled.checked = !!(r.ruleset && r.ruleset.enabled)
        rsMode.currentIndex = (r.ruleset && r.ruleset.mode === "any") ? 1 : 0
        rsReversed.checked = !!(r.ruleset && r.ruleset.reversed)
        page.trigCount = (r.triggers || []).length
        page.ruleCount = ((r.ruleset && r.ruleset.rules) || []).length
        page.actCount = (r.actions || []).length
        page.trigVersion++
        page.ruleVersion++
        page.actVersion++
    }

    function save() {
        if (!backend) return
        var ok = backend.saveRulesJson(JSON.stringify(page.rules))
        statusText = ok ? "已保存（" + page.rules.length + " 条规则）" : "保存失败（详见主程序日志）"
        if (ok) saveTimer.restart()
    }

    function addRule() {
        page.rules.push({
            "uid": "", "name": "新自动化", "enabled": true, "revert": false,
            "triggers": [{"type": "class_start", "p1": "", "p2": "", "p3": "", "p4": ""}],
            "ruleset": {"enabled": false, "mode": "all", "reversed": false, "rules": []},
            "actions": [{"type": "set_config", "p1": "interactions.hide.state", "p2": "true", "p3": "", "p4": ""}]
        })
        page.current = page.rules.length - 1
        refreshNames()
        loadRule()
        editor.visible = true
        emptyHint.visible = false
    }

    function deleteRule() {
        if (!page.rules.length) return
        page.rules.splice(page.current, 1)
        if (page.current >= page.rules.length) page.current = page.rules.length - 1
        refreshNames()
        if (page.rules.length) { loadRule() }
        else { page.current = -1; editor.visible = false; emptyHint.visible = true; statusText = "暂无自动化规则" }
    }

    function commit(key, value) {
        var r = page.cur()
        if (!r) return
        r[key] = value
        if (key === "name") { refreshNames(); ruleCombo.currentIndex = page.current }
    }

    // ── 子项操作 ────────────────────────────────────────────
    function addTrigger() {
        var r = page.cur(); if (!r) return
        if (!r.triggers) r.triggers = []
        r.triggers.push({"type": "class_start", "p1": "", "p2": "", "p3": "", "p4": ""})
        page.trigCount = r.triggers.length; page.trigVersion++
    }
    function removeTrigger(i) {
        var r = page.cur(); if (!r || !r.triggers) return
        r.triggers.splice(i, 1); page.trigCount = r.triggers.length; page.trigVersion++
    }
    function addRuleItem() {
        var r = page.cur(); if (!r) return
        if (!r.ruleset) r.ruleset = {"enabled": true, "mode": "all", "reversed": false, "rules": []}
        if (!r.ruleset.rules) r.ruleset.rules = []
        r.ruleset.rules.push({"type": "current_status", "p1": "class", "p2": "", "p3": "", "p4": "", "reversed": false})
        page.ruleCount = r.ruleset.rules.length; page.ruleVersion++
    }
    function removeRuleItem(i) {
        var r = page.cur(); if (!r || !r.ruleset || !r.ruleset.rules) return
        r.ruleset.rules.splice(i, 1); page.ruleCount = r.ruleset.rules.length; page.ruleVersion++
    }
    function addAction() {
        var r = page.cur(); if (!r) return
        if (!r.actions) r.actions = []
        r.actions.push({"type": "notify", "p1": "自动化提醒", "p2": "", "p3": "4000", "p4": "0"})
        page.actCount = r.actions.length; page.actVersion++
    }
    function removeAction(i) {
        var r = page.cur(); if (!r || !r.actions) return
        r.actions.splice(i, 1); page.actCount = r.actions.length; page.actVersion++
    }
    function moveAction(i, dir) {
        var r = page.cur(); if (!r || !r.actions) return
        var j = i + dir
        if (j < 0 || j >= r.actions.length) return
        var t = r.actions[i]; r.actions[i] = r.actions[j]; r.actions[j] = t
        page.actVersion++
    }

    // ── 类型 → 字段编辑器组件 ──────────────────────────────
    function trigFieldComp(t) {
        switch (t) {
            case "time": return trigTimeComp
            case "interval": return trigIntervalComp
            case "before_class": return trigBeforeComp
            case "signal": return trigSignalComp
            default: return null
        }
    }
    function ruleFieldComp(t) {
        switch (t) {
            case "today_is": return ruleTodayComp
            case "later_than": return ruleLaterComp
            case "current_subject":
            case "next_subject":
            case "prev_subject": return ruleSubjectComp
            case "current_status": return ruleStatusComp
            case "foreground_window": return ruleForegroundComp
            case "flag_is": return ruleFlagComp
            case "current_teacher":
            case "next_teacher": return ruleTeacherComp
            default: return null
        }
    }
    function actFieldComp(t) {
        switch (t) {
            case "run": return actRunComp
            case "notify": return actNotifyComp
            case "wait": return actWaitComp
            case "broadcast": return actBroadcastComp
            case "set_flag": return actSetFlagComp
            case "set_config": return actSetConfigComp
            case "lock": return actLockComp
            default: return null
        }
    }

    function keyIndexOf(key) {
        for (var i = 0; i < page.configKeys.length; i++)
            if (page.configKeys[i].key === key) return i
        return 0
    }

    function defaultFor(meta) {
        if (!meta) return ""
        switch (meta.kind) {
            case "bool": return "true"
            case "theme": return page.themeIds.length ? page.themeIds[0] : ""
            case "anchor": return "top_center"
            case "layer": return "top"
            case "precision": return "second"
            case "tap": return "hide"
            case "preset": return page.presets.length ? page.presets[0] : "default"
            case "int": return "0"
            case "float01": return "1"
            case "floatScale": return "1"
            default: return ""
        }
    }

    // ══════════════ 触发器字段组件 ══════════════
    Component {
        id: trigTimeComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                timeF.text = item.p1 || ""
                dayF.text = item.p2 || ""
                loading = false
            }
            TextField {
                id: timeF
                Layout.fillWidth: true
                placeholderText: "时刻 HH:MM（如 07:50）"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: dayF
                Layout.fillWidth: true
                placeholderText: "星期，留空=每天（如 1,2,3,4,5）"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: trigIntervalComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                secSpin.value = parseInt(item.p1 || "60")
                loading = false
            }
            SpinBox {
                id: secSpin
                Layout.preferredWidth: 120
                from: 1; to: 86400; stepSize: 1; editable: true
                onValueChanged: if (!loading && it) it.p1 = String(Math.round(value))
            }
            Text { text: "秒" }
        }
    }

    Component {
        id: trigBeforeComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                secSpin.value = parseInt(item.p1 || "30")
                loading = false
            }
            SpinBox {
                id: secSpin
                Layout.preferredWidth: 120
                from: 0; to: 3600; stepSize: 5; editable: true
                onValueChanged: if (!loading && it) it.p1 = String(Math.round(value))
            }
            Text { text: "秒前（上课/课间开始前触发）" }
        }
    }

    Component {
        id: trigSignalComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                sigF.text = item.p1 || ""
            }
            TextField {
                id: sigF
                Layout.fillWidth: true
                placeholderText: "信号名（配合「广播信号」行动使用）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    // ══════════════ 规则字段组件 ══════════════
    Component {
        id: ruleTodayComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                var i = page.weekValues.indexOf(item.p1 || "")
                weekCombo.currentIndex = Math.max(0, i)
            }
            ComboBox {
                id: weekCombo
                Layout.fillWidth: true
                model: page.weekLabels
                onActivated: if (it) it.p1 = page.weekValues[index]
            }
        }
    }

    Component {
        id: ruleLaterComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                timeF.text = item.p1 || ""
            }
            TextField {
                id: timeF
                Layout.fillWidth: true
                placeholderText: "时间 HH:MM（当前时刻晚于该时间则满足）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    Component {
        id: ruleSubjectComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                var i = page.subjects.indexOf(item.p1 || "")
                subCombo.currentIndex = Math.max(0, i)
            }
            ComboBox {
                id: subCombo
                Layout.fillWidth: true
                model: page.subjects
                onActivated: if (it) it.p1 = page.subjects[index]
            }
            Text { text: "（在课表设置中维护科目）"; visible: page.subjects.length === 0; color: "#888888" }
        }
    }

    Component {
        id: ruleStatusComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                var i = page.statusValues.indexOf(item.p1 || "")
                stCombo.currentIndex = Math.max(0, i)
            }
            ComboBox {
                id: stCombo
                Layout.fillWidth: true
                model: page.statusLabels
                onActivated: if (it) it.p1 = page.statusValues[index]
            }
        }
    }

    Component {
        id: ruleForegroundComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                procF.text = item.p1 || ""
                var mi = page.matchValues.indexOf(item.p2 || "")
                matchCombo.currentIndex = Math.max(0, mi)
                var wi = page.winStateValues.indexOf(item.p3 || "")
                winCombo.currentIndex = Math.max(0, wi)
            }
            TextField {
                id: procF
                Layout.fillWidth: true
                placeholderText: "窗口进程名或标题"
                onTextEdited: if (it) it.p1 = text
            }
            ComboBox {
                id: matchCombo
                Layout.preferredWidth: 90
                model: page.matchLabels
                onActivated: if (it) it.p2 = page.matchValues[index]
            }
            ComboBox {
                id: winCombo
                Layout.preferredWidth: 110
                model: page.winStateLabels
                onActivated: if (it) it.p3 = page.winStateValues[index]
            }
        }
    }

    Component {
        id: ruleFlagComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                nameF.text = item.p1 || ""
                valF.text = item.p2 || ""
            }
            TextField {
                id: nameF
                Layout.fillWidth: true
                placeholderText: "标志名（配合「设标志」行动）"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                placeholderText: "期望值"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: ruleTeacherComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                var i = page.teachers.indexOf(item.p1 || "")
                teaCombo.currentIndex = Math.max(0, i)
            }
            ComboBox {
                id: teaCombo
                Layout.fillWidth: true
                model: page.teachers
                onActivated: if (it) it.p1 = page.teachers[index]
            }
            Text { text: "（在课表设置中维护教师）"; visible: page.teachers.length === 0; color: "#888888" }
        }
    }

    // ══════════════ 行动字段组件 ══════════════
    Component {
        id: actRunComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                cmdF.text = item.p1 || ""
            }
            TextField {
                id: cmdF
                Layout.fillWidth: true
                placeholderText: "命令/程序/网址（如 notepad.exe 或 https://…）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    Component {
        id: actNotifyComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                titleF.text = item.p1 || ""
                bodyF.text = item.p2 || ""
                durSpin.value = parseInt(item.p3 || "4000") / 1000
                var li = page.levelValues.indexOf(item.p4 || "")
                lvlCombo.currentIndex = Math.max(0, li)
                loading = false
            }
            TextField {
                id: titleF
                Layout.fillWidth: true
                placeholderText: "标题"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: bodyF
                Layout.fillWidth: true
                placeholderText: "正文（可空）"
                onTextEdited: if (it) it.p2 = text
            }
            SpinBox {
                id: durSpin
                Layout.preferredWidth: 100
                from: 0; to: 60; stepSize: 1; editable: true
                onValueChanged: if (!loading && it) it.p3 = String(Math.round(value * 1000))
            }
            Text { text: "秒" }
            ComboBox {
                id: lvlCombo
                Layout.preferredWidth: 130
                model: page.levelLabels
                onActivated: if (it) it.p4 = page.levelValues[index]
            }
        }
    }

    Component {
        id: actWaitComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                secSpin.value = parseInt(item.p1 || "1")
                loading = false
            }
            SpinBox {
                id: secSpin
                Layout.preferredWidth: 120
                from: 0; to: 3600; stepSize: 1; editable: true
                onValueChanged: if (!loading && it) it.p1 = String(Math.round(value))
            }
            Text { text: "秒（暂停后再执行下一条行动）" }
        }
    }

    Component {
        id: actBroadcastComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                sigF.text = item.p1 || ""
            }
            TextField {
                id: sigF
                Layout.fillWidth: true
                placeholderText: "信号名（触发其它自动化的「收到信号」）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    Component {
        id: actSetFlagComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                nameF.text = item.p1 || ""
                valF.text = item.p2 || ""
            }
            TextField {
                id: nameF
                Layout.fillWidth: true
                placeholderText: "标志名"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                placeholderText: "值"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: actSetConfigComp
        RowLayout {
            spacing: 6
            property var it: null
            property var meta: null
            property bool loading: false

            function load(item) {
                it = item
                var ki = page.keyIndexOf(item.p1 || "")
                keyCombo.currentIndex = ki
                meta = page.configKeys[ki]
                applyValue()
            }
            function applyValue() {
                loading = true
                var v = it ? it.p2 : ""
                boolSw.checked = (v === "true" || v === "1" || v === "开" || v === "是")
                themeCombo.currentIndex = Math.max(0, page.themeIds.indexOf(v))
                anchorCombo.currentIndex = Math.max(0, page.anchorValues.indexOf(v))
                layerCombo.currentIndex = Math.max(0, page.layerValues.indexOf(v))
                precCombo.currentIndex = Math.max(0, page.precisionValues.indexOf(v))
                tapCombo.currentIndex = Math.max(0, page.tapValues.indexOf(v))
                presetCombo.currentIndex = Math.max(0, page.presets.indexOf(v))
                numSpin.value = parseFloat(v) || 0
                textF.text = v || ""
                loading = false
            }

            ComboBox {
                id: keyCombo
                Layout.preferredWidth: 140
                model: page.keyLabels
                onActivated: {
                    meta = page.configKeys[index]
                    if (it) { it.p1 = meta.key; it.p2 = page.defaultFor(meta) }
                    applyValue()
                }
            }
            Switch {
                id: boolSw
                visible: meta && meta.kind === "bool"
                text: "开"
                onToggled: if (!loading && it) it.p2 = checked ? "true" : "false"
            }
            ComboBox {
                id: themeCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "theme"
                model: page.themeNames
                onActivated: if (!loading && it) it.p2 = page.themeIds[index]
            }
            ComboBox {
                id: anchorCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "anchor"
                model: page.anchorLabels
                onActivated: if (!loading && it) it.p2 = page.anchorValues[index]
            }
            ComboBox {
                id: layerCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "layer"
                model: page.layerLabels
                onActivated: if (!loading && it) it.p2 = page.layerValues[index]
            }
            ComboBox {
                id: precCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "precision"
                model: page.precisionLabels
                onActivated: if (!loading && it) it.p2 = page.precisionValues[index]
            }
            ComboBox {
                id: tapCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "tap"
                model: page.tapLabels
                onActivated: if (!loading && it) it.p2 = page.tapValues[index]
            }
            ComboBox {
                id: presetCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "preset"
                model: page.presets
                onActivated: if (!loading && it) it.p2 = page.presets[index]
            }
            SpinBox {
                id: numSpin
                Layout.preferredWidth: 140
                visible: meta && (meta.kind === "int" || meta.kind === "float01" || meta.kind === "floatScale")
                editable: true
                from: meta && meta.kind === "floatScale" ? 0.1 : (meta && meta.kind === "int" ? -2000 : 0)
                to: meta && meta.kind === "int" ? 2000 : (meta && meta.kind === "floatScale" ? 4 : 1)
                stepSize: meta && meta.kind === "int" ? 4 : 0.05
                onValueChanged: {
                    if (!loading && it) {
                        if (meta && meta.kind === "int") it.p2 = String(Math.round(value))
                        else it.p2 = String(Math.round(value * 100) / 100)
                    }
                }
            }
            TextField {
                id: textF
                Layout.fillWidth: true
                visible: meta && (meta.kind === "text" || meta.kind === undefined)
                placeholderText: "值"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: actLockComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                var ki = page.keyIndexOf(item.p1 || "")
                keyCombo.currentIndex = ki
                var li = page.lockValues.indexOf(item.p2 || "lock")
                lockCombo.currentIndex = Math.max(0, li)
            }
            ComboBox {
                id: keyCombo
                Layout.fillWidth: true
                model: page.keyLabels
                onActivated: if (it) it.p1 = page.configKeys[index].key
            }
            ComboBox {
                id: lockCombo
                Layout.preferredWidth: 100
                model: page.lockLabels
                onActivated: if (it) it.p2 = page.lockValues[index]
            }
        }
    }

    // ══════════════ 界面 ══════════════
    SettingsLayout {
        width: parent.width
        spacing: 12

        SettingCard {
            Layout.fillWidth: true
            title: "自动化"
            description: "触发器触发 → 规则集过滤 → 依次执行行动；开启「恢复」后，逆事件（如下课）或规则集不再满足时自动还原被修改的配置。每种类型选中后即显示对应的专属选项。"
        }

        SettingCard {
            Layout.fillWidth: true
            title: "选择要编辑的自动化"
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                ComboBox {
                    id: ruleCombo
                    Layout.fillWidth: true
                    onActivated: { page.current = index; loadRule() }
                }
                Button { text: "新增"; onClicked: page.addRule() }
                Button { text: "删除"; onClicked: page.deleteRule() }
            }
        }

        Item { width: 1; height: 1 }

        ColumnLayout {
            id: editor
            Layout.fillWidth: true
            visible: false
            spacing: 10

            SettingCard {
                Layout.fillWidth: true
                title: "基础设置"
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { text: "名称"; Layout.preferredWidth: 40 }
                    TextField {
                        id: nameField
                        Layout.fillWidth: true
                        placeholderText: "自动化名称"
                        onTextEdited: page.commit("name", text)
                    }
                    Switch { id: enabledSwitch; text: "启用"; onToggled: page.commit("enabled", checked) }
                    Switch { id: revertSwitch; text: "恢复"; onToggled: page.commit("revert", checked) }
                }
            }

            SettingCard {
                Layout.fillWidth: true
                title: "触发器（任一触发即可）"
                description: "定时、间隔、上课/下课/课间/放学/状态变化、上课前、应用启动、收到信号。"
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: page.trigCount
                        delegate: RowLayout {
                            id: trigRow
                            Layout.fillWidth: true
                            spacing: 6
                            property int idx: index
                            property int ver: page.trigVersion
                            property var obj: null
                            onVerChanged: initRow()

                            function arr() { var r = page.cur(); return r ? (r.triggers || []) : [] }
                            function initRow() {
                                var a = arr()
                                if (idx >= a.length) { obj = null; return }
                                obj = a[idx]
                                typeBox.currentIndex = Math.max(0, page.trigTypes.indexOf(obj.type || ""))
                                refreshFields()
                            }
                            function refreshFields() {
                                if (obj && fld.item && fld.item.load) fld.item.load(obj)
                            }
                            Component.onCompleted: initRow()

                            ComboBox {
                                id: typeBox
                                Layout.preferredWidth: 170
                                model: page.trigLabels
                                onActivated: {
                                    var r = page.cur(); if (!r || !r.triggers) return
                                    r.triggers[trigRow.idx] = {"type": page.trigTypes[index], "p1": "", "p2": "", "p3": "", "p4": ""}
                                    trigRow.obj = r.triggers[trigRow.idx]
                                }
                            }
                            Loader {
                                id: fld
                                Layout.fillWidth: true
                                sourceComponent: page.trigFieldComp(trigRow.obj ? trigRow.obj.type : "")
                                onLoaded: trigRow.refreshFields()
                            }
                            Button { text: "移除"; implicitWidth: 52; implicitHeight: 30; onClicked: page.removeTrigger(trigRow.idx) }
                        }
                    }
                    Button { text: "+ 添加触发器"; onClicked: page.addTrigger() }
                }
            }

            SettingCard {
                Layout.fillWidth: true
                title: "规则集（条件，满足才执行）"
                description: "规则集关闭时无条件执行；开启后按下方规则过滤。"
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    RowLayout {
                        spacing: 8
                        Switch {
                            id: rsEnabled
                            text: "启用规则集"
                            onToggled: { var r = page.cur(); if (r && r.ruleset) r.ruleset.enabled = checked }
                        }
                        ComboBox {
                            id: rsMode
                            Layout.preferredWidth: 120
                            model: ["全部满足", "任一满足"]
                            onActivated: { var r = page.cur(); if (r && r.ruleset) r.ruleset.mode = (index === 1 ? "any" : "all") }
                        }
                        Switch {
                            id: rsReversed
                            text: "取反"
                            onToggled: { var r = page.cur(); if (r && r.ruleset) r.ruleset.reversed = checked }
                        }
                    }
                    Repeater {
                        model: page.ruleCount
                        delegate: RowLayout {
                            id: ruleRow
                            Layout.fillWidth: true
                            spacing: 6
                            property int idx: index
                            property int ver: page.ruleVersion
                            property var obj: null
                            onVerChanged: initRow()

                            function arr() { var r = page.cur(); return (r && r.ruleset) ? (r.ruleset.rules || []) : [] }
                            function initRow() {
                                var a = arr()
                                if (idx >= a.length) { obj = null; return }
                                obj = a[idx]
                                typeBox.currentIndex = Math.max(0, page.ruleTypes.indexOf(obj.type || ""))
                                revSw.checked = !!obj.reversed
                                refreshFields()
                            }
                            function refreshFields() {
                                if (obj && fld.item && fld.item.load) fld.item.load(obj)
                            }
                            Component.onCompleted: initRow()

                            ComboBox {
                                id: typeBox
                                Layout.preferredWidth: 170
                                model: page.ruleLabels
                                onActivated: {
                                    var r = page.cur(); if (!r || !r.ruleset || !r.ruleset.rules) return
                                    r.ruleset.rules[ruleRow.idx] = {"type": page.ruleTypes[index], "p1": "", "p2": "", "p3": "", "p4": "", "reversed": false}
                                    ruleRow.obj = r.ruleset.rules[ruleRow.idx]
                                    revSw.checked = false
                                }
                            }
                            Loader {
                                id: fld
                                Layout.fillWidth: true
                                sourceComponent: page.ruleFieldComp(ruleRow.obj ? ruleRow.obj.type : "")
                                onLoaded: ruleRow.refreshFields()
                            }
                            Switch {
                                id: revSw
                                text: "取反"
                                onToggled: if (obj) obj.reversed = checked
                            }
                            Button { text: "移除"; implicitWidth: 52; implicitHeight: 30; onClicked: page.removeRuleItem(ruleRow.idx) }
                        }
                    }
                    Button { text: "+ 添加规则"; onClicked: page.addRuleItem() }
                }
            }

            SettingCard {
                Layout.fillWidth: true
                title: "行动（顺序执行，可排序）"
                description: "运行命令、显示提醒、等待、广播信号、设标志、设置配置项、锁定配置项、重启主程序。"
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: page.actCount
                        delegate: RowLayout {
                            id: actRow
                            Layout.fillWidth: true
                            spacing: 6
                            property int idx: index
                            property int ver: page.actVersion
                            property var obj: null
                            onVerChanged: initRow()

                            function arr() { var r = page.cur(); return r ? (r.actions || []) : [] }
                            function initRow() {
                                var a = arr()
                                if (idx >= a.length) { obj = null; return }
                                obj = a[idx]
                                typeBox.currentIndex = Math.max(0, page.actTypes.indexOf(obj.type || ""))
                                refreshFields()
                            }
                            function refreshFields() {
                                if (obj && fld.item && fld.item.load) fld.item.load(obj)
                            }
                            Component.onCompleted: initRow()

                            ComboBox {
                                id: typeBox
                                Layout.preferredWidth: 170
                                model: page.actLabels
                                onActivated: {
                                    var r = page.cur(); if (!r || !r.actions) return
                                    r.actions[actRow.idx] = {"type": page.actTypes[index], "p1": "", "p2": "", "p3": "", "p4": ""}
                                    actRow.obj = r.actions[actRow.idx]
                                }
                            }
                            Loader {
                                id: fld
                                Layout.fillWidth: true
                                sourceComponent: page.actFieldComp(actRow.obj ? actRow.obj.type : "")
                                onLoaded: actRow.refreshFields()
                            }
                            Button { text: "↑"; implicitWidth: 30; implicitHeight: 30; onClicked: page.moveAction(actRow.idx, -1) }
                            Button { text: "↓"; implicitWidth: 30; implicitHeight: 30; onClicked: page.moveAction(actRow.idx, 1) }
                            Button { text: "移除"; implicitWidth: 52; implicitHeight: 30; onClicked: page.removeAction(actRow.idx) }
                        }
                    }
                    Button { text: "+ 添加行动"; onClicked: page.addAction() }
                }
            }

            SettingCard {
                Layout.fillWidth: true
                title: "保存与测试"
                description: "保存后引擎立即生效。「测试执行」忽略触发器与规则集，立即执行一次当前自动化的行动。"
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Button {
                        text: "保存规则"
                        highlighted: true
                        onClicked: page.save()
                    }
                    Button {
                        text: "测试执行"
                        onClicked: {
                            if (backend) { backend.fireRuleNow(page.current); statusText = "已执行测试（查看日志确认）" }
                        }
                    }
                    Text {
                        text: page.statusText
                        color: "#888888"
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }
        }

        Text {
            id: emptyHint
            Layout.fillWidth: true
            text: "还没有自动化规则。点击上方「新增」创建第一条。\n例如：上课隐藏小组件并自动恢复 —— 新增后，触发器选「上课时」，行动选「设置配置项」→「隐藏小组件」→ 开，并打开「恢复」开关，下课时即自动还原。"
            color: "#888888"
            wrapMode: Text.Wrap
            visible: true
        }
    }

    Timer {
        id: saveTimer
        interval: 1500
        onTriggered: { statusText = "" }
    }
}
