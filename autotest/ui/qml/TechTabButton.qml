import QtQuick
import QtQuick.Controls

// 深蓝科技风页签：选中态青蓝下划线
TabButton {
    id: control
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.checked ? "#EAF7FF" : (control.hovered ? "#9FD3FF" : "#7FA6CC")
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        color: control.checked ? "#12345A" : (control.hovered ? "#0E2747" : "transparent")
        radius: 3
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: control.checked ? 2 : 0
            color: "#38BDF8"
        }
    }
}