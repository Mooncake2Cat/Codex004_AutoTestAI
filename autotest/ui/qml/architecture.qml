import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// 窗口2：架构台（只读展示六层实现与层间关系；事件来自真实事件总线）
ApplicationWindow {
    id: arch
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    objectName: "architectureWindow"
    title: qsTr("架构台 - 分层实现与数据流转（只读）")
    visibility: Window.Maximized
    visible: true
    color: "#0B1830"

    signal clearRequested()

    // 自动滚动：新日志到达时滚到最底部（可关闭）
    property bool autoScroll: true

    // 分层配色（与操作台一致）
    function layerColor(layer) {
        if (layer === "ui") return "#38BDF8";
        if (layer === "glue") return "#22D3EE";
        if (layer === "app") return "#34D399";
        if (layer === "hal") return "#FB923C";
        if (layer === "data") return "#A78BFA";
        if (layer === "report") return "#64748B";
        return "#8FB3D9";
    }

    // 层定义（实现内容与层间关系）
    ListModel {
        id: layers
        ListElement {
            layer: "ui"; title: "① 表示层"
            files: "qml/main.qml · qml/architecture.qml · scope_panel 面板"
            rel: "向下：QML 调用胶合层 Slot/Property（QML→Python）；接受 Signal 推送"
            state: "已实现"
        }
        ListElement {
            layer: "glue"; title: "② 胶合层"
            files: "controller.py · scope_panel.py · trace_view.py"
            rel: "上层：表示层动作入口　下层：调用应用层引擎与 HAL，并回推状态"
            state: "已实现"
        }
        ListElement {
            layer: "app"; title: "③ 应用与算法层"
            files: "engine.py · methods.py · models.py（阶段4：能力库/算法库）"
            rel: "上层：被胶合层调用　下层：经仪器接口调用 HAL（measure/loop/branch）"
            state: "已实现"
        }
        ListElement {
            layer: "hal"; title: "④ 硬件抽象层"
            files: "instrument.py · scpi.py · rigol_dho.py · mock.py · factory.py"
            rel: "上层：向上提供统一仪器接口　下层：传输层（Socket/串口/VISA，阶段6）"
            state: "已实现"
        }
        ListElement {
            layer: "data"; title: "⑤ 数据层"
            files: "store.py（SQLite：results / measurements）"
            rel: "上层：接收应用层测量结果　输出：报告层读取"
            state: "已实现"
        }
        ListElement {
            layer: "report"; title: "⑥ 报告层"
            files: "html_report.py（HTML 总表）"
            rel: "上层：由胶合层触发　输入：数据层结果"
            state: "已实现"
        }
        ListElement {
            layer: "server"; title: "⑦ 服务器通信层"
            files: "（本阶段范围外）"
            rel: "预留：Push 结果上报 / Pull 配置下发 / 分析回传"
            state: "范围外"
        }
    }

    header: Rectangle {
        height: 52
        gradient: Gradient {
        GradientStop { position: 0.0; color: "#0A1C36" }
        GradientStop { position: 1.0; color: "#04101F" }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12

            Label {
                text: qsTr("架构台 · 分层实现与数据流转")
                color: "#EAF4FF"
                font.pixelSize: 16
                font.bold: true
            }
            Label {
                text: qsTr("（只读展示；事件来自真实执行）")
                color: "#7FA6CC"
                font.pixelSize: 11
            }
            Item { Layout.fillWidth: true }
            Label {
                id: statsLabel
                text: qsTr("等待事件…")
                color: "#7FA6CC"
                font.pixelSize: 11
            }
            CheckBox {
                text: qsTr("自动滚动")
                checked: arch.autoScroll
                onToggled: arch.autoScroll = checked
            }
            Button {
                text: qsTr("清空事件")
                onClicked: { trace.clear(); arch.clearRequested() }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        z: 0
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#050B1A" }
            GradientStop { position: 0.5; color: "#071A33" }
            GradientStop { position: 1.0; color: "#030814" }
        }
    }
    Canvas {
        anchors.fill: parent
        z: 0
        opacity: 0.28
        onPaint: {
            var ctx = getContext("2d");
            var w = width;
            var h = height;
            ctx.clearRect(0, 0, w, h);
            ctx.strokeStyle = "#0E3A66";
            ctx.lineWidth = 1;
            for (var x = 0; x < w; x += 40) {
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, h);
                ctx.stroke();
            }
            for (var y = 0; y < h; y += 40) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
    ColumnLayout {
        z: 1
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // 层间关系（静态说明，与卡片一一对应）
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            color: "#0C1B33"
            border.color: "#1E3A5F"
            radius: 4
            Label {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                verticalAlignment: Text.AlignVCenter
                text: qsTr("数据/调用流向：  表示层  →  胶合层  →  应用与算法层  →  硬件抽象层  →  （测量结果）数据层  →  报告层        服务器通信层：本阶段范围外")
                color: "#DCEBFF"
                font.pixelSize: 12
                elide: Text.ElideRight
            }
        }

        // 分层卡片（3 列网格；每张卡片内显示该层的真实事件日志）
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            rowSpacing: 8
            columnSpacing: 8

            Repeater {
                model: layers

                Rectangle {
                    id: card
                    property string layerKey: model.layer
                    property int layerCount: 0
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#050D1C"
                    border.color: arch.layerColor(model.layer)
                    border.width: model.state === "范围外" ? 1 : 2
                    radius: 4

                    ListModel { id: cardModel }

                    Connections {
                        target: trace
                        function onEventLogged(ev) {
                            if (ev.layer !== card.layerKey) return
                            // 全量保留（不再裁剪），最新日志追加在末尾
                            cardModel.append({
                                "line": (ev.ts.length >= 23 ? ev.ts.substring(11, 23) : ev.ts)
                                        + "  " + ev.kind + "/" + ev.action
                                        + (ev.result.length > 0 ? " ⇒ " + ev.result : "")
                            })
                            card.layerCount += 1
                            // 持续滚动到最新一条
                            if (arch.autoScroll) Qt.callLater(cardList.positionViewAtEnd)
                        }
                    }

                    Connections {
                        target: arch
                        function onClearRequested() {
                            cardModel.clear()
                            card.layerCount = 0
                        }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4

                        RowLayout {
                            Label {
                                text: card.cardTitleText
                                color: arch.layerColor(card.layerKey)
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: model.state
                                color: model.state === "范围外" ? "#5F7FA8" : "#34D399"
                                font.pixelSize: 10
                            }
                            Label {
                                text: qsTr("事件 ") + card.layerCount
                                color: "#5F7FA8"
                                font.pixelSize: 10
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: model.files
                            color: "#5F7FA8"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Label {
                            Layout.fillWidth: true
                            text: model.rel
                            color: "#C7E0FF"
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: "#0A2540" }

                        ListView {
                            id: cardList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: cardModel
                            clip: true
                            spacing: 1
                            // 滚动条：始终显示，便于查看历史日志
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn }
                            delegate: Label {
                                width: cardList.width - 14
                                text: model.line
                                color: "#5F7FA8"
                                font.pixelSize: 9
                                font.family: "Consolas, monospace"
                                elide: Text.ElideRight
                            }
                        }
                    }

                    // 卡片标题文本（ListModel 角色 title 与控件属性不冲突，用别名属性承载）
                    property string cardTitleText: model.title
                }
            }
        }
    }

    Connections {
        target: trace
        function onStatsChanged(st) {
            var bl = st.by_layer
            statsLabel.text = qsTr("事件 ") + st.total + qsTr(" / 存储 ") + st.stored + qsTr(" / 轮询噪声 ") + st.noisy
                              + "　UI " + bl.ui + " · 胶合 " + bl.glue + " · 应用 " + bl.app
                              + " · HAL " + bl.hal + " · 数据 " + bl.data + " · 报告 " + bl.report
        }
    }
}

