import QtQuick
import QtQuick.Controls

// 深蓝科技风页签：选中态暖金下划线
TabButton {
    id: control
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        font.family: control.font.family
        font.pixelSize: control.font.pixelSize
        font.bold: control.checked
        color: control.checked ? "#F0C674" : (control.hovered ? "#FFFFFF" : "#D9E9FA")
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        color: control.checked ? "#20354F" : (control.hovered ? "#143253" : "#0B1B31")
        border.width: 1
        border.color: control.checked ? "#A98243" : "#294C70"
        radius: 3
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: control.checked ? 2 : 0
            color: "#D7A84A"
        }
    }
}