import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts

ApplicationWindow {
    id: root
    // 默认约为屏幕面积的 1/2，居中；每次启动按默认几何（不记忆位置）
    property var archWindow: null
    // 仪器坞：各仪器格子可见性（阶段3 为固定两格；更多仪器时按 2×2/标签页扩展）
    property bool scopeVisible: true
    property bool powerVisible: true
    // 示波器参数面板：可整体收起（把空间让给波形）；高度按页自适应，避免空白
    property bool showScopeSettings: true
    property string reportSummaryText: ""
    width: Math.round(Screen.width * 0.72)
    height: Math.round(Screen.height * 0.70)
    x: Math.round((Screen.width - width) / 2)
    y: Math.round((Screen.height - height) / 2)
    visible: true
    title: qsTr("操作台 - 通用自动化测试平台原型（Rigol DHO924S）")
    minimumWidth: 1000
    minimumHeight: 620

    // 隐藏 / 显示窗口2（架构台）；快捷键 F2
    function toggleArchitecture() {
        if (archWindow) archWindow.visible = !archWindow.visible
    }

    Shortcut {
        sequence: "F2"
        onActivated: root.toggleArchitecture()
    }
            Button {
                text: qsTr("????")
                onClicked: discoveryDialog.open()
            }

    // 面板选项表
    property int selectedChannel: 1
    property var vDivValues: [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
    property var vDivLabels: ["1mV", "2mV", "5mV", "10mV", "20mV", "50mV", "100mV", "200mV", "500mV", "1V", "2V", "5V", "10V"]
    property var timeValues: [5e-9, 1e-8, 2e-8, 5e-8, 1e-7, 2e-7, 5e-7, 1e-6, 2e-6, 5e-6, 1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3, 2e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1, 5e-1, 1]
    property var timeLabels: ["5ns", "10ns", "20ns", "50ns", "100ns", "200ns", "500ns", "1µs", "2µs", "5µs", "10µs", "20µs", "50µs", "100µs", "200µs", "500µs", "1ms", "2ms", "5ms", "10ms", "20ms", "50ms", "100ms", "200ms", "500ms", "1s"]
    property var couplingValues: ["DC", "AC", "GND"]
    property var sweepValues: ["AUTO", "NORMal", "SINGle"]
    property var slopeValues: ["POSitive", "NEGative", "RFALl"]
    property var slopeLabels: ["上升沿", "下降沿", "任意沿"]
    property var afgValues: ["SINusoid", "SQUare", "RAMP", "PULSe", "DC"]
    property var afgLabels: ["正弦", "方波", "斜坡", "脉冲", "直流"]
    property var measureKeys: ["vpp", "vrms", "vavg", "freq", "per", "rtime", "ftime", "duty"]
    property var measureLabels: ["Vpp", "Vrms", "Vavg", "Freq", "Period", "Rise", "Fall", "Duty"]

    // 分层配色（表示/胶合/应用/HAL/数据/报告）
    function layerColor(layer) {
        if (layer === "ui") return "#58a6ff";
        if (layer === "glue") return "#39c5cf";
        if (layer === "app") return "#3fb950";
        if (layer === "hal") return "#f0883e";
        if (layer === "data") return "#bc8cff";
        if (layer === "report") return "#8b949e";
        return "#8b98a5";
    }

    function indexOfValue(arr, v) {
        for (var i = 0; i < arr.length; i++) {
            if (Math.abs(arr[i] - v) <= Math.abs(arr[i]) * 1e-3 + 1e-15)
                return i;
        }
        return -1;
    }

    // 切换通道时刷新“垂直”页控件。
    // 说明：ComboBox/Switch/SpinBox 一旦被用户改过，原来的属性绑定会被破坏，
    // 因此这里统一用函数同步，避免出现“换了通道但控件还显示上一个通道值”的粘滞现象。
    function refreshVertical() {
        var ch = root.selectedChannel
        chEnableSwitch.checked = scope.channelEnabled(ch)
        chInvertSwitch.checked = scope.channelInvert(ch)
        chBwSwitch.checked = scope.channelBwLimit(ch)
        vdivCombo.currentIndex = root.indexOfValue(root.vDivValues, scope.channelScale(ch))
        couplingCombo.currentIndex = root.couplingValues.indexOf(scope.channelCoupling(ch))
        probeCombo.currentIndex = [1, 10, 100].indexOf(scope.channelProbe(ch))
        offsetSpin.value = Math.round(scope.channelOffset(ch) * 1000)
    }

    // 示波器设置面板：按当前页返回紧凑高度（px）
    function settingsPanelHeight(page) {
        switch (page) {
        case 0: return 84;    // 垂直（2 行控件）
        case 1: return 56;    // 水平（1 行控件）
        case 2: return 80;    // 触发（2 行）
        case 3: return 80;    // 采集（2 行）
        case 4: return 84;    // 测量（2 行）
        case 5: return 80;    // 信号源（2 行）
        default: return 80;
        }
    }

    // 可添加的步骤/动作（能力模型 + 内置步骤）
    function refreshActions() {
        addActionModel.clear()
        var rows = controller.addableSteps()
        for (var i = 0; i < rows.length; i++) addActionModel.append(rows[i])
    }

    // 所选步骤的参数（由能力模型自动生成）
    function addDiscoveryRow(item, kind) {
        discoveryModel.append({
            "transportKind": kind,
            "host": item.host || "",
            "port": item.port || 0,
            "resource": item.resource || "",
            "idn": item.idn || "",
            "vendor": item.vendor || "",
            "modelName": item.model || "",
            "serial": item.serial || "",
            "firmware": item.firmware || "",
            "title": (kind === "visa" ? "VISA" : "TCP") + " ? "
                     + (item.model || item.idn || item.host || item.resource || "????")
        })
    }
    function testTcp(host, port) {
        var r = controller.testInstrumentConnection(JSON.stringify({
            transport: { kind: "tcp", host: host, port: port },
            protocol: { kind: "scpi", terminator: "\n" }
        }))
        tcpTestResult.text = r.ok ? ("?????" + r.idn) : ("?????" + r.error)
    }
    function addTcp(host, port) {
        controller.addDiscoveredInstrument(JSON.stringify({
            transport_kind: "tcp", host: host, port: port, idn: "", model: "", vendor: ""
        }))
        discoveryStatus.text = "???? config/instruments.json?????????????"
    }
    function runScan(subnet) {
        discoveryModel.clear()
        discoveryStatus.text = "???????????..."
        var results = controller.scanInstruments(subnet)
        for (var i = 0; i < results.length; i++) addDiscoveryRow(results[i], "tcp")
        discoveryStatus.text = "??????? " + results.length + " ???"
    }
    function runVisa() {
        discoveryModel.clear()
        discoveryStatus.text = "?? VISA ??..."
        var results = controller.enumerateVisaInstruments()
        for (var i = 0; i < results.length; i++) addDiscoveryRow(results[i], "visa")
        discoveryStatus.text = "VISA ?????" + results.length + " ???"
    }
    function addDiscovered(model) {
        var payload = {
            transport_kind: model.transportKind,
            host: model.host,
            port: model.port,
            resource: model.resource,
            idn: model.idn,
            vendor: model.vendor,
            model: model.modelName,
            serial: model.serial,
            firmware: model.firmware
        }
        discoveryStatus.text = controller.addDiscoveredInstrument(JSON.stringify(payload))
    }

    function refreshStepParams() {
        stepParamModel.clear()
        if (flowStepList.currentIndex < 0) return
        var rows = controller.stepParams(flowStepList.currentIndex)
        for (var i = 0; i < rows.length; i++) stepParamModel.append(rows[i])
    }

    // 流程步骤（阶段4：可编辑 + 运行高亮）
    function refreshFlow() {
        flowStepModel.clear()
        var rows = controller.flowSteps()
        for (var i = 0; i < rows.length; i++) flowStepModel.append(rows[i])
        if (flowStepModel.count > 0 && flowStepList.currentIndex < 0) flowStepList.currentIndex = 0
        refreshStepParams()
    }

    // 报表总表（右区）
    function refreshReport() {
        reportModel.clear()
        var rows = controller.reportRows()
        for (var i = 0; i < rows.length; i++) reportModel.append(rows[i])
        root.reportSummaryText = controller.reportSummary()
    }

    onSelectedChannelChanged: {
        refreshVertical()
        scope.setPollChannel(root.selectedChannel)
    }
    Component.onCompleted: {
        refreshVertical()
        scope.setPollChannel(root.selectedChannel)
        refreshFlow()
        refreshReport()
        refreshActions()
        // 仪器坞：按注册表初始化各仪器可见性
        var list = controller.instruments()
        for (var i = 0; i < list.length; i++) {
            if (list[i].panel === "ScopeInstrument") root.scopeVisible = list[i].visible
            if (list[i].panel === "PowerSupplyInstrument") root.powerVisible = list[i].visible
        }
    }

    // ================= 顶部标题栏 =================
    header: Rectangle {
        height: 52
        color: "#1f2933"
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 12
            Label {
                text: qsTr("通用自动化测试软件平台 · 原型验证")
                color: "#e6edf3"
                font.pixelSize: 16
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Label {
                text: qsTr("仪器: ") + controller.instrumentInfo
                color: "#9fb3c8"
                font.pixelSize: 12
            }
            Rectangle {
                width: 80
                height: 22
                radius: 11
                color: "#6e7681"
                Label {
                    anchors.centerIn: parent
                    text: scope.sourceLabel
                    color: "white"
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // ================= 流程按钮行 =================
        RowLayout {
            spacing: 8
            Button { text: qsTr("加载示例流程"); onClicked: controller.loadFlow("config/flow_sample.json") }
            Button { text: qsTr("运行流程"); onClicked: { resultModel.clear(); controller.runFlow() } }
            Button { text: qsTr("保存报告"); onClicked: controller.saveReport("reports/report.html") }
            Rectangle { width: 1; height: 24; color: "#d0d7de" }
            Button {
                text: scope.running ? qsTr("⏸ STOP") : qsTr("▶ RUN")
                onClicked: scope.setRunning(!scope.running)
            }
            Button { text: qsTr("SINGLE"); onClicked: scope.singleShot() }
            Button { text: qsTr("AUTO 自动设置"); onClicked: scope.autoSet() }
            Button {
                text: (scope.waveformOn ? "● " : "○ ")
                      + (scope.simulationMode ? qsTr("仿真波形") : qsTr("波形读取"))
                onClicked: scope.setWaveformOn(!scope.waveformOn)
            }
            Button {
                text: qsTr("架构台 (F2)")
                onClicked: root.toggleArchitecture()
            }
            Item { Layout.fillWidth: true }
            Label {
                text: qsTr("状态：") + controller.status
                font.bold: true
                color: controller.status.indexOf("完成") === 0 ? "#1a7f37" : "#24292f"
            }
        }

        // ================= 三区：左(流程) | 中(仪器) | 右(报表) =================
        SplitView {
            id: mainSplit
            orientation: Qt.Horizontal
            Layout.fillWidth: true
            Layout.fillHeight: true

            // ---------- 左区：流程控制 + 流程编辑 ----------
            Rectangle {
                SplitView.preferredWidth: 350
                color: "#f6f8fa"
                border.color: "#d0d7de"
                radius: 4

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6

                    Label { text: qsTr("流程控制"); font.bold: true; color: "#24292f" }

                    GridLayout {
                        columns: 4
                        columnSpacing: 6
                        rowSpacing: 4
                        Label { text: qsTr("产品"); color: "#57606a"; font.pixelSize: 11 }
                        TextField { id: dutModel; Layout.fillWidth: true; text: "演示被测件"; placeholderText: qsTr("型号") }
                        Label { text: qsTr("序列号"); color: "#57606a"; font.pixelSize: 11 }
                        TextField { id: dutSn; Layout.fillWidth: true; text: "DEMO-001"; placeholderText: "SN" }
                    }

                    RowLayout {
                        spacing: 6
                        Button {
                            text: qsTr("加电")
                            onClicked: {
                                power.setChannel(1)
                                power.setOutput(true)
                                controller.manualAction("power_on")
                            }
                        }
                        Button {
                            text: qsTr("断电")
                            onClicked: {
                                power.setChannel(1)
                                power.setOutput(false)
                                controller.manualAction("power_off")
                            }
                        }
                        Button { text: qsTr("测波形"); onClicked: scope.setWaveformOn(true) }
                        Item { Layout.fillWidth: true }
                    }

                    RowLayout {
                        spacing: 6
                        Button {
                            text: qsTr("▶ 启动")
                            enabled: !controller.flowRunning && controller.flowLoaded
                            onClicked: { resultModel.clear(); controller.runFlow() }
                        }
                        Button {
                            text: controller.flowPaused ? qsTr("▶ 继续") : qsTr("⏸ 暂停")
                            enabled: controller.flowRunning
                            onClicked: controller.flowPaused ? controller.resumeFlow() : controller.pauseFlow()
                        }
                        Button {
                            text: qsTr("■ 停止")
                            enabled: controller.flowRunning
                            onClicked: controller.stopFlow()
                        }
                        Button {
                            text: qsTr("⏭ 单步")
                            onClicked: controller.stepFlow()
                        }
                        Item { Layout.fillWidth: true }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: "#d0d7de" }

                    RowLayout {
                        Label { text: qsTr("流程编辑"); font.bold: true; color: "#24292f" }
                        Label {
                            text: controller.flowLoaded
                                  ? qsTr("（") + controller.flowName + qsTr("）")
                                  : qsTr("（未加载流程）")
                            color: "#57606a"; font.pixelSize: 10
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        Label {
                            text: controller.flowRunning
                                  ? (controller.flowPaused ? qsTr("已暂停") : (controller.stepMode ? qsTr("单步") : qsTr("运行中")))
                                  : qsTr("编辑态")
                            color: controller.flowRunning ? "#bc4c00" : "#1a7f37"
                            font.pixelSize: 10
                        }
                    }

                    RowLayout {
                        spacing: 4
                        ComboBox {
                            id: addActionCombo
                            Layout.fillWidth: true
                            Layout.preferredHeight: 24
                            font.pixelSize: 11
                            textRole: "label"
                            model: addActionModel
                        }
                        Button {
                            text: qsTr("添加")
                            padding: 2
                            Layout.preferredHeight: 24
                            enabled: !controller.flowRunning && addActionModel.count > 0
                            onClicked: {
                                var item = addActionModel.get(addActionCombo.currentIndex)
                                if (item) controller.addStep(item.action || item.stepType)
                                root.refreshFlow()
                            }
                        }
                    }

                    RowLayout {
                        spacing: 4
                        Button {
                            text: qsTr("删除")
                            padding: 2
                            Layout.preferredHeight: 24
                            enabled: !controller.flowRunning && flowStepList.currentIndex >= 0
                            onClicked: { controller.removeStep(flowStepList.currentIndex); root.refreshFlow() }
                        }
                        Button {
                            text: qsTr("上移")
                            padding: 2
                            Layout.preferredHeight: 24
                            enabled: !controller.flowRunning && flowStepList.currentIndex > 0
                            onClicked: { controller.moveStep(flowStepList.currentIndex, -1); root.refreshFlow() }
                        }
                        Button {
                            text: qsTr("下移")
                            padding: 2
                            Layout.preferredHeight: 24
                            enabled: !controller.flowRunning && flowStepList.currentIndex >= 0
                                     && flowStepList.currentIndex < flowStepModel.count - 1
                            onClicked: { controller.moveStep(flowStepList.currentIndex, 1); root.refreshFlow() }
                        }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: qsTr("保存流程")
                            padding: 2
                            Layout.preferredHeight: 24
                            enabled: !controller.flowRunning && controller.flowLoaded
                            onClicked: controller.saveFlow("config/flows/flow_current.json")
                        }
                    }

                    ListView {
                        id: flowStepList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: flowStepModel
                        clip: true
                        spacing: 2
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        onCurrentIndexChanged: root.refreshStepParams()
                        delegate: Rectangle {
                            width: flowStepList.width - 10
                            height: 26
                            property bool isCurrent: controller.currentStepId.length > 0 && model.stepId === controller.currentStepId
                            color: isCurrent ? "#fff8e5" : (flowStepList.currentIndex === index ? "#eef4ff" : "#ffffff")
                            border.color: isCurrent ? "#d4a72c" : (flowStepList.currentIndex === index ? "#0969da" : "#d0d7de")
                            radius: 3
                            MouseArea {
                                anchors.fill: parent
                                onClicked: flowStepList.currentIndex = index
                            }
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 6
                                anchors.rightMargin: 6
                                spacing: 6
                                Label { text: model.seq; color: "#57606a"; font.pixelSize: 11; Layout.preferredWidth: 20 }
                                Label { text: model.stepType; color: "#0969da"; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 58 }
                                Label { text: model.summary; color: "#24292f"; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            }
                        }
                    }

                    RowLayout {
                        Label { text: qsTr("步骤参数"); font.bold: true; color: "#24292f" }
                        Label {
                            text: controller.flowRunning ? qsTr("（运行中只读）") : qsTr("（由能力模型生成）")
                            color: "#8b98a5"; font.pixelSize: 10
                        }
                        Item { Layout.fillWidth: true }
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 6
                        rowSpacing: 3
                        Repeater {
                            model: stepParamModel
                            Label {
                                text: model.label
                                color: "#57606a"
                                font.pixelSize: 11
                                horizontalAlignment: Text.AlignRight
                            }
                            ComboBox {
                                visible: model.options !== undefined && model.options.length > 0
                                enabled: !controller.flowRunning
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                font.pixelSize: 11
                                model: model.options
                                currentIndex: model.options ? model.options.indexOf(String(model.value)) : -1
                                onActivated: {
                                    controller.setStepParam(model.stepIndex, model.name, model.options[index])
                                    root.refreshStepParams()
                                }
                            }
                            SpinBox {
                                visible: (model.options === undefined || model.options.length === 0) && model.type === "int"
                                enabled: !controller.flowRunning
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                font.pixelSize: 11
                                from: model.min === null || model.min === undefined ? -999999 : model.min
                                to: model.max === null || model.max === undefined ? 999999 : model.max
                                value: Number(model.value === null || model.value === undefined ? 0 : model.value)
                                onValueModified: {
                                    controller.setStepParam(model.stepIndex, model.name, String(value))
                                    root.refreshStepParams()
                                }
                            }
                            TextField {
                                visible: (model.options === undefined || model.options.length === 0) && model.type !== "int"
                                enabled: !controller.flowRunning
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                font.pixelSize: 11
                                text: model.value === null || model.value === undefined ? "" : String(model.value)
                                onEditingFinished: {
                                    controller.setStepParam(model.stepIndex, model.name, text)
                                    root.refreshStepParams()
                                }
                            }
                        }
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: "#d0d7de" }
                    Label { text: qsTr("最近命令"); font.bold: true; color: "#24292f" }
                    Label {
                        Layout.fillWidth: true
                        text: controller.lastCommandText.length > 0 ? controller.lastCommandText : "—"
                        font.family: "Consolas, monospace"
                        font.pixelSize: 10
                        color: "#57606a"
                        wrapMode: Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                    }
                }
            }

            // ---------- 中区：仪器坞（示波器仪器格） ----------
            Rectangle {
                SplitView.fillWidth: true
                clip: true
                color: "transparent"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 6

                    RowLayout {
                        Label { text: qsTr("仪器坞"); font.bold: true; color: "#24292f" }
                        CheckBox {
                            text: qsTr("示波器 DHO924S")
                            checked: root.scopeVisible
                            onToggled: { root.scopeVisible = checked; controller.setInstrumentVisible("scope1", checked) }
                        }
                        CheckBox {
                            text: qsTr("直流电源 SPD3303X-E（虚拟）")
                            checked: root.powerVisible
                            onToggled: { root.powerVisible = checked; controller.setInstrumentVisible("power1", checked) }
                        }
                        Label {
                            text: controller.instrumentSummary
                            color: "#8b98a5"
                            font.pixelSize: 9
                            elide: Text.ElideRight
                            Layout.maximumWidth: 300
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: qsTr("上下分栏可拖拽；仪器数 >4 时自动改为 2×2 / 标签页")
                            color: "#8b98a5"; font.pixelSize: 10
                        }
                    }

                    // ---------- 仪器格 1：示波器（阶段3：包成仪器格） ----------
                    SplitView {
                        orientation: Qt.Vertical
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        Rectangle {
                            id: scopeCell
                            SplitView.fillHeight: true
                            SplitView.minimumHeight: 300
                            visible: root.scopeVisible
                            clip: true
                            color: "#0d1117"
                            border.color: "#30363d"
                            radius: 4

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 6
                                spacing: 4

                                RowLayout {
                                    Label { text: qsTr("示波器 · Rigol DHO924S"); color: "#e6edf3"; font.bold: true }
                                    Label {
                                        text: scope.simulationMode ? qsTr("（仿真）") : qsTr("（真机）")
                                        color: "#8b98a5"; font.pixelSize: 10
                                    }
                                    Button {
                                        text: qsTr("参数")
                                        checkable: true
                                        checked: root.showScopeSettings
                                        focusPolicy: Qt.NoFocus
                                        font.pixelSize: 10
                                        onClicked: root.showScopeSettings = checked
                                    }
                                    Item { Layout.fillWidth: true }
                                    Label {
                                        Layout.fillWidth: true
                                        horizontalAlignment: Text.AlignRight
                                        elide: Text.ElideRight
                                        text: scope.commandText.length > 0 ? scope.commandText : "—"
                                        color: "#8b98a5"; font.pixelSize: 9
                                        font.family: "Consolas, monospace"
                                    }
                                }

        // ================= 波形屏 + 读数 =================
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#0a0f14"
                border.color: "#30363d"
                radius: 4
                clip: true

                Canvas {
                    id: scopeCanvas
                    anchors.fill: parent

                    function paintGrid(ctx, w, h) {
                        var divX = w / 10;
                        var divY = h / 8;
                        ctx.lineWidth = 1;
                        ctx.strokeStyle = "#2a3942";
                        ctx.beginPath();
                        for (var i = 1; i < 10; i++) { var x = i * divX; ctx.moveTo(x, 0); ctx.lineTo(x, h); }
                        for (var j = 1; j < 8; j++) { var y = j * divY; ctx.moveTo(0, y); ctx.lineTo(w, y); }
                        ctx.stroke();
                        ctx.strokeStyle = "#5a707c";
                        ctx.beginPath();
                        ctx.moveTo(5 * divX, 0); ctx.lineTo(5 * divX, h);
                        ctx.moveTo(0, 4 * divY); ctx.lineTo(w, 4 * divY);
                        ctx.stroke();
                    }


                    // 绘制真机波形（数据来自 :WAVeform 下载；未开启/无数据时不画）
                    function paintChannel(ctx, w, h, ch) {
                        var ys = scope.samples(ch);
                        if (!ys || ys.length < 2) return false;
                        var scale = scope.channelScale(ch);
                        if (!scale || scale <= 0) return false;
                        var divY = h / 8;
                        var cy = h / 2;
                        ctx.strokeStyle = scope.channelColor(ch);
                        ctx.lineWidth = 1.6;
                        ctx.beginPath();
                        var n = ys.length;
                        for (var i = 0; i < n; i++) {
                            var x = (i / (n - 1)) * w;
                            var y = cy - (ys[i] / scale) * divY;
                            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                        }
                        ctx.stroke();
                        return true;
                    }

                    function paintTrigger(ctx, w, h) {
                        var ch = scope.triggerSource();
                        var scale = scope.channelScale(ch);
                        if (!scale || scale <= 0) return;
                        var divY = h / 8;
                        var y = h / 2 - (scope.triggerLevel() / scale) * divY;
                        if (y < 0 || y > h) return;
                        ctx.strokeStyle = "#f0883e";
                        ctx.setLineDash([4, 4]);
                        ctx.beginPath();
                        ctx.moveTo(0, y); ctx.lineTo(w, y);
                        ctx.stroke();
                        ctx.setLineDash([]);
                        ctx.fillStyle = "#f0883e";
                        ctx.font = "11px sans-serif";
                        ctx.fillText("T " + scope.triggerLevel().toFixed(2) + "V", 8, y - 4);
                    }

                    function paintText(ctx, w, h) {
                        ctx.font = "12px 'Microsoft YaHei', sans-serif";
                        ctx.textAlign = "left";
                        var ty = 16;
                        for (var i = 1; i <= 4; i++) {
                            if (!scope.channelEnabled(i)) continue;
                            ctx.fillStyle = scope.channelColor(i);
                            ctx.fillText("CH" + i + "  " + scope.channelText(i), 10, ty);
                            ty += 16;
                        }
                        ctx.textAlign = "right";
                        ctx.fillStyle = scope.running ? "#3fb950" : "#f85149";
                        ctx.fillText(scope.running ? "RUN" : "STOP", w - 10, 16);
                        ctx.fillStyle = "#8b98a5";
                        ctx.fillText("T: " + scope.timebaseText, w - 10, 32);
                        ctx.textAlign = "left";
                    }

                    onPaint: {
                        var ctx = getContext("2d");
                        var w = width;
                        var h = height;
                        ctx.clearRect(0, 0, w, h);
                        ctx.fillStyle = "#0a0f14";
                        ctx.fillRect(0, 0, w, h);
                        paintGrid(ctx, w, h);
                        var drawn = false;
                        drawn = paintChannel(ctx, w, h, 1) || drawn;
                        drawn = paintChannel(ctx, w, h, 2) || drawn;
                        drawn = paintChannel(ctx, w, h, 3) || drawn;
                        drawn = paintChannel(ctx, w, h, 4) || drawn;
                        paintTrigger(ctx, w, h);
                        paintText(ctx, w, h);
                        if (!drawn) {
                            ctx.save();
                            ctx.font = "15px 'Microsoft YaHei', sans-serif";
                            ctx.fillStyle = "#7d8590";
                            ctx.textAlign = "center";
                            ctx.fillText(scope.waveformOn
                                         ? (scope.simulationMode
                                            ? "正在生成仿真波形…"
                                            : "等待真机波形数据…（若一直为空，请检查通道是否开启、探头是否接信号）")
                                         : (scope.simulationMode
                                            ? "仿真波形已关闭：点击上方“仿真波形”开关开启"
                                            : "波形未显示：请点击上方“波形读取”开关（从示波器下载 :WAVeform 数据）"), w / 2, h / 2);
                            ctx.restore();
                            ctx.textAlign = "left";
                        }
                    }

                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                }

                Connections {
                    target: scope
                    function onMeasurementsChanged() { }
                    function onFrameReady() { scopeCanvas.requestPaint() }
                    function onChannelsChanged() { scopeCanvas.requestPaint() }
                    function onRunningChanged() { scopeCanvas.requestPaint() }
                    function onStateChanged() { scopeCanvas.requestPaint() }
                }
            }

            // 右侧读数
            Rectangle {
                Layout.preferredWidth: 236
                Layout.fillHeight: true
                color: "#161b22"
                border.color: "#30363d"
                radius: 4

                ScrollView {
                    id: readoutScroll
                    anchors.fill: parent
                    anchors.margins: 10
                    contentWidth: availableWidth
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    ColumnLayout {
                    width: readoutScroll.availableWidth
                    spacing: 6

                    Label { text: qsTr("自动测量"); color: "#e6edf3"; font.bold: true }

                    Repeater {
                        model: 4
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 128
                            visible: scope.channelEnabled(index + 1)
                            radius: 4
                            color: "#1c2128"
                            border.color: "#30363d"
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 3
                                RowLayout {
                                    spacing: 6
                                    Rectangle { width: 10; height: 10; radius: 5; color: scope.channelColor(index + 1) }
                                    Label { text: "CH" + (index + 1); color: "white"; font.bold: true }
                                    Label { text: (scope.stateSeq >= 0 ? "" : "") + scope.channelText(index + 1); color: "#9fb3c8"; font.pixelSize: 11 }
                                    Item { Layout.fillWidth: true }
                                }
                                Label {
                                    text: (scope.stateSeq >= 0 ? "" : "")
                                          + scope.channelCoupling(index + 1) + "  "
                                          + scope.channelProbe(index + 1) + "x  "
                                          + scope.channelOffset(index + 1).toFixed(2) + "V"
                                    color: "#8b98a5"
                                    font.pixelSize: 10
                                }
                                Label {
                                    text: scope.measureSeq >= 0 ? scope.measurementText(index + 1) : ""
                                    color: "#d7e2ea"
                                    font.pixelSize: 11
                                    font.family: "Consolas, monospace"
                                }
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("提示：本屏不显示波形（真机波形下载未接入）；\n右侧读数为真机轮询值，面板命令直接下发真机。")
                        color: "#8b98a5"
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                    }
                    }
                }
            }
        }

        // ================= 示波器设置面板 =================
        TabBar {
            id: ctrlTabs
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            visible: root.showScopeSettings
            TabButton { text: qsTr("垂直") }
            TabButton { text: qsTr("水平") }
            TabButton { text: qsTr("触发") }
            TabButton { text: qsTr("采集") }
            TabButton { text: qsTr("测量") }
            TabButton { text: qsTr("信号源") }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.settingsPanelHeight(ctrlTabs.currentIndex)
            Layout.minimumHeight: 60
            visible: root.showScopeSettings
            clip: true
            color: "#f6f8fa"
            border.color: "#d0d7de"
            radius: 4

            // Pane：紧凑字体容器（子控件继承 11px 字号）
            Pane {
                anchors.fill: parent
                padding: 0
                font.pixelSize: 11
                background: null

                StackLayout {
                    anchors.fill: parent
                    anchors.margins: 4
                    currentIndex: ctrlTabs.currentIndex

                    // ---------- 垂直（通道） ----------
                    GridLayout {
                        columns: 9
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("通道"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        RowLayout {
                            Layout.columnSpan: 3
                            spacing: 3
                            ButtonGroup { id: chButtonGroup; exclusive: true }
                            Repeater {
                                model: 4
                                Button {
                                    padding: 2
                                    Layout.preferredHeight: 22
                                    text: (checked ? "●" : "○") + "CH" + (index + 1)
                                    checkable: true
                                    focusPolicy: Qt.NoFocus
                                    ButtonGroup.group: chButtonGroup
                                    checked: root.selectedChannel === (index + 1)
                                    onClicked: root.selectedChannel = index + 1
                                }
                            }
                        }
                        Label { text: qsTr("显示"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Switch {
                            id: chEnableSwitch
                            padding: 0
                            spacing: 4
                            Layout.preferredHeight: 22
                            text: qsTr("开启")
                            onClicked: scope.setChannelEnabled(root.selectedChannel, checked)
                        }
                        Switch {
                            id: chInvertSwitch
                            padding: 0
                            spacing: 4
                            Layout.preferredHeight: 22
                            text: qsTr("反相")
                            onClicked: scope.setChannelInvert(root.selectedChannel, checked)
                        }
                        Label { text: qsTr("带宽"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Switch {
                            id: chBwSwitch
                            padding: 0
                            spacing: 4
                            Layout.preferredHeight: 22
                            text: qsTr("20MHz")
                            onClicked: scope.setChannelBwLimit(root.selectedChannel, checked)
                        }

                        Label { text: qsTr("档位"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            id: vdivCombo
                            padding: 2
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 22
                            model: root.vDivLabels
                            onActivated: scope.setChannelScale(root.selectedChannel, root.vDivValues[index])
                        }
                        Label { text: qsTr("耦合"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            id: couplingCombo
                            padding: 2
                            Layout.preferredWidth: 70
                            Layout.preferredHeight: 22
                            model: root.couplingValues
                            onActivated: scope.setChannelCoupling(root.selectedChannel, root.couplingValues[index])
                        }
                        Label { text: qsTr("探头"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            id: probeCombo
                            padding: 2
                            Layout.preferredWidth: 70
                            Layout.preferredHeight: 22
                            model: ["1x", "10x", "100x"]
                            onActivated: scope.setChannelProbe(root.selectedChannel, [1, 10, 100][index])
                        }
                        Label { text: qsTr("偏移(mV)"); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            id: offsetSpin
                            padding: 2
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 22
                            from: -10000
                            to: 10000
                            stepSize: 10
                            editable: true
                            onValueModified: scope.setChannelOffset(root.selectedChannel, value / 1000.0)
                        }
                        Item { Layout.fillWidth: true }
                    }

                    // ---------- 水平 ----------
                    GridLayout {
                        columns: 6
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("时基"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            padding: 2
                            Layout.preferredWidth: 92
                            Layout.preferredHeight: 22
                            model: root.timeLabels
                            currentIndex: root.indexOfValue(root.timeValues, scope.timeScale())
                            onActivated: scope.setTimeScale(root.timeValues[index])
                        }
                        Label { text: qsTr("位置(µs)"); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            padding: 2
                            Layout.preferredWidth: 92
                            Layout.preferredHeight: 22
                            from: -5000
                            to: 5000
                            stepSize: 10
                            editable: true
                            value: Math.round(scope.timeOffset() * 1000000)
                            onValueModified: scope.setTimeOffset(value / 1000000.0)
                        }
                        Label { text: qsTr("满屏"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Label { text: (scope.timeScale() * 10 * 1000).toFixed(3) + " ms"; color: "#24292f" }
                    }

                    // ---------- 触发 ----------
                    GridLayout {
                        columns: 6
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("模式"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            padding: 2
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 22
                            model: root.sweepValues
                            currentIndex: root.sweepValues.indexOf(scope.triggerSweep())
                            onActivated: scope.setTriggerSweep(root.sweepValues[index])
                        }
                        Label { text: qsTr("源"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            padding: 2
                            Layout.preferredWidth: 72
                            Layout.preferredHeight: 22
                            model: ["CH1", "CH2", "CH3", "CH4"]
                            currentIndex: scope.triggerSource() - 1
                            onActivated: scope.setTriggerSource(index + 1)
                        }
                        Label { text: qsTr("斜率"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            padding: 2
                            Layout.preferredWidth: 88
                            Layout.preferredHeight: 22
                            model: root.slopeLabels
                            currentIndex: root.slopeValues.indexOf(scope.triggerSlope())
                            onActivated: scope.setTriggerSlope(root.slopeValues[index])
                        }

                        Label { text: qsTr("电平(mV)"); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            padding: 2
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 22
                            from: -10000
                            to: 10000
                            stepSize: 10
                            editable: true
                            value: Math.round(scope.triggerLevel() * 1000)
                            onValueModified: scope.setTriggerLevel(value / 1000.0)
                        }
                        Button {
                            padding: 2
                            Layout.preferredHeight: 22
                            Layout.columnSpan: 2
                            text: qsTr("强制触发")
                            onClicked: scope.forceTrigger()
                        }
                        Item { Layout.fillWidth: true }
                    }

                    // ---------- 采集 ----------
                    GridLayout {
                        columns: 8
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("采集"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        RowLayout {
                            Layout.columnSpan: 3
                            spacing: 4
                            Button { padding: 2; Layout.preferredHeight: 22; text: "RUN"; highlighted: scope.running; onClicked: scope.setRunning(true) }
                            Button { padding: 2; Layout.preferredHeight: 22; text: "STOP"; highlighted: !scope.running; onClicked: scope.setRunning(false) }
                            Button { padding: 2; Layout.preferredHeight: 22; text: "SINGLE"; onClicked: scope.singleShot() }
                        }
                        Label { text: qsTr("设置"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        RowLayout {
                            Layout.columnSpan: 3
                            spacing: 4
                            Button { padding: 2; Layout.preferredHeight: 22; text: qsTr("AUTO 自动设置"); onClicked: scope.autoSet() }
                            Button { padding: 2; Layout.preferredHeight: 22; text: qsTr("清除显示"); onClicked: scope.clearScope() }
                        }

                        Label { text: qsTr("状态"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Label {
                            Layout.columnSpan: 3
                            text: scope.running ? qsTr("运行中 (RUN)") : qsTr("已停止 (STOP)")
                            color: scope.running ? "#1a7f37" : "#57606a"
                        }
                        Label { text: qsTr("时基"); Layout.preferredWidth: 30; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Label {
                            Layout.columnSpan: 3
                            text: scope.timebaseText
                            color: "#24292f"
                        }
                    }

                    // ---------- 测量 ----------
                    GridLayout {
                        columns: 6
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("测量项"); Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        RowLayout {
                            Layout.columnSpan: 4
                            spacing: 3
                            Repeater {
                                model: root.measureKeys.length
                                Button {
                                    property string mkey: root.measureKeys[index]
                                    padding: 2
                                    Layout.preferredHeight: 22
                                    text: (scope.stateSeq >= 0 && scope.measureItemEnabled(mkey) ? "●" : "○") + root.measureLabels[index]
                                    onClicked: scope.setMeasureItem(mkey, !scope.measureItemEnabled(mkey))
                                }
                            }
                        }
                        Button {
                            padding: 2
                            Layout.preferredHeight: 22
                            text: qsTr("复位统计")
                            onClicked: scope.measureReset()
                        }

                        Label { text: qsTr("统计"); Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Switch {
                            padding: 0
                            spacing: 4
                            Layout.preferredHeight: 22
                            text: qsTr("显示统计")
                            checked: scope.measureStat
                            onToggled: scope.setMeasureStat(checked)
                        }
                        Item { Layout.columnSpan: 4; Layout.fillWidth: true }
                    }

                    // ---------- 信号源（AFG） ----------
                    GridLayout {
                        columns: 8
                        columnSpacing: 8
                        rowSpacing: 4

                        Label { text: qsTr("波形"); Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        ComboBox {
                            padding: 2
                            Layout.preferredWidth: 84
                            Layout.preferredHeight: 22
                            model: root.afgLabels
                            currentIndex: root.afgValues.indexOf(scope.afgFunction())
                            onActivated: scope.setAfgFunction(root.afgValues[index])
                        }
                        Label { text: qsTr("频率(Hz)"); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            padding: 2
                            Layout.preferredWidth: 104
                            Layout.preferredHeight: 22
                            from: 1
                            to: 25000000
                            stepSize: 100
                            editable: true
                            value: Math.round(scope.afgFrequency())
                            onValueModified: scope.setAfgFrequency(value)
                        }
                        Label { text: qsTr("幅度(mVpp)"); Layout.preferredWidth: 66; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            padding: 2
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 22
                            from: 10
                            to: 5000
                            stepSize: 10
                            editable: true
                            value: Math.round(scope.afgAmplitude() * 1000)
                            onValueModified: scope.setAfgAmplitude(value / 1000.0)
                        }
                        Label { text: qsTr("偏移(mV)"); Layout.preferredWidth: 52; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        SpinBox {
                            padding: 2
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 22
                            from: -2500
                            to: 2500
                            stepSize: 10
                            editable: true
                            value: Math.round(scope.afgOffset() * 1000)
                            onValueModified: scope.setAfgOffset(value / 1000.0)
                        }

                        Label { text: qsTr("输出"); Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; color: "#57606a" }
                        Switch {
                            padding: 0
                            spacing: 4
                            Layout.preferredHeight: 22
                            text: qsTr("开启 AFG")
                            checked: scope.afgOutput()
                            onToggled: scope.setAfgOutput(checked)
                        }
                        Item { Layout.columnSpan: 6; Layout.fillWidth: true }
                    }
                }
            }
        }

                                }
                            }

                            // ---------- 仪器格 2：直流电源（虚拟 SPD3303X-E） ----------
                            Rectangle {
                                id: powerCell
                                SplitView.preferredHeight: 200
                                SplitView.minimumHeight: 140
                                visible: root.powerVisible
                                clip: true
                                color: "#0d1117"
                                border.color: "#30363d"
                                radius: 4

                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 6

                                    RowLayout {
                                        Label { text: qsTr("直流电源 · Siglent SPD3303X-E"); color: "#e6edf3"; font.bold: true }
                                        Label { text: qsTr("（虚拟仪器）"); color: "#8b98a5"; font.pixelSize: 10 }
                                        Item { Layout.fillWidth: true }
                                        Label {
                                            Layout.preferredWidth: 300
                                            horizontalAlignment: Text.AlignRight
                                            elide: Text.ElideRight
                                            text: power.commandText.length > 0 ? power.commandText : "—"
                                            color: "#8b98a5"; font.pixelSize: 9
                                            font.family: "Consolas, monospace"
                                        }
                                    }

                                    RowLayout {
                                        spacing: 10
                                        Label { text: qsTr("通道") }
                                        ComboBox {
                                            Layout.preferredWidth: 80
                                            model: ["CH1", "CH2", "CH3"]
                                            currentIndex: power.channel - 1
                                            onActivated: power.setChannel(index + 1)
                                        }
                                        Switch {
                                            text: qsTr("输出")
                                            checked: power.outputOn
                                            onClicked: power.setOutput(checked)
                                        }
                                        Label { text: qsTr("设定电压 (mV)") }
                                        SpinBox {
                                            from: 0; to: 32000; stepSize: 100; editable: true
                                            value: Math.round(power.voltage * 1000)
                                            onValueModified: power.setVoltage(value / 1000.0)
                                        }
                                        Label { text: qsTr("设定电流 (mA)") }
                                        SpinBox {
                                            from: 0; to: 5000; stepSize: 10; editable: true
                                            value: Math.round(power.current * 1000)
                                            onValueModified: power.setCurrent(value / 1000.0)
                                        }
                                        Item { Layout.fillWidth: true }
                                    }

                                    RowLayout {
                                        spacing: 16
                                        Label {
                                            text: qsTr("实测电压：") + power.measuredVoltage.toFixed(3) + " V"
                                            color: "#d7e2ea"; font.family: "Consolas, monospace"
                                        }
                                        Label {
                                            text: qsTr("实测电流：") + power.measuredCurrent.toFixed(4) + " A"
                                            color: "#d7e2ea"; font.family: "Consolas, monospace"
                                        }
                                        Label {
                                            text: power.outputOn ? qsTr("输出：ON") : qsTr("输出：OFF")
                                            color: power.outputOn ? "#3fb950" : "#8b98a5"
                                        }
                                        Item { Layout.fillWidth: true }
                                        Button { text: qsTr("读取一次"); onClicked: power.refresh() }
                                    }

                                    Label {
                                        Layout.fillWidth: true
                                        text: qsTr("说明：阶段3 为虚拟电源（SCPI 已按鼎阳 SPD 系列常见写法实现，待真机核对）；加电/断电按钮随后接入。")
                                        color: "#8b98a5"; font.pixelSize: 10; wrapMode: Text.Wrap
                                    }
                                }
                            }

                        }
                }
            }

            // ---------- 右区：测试报表（总表） ----------
            Rectangle {
                SplitView.preferredWidth: 320
                color: "#f6f8fa"
                border.color: "#d0d7de"
                radius: 4

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6

                    Label { text: qsTr("测试报表（验收记录）"); font.bold: true; color: "#24292f" }
                    Label {
                        Layout.fillWidth: true
                        text: root.reportSummaryText
                        color: "#57606a"
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                    }

                    ListView {
                        id: reportList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: reportModel
                        clip: true
                        spacing: 3
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: Rectangle {
                            width: reportList.width - 8
                            height: 42
                            color: model.passed ? "#f2fbf4" : "#fff5f5"
                            border.color: model.passed ? "#b7e0c0" : "#f0b8b8"
                            radius: 3
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 4
                                spacing: 1
                                RowLayout {
                                    spacing: 4
                                    Label {
                                        text: model.group + (model.sub ? " · " + model.sub : "")
                                        color: "#57606a"; font.pixelSize: 10
                                        Layout.fillWidth: true; elide: Text.ElideRight
                                    }
                                    Label {
                                        text: model.verdict
                                        color: model.passed ? "#1a7f37" : "#cf222e"
                                        font.pixelSize: 10; font.bold: true
                                    }
                                }
                                RowLayout {
                                    spacing: 6
                                    Label { text: model.detail; color: "#24292f"; font.pixelSize: 11; font.bold: true }
                                    Label {
                                        text: model.spec + (model.unit ? " " + model.unit : "")
                                        color: "#8b98a5"; font.pixelSize: 10
                                    }
                                    Item { Layout.fillWidth: true }
                                    Label {
                                        text: model.value + (model.unit ? " " + model.unit : "")
                                        color: "#24292f"; font.pixelSize: 11
                                        font.family: "Consolas, monospace"
                                    }
                                }
                            }
                        }
                    }

                    RowLayout {
                        spacing: 4
                        Button {
                            text: qsTr("导出 HTML")
                            padding: 2
                            Layout.preferredHeight: 24
                            onClicked: controller.saveReport("reports/report.html")
                        }
                        Button {
                            text: qsTr("导出 Excel（预留）")
                            padding: 2
                            Layout.preferredHeight: 24
                            onClicked: controller.saveReportExcel("reports/report.xlsx")
                        }
                        Item { Layout.fillWidth: true }
                    }
                }
            }
        }

        // ================= 最近下发的 SCPI 命令 =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            color: "#eef2f6"
            border.color: "#d0d7de"
            radius: 3
            Label {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                text: qsTr("最近命令：") + (controller.lastCommandText.length > 0 ? controller.lastCommandText : "—")
                font.family: "Consolas, monospace"
                font.pixelSize: 11
                color: "#24292f"
            }
        }

        // ================= 流程执行结果 =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 108
            color: "#f6f8fa"
            border.color: "#d0d7de"
            radius: 4

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4
                Label { text: qsTr("流程执行结果"); font.bold: true; color: "#24292f" }
                ListView {
                    id: resultList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: resultModel
                    clip: true
                    spacing: 2
                    delegate: Label {
                        text: model.text
                        padding: 2
                        font.pixelSize: 11
                        font.family: "Consolas, monospace"
                        color: "#24292f"
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }

    ListModel { id: resultModel }
    ListModel { id: flowStepModel }
    ListModel { id: addActionModel }
    ListModel { id: stepParamModel }
    ListModel { id: discoveryModel }
    ListModel { id: reportModel }

    Connections {
        target: controller
        function onResultAdded(line) { resultModel.append({ "text": line }) }
        function onFlowFinished(testId) {
            resultModel.append({ "text": "流程结束: " + testId })
            root.refreshReport()
        }
        function onFlowChanged() { root.refreshFlow() }
        function onReportChanged() { root.refreshReport() }
    }
    Dialog {
        id: discoveryDialog
        title: qsTr("仪器发现（连接测试 / 网络扫描 / VISA 枚举）")
        modal: true
        width: 820
        height: 560
        standardButtons: Dialog.Close

        ColumnLayout {
            anchors.fill: parent
            spacing: 6

            RowLayout {
                Label { text: qsTr("TCP 手工添加"); font.bold: true }
                TextField {
                    id: tcpHost
                    placeholderText: qsTr("IP 地址")
                    text: "192.168.10.16"
                    Layout.preferredWidth: 150
                }
                Label { text: qsTr("端口") }
                SpinBox {
                    id: tcpPort
                    from: 1
                    to: 65535
                    value: 5555
                    editable: true
                    Layout.preferredWidth: 110
                }
                Button { text: qsTr("连接测试"); onClicked: root.testTcp(tcpHost.text, tcpPort.value) }
                Button { text: qsTr("添加"); onClicked: root.addTcp(tcpHost.text, tcpPort.value) }
                Item { Layout.fillWidth: true }
            }
            Label {
                id: tcpTestResult
                text: ""
                color: "#57606a"
                font.pixelSize: 10
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#d0d7de" }

            RowLayout {
                Label { text: qsTr("网络扫描 / VISA"); font.bold: true }
                TextField {
                    id: subnetField
                    text: controller.localSubnet()
                    placeholderText: qsTr("网段，如 192.168.1.0/24")
                    Layout.preferredWidth: 180
                }
                Button { text: qsTr("开始扫描"); onClicked: root.runScan(subnetField.text) }
                Button { text: qsTr("枚举 VISA"); onClicked: root.runVisa() }
                Item { Layout.fillWidth: true }
            }
            Label {
                id: discoveryStatus
                text: qsTr("手动触发，避免自动扫描公司网络")
                color: "#8b98a5"
                font.pixelSize: 10
            }

            ListView {
                id: discoveryList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: discoveryModel
                clip: true
                spacing: 3
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Rectangle {
                    width: discoveryList.width - 8
                    height: 52
                    color: "#f6f8fa"
                    border.color: "#d0d7de"
                    radius: 3
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Label { text: model.title; font.bold: true; color: "#24292f" }
                            Label {
                                text: model.idn
                                color: "#57606a"
                                font.pixelSize: 10
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        Button {
                            text: qsTr("添加到注册表")
                            padding: 2
                            Layout.preferredHeight: 24
                            onClicked: root.addDiscovered(model)
                        }
                    }
                }
            }
        }
    }
}






















