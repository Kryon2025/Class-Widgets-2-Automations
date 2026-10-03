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

    extraHeaderItems: RowLayout {
        spacing: 8

        Switch {
            id: rollcallSwitch
            text: "随机点名联动"
            checked: page.rollcallExt
            enabled: backend && backend.setRollcallExtEnabled
            Component.onCompleted: if (backend && backend.rollcallExtEnabled)
                                       page.rollcallExt = backend.rollcallExtEnabled()
            onToggled: {
                page.rollcallExt = checked
                if (backend && backend.setRollcallExtEnabled)
                    backend.setRollcallExtEnabled(checked)
            }
            ToolTip.visible: hovered
            ToolTip.text: backend && backend.rollcallAvailable && backend.rollcallAvailable()
                          ? "在三个模块中显示随机点名（com.rollcall）相关项"
                          : "未检测到随机点名插件（com.rollcall）"
        }

        Button {
            text: "窗口调试"
            onClicked: if (backend) backend.openWindowDebugger()
        }
    }

    // ── 类型清单（顺序 = 后端常量表）────────────────────────
    // 扩展功能：随机点名联动（关闭时三个模块都不出现随机点名项）
    property bool rollcallExt: false

    readonly property var trigTypes: {
        var a = ["time", "interval", "class_start", "class_end", "break_start",
            "after_school", "status_change", "before_class", "app_start", "signal", "alarm", "sys_change", "boot", "notif_new"]
        if (page.rollcallExt) a = a.concat(["rollcall_start", "rollcall_picked"])
        return a
    }
    readonly property var trigLabels: {
        var a = ["定时", "间隔触发", "上课时", "下课时", "课间休息时",
            "放学时", "时间状态变化时", "上课前", "应用启动时", "收到信号", "闹钟", "系统设置变化时", "开机后", "收到系统通知时"]
        if (page.rollcallExt) a = a.concat(["随机点名开始", "随机点名出结果后"])
        return a
    }

    readonly property var ruleTypes: {
        var a = ["always_true", "always_false", "today_is", "later_than",
            "current_subject", "next_subject", "prev_subject", "current_status",
            "foreground_window", "flag_is", "current_teacher", "next_teacher", "sys_setting", "media", "notif"]
        if (page.rollcallExt) a = a.concat(["rollcall_config"])
        return a
    }

    // 系统设置条件（与 win_settings.SYS_RULE_KEYS 一致）
    property var sysKeys: ["theme_apps", "theme_system", "ac_power", "battery_percent", "network"]
    property var sysKeyLabels: ["应用主题（深/浅）", "系统主题（深/浅）", "电源（接电/电池）",
        "电池电量 %", "网络"]
    property var sysValueMap: {
        "theme_apps": ["light", "dark"],
        "theme_system": ["light", "dark"],
        "ac_power": ["ac", "battery"],
        "network": ["online", "offline"]
    }
    property var sysValueLabelMap: {
        "theme_apps": ["浅色", "深色"],
        "theme_system": ["浅色", "深色"],
        "ac_power": ["接电源", "用电池"],
        "network": ["已连接", "未连接"]
    }
    function sysValueOptions(k) { return sysValueMap[k] || [] }
    function sysValueLabels(k) { return sysValueLabelMap[k] || [] }
    function sysIsNumber(k) { return k === "battery_percent" }
    property var sysOps: ["==", "!=", ">", ">=", "<", "<="]
    property var sysOpLabels: ["是", "不是", "大于", "大于等于", "小于", "小于等于"]
    readonly property var ruleLabels: {
        var a = ["总是为真", "总是为假", "今天是…", "时间晚于…", "当前科目是",
            "下节课科目是", "上节课科目是", "当前时间状态是", "前台窗口…", "读标志…",
            "当前教师是", "下节课教师是", "系统设置…", "媒体状态", "系统通知…"]
        if (page.rollcallExt) a = a.concat(["随机点名配置…"])
        return a
    }

    readonly property var actTypes: {
        var a = ["run", "notify", "wait", "broadcast", "set_flag",
            "set_config", "lock", "restart", "open_settings", "set_theme", "power", "volume", "media", "app", "sys_notify"]
        if (page.rollcallExt) a = a.concat(["rollcall_roll", "rollcall_set", "rollcall_close"])
        return a
    }
    readonly property var actLabels: {
        var a = ["运行命令/程序", "显示提醒", "等待", "广播信号", "设标志",
            "设置配置项", "锁定配置项", "重启主程序", "打开系统设置页",
            "切换深/浅色主题", "电源", "音量", "媒体控制", "应用管理", "发系统通知"]
        if (page.rollcallExt) a = a.concat(["触发随机点名", "设置随机点名", "关闭点名窗口"])
        return a
    }

    // ── 随机点名（com.rollcall）配置项清单（顺序 = 后端 ROLLCALL_SETTERS）
    property var rollcallKeys: ["luck_enabled", "no_repeat", "animation_seconds",
        "notify_duration", "window_visible", "float_mode", "click_hide",
        "button_width", "button_height", "mode"]
    property var rollcallLabels: ["概率抽点（按权重）", "一轮之内不重复", "滚动动画时长（秒）",
        "播报停留时长（秒）", "显示悬浮按钮", "浮窗模式", "点击后隐藏",
        "按钮宽度", "按钮高度", "表现形式"]
    property var rollcallBoolKeys: ["luck_enabled", "no_repeat", "window_visible",
                                    "float_mode", "click_hide"]
    function rollcallIsBool(k) { return page.rollcallBoolKeys.indexOf(k) >= 0 }

    // 主题模式 / 范围（与 win_settings.THEME_MODES / THEME_SCOPES 一致）
    // 电源 / 音量（与 win_settings.POWER_MODES / VOLUME_MODES 一致）
    property var powerModes: ["poweroff", "restart", "logoff", "sleep", "hibernate"]
    property var powerLabels: ["关机", "重启", "注销", "睡眠", "休眠"]
    // 媒体控制 / 媒体状态（与 media.py 一致）
    property var mediaActions: ["toggle", "play", "pause", "prev", "next", "stop"]
    property var mediaActionLabels: ["播放 / 暂停", "播放", "暂停", "上一首", "下一首", "停止"]
    property var mediaKeys: ["playing", "title", "artist"]
    property var mediaKeyLabels: ["是否在播放", "曲名", "歌手"]
    // 系统通知（与 notify.py 一致）
    property var notifKeys: ["app", "text"]
    property var notifKeyLabels: ["应用名", "内容"]
    property var notifOps: ["==", "!="]
    property var notifOpLabels: ["包含", "不包含"]
    property var volumeModes: ["up", "down", "mute", "set"]
    property var volumeLabels: ["增大", "减小", "静音（切换）", "设为指定值 %"]
    property var themeModes: ["light", "dark", "toggle"]
    property var themeModeLabels: ["浅色", "深色", "切换"]
    property var themeScopes: ["both", "apps", "system"]
    property var themeScopeLabels: ["全部（应用+系统）", "仅应用", "仅系统"]

    // 系统设置页（值 = ms-settings: 后面那段，与 win_settings.SETTINGS_PAGES 一致）
    property var settingsPages: ["personalization", "colors", "themes", "display",
        "sound", "notifications", "powersleep", "batterysaver", "network",
        "network-wifi", "bluetooth", "datetime", "language", "appsfeatures",
        "defaultapps", "windowsupdate", "privacy", "gaming-gamebar",
        "easeofaccess", "about"]
    property var settingsPageLabels: ["个性化", "颜色", "主题", "显示", "声音",
        "通知", "电源和睡眠", "电池", "网络状态", "WLAN", "蓝牙", "日期和时间",
        "语言", "应用", "默认应用", "Windows 更新", "隐私", "游戏栏",
        "辅助功能", "关于"]

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

    // ── 已安装应用（「打开应用」行动用，首次需要时枚举一次）──
    property var apps: []
    property var appTargets: []
    property var appLabels: []
    property bool appsLoaded: false

    // ── 卡片外观（圆角取主题窗口圆角的两倍；主题默认只有 3，太方了）──
    readonly property int cardRadius: {
        var t = Theme.currentTheme
        if (t && t.appearance && t.appearance.windowRadius) return t.appearance.windowRadius * 2
        return 14
    }
    // 卡片宽度按页面内容宽度算，不依赖 Flow 自身宽度（避免布局循环）
    readonly property real gridWidth: Math.min(page.width - (page.horizontalPadding || 56) * 2,
                                               page.wrapperWidth || 1000)
    readonly property real cardWidth: Math.max(200, Math.min(280, (gridWidth - 14) / 2))
    readonly property int cardHeight: 120

    // 应用挑选弹窗：appPicking 控制显隐，appPickNonce 用于通知编辑器接收结果
    // （用计数器而不是直接监听值，避免连续选同一个值时不再触发）
    property bool appPicking: false
    property var appPickValue: ""
    // 谁发起的挑选：弹窗结果只回填这一行，避免多行一起被改写
    property var appPickOwner: null
    property int appPickNonce: 0

    // 多个规则集（rulesets）：rsCount 是外层行数，rsVersion 变更时各规则集重算自己的行数
    property int rsCount: 0
    property int rsVersion: 0

    // 通用列表挑选（科目/教师/主题/预设/配置项…）：与「选择应用」同一套写法
    property bool listPicking: false
    property var listPickCombo: null
    property var listPickLabels: []
    property string listPickTitle: ""
    property int listPickIndex: -1
    property string listPickValue: ""

    function acceptAppPick() {
        appPickNonce++
        appPicking = false
    }

    function openListPick(combo, labels, title) {
        page.listPickCombo = combo
        page.listPickLabels = labels || []
        page.listPickTitle = title || "选择"
        page.listPickIndex = -1
        page.listPickValue = ""
        if (combo && combo.currentIndex >= 0 && combo.currentIndex < page.listPickLabels.length) {
            page.listPickIndex = combo.currentIndex
            page.listPickValue = String(page.listPickLabels[combo.currentIndex])
        }
        listPickSearch.text = ""
        listPickFilter.refresh()
        page.listPicking = true
    }
    function acceptListPick(i) {
        if (!page.listPickCombo) { page.listPicking = false; return }
        if (i < 0) return
        page.listPickCombo.currentIndex = i
        page.listPickCombo.activated(i)      // 下拉原本的处理逻辑照常执行
        page.listPicking = false
    }

    // ── 编辑草稿（点卡片打开上浮编辑页，取消即丢弃）─────────
    property bool editing: false
    property var draft: null
    property bool draftIsNew: false
    property int draftIndex: -1
    property bool closing: false
    // 卡片状态点数据：引擎当前「已生效」的 uid 列表（红=停用 / 绿=运行中 / 蓝=待命）
    property var activeUids: []

    // 页面构造期不做任何取数：不启动「加载后自动枚举应用」的定时器，
    // 也不在构造中调用 Python 槽。等宿主把 backend 绑定
    // （PluginBackendBridge.get_backend(pluginId)）求值稳定、整页建好之后，
    // 再回到事件循环里取数——避免「构造中重入 Python/QML 边界」。
    Component.onCompleted: firstLoad.start()
    // backend 一到也不马上取数：同样推到页面完全建好之后（与 firstLoad 合并成一次）。
    onBackendChanged: { if (backend) firstLoad.restart() }

    function cur() {
        // 编辑页打开时，所有字段写进草稿；点「保存」才写回配置，取消即丢弃。
        if (page.editing && page.draft) return page.draft
        return (page.current >= 0 && page.current < page.rules.length) ? page.rules[page.current] : null
    }

    function cloneRule(r) {
        try { return JSON.parse(JSON.stringify(r)) } catch (e) { return r }
    }


    function reload() {
        if (!backend) return
        try { page.rules = JSON.parse(backend.getRulesJson() || "[]") } catch (e) { page.rules = [] }
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
        statusText = ""
    }

    function loadRule() {
        var r = page.cur()
        if (!r) return
        nameField.text = r.name || ""
        descField.text = r.description || ""
        enabledSwitch.checked = !!r.enabled
        revertSwitch.checked = !!r.revert
        // 兼容旧数据：以前是单个 ruleset，现在统一迁移成 rulesets 数组
        if (!r.rulesets || !r.rulesets.length) {
            r.rulesets = [ r.ruleset || {"enabled": false, "mode": "all", "reversed": false, "rules": []} ]
        }
        if (!r.rulesetMode) r.rulesetMode = "all"
        rsGroupMode.currentIndex = (r.rulesetMode === "any") ? 1 : 0
        var totalRules = 0
        for (var ri = 0; ri < r.rulesets.length; ri++)
            totalRules += (((r.rulesets[ri] || {}).rules) || []).length
        page.trigCount = (r.triggers || []).length
        page.ruleCount = totalRules
        page.actCount = (r.actions || []).length
        page.rsCount = r.rulesets.length
        page.trigVersion++
        page.rsVersion++          // 先让外层重算行数（内层 Repeater 因此建行）
        page.ruleVersion++        // 再让每一行回填字段
        page.actVersion++
    }

    function save() {
        if (!backend) return false
        var ok = backend.saveRulesJson(JSON.stringify(page.rules))
        statusText = ok ? "已保存（共 " + page.rules.length + " 条自动化）" : "保存失败（详见主程序日志）"
        if (ok) saveTimer.restart()
        return ok
    }

    // ── 卡片：右下角开关 & 右上角状态点 ────────────────────────
    function setRuleEnabled(i, on) {
        if (i < 0 || i >= page.rules.length) return
        // 用副本替换整个数组：让卡片的开关 / 状态点绑定重新求值
        var list = page.rules.slice()
        var item = page.cloneRule(list[i]) || {}
        item.enabled = !!on
        list[i] = item
        page.rules = list
        page.save()
    }

    function cardStateColor(ruleObj) {
        if (!ruleObj) return "#9e9e9e"
        if (!ruleObj.enabled) return "#e53935"            // 红：已停用
        var uids = page.activeUids || []
        for (var i = 0; i < uids.length; i++)
            if (uids[i] === ruleObj.uid) return "#43a047" // 绿：运行中（正在生效）
        return "#1e88e5"                                  // 蓝：待命（已启用、未生效）
    }

    // 轮询引擎「当前已生效」的自动化，驱动卡片绿点
    Timer {
        id: activePoll
        interval: 1000
        repeat: true
        running: !!backend
        onTriggered: {
            try { page.activeUids = JSON.parse(backend.activeRuleUidsJson() || "[]") }
            catch (e) { page.activeUids = [] }
        }
    }

    // ── 编辑页开合（草稿式：改动先落在草稿上）────────────────
    function openEditor(i) {
        if (i < 0 || i >= page.rules.length) return
        page.current = i
        page.draftIndex = i
        page.draftIsNew = false
        page.draft = page.cloneRule(page.rules[i])
        page.editing = true
        statusText = ""
        // 先只把面板建出来，数据留到下一个事件循环再填。
        // 否则 Repeater 会在「创建 delegate 的过程中」被要求换 Loader 组件、
        // 写字段，属于视图构建中途改数据，主程序会在这条路径上崩溃。
        editorDialog.open()
        Qt.callLater(page.loadRule)
    }

    function applyDraft() {
        if (page.draftIndex < 0 || page.draftIndex >= page.rules.length) return false
        var list = page.rules.slice()
        list[page.draftIndex] = page.draft
        page.rules = list
        return page.save()
    }

    function closeEditor(saveIt) {
        if (page.closing) return          // 面板收起时也会走到这里，防重入
        page.closing = true
        var ok = true
        if (saveIt) {
            ok = page.applyDraft()        // 保存失败就留在编辑页，别悄悄丢掉改动
        } else if (page.draftIsNew && page.draftIndex >= 0 && page.draftIndex < page.rules.length) {
            var keep = page.rules.slice()            // 新建后取消 → 不留空壳
            keep.splice(page.draftIndex, 1)
            page.rules = keep
            page.save()
        }
        if (ok) {
            page.editing = false
            page.draft = null
            page.draftIsNew = false
            page.draftIndex = -1
            page.current = -1
            editorDialog.close()
        }
        page.closing = false
    }

    function testDraft() {
        if (!backend) return
        var i = page.draftIndex
        if (!page.applyDraft()) return
        backend.fireRuleNow(i)
        statusText = "已执行一次（详情见主程序日志）"
    }

    function askDelete() {
        if (page.draftIndex < 0 || page.draftIndex >= page.rules.length) return
        var nm = page.rules[page.draftIndex].name || "未命名"
        confirmText.text = "确定要删除「" + nm + "」吗？删除后无法撤销。"
        confirmDialog.open()
    }

    function doDelete() {
        var i = page.draftIndex
        if (i >= 0 && i < page.rules.length) {
            var keep = page.rules.slice()
            keep.splice(i, 1)
            page.rules = keep
        }
        page.editing = false
        page.draft = null
        page.draftIsNew = false
        page.draftIndex = -1
        page.current = -1
        page.save()
        confirmDialog.close()
        editorDialog.close()
    }

    function addRule() {
        var fresh = {
            "uid": "", "name": "新自动化", "description": "", "enabled": true, "revert": false,
            "triggers": [{"type": "class_start", "p1": "", "p2": "", "p3": "", "p4": ""}],
            "rulesets": [{"enabled": false, "mode": "all", "reversed": false, "rules": []}],
            "rulesetMode": "all",
            "actions": [{"type": "set_config", "p1": "interactions.hide.state", "p2": "true", "p3": "", "p4": ""}]
        }
        // 注意：一律重新赋值一个新数组，不用原地 push/splice。
        // 原地改不会触发属性变更通知，而且会让 Repeater 在事件派发中途重建 item。
        var list = page.rules.slice()
        list.push(fresh)
        page.rules = list
        var i = list.length - 1
        page.current = i
        page.draftIndex = i
        page.draftIsNew = true
        page.draft = page.cloneRule(fresh)
        page.editing = true
        statusText = ""
        // 先只把面板建出来，数据留到下一个事件循环再填。
        // 否则 Repeater 会在「创建 delegate 的过程中」被要求换 Loader 组件、
        // 写字段，属于视图构建中途改数据，主程序会在这条路径上崩溃。
        editorDialog.open()
        Qt.callLater(page.loadRule)
    }

    function commit(key, value) {
        var r = page.cur()
        if (r) r[key] = value
    }

    // ── 卡片摘要与工具（全部只读，用来在卡片上说明每条自动化）──
    function labelOf(values, labels, v) {
        var i = values.indexOf(v)
        return i >= 0 ? labels[i] : String(v || "")
    }
    function keyLabelOf(key) {
        for (var i = 0; i < page.configKeys.length; i++)
            if (page.configKeys[i].key === key) return page.configKeys[i].label
        return String(key || "")
    }
    function appNameOf(target) {
        for (var i = 0; i < page.apps.length; i++)
            if (page.apps[i] && page.apps[i].target === target) return page.apps[i].name || target
        return String(target || "")
    }
    function detailOf(t) {
        if (!t) return ""
        switch (t.type) {
            case "time": return t.p1 || ""
            case "interval": return t.p1 ? (t.p1 + " 秒") : ""
            case "sys_change": return page.sysKeyLabels[Math.max(0, page.sysKeys.indexOf(t.p1))]
                + " 变化" + (t.p2 ? ("为 " + t.p2) : "")
            case "boot": return "开机后 " + (t.p1 || "120") + " 秒内"
            case "notif_new": return "收到系统通知" + (t.p1 ? (" · 应用含「" + t.p1 + "」") : "") + (t.p2 ? (" · 内容含「" + t.p2 + "」") : "")
            case "before_class": return t.p1 ? (t.p1 + " 秒前") : ""
            case "signal": return t.p1 || ""
            case "today_is": return page.labelOf(page.weekValues, page.weekLabels, t.p1)
            case "later_than": return t.p1 || ""
            case "current_subject":
            case "next_subject":
            case "prev_subject": return t.p1 || ""
            case "current_status": return page.labelOf(page.statusValues, page.statusLabels, t.p1)
            case "current_teacher":
            case "next_teacher": return t.p1 || ""
            case "foreground_window": return t.p1 || ""
            case "sys_setting": return page.sysKeyLabels[Math.max(0, page.sysKeys.indexOf(t.p1))]
                + " " + page.sysOpLabels[Math.max(0, page.sysOps.indexOf(t.p2))] + " " + (t.p3 || "")
            case "media": return page.mediaKeyLabels[Math.max(0, page.mediaKeys.indexOf(t.p1))]
                + " " + page.sysOpLabels[Math.max(0, page.sysOps.indexOf(t.p2))] + " " + (t.p3 || "")
            case "notif": return page.notifKeyLabels[Math.max(0, page.notifKeys.indexOf(t.p1))]
                + " " + page.notifOpLabels[Math.max(0, page.notifOps.indexOf(t.p2))] + " " + (t.p3 || "")
            case "flag_is": return t.p1 || ""
            case "run": return t.p1 || ""
            case "app": return (t.p4 === "close" ? "关闭 " : "打开 ") + page.appNameOf(t.p1)
            case "notify": return t.p1 || ""
            case "wait": return t.p1 ? (t.p1 + " 秒") : ""
            case "broadcast": return t.p1 || ""
            case "set_flag": return t.p1 || ""
            case "set_config": return page.keyLabelOf(t.p1)
            case "lock": return page.keyLabelOf(t.p1) + (t.p2 === "unlock" ? "（解锁）" : "（锁定）")
            case "open_settings": return page.settingsPageLabels[Math.max(0, page.settingsPages.indexOf(t.p1))]
            case "set_theme": return page.themeModeLabels[Math.max(0, page.themeModes.indexOf(t.p1))]
                + " · " + page.themeScopeLabels[Math.max(0, page.themeScopes.indexOf(t.p2))]
            case "power": return "电源：" + page.powerLabels[Math.max(0, page.powerModes.indexOf(t.p1))]
            case "volume": return "音量：" + page.volumeLabels[Math.max(0, page.volumeModes.indexOf(t.p1))]
                + (t.p1 === "set" ? (" " + (t.p2 || "50") + "%") : "")
            case "media": return "媒体控制：" + page.mediaActionLabels[Math.max(0, page.mediaActions.indexOf(t.p1))]
            case "sys_notify": return "发系统通知：" + (t.p1 || "")
            case "rollcall_start": return "随机点名开始"
            case "rollcall_picked": return "随机点名出结果后"
            case "rollcall_roll": return "随机点名 " + (t.p1 || "1") + " 人"
            case "rollcall_set":
            case "rollcall_config": return page.labelOf(page.rollcallKeys, page.rollcallLabels, t.p1)
                + " = " + (t.p2 || "")
            case "rollcall_close": return "关闭点名窗口"
            default: return ""
        }
    }
    function summarize(list, types, labels) {
        if (!list || !list.length) return "无"
        var out = []
        for (var i = 0; i < list.length; i++) {
            var t = list[i]
            if (!t) continue
            var name = page.labelOf(types, labels, t.type)
            var extra = page.detailOf(t)
            var s = extra ? (name + " " + extra) : name
            if (t.reversed) s = "非 " + s
            out.push(s)
        }
        return out.length ? out.join(" / ") : "无"
    }
    function trigSummary(r) { return page.summarize(r ? r.triggers : [], page.trigTypes, page.trigLabels) }
    function actSummary(r) { return page.summarize(r ? r.actions : [], page.actTypes, page.actLabels) }
    function cardTitle(r) {
        var n = (r && r.name) ? String(r.name) : "未命名"
        return (r && !r.enabled) ? (n + "（已停用）") : n
    }
    function cardDesc(r) {
        if (!r) return ""
        var out = []
        if (r.description) out.push(String(r.description))
        out.push("触发器：" + page.trigSummary(r))
        out.push("条件：" + page.rulesSummary(r))
        out.push("行动：" + page.actSummary(r))
        return out.join("\n")
    }

    function rulesSummary(r) {
        if (!r) return "无"
        var list = r.rulesets
        if (!list || !list.length) list = r.ruleset ? [r.ruleset] : []
        var on = []
        for (var i = 0; i < list.length; i++) if (list[i] && list[i].enabled) on.push(list[i])
        if (!on.length) return "无条件（直接执行）"
        var parts = []
        for (var j = 0; j < on.length; j++) {
            var rs = on[j]
            parts.push("规则集" + (j + 1) + "（" + ((rs.mode === "any") ? "任一满足" : "全部满足")
                       + "·" + (((rs.rules) || []).length) + "条）")
        }
        return parts.join((r.rulesetMode === "any") ? " 或 " : " 且 ")
    }

    // ── 已安装应用（「打开应用」行动的下拉来源）────────────────
    function ensureApps(force) {
        if (page.appsLoaded && !force) return
        if (!backend) return
        try {
            // 优先读主程序后台线程预先枚举好的缓存：瞬时返回，绝不阻塞图形线程
            var raw = force ? "" : backend.getCachedAppsJson()
            if (!raw || raw === "[]") {
                // 没有缓存时才同步枚举（只在用户明确打开「打开应用」下拉 / 点「刷新列表」时发生）
                raw = force ? backend.refreshInstalledAppsJson() : backend.getInstalledAppsJson()
            }
            var list = JSON.parse(raw || "[]")
            var targets = [], labels = []
            for (var i = 0; i < list.length; i++) {
                var a = list[i]
                if (!a || !a.target) continue
                targets.push(String(a.target))
                labels.push(String(a.name || a.target))
            }
            targets.push("")
            labels.push("（手动输入路径 / 网址）")
            page.apps = list
            page.appTargets = targets
            page.appLabels = labels
            page.appsLoaded = true
        } catch (e) {
            page.apps = []
            page.appTargets = [""]
            page.appLabels = ["（手动输入路径 / 网址）"]
            page.appsLoaded = false
        }
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
    function addRuleset() {
        var r = page.cur(); if (!r) return
        if (!r.rulesets) r.rulesets = []
        r.rulesets.push({"enabled": true, "mode": "all", "reversed": false, "rules": []})
        page.rsCount = r.rulesets.length
        page.rsVersion++      // 外层建新卡 → 内层据此建行
        page.ruleVersion++
    }
    function removeRuleset(i) {
        var r = page.cur(); if (!r || !r.rulesets) return
        if (r.rulesets.length <= 1) return          // 至少留一个
        r.rulesets.splice(i, 1)
        page.rsCount = r.rulesets.length
        page.rsVersion++
        page.ruleVersion++
    }
    function addRuleItem(ri) {
        var r = page.cur(); if (!r || !r.rulesets || !r.rulesets[ri]) return
        var rs = r.rulesets[ri]
        if (!rs.rules) rs.rules = []
        rs.rules.push({"type": "current_status", "p1": "class", "p2": "", "p3": "", "p4": "", "reversed": false})
        page.rsVersion++      // 该卡重算行数
        page.ruleVersion++    // 新行回填
    }
    function removeRuleItem(ri, i) {
        var r = page.cur(); if (!r || !r.rulesets || !r.rulesets[ri]) return
        var rs = r.rulesets[ri]
        if (!rs.rules) return
        rs.rules.splice(i, 1)
        page.rsVersion++
        page.ruleVersion++
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
            case "sys_change": return trigSysComp
            case "boot": return trigBootComp
            case "notif_new": return trigNotifComp
            case "before_class": return trigBeforeComp
            case "signal": return trigSignalComp
            case "alarm": return trigAlarmComp
            case "rollcall_start": return trigRollcallStartComp
            case "rollcall_picked": return trigRollcallPickedComp
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
            case "sys_setting": return ruleSysComp
            case "media": return ruleMediaComp
            case "notif": return ruleNotifComp
            case "flag_is": return ruleFlagComp
            case "current_teacher":
            case "next_teacher": return ruleTeacherComp
            case "rollcall_config": return ruleRollcallComp
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
            case "app": return actAppComp
            case "open_settings": return actOpenSettingsComp
            case "set_theme": return actSetThemeComp
            case "power": return actPowerComp
            case "volume": return actVolumeComp
            case "media": return actMediaComp
            case "sys_notify": return actSysNotifyComp
            case "rollcall_roll": return actRollcallRollComp
            case "rollcall_set": return actRollcallSetComp
            case "rollcall_close": return actRollcallCloseComp
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
        id: trigRollcallStartComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) { it = item }
            Text { text: "随机点名开始滚动时（无需参数）" }
        }
    }

    Component {
        id: trigRollcallPickedComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) { it = item }
            Text { text: "随机点名出结果后（无需参数）" }
        }
    }

    Component {
        id: trigTimeComp
        ColumnLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                var t = item.p1 || ""
                if (!/^\d{2}:\d{2}$/.test(t)) { t = "08:00"; item.p1 = t }
                timeF.setTime(t)
                weekBox.load(item)
                skipSw.checked = (item.p4 === "1")
                loading = false
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TimePicker {
                    id: timeF
                    Layout.preferredWidth: 150
                    use24Hour: true
                    onTimeChanged: if (!loading && it && time) it.p1 = time
                }
                Text { text: "星期" }
                WeekdayPicker { id: weekBox }
                Item { Layout.fillWidth: true }
            }
            Switch {
                id: skipSw
                text: "自动跳过非上课日（当天课表没有课程时不触发）"
                onToggled: if (!loading && it) it.p4 = (checked ? "1" : "")
            }
        }
    }

    Component {
        id: trigAlarmComp
        ColumnLayout {
            spacing: 6
            property var it: null
            property bool loading: false

            readonly property var soundLabels: ["系统提示音", "警告音", "询问音", "闹钟铃声", "自定义文件…"]
            readonly property var soundValues: ["", "exclamation", "question", "alarm", "custom"]

            function load(item) {
                it = item
                loading = true
                var t = item.p1 || ""
                if (!/^\d{2}:\d{2}$/.test(t)) { t = "07:00"; item.p1 = t }
                alarmTime.setTime(t)
                alarmWeek.load(item)
                alarmSkip.checked = (item.p4 === "1")
                var s = String(item.p3 || "")
                var idx = soundValues.indexOf(s)
                if (idx < 0) idx = s ? 4 : 0        // 不是预设值 → 当自定义文件
                soundCombo.currentIndex = idx
                customF.text = (idx === 4) ? s : ""
                loading = false
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TimePicker {
                    id: alarmTime
                    Layout.preferredWidth: 150
                    use24Hour: true
                    onTimeChanged: if (!loading && it && time) it.p1 = time
                }
                Text { text: "星期" }
                WeekdayPicker { id: alarmWeek }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { text: "铃音" }
                ComboBox {
                    id: soundCombo
                    Layout.preferredWidth: 140
                    model: soundLabels
                    onActivated: {
                        if (loading || !it) return
                        if (index === 4) it.p3 = (customF.text || "alarm")
                        else it.p3 = soundValues[index]
                    }
                }
                TextField {
                    id: customF
                    Layout.fillWidth: true
                    visible: soundCombo.currentIndex === 4
                    placeholderText: "自定义铃声文件（.wav）"
                    onTextEdited: if (it) it.p3 = text
                }
                Button {
                    text: "选择铃声…"
                    visible: soundCombo.currentIndex === 4
                    onClicked: {
                        var p = backend ? backend.pickSoundFile() : ""
                        if (!p) return
                        customF.text = p
                        if (it) it.p3 = p
                    }
                }
            }
            Switch {
                id: alarmSkip
                text: "自动跳过非上课日（当天课表没有课程时不响）"
                onToggled: if (!loading && it) it.p4 = (checked ? "1" : "")
            }
            Text {
                text: "到点会弹出「系统」级通知（标题 = 自动化名称）并响铃；不需要另外添加行动。"
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                opacity: 0.62
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(weekCombo, page.weekLabels, "选择星期")
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
                var t = item.p1 || ""
                if (!/^\d{2}:\d{2}$/.test(t)) { t = "08:00"; item.p1 = t }
                timeF.setTime(t)
            }
            TimePicker {
                id: timeF
                Layout.preferredWidth: 150
                use24Hour: true
                onTimeChanged: if (it && time) it.p1 = time
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(subCombo, page.subjects, "选择科目")
            }
            Text { text: "（在课表设置中维护科目）"; visible: page.subjects.length === 0; opacity: 0.62 }
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(stCombo, page.statusLabels, "选择时间状态")
            }
        }
    }

    Component {
        id: trigSysComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (!it.p1) it.p1 = "theme_apps"   // 补默认（p2 留空 = 任意变化）
                keyCombo.currentIndex = Math.max(0, page.sysKeys.indexOf(item.p1 || "theme_apps"))
                refresh()
                wantCombo.currentIndex = Math.max(0, page.sysValueOptions(item.p1 || "theme_apps").indexOf(item.p2 || "") + 1)
            }

            function refresh() {
                var k = it ? (it.p1 || "theme_apps") : "theme_apps"
                wantCombo.model = ["（任意变化）"].concat(page.sysValueLabels(k))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: keyCombo
                    Layout.fillWidth: true
                    model: page.sysKeyLabels
                    onActivated: {
                        if (!it) return
                        it.p1 = page.sysKeys[index]
                        it.p2 = ""
                        refresh()
                        wantCombo.currentIndex = 0
                    }
                }
                ComboBox {
                    id: wantCombo
                    Layout.fillWidth: true
                    model: ["（任意变化）"]
                    onActivated: if (it) it.p2 = (index === 0 ? "" : page.sysValueOptions(it.p1)[index - 1])
                }
            }
        }
    }

    Component {
        id: trigBootComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                if (!it.p1) it.p1 = "120"
                secF.text = it.p1
            }
            TextField {
                id: secF
                Layout.fillWidth: true
                placeholderText: "开机多少秒内算「刚开机」（默认 120）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    Component {
        id: trigNotifComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                page.ensureApps(false)
                rebuild()
                textF.text = item.p2 || ""
            }

            // 来源下拉：用「已安装应用列表」（去掉末尾的「手动输入路径」哨兵）
            function rebuild() {
                var all = page.appLabels || []
                var labels = all.slice(0, Math.max(0, all.length - 1))
                appCombo.model = ["（任意应用）"].concat(labels)
                var v = it ? String(it.p1 || "") : ""
                var i = labels.indexOf(v)
                appCombo.currentIndex = (v === "" ? 0 : (i >= 0 ? i + 1 : 0))
                customF.text = v
                customF.visible = (v !== "" && i < 0)
            }

            Connections {
                target: page
                function onAppLabelsChanged() { if (it) rebuild() }
            }
            Connections {
                target: page
                function onAppPickNonceChanged() {
                    if (!page.appPickValue || !it || page.appPickOwner !== it) return
                    var i = page.appTargets.indexOf(String(page.appPickValue))
                    it.p1 = (i >= 0 ? String(page.appLabels[i]) : String(page.appPickValue))
                    rebuild()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: appCombo
                    Layout.fillWidth: true
                    model: ["（任意应用）"]
                    onActivated: {
                        if (!it) return
                        it.p1 = (index === 0 ? "" : String(appCombo.model[index]))
                        customF.text = it.p1
                        customF.visible = false
                    }
                }
                Button {
                    text: "从列表选择…"
                    onClicked: {
                        page.appPickValue = ""
                        page.appPickOwner = it
                        page.appPicking = true
                    }
                }
            }
            TextField {
                id: customF
                Layout.fillWidth: true
                visible: false
                placeholderText: "或手输应用名（按「包含」匹配，可空 = 任意应用）"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: textF
                Layout.fillWidth: true
                placeholderText: "通知内容包含（可空 = 任意内容）"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: ruleMediaComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (!it.p1) it.p1 = "playing"
                if (!it.p2) it.p2 = "=="
                keyCombo.currentIndex = Math.max(0, page.mediaKeys.indexOf(it.p1))
                opCombo.currentIndex = Math.max(0, page.sysOps.indexOf(it.p2))
                if (it.p3 === undefined || it.p3 === null || it.p3 === "") it.p3 = (it.p1 === "playing" ? "yes" : "")
                valF.text = it.p3
                valF.visible = (it.p1 !== "playing")
                yesCombo.visible = (it.p1 === "playing")
                yesCombo.currentIndex = (it.p3 === "no" ? 1 : 0)
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: keyCombo
                    Layout.fillWidth: true
                    model: page.mediaKeyLabels
                    onActivated: {
                        if (!it) return
                        it.p1 = page.mediaKeys[index]
                        it.p3 = (it.p1 === "playing" ? "yes" : "")
                        valF.text = it.p3
                        valF.visible = (it.p1 !== "playing")
                        yesCombo.visible = (it.p1 === "playing")
                        yesCombo.currentIndex = 0
                    }
                }
                ComboBox {
                    id: opCombo
                    Layout.preferredWidth: 96
                    model: ["是", "不是"]
                    visible: (it && it.p1 === "playing")
                    onActivated: {
                        if (!it) return
                        it.p2 = (index === 0 ? "==" : "!=")
                        yesCombo.currentIndex = index
                    }
                }
                ComboBox {
                    id: yesCombo
                    Layout.preferredWidth: 96
                    model: ["在播放", "未播放"]
                    visible: (it && it.p1 === "playing")
                    onActivated: {
                        if (!it) return
                        it.p3 = (index === 0 ? "yes" : "no")
                    }
                }
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                visible: false
                placeholderText: "内容（按「包含」匹配，如 歌名片段 / 歌手）"
                onTextEdited: if (it) it.p3 = text
            }
        }
    }

    Component {
        id: ruleNotifComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                if (!it.p1) it.p1 = "app"
                if (!it.p2) it.p2 = "=="
                if (!it.p4) it.p4 = "60"
                keyCombo.currentIndex = Math.max(0, page.notifKeys.indexOf(it.p1))
                opCombo.currentIndex = Math.max(0, page.notifOps.indexOf(it.p2))
                valF.text = it.p3 || ""
                winF.text = it.p4
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: keyCombo
                    Layout.fillWidth: true
                    model: page.notifKeyLabels
                    onActivated: if (it) it.p1 = page.notifKeys[index]
                }
                ComboBox {
                    id: opCombo
                    Layout.preferredWidth: 96
                    model: page.notifOpLabels
                    onActivated: if (it) it.p2 = page.notifOps[index]
                }
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                placeholderText: "匹配内容"
                onTextEdited: if (it) it.p3 = text
            }
            TextField {
                id: winF
                Layout.fillWidth: true
                placeholderText: "最近多少秒内（默认 60）"
                onTextEdited: if (it) it.p4 = text
            }
        }
    }

    Component {
        id: ruleSysComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (!it.p1) it.p1 = "theme_apps"   // 补默认
                if (!it.p2) it.p2 = "=="           // 补默认
                keyCombo.currentIndex = Math.max(0, page.sysKeys.indexOf(item.p1 || "theme_apps"))
                opCombo.currentIndex = Math.max(0, page.sysOps.indexOf(item.p2 || "=="))
                refreshValue()
            }

            function refreshValue() {
                var k = it ? (it.p1 || "theme_apps") : "theme_apps"
                var num = page.sysIsNumber(k)
                valueCombo.visible = !num
                valF.visible = num
                var opts = page.sysValueOptions(k)
                valueCombo.model = page.sysValueLabels(k)
                var i = opts.indexOf(it ? (it.p3 || "") : "")
                valueCombo.currentIndex = i >= 0 ? i : 0
                if (num) { valF.text = it ? (it.p3 || "") : "" }
                else if (it && it.p3 !== opts[valueCombo.currentIndex]) { it.p3 = opts[valueCombo.currentIndex] || "" }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: keyCombo
                    Layout.fillWidth: true
                    model: page.sysKeyLabels
                    onActivated: {
                        if (!it) return
                        it.p1 = page.sysKeys[index]
                        it.p3 = ""
                        refreshValue()
                    }
                }
                ComboBox {
                    id: opCombo
                    Layout.preferredWidth: 110
                    model: page.sysOpLabels
                    onActivated: if (it) it.p2 = page.sysOps[index]
                }
            }
            ComboBox {
                id: valueCombo
                Layout.fillWidth: true
                onActivated: if (it) it.p3 = page.sysValueOptions(it.p1)[index]
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                visible: false
                placeholderText: "数值（如 30）"
                onTextEdited: if (it) it.p3 = text
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
        id: ruleRollcallComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false

            function keyOf() { return page.rollcallKeys[rrKey.currentIndex] || page.rollcallKeys[0] }
            function isBoolKey() { return page.rollcallIsBool(keyOf()) }

            function write() {
                if (loading || !it)
                    return
                it.p1 = keyOf()
                it.p2 = isBoolKey() ? (rrBool.checked ? "true" : "false") : String(Math.round(rrNum.value))
            }

            function load(item) {
                it = item
                loading = true
                var idx = page.rollcallKeys.indexOf(item.p1)
                rrKey.currentIndex = idx >= 0 ? idx : 0
                var raw = String(item.p2 === undefined || item.p2 === null ? "" : item.p2).trim().toLowerCase()
                rrBool.checked = ["1", "true", "on", "yes", "是", "开", "开启"].indexOf(raw) >= 0
                rrNum.value = parseInt(raw) || 0
                loading = false
            }

            Text { text: "随机点名" }
            ComboBox {
                id: rrKey
                Layout.preferredWidth: 180
                model: page.rollcallLabels
                onActivated: write()
            }
            Text { text: "是" }
            Switch {
                id: rrBool
                visible: isBoolKey()
                onToggled: write()
            }
            SpinBox {
                id: rrNum
                Layout.preferredWidth: 110
                from: 0; to: 3600; stepSize: 1; editable: true
                visible: !isBoolKey()
                onValueChanged: write()
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(teaCombo, page.teachers, "选择教师")
            }
            Text { text: "（在课表设置中维护教师）"; visible: page.teachers.length === 0; opacity: 0.62 }
        }
    }

    // ══════════════ 行动字段组件 ══════════════
    Component {
        id: actAppComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (item.p4 !== "close") item.p4 = "open"
                modeCombo.currentIndex = (item.p4 === "close" ? 1 : 0)
                refreshSub()
            }

            function refreshSub() {
                if (!it) return
                sub.sourceComponent = (it.p4 === "close" ? actCloseComp : actLaunchComp)
                if (sub.item && sub.item.load) sub.item.load(it)
            }

            ComboBox {
                id: modeCombo
                Layout.fillWidth: true
                model: ["打开应用", "关闭应用"]
                onActivated: {
                    if (!it) return
                    it.p4 = (index === 1 ? "close" : "open")
                    refreshSub()
                }
            }
            Loader {
                id: sub
                Layout.fillWidth: true
            }
        }
    }

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
        id: actRollcallRollComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false
            function load(item) {
                it = item
                loading = true
                cntSpin.value = parseInt(item.p1 || "1")
                loading = false
            }
            SpinBox {
                id: cntSpin
                Layout.preferredWidth: 120
                from: 1; to: 5; stepSize: 1; editable: true
                onValueChanged: if (!loading && it) it.p1 = String(Math.round(value))
            }
            Text { text: "人（一次点名抽几人）" }
        }
    }

    Component {
        id: actRollcallSetComp
        RowLayout {
            spacing: 6
            property var it: null
            property bool loading: false

            function keyOf() { return page.rollcallKeys[rcKey.currentIndex] || page.rollcallKeys[0] }
            function isBoolKey() { return page.rollcallIsBool(keyOf()) }

            function write() {
                if (loading || !it)
                    return
                it.p1 = keyOf()
                it.p2 = isBoolKey() ? (rcBool.checked ? "true" : "false") : String(Math.round(rcNum.value))
            }

            function load(item) {
                it = item
                loading = true
                var idx = page.rollcallKeys.indexOf(item.p1)
                rcKey.currentIndex = idx >= 0 ? idx : 0
                var raw = String(item.p2 === undefined || item.p2 === null ? "" : item.p2).trim().toLowerCase()
                rcBool.checked = ["1", "true", "on", "yes", "是", "开", "开启"].indexOf(raw) >= 0
                rcNum.value = parseInt(raw) || 0
                loading = false
            }

            ComboBox {
                id: rcKey
                Layout.preferredWidth: 180
                model: page.rollcallLabels
                onActivated: write()
            }
            Switch {
                id: rcBool
                text: "开"
                visible: isBoolKey()
                onToggled: write()
            }
            SpinBox {
                id: rcNum
                Layout.preferredWidth: 110
                from: 0; to: 3600; stepSize: 1; editable: true
                visible: !isBoolKey()
                onValueChanged: write()
            }
        }
    }

    Component {
        id: actRollcallCloseComp
        RowLayout {
            spacing: 6
            property var it: null
            function load(item) { it = item }
            Text { text: "关闭点名结果窗口（滚动中或已定格都能关）" }
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(keyCombo, page.keyLabels, "选择配置项")
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(themeCombo, page.themeNames, "选择主题")
            }
            ComboBox {
                id: anchorCombo
                Layout.fillWidth: true
                visible: meta && meta.kind === "anchor"
                model: page.anchorLabels
                onActivated: if (!loading && it) it.p2 = page.anchorValues[index]
            }
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(anchorCombo, page.anchorLabels, "选择锚点")
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(presetCombo, page.presets, "选择预设方案")
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
            Button {
                text: "列表…"
                implicitWidth: 68
                implicitHeight: 30
                onClicked: page.openListPick(keyCombo, page.keyLabels, "选择配置项")
            }
            ComboBox {
                id: lockCombo
                Layout.preferredWidth: 100
                model: page.lockLabels
                onActivated: if (it) it.p2 = page.lockValues[index]
            }
        }
    }

    Component {
        id: actCloseComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                exeF.text = item.p1 || ""
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                TextField {
                    id: exeF
                    Layout.fillWidth: true
                    placeholderText: "要关闭的程序（进程名或 .exe 路径，例如 chrome.exe）"
                    onTextEdited: if (it) it.p1 = text
                }
                Button {
                    text: "从列表选择…"
                    onClicked: {
                        page.appPickValue = exeF.text
                        page.appPickOwner = it
                        page.appPicking = true
                    }
                }
                Button {
                    text: "选择程序…"
                    onClicked: {
                        var p = backend ? backend.pickExeFile() : ""
                        if (!p) return
                        exeF.text = p
                        if (it) it.p1 = p
                    }
                }
            }
            Connections {
                target: page
                function onAppPickNonceChanged() {
                    if (!page.appPickValue || !it || page.appPickOwner !== it) return
                    exeF.text = page.appPickValue
                    it.p1 = page.appPickValue
                }
            }
            Text {
                text: "按进程名强制结束（taskkill /F）。UWP / 商店应用没有独立进程名，关不掉。"
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                opacity: 0.62
            }
        }
    }

    Component {
        id: actMediaComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                if (!it.p1) it.p1 = "toggle"
                cmdCombo.currentIndex = Math.max(0, page.mediaActions.indexOf(it.p1))
            }
            ComboBox {
                id: cmdCombo
                Layout.fillWidth: true
                model: page.mediaActionLabels
                onActivated: if (it) it.p1 = page.mediaActions[index]
            }
        }
    }

    Component {
        id: actSysNotifyComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                titleF.text = item.p1 || ""
                bodyF.text = item.p2 || ""
            }
            TextField {
                id: titleF
                Layout.fillWidth: true
                placeholderText: "通知标题"
                onTextEdited: if (it) it.p1 = text
            }
            TextField {
                id: bodyF
                Layout.fillWidth: true
                placeholderText: "通知内容"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: actPowerComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                if (!it.p1) it.p1 = "poweroff"
                modeCombo.currentIndex = Math.max(0, page.powerModes.indexOf(it.p1))
            }
            ComboBox {
                id: modeCombo
                Layout.fillWidth: true
                model: page.powerLabels
                onActivated: if (it) it.p1 = page.powerModes[index]
            }
        }
    }

    Component {
        id: actVolumeComp
        ColumnLayout {
            spacing: 6
            property var it: null
            function load(item) {
                it = item
                if (!it.p1) it.p1 = "up"
                modeCombo.currentIndex = Math.max(0, page.volumeModes.indexOf(it.p1))
                if (!it.p2) it.p2 = "50"
                valF.text = it.p2
                valF.visible = (it.p1 === "set")
            }
            ComboBox {
                id: modeCombo
                Layout.fillWidth: true
                model: page.volumeLabels
                onActivated: {
                    if (!it) return
                    it.p1 = page.volumeModes[index]
                    valF.visible = (it.p1 === "set")
                }
            }
            TextField {
                id: valF
                Layout.fillWidth: true
                visible: false
                placeholderText: "音量 0-100"
                onTextEdited: if (it) it.p2 = text
            }
        }
    }

    Component {
        id: actSetThemeComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (!it.p1) it.p1 = "dark"      // 补默认
                if (!it.p2) it.p2 = "both"      // 补默认
                modeCombo.currentIndex = Math.max(0, page.themeModes.indexOf(item.p1 || "dark"))
                scopeCombo.currentIndex = Math.max(0, page.themeScopes.indexOf(item.p2 || "both"))
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: modeCombo
                    Layout.fillWidth: true
                    model: page.themeModeLabels
                    onActivated: if (it) it.p1 = page.themeModes[index]
                }
                ComboBox {
                    id: scopeCombo
                    Layout.fillWidth: true
                    model: page.themeScopeLabels
                    onActivated: if (it) it.p2 = page.themeScopes[index]
                }
            }
        }
    }

    Component {
        id: actOpenSettingsComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                if (!it.p1) it.p1 = "personalization"   // 补默认：显示即已存
                var t = item.p1 || "personalization"
                var i = page.settingsPages.indexOf(t)
                pageCombo.currentIndex = i >= 0 ? i : 0
                manualF.text = t
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: pageCombo
                    Layout.fillWidth: true
                    model: page.settingsPageLabels
                    onActivated: {
                        if (!it) return
                        it.p1 = page.settingsPages[index]
                        manualF.text = it.p1
                    }
                }
            }
            TextField {
                id: manualF
                Layout.fillWidth: true
                placeholderText: "或手输页 id（如 colors / display / bluetooth）"
                onTextEdited: if (it) it.p1 = text
            }
        }
    }

    Component {
        id: actLaunchComp
        ColumnLayout {
            spacing: 6
            property var it: null

            function load(item) {
                it = item
                page.ensureApps(false)
                var t = item.p1 || ""
                var i = page.appTargets.indexOf(t)
                appCombo.currentIndex = i >= 0 ? i : Math.max(0, page.appTargets.length - 1)
                manualF.text = t
                argsF.text = item.p2 || ""
                cwdF.text = item.p3 || ""
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                ComboBox {
                    id: appCombo
                    Layout.fillWidth: true
                    model: page.appLabels
                    onActivated: {
                        if (index >= page.appTargets.length - 1) return   // 选中「手动输入」时不动已有内容
                        var t = page.appTargets[index]
                        manualF.text = t
                        if (it) it.p1 = t
                    }
                }
                Button {
                    text: "从列表选择…"
                    onClicked: {
                        page.appPickValue = manualF.text
                        page.appPickOwner = it
                        page.appPicking = true
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                TextField {
                    id: manualF
                    Layout.fillWidth: true
                    placeholderText: "应用路径 / 网址 / shell:AppsFolder\\…（上面下拉选，或在这里手输）"
                    onTextEdited: if (it) it.p1 = text
                }
                Connections {
                    target: page
                    function onAppPickNonceChanged() {
                        if (!page.appPickValue || !it || page.appPickOwner !== it) return
                        it.p1 = page.appPickValue
                        load(it)                     // 整行回填：下拉 + 程序框 + 参数 + 目录
                        var v = String(page.appPickValue)
                        if (v.toLowerCase().slice(-4) === ".exe" && !(it.p3 || "")) {
                            var k = v.lastIndexOf("\\")
                            if (k > 0) { cwdF.text = v.substring(0, k); it.p3 = cwdF.text }
                        }
                    }
                }
                Button {
                    text: "浏览…"
                    onClicked: {
                        var p = backend ? backend.pickExeFile() : ""
                        if (!p) return
                        manualF.text = p
                        if (!it) return
                        it.p1 = p
                        // 选了 .exe 就把它所在目录填进工作目录（工作目录原本为空时）
                        var k = p.lastIndexOf("\\")
                        if (k > 0 && !(it.p3 || "")) {
                            var dir = p.substring(0, k)
                            cwdF.text = dir
                            it.p3 = dir
                        }
                    }
                }
                TextField {
                    id: argsF
                    Layout.preferredWidth: 150
                    placeholderText: "启动参数"
                    onTextEdited: if (it) it.p2 = text
                }
                Button {
                    text: "试运行"
                    onClicked: if (backend) backend.launchApp(manualF.text, argsF.text, cwdF.text)
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                TextField {
                    id: cwdF
                    Layout.fillWidth: true
                    placeholderText: "工作目录（留空 = 应用自身目录）"
                    onTextEdited: if (it) it.p3 = text
                }
                Button {
                    text: "选择目录…"
                    onClicked: {
                        var d = backend ? backend.pickFolder() : ""
                        if (!d) return
                        cwdF.text = d
                        if (it) it.p3 = d
                    }
                }
            }
        }
    }

    // ══════════════ 界面 ══════════════
    SettingsLayout {
        width: parent.width
        spacing: 12

        Frame {
            Layout.fillWidth: true
            radius: page.cardRadius

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        typography: Typography.BodyStrong
                        text: "自动化"
                        Layout.fillWidth: true
                    }
                    Button { text: "刷新"; onClicked: Qt.callLater(page.reload) }
                }
                Text {
                    text: "触发器触发 → 规则集过滤 → 依次执行行动；开启「恢复」后，逆事件（如下课）或规则集不再满足时会自动还原被修改的配置。点任意卡片从下方拉出编辑页，或点「＋」新建。"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: page.statusText.length > 0
            text: page.statusText
            opacity: 0.62
            wrapMode: Text.Wrap
        }

        Text {
            id: emptyHint
            Layout.fillWidth: true
            visible: page.rules.length === 0
            opacity: 0.62
            wrapMode: Text.Wrap
            text: "还没有自动化规则，点上方「新建自动化」创建第一条。\n例如「上课隐藏小组件并自动恢复」：触发器选「上课时」，行动选「设置配置项」→「隐藏小组件」→ 开，再打开「恢复」开关，下课时即自动还原。"
        }

        Flow {
            id: cardFlow
            Layout.fillWidth: true
            spacing: 14

            // 每条自动化一张大卡片：状态圆点 + 名称 + 触发器/行动摘要
            Repeater {
                model: page.rules.length
                delegate: Frame {
                    id: ruleCard
                    property var ruleObj: page.rules[index]
                    width: page.cardWidth
                    height: page.cardHeight
                    radius: page.cardRadius
                    hoverable: true

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        // 推迟到本次点击派发结束再执行：否则会一边派发一边重建列表 item。
                        // 直接传下标，不闭包捕获委托作用域。
                        onClicked: Qt.callLater(page.openEditor, index)
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        anchors.topMargin: 10
                        anchors.bottomMargin: 10
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.alignment: Qt.AlignTop
                            spacing: 8
                            Text {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                typography: Typography.BodyStrong
                                text: page.cardTitle(ruleCard.ruleObj)
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                Layout.preferredWidth: 10
                                Layout.preferredHeight: 10
                                Layout.alignment: Qt.AlignVCenter
                                radius: 5
                                color: page.cardStateColor(ruleCard.ruleObj)
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.alignment: Qt.AlignTop
                            Layout.bottomMargin: 26
                            typography: Typography.Caption
                            opacity: 0.75
                            text: page.cardDesc(ruleCard.ruleObj)
                            wrapMode: Text.WordWrap
                            elide: Text.ElideRight
                            maximumLineCount: 4
                            verticalAlignment: Text.AlignTop
                        }
                    }

                    Switch {
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        anchors.rightMargin: 10
                        anchors.bottomMargin: 6
                        checked: !!(ruleCard.ruleObj && ruleCard.ruleObj.enabled)
                        onToggled: page.setRuleEnabled(index, checked)
                    }
                }
            }

            // 新建卡片：和规则卡片一样大，放在最后
            Frame {
                id: newCard
                width: page.cardWidth
                height: page.cardHeight
                radius: page.cardRadius
                hoverable: true
                color: newCard.hovered ? Theme.currentTheme.colors.controlSecondaryColor
                                       : Theme.currentTheme.colors.cardSecondaryColor
                border.color: newCard.hovered ? Utils.primaryColor
                                              : Theme.currentTheme.colors.cardBorderColor

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Qt.callLater(page.addRule)
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "＋"
                        font.pixelSize: 30
                        color: Utils.primaryColor
                    }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        typography: Typography.Body
                        text: "新建自动化"
                    }
                }
            }
        }
    }

    // ══════════════ 编辑页：从下方向上拉出，盖住插件页原来的区域 ══════════════
    Item {
        // 编辑面板刻意不用 Popup：
        // Popup.open() 会把内容重父级到窗口 Overlay 上并顺带跑几何/布局，而这块内容很大
        // （三张卡 + 三个 Repeater + 三个 Loader），宽高又绑在 Overlay.overlay 上——
        // 等于「一边被搬进 overlay、一边读 overlay」。实测这就是一点击就崩、
        // 且崩溃偏移每次都相同的现场。改成本页内的普通 Item，彻底不进那套机制。
        id: editorDialog
        // 宽度跟 parent（横向不会造成循环），高度只跟窗口走。
        // 之前 height 用了 parent.height，而宿主内容区的高度又由子项撑开，
        // 于是「面板高度 ↔ 父项高度」互相依赖，滚动位置被反复重算：
        // 现象就是快速下滑时闪一下又弹回去、最后一张卡永远够不到。
        // 锚定顶部与左右、高度用显式值：
        // 高度一旦写 parent.height 就会和「宿主内容区高度由子项撑开」互相依赖，
        // 触发滚动回弹；而完全不锚定又会让面板回到布局流、被排到卡片列表下面，
        // 于是盖不住卡片。这里两者兼顾。
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        // 等比自适应：面板高度 = 窗口高 × 1.06。
        //   · 跟窗口等比缩放（放大窗口 → 面板与卡片一起变大）
        //   · 多出的 6% 让底边必然落在窗口之外，Sheet 底边永远看不见
        //   · 不要再用「硬凑的边距」去实现探出，那样会把内部 ScrollView 压扁
        // 配套：ScrollView 设了 bottomPadding 70，正好盖住这 6%，最后一项仍滚得到。
        height: (page.Window && page.Window.height ? page.Window.height : 640) * 1.06
        z: 1000

        // 关闭时不能立刻隐藏：那张纸还要往下滑 200ms，一隐藏动画就白做了。
        // 所以关掉之后再保留可见 260ms。
        property bool closing: false
        visible: page.editing || closing

        Connections {
            target: page
            function onEditingChanged() {
                if (page.editing) {
                    editorDialog.closing = false
                } else {
                    editorDialog.closing = true
                    closeHold.restart()
                }
            }
        }

        Timer {
            id: closeHold
            interval: 260
            onTriggered: editorDialog.closing = false
        }

        // 保持原有调用方式，openEditor / addRule 一行都不用改
        function open() { page.editing = true }
        function close() { page.editing = false }

        // 遮罩：淡入淡出（原来由 Popup 自带的背景承担）
        Rectangle {
            anchors.fill: parent
            color: "#66000000"
            opacity: page.editing ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
        }

        Rectangle {
            // 面板 = 一张「从下方升起的卡片」：四周留边距 + 圆角 + 滑入动画。
            // 里面再放三张模块卡（触发器 / 规则集 / 行动），层级和卡片列表页保持一致。
            id: sheet
            width: parent.width - 32
            // 高度封顶到一个窗口：内容区可滚动，不封顶的话面板会比视口还高，
            // 底部的按钮就会被挤到看不见的地方。
            height: parent.height - 32      // 跟随面板（窗口 × 1.06），底边一起探出屏幕
            x: 16
            radius: page.cardRadius
            // 颜色一律跟随主程序主题，不写死颜色值。
            // （试过写死浅灰 #F1F2F4：白卡片叠在白面板上对比度太低，设置项看不清。）
            color: Theme.currentTheme.colors.backgroundAcrylicColor
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.windowBorderColor

            // 收起时停在屏幕外，展开时升到 y = 16
            y: page.editing ? 16 : parent.height
            Behavior on y {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 22
                // 四边统一 22：内容铺满整张纸，随窗口等比变大。
                // （探出的那 6% 交给 ScrollView 的 bottomPadding 处理，不在这里挤内容。）
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text {
                        Layout.fillWidth: true
                        typography: Typography.Subtitle
                        text: page.draftIsNew ? "新建自动化" : "编辑自动化"
                    }
                    Text {
                        typography: Typography.Caption
                        opacity: 0.7
                        text: page.statusText
                    }
                }

                RowLayout {
                    // 按钮行放在页头下方，而不是面板底部。
                    // 原因：设置页的内容区本身可滚动，面板底部会落到视口之外，
                    // 按钮就"看不见"了（之前找不到删除按钮就是这个原因）。
                    Layout.fillWidth: true
                    spacing: 8
                    Button {
                        text: page.draftIsNew ? "放弃新建" : "删除此自动化"
                        flat: true
                        contentItem: Text {
                            text: parent.text
                            color: page.draftIsNew ? "#8a8a8a" : "#d13438"
                            font: parent.font
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: page.draftIsNew ? page.closeEditor(false) : page.askDelete()
                    }
                    Button { text: "测试执行"; onClicked: page.testDraft() }
                    Item { Layout.fillWidth: true }
                    Button { text: "取消"; onClicked: page.closeEditor(false) }
                    Button { text: "保存"; highlighted: true; onClicked: page.closeEditor(true) }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    bottomPadding: 70          // 盖住面板探出屏幕的那 6%，最后一项也滚得到
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    ColumnLayout {
                        width: sheet.width - 44 - 14
                        spacing: 12

                        SettingCard {
                            Layout.fillWidth: true
                            title: qsTr("提示")
                            description: qsTr("未开启「恢复」的自动化只会执行一次，执行完毕后会自动停用。需要反复触发请开启「恢复」。")
                        }

                        Frame {
                            Layout.fillWidth: true
                            radius: page.cardRadius

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12

                                Text {
                                    typography: Typography.BodyStrong
                                    text: "基础设置"
                                }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        Text { text: "名称"; Layout.preferredWidth: 36 }
                                        TextField {
                                            id: nameField
                                            Layout.fillWidth: true
                                            Layout.preferredWidth: 140
                                            placeholderText: "自动化名称"
                                            onTextEdited: page.commit("name", text)
                                        }
                                        Text { text: "描述"; Layout.preferredWidth: 36 }
                                        TextField {
                                            id: descField
                                            Layout.fillWidth: true
                                            Layout.preferredWidth: 180
                                            placeholderText: "显示在卡片上的说明（可空）"
                                            onTextEdited: page.commit("description", text)
                                        }
                                        Switch { id: enabledSwitch; text: "启用"; onToggled: page.commit("enabled", checked) }
                                        Switch { id: revertSwitch; text: "恢复"; onToggled: page.commit("revert", checked) }
                                    }
                            }
                        }

                    Frame {
                        Layout.fillWidth: true
                        radius: page.cardRadius

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 12

                            Text {
                                typography: Typography.BodyStrong
                                text: "触发器（任一触发即可）"
                            }
                            Text {
                                text: "定时、间隔、上课/下课/课间/放学/状态变化、上课前、应用启动、收到信号。"
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

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
                                                    trigType.currentIndex = Math.max(0, page.trigTypes.indexOf(obj.type || ""))
                                                    refreshFields()
                                                }
                                                function refreshFields() {
                                                    if (obj && trigFld.item && trigFld.item.load) trigFld.item.load(obj)
                                                }
                                                // 刻意不在构造期 initRow()：初始化统一由上面
                                                // 那次延后的版本号变更（onVerChanged）驱动，
                                                // 保证发生在 delegate 建好之后。

                                                ComboBox {
                                                    id: trigType
                                                    Layout.preferredWidth: 170
                                                    model: page.trigLabels
                                                    onActivated: {
                                                        var r = page.cur(); if (!r || !r.triggers) return
                                                        r.triggers[trigRow.idx] = {"type": page.trigTypes[index], "p1": "", "p2": "", "p3": "", "p4": ""}
                                                        trigRow.obj = r.triggers[trigRow.idx]
                                                    }
                                                }
                                                Loader {
                                                    id: trigFld
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
                    }

                    Frame {
                        Layout.fillWidth: true
                        radius: page.cardRadius

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 12

                            Text {
                                typography: Typography.BodyStrong
                                text: "规则集（条件，满足才执行）"
                            }
                            Text {
                                text: "规则集关闭时无条件执行；开启后按下方规则过滤。"
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8
                                            Text { text: "多个规则集之间" }
                                            ComboBox {
                                                id: rsGroupMode
                                                Layout.preferredWidth: 130
                                                model: ["全部满足", "满足其一"]
                                                onActivated: {
                                                    var r = page.cur()
                                                    if (r) r.rulesetMode = (index === 1 ? "any" : "all")
                                                }
                                            }
                                            Item { Layout.fillWidth: true }
                                            Button { text: "+ 添加规则集"; onClicked: page.addRuleset() }
                                        }

                                        Repeater {
                                            model: page.rsCount
                                            delegate: Frame {
                                                id: rsRow
                                                Layout.fillWidth: true
                                                radius: page.cardRadius
                                                property int idx: index
                                                property int ver: page.rsVersion
                                                property int rowCount: 0
                                                property var obj: null
                                                onVerChanged: sync()
                                                // 刻意不在构造期读数据/动数据：初始化统一由
                                                // rsVersion 变更驱动，保证发生在 delegate 建好之后。

                                                function rsArr() {
                                                    var r = page.cur()
                                                    if (!r || !r.rulesets) return null
                                                    return (idx < r.rulesets.length) ? r.rulesets[idx] : null
                                                }
                                                function sync() {
                                                    obj = rsArr()
                                                    if (!obj) { rowCount = 0; return }
                                                    rsEnabled.checked = !!obj.enabled
                                                    rsModeC.currentIndex = (obj.mode === "any") ? 1 : 0
                                                    rsReversed.checked = !!obj.reversed
                                                    rowCount = (obj.rules || []).length
                                                }

                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    spacing: 6

                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 8
                                                        Text {
                                                            typography: Typography.BodyStrong
                                                            text: "规则集 " + (rsRow.idx + 1)
                                                        }
                                                        Switch {
                                                            id: rsEnabled
                                                            text: "启用"
                                                            onToggled: { var o = rsRow.rsArr(); if (o) o.enabled = checked }
                                                        }
                                                        ComboBox {
                                                            id: rsModeC
                                                            Layout.preferredWidth: 120
                                                            model: ["全部满足", "任一满足"]
                                                            onActivated: { var o = rsRow.rsArr(); if (o) o.mode = (index === 1 ? "any" : "all") }
                                                        }
                                                        Switch {
                                                            id: rsReversed
                                                            text: "取反"
                                                            onToggled: { var o = rsRow.rsArr(); if (o) o.reversed = checked }
                                                        }
                                                        Item { Layout.fillWidth: true }
                                                        Button {
                                                            text: "移除该规则集"
                                                            implicitHeight: 30
                                                            enabled: page.rsCount > 1
                                                            onClicked: page.removeRuleset(rsRow.idx)
                                                        }
                                                    }

                                                    Repeater {
                                                        model: rsRow.rowCount
                                                        delegate: RowLayout {
                                                            id: ruleRow
                                                            Layout.fillWidth: true
                                                            spacing: 6
                                                            property int idx: index
                                                            property int ver: page.ruleVersion
                                                            property var obj: null
                                                            onVerChanged: initRow()

                                                            function arr() {
                                                                var o = rsRow.rsArr()
                                                                return o ? (o.rules || []) : []
                                                            }
                                                            function initRow() {
                                                                var a = arr()
                                                                if (idx >= a.length) { obj = null; return }
                                                                obj = a[idx]
                                                                ruleType.currentIndex = Math.max(0, page.ruleTypes.indexOf(obj.type || ""))
                                                                revSw.checked = !!obj.reversed
                                                                refreshFields()
                                                            }
                                                            function refreshFields() {
                                                                if (obj && ruleFld.item && ruleFld.item.load) ruleFld.item.load(obj)
                                                            }
                                                            // 同样：构造期不动数据，等 ruleVersion 变更。

                                                            ComboBox {
                                                                id: ruleType
                                                                Layout.preferredWidth: 170
                                                                model: page.ruleLabels
                                                                onActivated: {
                                                                    var o = rsRow.rsArr(); if (!o) return
                                                                    if (!o.rules) o.rules = []
                                                                    o.rules[ruleRow.idx] = {"type": page.ruleTypes[index], "p1": "", "p2": "", "p3": "", "p4": "", "reversed": false}
                                                                    ruleRow.obj = o.rules[ruleRow.idx]
                                                                    revSw.checked = false
                                                                }
                                                            }
                                                            Loader {
                                                                id: ruleFld
                                                                Layout.fillWidth: true
                                                                sourceComponent: page.ruleFieldComp(ruleRow.obj ? ruleRow.obj.type : "")
                                                                onLoaded: ruleRow.refreshFields()
                                                            }
                                                            Switch {
                                                                id: revSw
                                                                text: "取反"
                                                                onToggled: if (obj) obj.reversed = checked
                                                            }
                                                            Button {
                                                                text: "移除"
                                                                implicitWidth: 52
                                                                implicitHeight: 30
                                                                onClicked: page.removeRuleItem(rsRow.idx, ruleRow.idx)
                                                            }
                                                        }
                                                    }
                                                    Button { text: "+ 添加规则"; onClicked: page.addRuleItem(rsRow.idx) }
                                                }
                                            }
                                        }
                                    }
                        }
                    }

                    Frame {
                        Layout.fillWidth: true
                        radius: page.cardRadius

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 12

                            Text {
                                typography: Typography.BodyStrong
                                text: "行动（顺序执行，可排序）"
                            }
                            Text {
                                text: "运行命令、显示提醒、打开应用、等待、广播信号、设标志、设置配置项、锁定配置项、重启主程序。"
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

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
                                                    actType.currentIndex = Math.max(0, page.actTypes.indexOf(obj.type || ""))
                                                    refreshFields()
                                                }
                                                function refreshFields() {
                                                    if (obj && actFld.item && actFld.item.load) actFld.item.load(obj)
                                                }
                                                // 刻意不在构造期 initRow()：初始化统一由上面
                                                // 那次延后的版本号变更（onVerChanged）驱动，
                                                // 保证发生在 delegate 建好之后。

                                                ComboBox {
                                                    id: actType
                                                    Layout.preferredWidth: 170
                                                    model: page.actLabels
                                                    onActivated: {
                                                        var r = page.cur(); if (!r || !r.actions) return
                                                        r.actions[actRow.idx] = {"type": page.actTypes[index], "p1": "", "p2": "", "p3": "", "p4": ""}
                                                        actRow.obj = r.actions[actRow.idx]
                                                    }
                                                }
                                                Loader {
                                                    id: actFld
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
                    }

                    }
                }


            }
        }
    }


    /*!
        应用挑选弹窗。

        为什么另做一个，而不是给 ComboBox 的下拉加滚动条：
        那要重写 Qt 自己维护的 popup 内部逻辑，实测会把列表搞成「只显示一项」。
        这里用与编辑面板同一套、已验证稳定的本页内覆盖层，
        列表与滚动条都是我们自己的：滚动条常驻且可以直接拖（拖比手指滑快得多）。
    */
    Item {
        id: appPicker
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: (page.Window && page.Window.height ? page.Window.height : 640) + 160
        z: 1100
        visible: page.appPicking

        onVisibleChanged: if (visible) {
            appPickSearch.text = ""
            // 读一次缓存即可：getCachedAppsJson() 内部在缓存为空时会触发
            // app_index.prefetch_async()（后台线程枚举，不阻塞图形线程）。
            page.ensureApps(false)
            appPickList.refresh()
            appPoll.restart()          // 抓到之前每隔 800ms 自动重读一次
        }

        // 后台枚举完成后自动把列表补上，用户不需要点任何按钮
        Timer {
            id: appPoll
            interval: 800
            repeat: true
            property int tries: 0
            onTriggered: {
                if (page.appLabels.length > 0 || tries++ > 25) {
                    appPoll.stop()
                    tries = 0
                }
                page.ensureApps(false)
                appPickList.refresh()
            }
        }

        Rectangle { anchors.fill: parent; color: "#66000000" }

        Rectangle {
            id: pickSheet
            x: 30
            width: parent.width - 60
            height: Math.min(parent.height - 80, 480)
            anchors.verticalCenter: parent.verticalCenter
            radius: page.cardRadius
            color: Theme.currentTheme.colors.backgroundAcrylicColor
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.windowBorderColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { typography: Typography.BodyStrong; text: "选择应用" }
                    Item { Layout.fillWidth: true }
                    Button { text: "关闭"; onClicked: page.appPicking = false }
                }

                TextField {
                    id: appPickSearch
                    Layout.fillWidth: true
                    placeholderText: "输入关键字筛选（例如 chrome、微信、记事本）"
                    onTextChanged: appPickList.refresh()
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: "transparent"
                    border.width: Theme.currentTheme.appearance.borderWidth
                    border.color: Theme.currentTheme.colors.windowBorderColor

                    ListView {
                        id: appPickList
                        anchors.fill: parent
                        anchors.rightMargin: 14          // 给滚动条留位置
                        clip: true
                        spacing: 2
                        boundsBehavior: Flickable.StopAtBounds
                        currentIndex: -1

                        function refresh() {
                            var kw = String(appPickSearch.text || "").toLowerCase()
                            var out = []
                            for (var i = 0; i < page.appLabels.length; i++) {
                                if (!kw || String(page.appLabels[i]).toLowerCase().indexOf(kw) >= 0)
                                    out.push(i)
                            }
                            appPickList.model = out
                        }

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 40
                            wrapMode: Text.Wrap
                            horizontalAlignment: Text.AlignHCenter
                            visible: appPickList.count === 0
                            text: page.appLabels.length === 0
                                  ? "正在获取应用列表…（首次约 3 秒，后台完成会自动出现；不用点任何按钮）"
                                  : "没有匹配的应用，换个关键字试试。"
                        }

                        delegate: ItemDelegate {
                            width: appPickList.width
                            text: page.appLabels[modelData]
                            onClicked: {
                                appPickList.currentIndex = index
                                page.appPickValue = page.appTargets[modelData]
                            }
                        }

                        // 常驻、可直接拖的右侧滚动条
                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AlwaysOn
                            width: 12
                            minimumSize: 0.08
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        text: page.appPickValue ? ("已选：" + page.appPickValue) : "未选择（在上面的列表里点一项）"
                    }
                    Button {
                        text: "重新抓取"
                        onClicked: {
                            if (backend) backend.prefetchAppsAsync()
                            page.appLabels = []
                            appPickList.refresh()
                            appPoll.restart()
                        }
                    }
                    Button {
                        text: "确定"
                        highlighted: true
                        enabled: !!page.appPickValue
                        onClicked: page.acceptAppPick()
                    }
                }
            }
        }
    }

    /* 通用列表挑选弹窗（科目 / 教师 / 主题 / 预设 / 配置项 …）
       与「选择应用」同一套本页覆盖层：列表与滚动条都是本页自己的，
       滚动条常驻、可以直接拖，不碰 Qt 自己维护的 ComboBox popup。 */
    Item {
        id: listPicker
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: (page.Window && page.Window.height ? page.Window.height : 640) + 160
        z: 1150
        visible: page.listPicking

        Rectangle { anchors.fill: parent; color: "#66000000" }

        Rectangle {
            id: listPickSheet
            x: 30
            width: parent.width - 60
            height: Math.min(parent.height - 80, 460)
            anchors.verticalCenter: parent.verticalCenter
            radius: page.cardRadius
            color: Theme.currentTheme.colors.backgroundAcrylicColor
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.windowBorderColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { typography: Typography.BodyStrong; text: page.listPickTitle }
                    Item { Layout.fillWidth: true }
                    Button { text: "关闭"; onClicked: page.listPicking = false }
                }

                TextField {
                    id: listPickSearch
                    Layout.fillWidth: true
                    placeholderText: "输入关键字筛选"
                    onTextChanged: listPickFilter.refresh()
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: "transparent"
                    border.width: Theme.currentTheme.appearance.borderWidth
                    border.color: Theme.currentTheme.colors.windowBorderColor

                    ListView {
                        id: listPickFilter
                        anchors.fill: parent
                        anchors.rightMargin: 14          // 给滚动条留位置
                        clip: true
                        spacing: 2
                        boundsBehavior: Flickable.StopAtBounds

                        function refresh() {
                            var kw = String(listPickSearch.text || "").toLowerCase()
                            var out = []
                            for (var i = 0; i < page.listPickLabels.length; i++) {
                                if (!kw || String(page.listPickLabels[i]).toLowerCase().indexOf(kw) >= 0)
                                    out.push(i)
                            }
                            listPickFilter.model = out
                        }

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - 40
                            wrapMode: Text.Wrap
                            horizontalAlignment: Text.AlignHCenter
                            visible: listPickFilter.count === 0
                            text: page.listPickLabels.length === 0
                                  ? "这个列表现在是空的（主程序里还没有对应内容）。"
                                  : "没有匹配的项，换个关键字试试。"
                        }

                        delegate: ItemDelegate {
                            width: listPickFilter.width
                            text: page.listPickLabels[modelData]
                            onClicked: {
                                page.listPickIndex = modelData
                                page.listPickValue = String(page.listPickLabels[modelData])
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AlwaysOn
                            width: 12
                            minimumSize: 0.08
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text {
                        Layout.fillWidth: true
                        elide: Text.ElideMiddle
                        text: page.listPickValue
                              ? ("已选：" + page.listPickValue)
                              : "未选择（在上面的列表里点一项）"
                    }
                    Button {
                        text: "确定"
                        highlighted: true
                        enabled: page.listPickIndex >= 0
                        onClicked: page.acceptListPick(page.listPickIndex)
                    }
                }
            }
        }
    }

    // ══════════════ 删除确认 ══════════════
    Dialog {
        id: confirmDialog
        modal: true
        title: "删除自动化"
        standardButtons: Dialog.Ok | Dialog.Cancel
        width: Math.min(420, Math.max(300, page.width - 96))

        onOpened: {
            if (footer && footer.okButton) footer.okButton.text = "删除"
            if (footer && footer.cancelButton) footer.cancelButton.text = "取消"
        }
        onAccepted: page.doDelete()

        Text {
            id: confirmText
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: ""
        }
    }


    // 刻意不做「页面加载后自动预枚举」：
    // 枚举要起一次 PowerShell（约 3 秒），若在图形线程的 Timer 回调里同步执行，
    // 会把事件循环卡住 3 秒，实测会让主程序在 QML 引擎层崩溃（Qt6Qml.dll / 0xc0000005）。
    // 现在改为主程序后台线程预先枚举并落盘缓存，QML 只读缓存（瞬时返回）。

    Timer {
        id: firstLoad
        interval: 300
        repeat: false
        onTriggered: page.reload()
    }

    Timer {
        id: saveTimer
        interval: 1500
        onTriggered: { statusText = "" }
    }
}
