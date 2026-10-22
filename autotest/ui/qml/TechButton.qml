import QtQuick
import QtQuick.Controls

// 深蓝科技风按钮：低饱和暗琥珀/古铜色，避免刺眼
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
        color: !control.enabled ? "#7A6E58" : "#F2E3C2"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 4
        border.width: 1
        border.color: !control.enabled ? "#3A3222"
                    : (control.down ? "#8A6420"
                    : (control.hovered || control.checked || control.highlighted ? "#A87B2A" : "#7A5A20"))
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: !control.enabled ? "#3A3222"
                     : (control.down ? "#5E3F10"
                     : (control.hovered || control.checked || control.highlighted ? "#9A6B1F" : "#87601A"))
            }
            GradientStop {
                position: 1.0
                color: !control.enabled ? "#2A2419"
                     : (control.down ? "#4A320C"
                     : (control.hovered || control.checked || control.highlighted ? "#7A5216" : "#6E4A14"))
            }
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            radius: 1
            color: "#C9A45A"
            opacity: control.enabled ? (control.hovered || control.checked || control.highlighted ? 0.35 : 0.16) : 0.08
        }
    }
}