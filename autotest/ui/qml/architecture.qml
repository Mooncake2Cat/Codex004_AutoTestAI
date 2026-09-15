import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// 窗口2：架构台（只读展示六层实现与层间关系；事件来自真实事件总线）
ApplicationWindow {
    id: arch
    objectName: "architectureWindow"
    title: qsTr("架构台 - 分层实现与数据流转（只读）")
    visibility: Window.Maximized
    visible: true
    color: "#f6f8fa"

    signal clearRequested()

    // 分层配色（与操作台一致）
    function layerColor(layer) {
        if (layer === "ui") return "#58a6ff";
        if (layer === "glue") return "#39c5cf";
        if (layer === "app") return "#3fb950";
        if (layer === "hal") return "#f0883e";
        if (layer === "data") return "#bc8cff";
        if (layer === "report") return "#8b949e";
        return "#57606a";
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
        color: "#1f2933"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12

            Label {
                text: qsTr("架构台 · 分层实现与数据流转")
                color: "#e6edf3"
                font.pixelSize: 16
                font.bold: true
            }
            Label {
                text: qsTr("（只读展示；事件来自真实执行）")
                color: "#9fb3c8"
                font.pixelSize: 11
            }
            Item { Layout.fillWidth: true }
            Label {
                id: statsLabel
                text: qsTr("等待事件…")
                color: "#9fb3c8"
                font.pixelSize: 11
            }
            Button {
                text: qsTr("清空事件")
                onClicked: { trace.clear(); arch.clearRequested() }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // 层间关系（静态说明，与卡片一一对应）
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            color: "#eef2f6"
            border.color: "#d0d7de"
            radius: 4
            Label {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                verticalAlignment: Text.AlignVCenter
                text: qsTr("数据/调用流向：  表示层  →  胶合层  →  应用与算法层  →  硬件抽象层  →  （测量结果）数据层  →  报告层        服务器通信层：本阶段范围外")
                color: "#24292f"
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
                    color: "#0d1117"
                    border.color: arch.layerColor(model.layer)
                    border.width: model.state === "范围外" ? 1 : 2
                    radius: 4

                    ListModel { id: cardModel }

                    Connections {
                        target: trace
                        function onEventLogged(ev) {
                            if (ev.layer !== card.layerKey) return
                            cardModel.append({
                                "line": (ev.ts.length >= 23 ? ev.ts.substring(11, 23) : ev.ts)
                                        + "  " + ev.kind + "/" + ev.action
                                        + (ev.result.length > 0 ? " ⇒ " + ev.result : "")
                            })
                            while (cardModel.count > 16) cardModel.remove(0)
                            card.layerCount += 1
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
                                color: model.state === "范围外" ? "#8b98a5" : "#3fb950"
                                font.pixelSize: 10
                            }
                            Label {
                                text: qsTr("事件 ") + card.layerCount
                                color: "#8b98a5"
                                font.pixelSize: 10
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: model.files
                            color: "#8b98a5"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        Label {
                            Layout.fillWidth: true
                            text: model.rel
                            color: "#c9d1d9"
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: "#21262d" }

                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: cardModel
                            clip: true
                            spacing: 1
                            delegate: Label {
                                width: ListView.view.width
                                text: model.line
                                color: "#8b98a5"
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
