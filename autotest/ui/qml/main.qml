import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1320
    height: 900
    visible: true
    title: qsTr("通用自动化测试软件平台 - 原型验证（Rigol DHO924S 示波器）")
    minimumWidth: 1100
    minimumHeight: 760

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

    onSelectedChannelChanged: {
        refreshVertical()
        scope.setPollChannel(root.selectedChannel)
    }
    Component.onCompleted: {
        refreshVertical()
        scope.setPollChannel(root.selectedChannel)
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
                text: qsTr("分层跟踪")
                onClicked: tracePanel.visible = !tracePanel.visible
            }
            Item { Layout.fillWidth: true }
            Label {
                text: qsTr("状态：") + controller.status
                font.bold: true
                color: controller.status.indexOf("完成") === 0 ? "#1a7f37" : "#24292f"
            }
        }

        // ================= 波形屏 + 读数 =================
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 260
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

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
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

                    Item { Layout.fillHeight: true }
                    Label {
                        text: qsTr("提示：本屏不显示波形（真机波形下载未接入）；\n右侧读数为真机轮询值，面板命令直接下发真机。")
                        color: "#8b98a5"
                        font.pixelSize: 10
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        // ================= 示波器设置面板 =================
        TabBar {
            id: ctrlTabs
            Layout.fillWidth: true
            TabButton { text: qsTr("垂直") }
            TabButton { text: qsTr("水平") }
            TabButton { text: qsTr("触发") }
            TabButton { text: qsTr("采集") }
            TabButton { text: qsTr("测量") }
            TabButton { text: qsTr("信号源") }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 176
            color: "#f6f8fa"
            border.color: "#d0d7de"
            radius: 4

            StackLayout {
                anchors.fill: parent
                anchors.margins: 10
                currentIndex: ctrlTabs.currentIndex

                // ---------- 垂直 ----------
                RowLayout {
                    spacing: 22
                    ColumnLayout {
                        Label { text: qsTr("通道"); font.bold: true }
                        RowLayout {
                            spacing: 4
                            ButtonGroup { id: chButtonGroup; exclusive: true }
                            Repeater {
                                model: 4
                                Button {
                                    text: (checked ? "● " : "○ ") + "CH" + (index + 1)
                                    checkable: true
                                    focusPolicy: Qt.NoFocus
                                    ButtonGroup.group: chButtonGroup
                                    checked: root.selectedChannel === (index + 1)
                                    onClicked: root.selectedChannel = index + 1
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("显示"); font.bold: true }
                        Switch {
                            id: chEnableSwitch
                            text: qsTr("开启")
                            onClicked: scope.setChannelEnabled(root.selectedChannel, checked)
                        }
                        Switch {
                            id: chInvertSwitch
                            text: qsTr("反相")
                            onClicked: scope.setChannelInvert(root.selectedChannel, checked)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("垂直档位"); font.bold: true }
                        ComboBox {
                            id: vdivCombo
                            Layout.preferredWidth: 120
                            model: root.vDivLabels
                            onActivated: scope.setChannelScale(root.selectedChannel, root.vDivValues[index])
                        }
                        Label { text: qsTr("耦合") }
                        ComboBox {
                            id: couplingCombo
                            Layout.preferredWidth: 120
                            model: root.couplingValues
                            onActivated: scope.setChannelCoupling(root.selectedChannel, root.couplingValues[index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("偏移 (mV)"); font.bold: true }
                        SpinBox {
                            id: offsetSpin
                            from: -10000; to: 10000; stepSize: 10
                            editable: true
                            onValueModified: scope.setChannelOffset(root.selectedChannel, value / 1000.0)
                        }
                        Label { text: qsTr("探头") }
                        ComboBox {
                            id: probeCombo
                            Layout.preferredWidth: 120
                            model: ["1x", "10x", "100x"]
                            onActivated: scope.setChannelProbe(root.selectedChannel, [1, 10, 100][index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("带宽限制"); font.bold: true }
                        Switch {
                            id: chBwSwitch
                            text: qsTr("20MHz")
                            onClicked: scope.setChannelBwLimit(root.selectedChannel, checked)
                        }
                    }
                    Item { Layout.fillWidth: true }
                }

                // ---------- 水平 ----------
                RowLayout {
                    spacing: 24
                    ColumnLayout {
                        Label { text: qsTr("时基 (s/div)"); font.bold: true }
                        ComboBox {
                            Layout.preferredWidth: 130
                            model: root.timeLabels
                            currentIndex: root.indexOfValue(root.timeValues, scope.timeScale())
                            onActivated: scope.setTimeScale(root.timeValues[index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("水平位置 (µs)"); font.bold: true }
                        SpinBox {
                            from: -5000; to: 5000; stepSize: 10
                            editable: true
                            value: Math.round(scope.timeOffset() * 1000000)
                            onValueModified: scope.setTimeOffset(value / 1000000.0)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("当前时基"); font.bold: true }
                        Label { text: scope.timebaseText; font.pixelSize: 14 }
                        Label { text: qsTr("(满屏 10 格 = ") + (scope.timeScale() * 10 * 1000).toFixed(3) + " ms)"; color: "#57606a" }
                    }
                    Item { Layout.fillWidth: true }
                }

                // ---------- 触发 ----------
                RowLayout {
                    spacing: 22
                    ColumnLayout {
                        Label { text: qsTr("触发模式"); font.bold: true }
                        ComboBox {
                            Layout.preferredWidth: 110
                            model: root.sweepValues
                            currentIndex: root.sweepValues.indexOf(scope.triggerSweep())
                            onActivated: scope.setTriggerSweep(root.sweepValues[index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("触发源"); font.bold: true }
                        ComboBox {
                            Layout.preferredWidth: 100
                            model: ["CH1", "CH2", "CH3", "CH4"]
                            currentIndex: scope.triggerSource() - 1
                            onActivated: scope.setTriggerSource(index + 1)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("边沿斜率"); font.bold: true }
                        ComboBox {
                            Layout.preferredWidth: 110
                            model: root.slopeLabels
                            currentIndex: root.slopeValues.indexOf(scope.triggerSlope())
                            onActivated: scope.setTriggerSlope(root.slopeValues[index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("触发电平 (mV)"); font.bold: true }
                        SpinBox {
                            from: -10000; to: 10000; stepSize: 10
                            editable: true
                            value: Math.round(scope.triggerLevel() * 1000)
                            onValueModified: scope.setTriggerLevel(value / 1000.0)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("操作"); font.bold: true }
                        Button { text: qsTr("强制触发"); onClicked: scope.forceTrigger() }
                    }
                    Item { Layout.fillWidth: true }
                }

                // ---------- 采集 ----------
                RowLayout {
                    spacing: 16
                    ColumnLayout {
                        Label { text: qsTr("采集中断"); font.bold: true }
                        RowLayout {
                            spacing: 6
                            Button { text: "RUN"; highlighted: scope.running; onClicked: scope.setRunning(true) }
                            Button { text: "STOP"; highlighted: !scope.running; onClicked: scope.setRunning(false) }
                            Button { text: "SINGLE"; onClicked: scope.singleShot() }
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("自动设置 / 清除"); font.bold: true }
                        RowLayout {
                            spacing: 6
                            Button { text: qsTr("AUTO 自动设置"); onClicked: scope.autoSet() }
                            Button { text: qsTr("清除显示"); onClicked: scope.clearScope() }
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("当前状态"); font.bold: true }
                        Label { text: scope.running ? qsTr("运行中 (RUN)") : qsTr("已停止 (STOP)"); font.pixelSize: 14 }
                        Label { text: qsTr("时基 ") + scope.timebaseText; color: "#57606a" }
                    }
                    Item { Layout.fillWidth: true }
                }

                // ---------- 测量 ----------
                ColumnLayout {
                    spacing: 8
                    RowLayout {
                        Label { text: qsTr("测量项（点击开关）"); font.bold: true }
                        Item { Layout.fillWidth: true }
                        Switch {
                            text: qsTr("统计")
                            checked: scope.measureStat
                            onToggled: scope.setMeasureStat(checked)
                        }
                        Button { text: qsTr("复位统计"); onClicked: scope.measureReset() }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: root.measureKeys.length
                            Button {
                                property string mkey: root.measureKeys[index]
                                text: (scope.stateSeq >= 0 && scope.measureItemEnabled(mkey) ? "● " : "○ ") + root.measureLabels[index]
                                onClicked: scope.setMeasureItem(mkey, !scope.measureItemEnabled(mkey))
                            }
                        }
                    }
                }

                // ---------- 信号源（AFG，DHO924S 内置） ----------
                RowLayout {
                    spacing: 22
                    ColumnLayout {
                        Label { text: qsTr("波形"); font.bold: true }
                        ComboBox {
                            Layout.preferredWidth: 110
                            model: root.afgLabels
                            currentIndex: root.afgValues.indexOf(scope.afgFunction())
                            onActivated: scope.setAfgFunction(root.afgValues[index])
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("频率 (Hz)"); font.bold: true }
                        SpinBox {
                            from: 1; to: 25000000; stepSize: 100; editable: true
                            value: Math.round(scope.afgFrequency())
                            onValueModified: scope.setAfgFrequency(value)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("幅度 (mVpp)"); font.bold: true }
                        SpinBox {
                            from: 10; to: 5000; stepSize: 10; editable: true
                            value: Math.round(scope.afgAmplitude() * 1000)
                            onValueModified: scope.setAfgAmplitude(value / 1000.0)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("偏移 (mV)"); font.bold: true }
                        SpinBox {
                            from: -2500; to: 2500; stepSize: 10; editable: true
                            value: Math.round(scope.afgOffset() * 1000)
                            onValueModified: scope.setAfgOffset(value / 1000.0)
                        }
                    }
                    ColumnLayout {
                        Label { text: qsTr("输出"); font.bold: true }
                        Switch {
                            text: qsTr("开启 AFG")
                            checked: scope.afgOutput()
                            onToggled: scope.setAfgOutput(checked)
                        }
                    }
                    Item { Layout.fillWidth: true }
                }
            }
        }

        // ================= 分层跟踪（阶段1 临时视图，事件驱动） =================
        Rectangle {
            id: tracePanel
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 190 : 0
            visible: false
            color: "#0d1117"
            border.color: "#30363d"
            radius: 4

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 4

                RowLayout {
                    Label { text: qsTr("分层跟踪（真实事件）"); color: "#e6edf3"; font.bold: true }
                    Label {
                        id: traceStats
                        text: qsTr("等待事件…")
                        color: "#8b98a5"
                        font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: qsTr("清空")
                        onClicked: { traceModel.clear(); trace.clear() }
                    }
                }

                RowLayout {
                    spacing: 4
                    Label { text: qsTr("时间"); color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 90 }
                    Label { text: qsTr("层"); color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 55 }
                    Label { text: qsTr("事件"); color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 140 }
                    Label { text: qsTr("详情 / 结果"); color: "#8b98a5"; font.pixelSize: 11; Layout.fillWidth: true }
                    Label { text: qsTr("耗时"); color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 70 }
                }

                ListView {
                    id: traceList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: traceModel
                    clip: true
                    delegate: RowLayout {
                        spacing: 4
                        Label { text: model.time; color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 90 }
                        Label { text: model.layer; color: root.layerColor(model.layer); font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 55 }
                        Label { text: model.kind + "/" + model.action; color: "#c9d1d9"; font.pixelSize: 11; Layout.preferredWidth: 140; elide: Text.ElideRight }
                        Label {
                            text: model.detail + (model.result.length > 0 ? "　⇒ " + model.result : "")
                            color: model.status === "error" ? "#f85149" : "#8b98a5"
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                        Label { text: model.duration; color: "#8b98a5"; font.pixelSize: 11; Layout.preferredWidth: 70 }
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
    ListModel { id: traceModel }

    Connections {
        target: controller
        function onResultAdded(line) { resultModel.append({ "text": line }) }
        function onFlowFinished(testId) { resultModel.append({ "text": "流程结束: " + testId }) }
    }

    // 分层跟踪：事件总线 -> 界面（真实调用链）
    Connections {
        target: trace
        function onEventLogged(ev) {
            traceModel.append({
                "time": (ev.ts && ev.ts.length >= 23) ? ev.ts.substring(11, 23) : (ev.ts || ""),
                "layer": ev.layer || "",
                "kind": ev.kind || "",
                "action": ev.action || "",
                "detail": ev.detail || "",
                "result": ev.result || "",
                "duration": (ev.duration_ms === undefined ? "" : ev.duration_ms.toFixed(1) + " ms"),
                "status": ev.status || "ok"
            })
            while (traceModel.count > 500) traceModel.remove(0)
            trace.refreshStats()
        }
        function onStatsChanged(st) {
            var bl = st.by_layer
            traceStats.text = qsTr("事件 ") + st.total + qsTr(" / 存储 ") + st.stored + qsTr(" / 轮询噪声 ") + st.noisy
                              + "　UI " + bl.ui + " · 胶合 " + bl.glue + " · 应用 " + bl.app
                              + " · HAL " + bl.hal + " · 数据 " + bl.data + " · 报告 " + bl.report
        }
    }
}










