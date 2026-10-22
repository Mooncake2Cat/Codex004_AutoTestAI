import QtQuick
import QtQuick.Controls

// 深蓝科技风按钮：渐变底、青蓝描边、悬停/按下/选中高亮
Button {
    id: control
    implicitHeight: 28
    implicitWidth: Math.max(64, contentItem.implicitWidth + 20)
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    hoverEnabled: true

    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? "#4B6584"
             : (control.checked || control.highlighted ? "#EAF7FF" : "#DCEBFF")
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 4
        border.width: 1
        border.color: !control.enabled ? "#1B3350"
                    : (control.down || control.hovered || control.checked || control.highlighted
                       ? "#38BDF8" : "#2A5A8A")
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: !control.enabled ? "#0A1628"
                     : (control.down ? "#07182E"
                     : (control.checked || control.highlighted ? "#144A78"
                     : (control.hovered ? "#123A63" : "#0E2747")))
            }
            GradientStop { position: 1.0; color: "#081A30" }
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            radius: 1
            color: control.enabled ? "#38BDF8" : "#1B3350"
            opacity: (control.hovered || control.checked || control.highlighted) ? 0.55 : 0.18
        }
    }
}