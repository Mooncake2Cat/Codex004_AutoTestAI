import QtQuick
import QtQuick.Controls

// 深蓝科技风按钮：琥珀/亮橙渐变，与深蓝背景形成强对比
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
        color: !control.enabled ? "#7A6A4A" : "#1A1206"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 4
        border.width: 1
        border.color: !control.enabled ? "#3A2E1A"
                    : (control.down ? "#FFE08A"
                    : (control.hovered || control.checked || control.highlighted ? "#FFE08A" : "#F59E0B"))
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: !control.enabled ? "#2E2415"
                     : (control.down ? "#B45309"
                     : (control.hovered || control.checked || control.highlighted ? "#FBBF24" : "#F59E0B"))
            }
            GradientStop {
                position: 1.0
                color: !control.enabled ? "#1F1A10"
                     : (control.down ? "#92400E" : "#D97706")
            }
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            radius: 1
            color: "#FFE08A"
            opacity: control.enabled ? (control.hovered || control.checked || control.highlighted ? 0.75 : 0.35) : 0.1
        }
    }
}