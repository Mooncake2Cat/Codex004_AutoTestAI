import QtQuick
import QtQuick.Controls

// 深蓝底 + 琥珀边框/文字 的下拉菜单
ComboBox {
    id: control
    font.family: "Microsoft YaHei UI"
    font.pixelSize: 12
    implicitHeight: 24
    hoverEnabled: true

    delegate: ItemDelegate {
        width: control.width
        height: 26
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: control.textRole ? model[control.textRole] : modelData
            font: control.font
            color: highlighted ? "#1A1206" : "#FDE68A"
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            color: highlighted ? "#F59E0B" : "transparent"
        }
    }

    indicator: Canvas {
        x: control.width - width - 8
        y: control.topPadding + (control.availableHeight - height) / 2
        width: 10
        height: 6
        contextType: "2d"
        onPaint: {
            context.reset();
            context.moveTo(0, 0);
            context.lineTo(width, 0);
            context.lineTo(width / 2, height);
            context.closePath();
            context.fillStyle = control.enabled ? "#F59E0B" : "#7A6A4A";
            context.fill();
        }
    }

    contentItem: Text {
        leftPadding: 8
        rightPadding: control.indicator.width + 6
        text: control.displayText
        font: control.font
        color: control.enabled ? "#FDE68A" : "#7A6A4A"
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: 100
        implicitHeight: 24
        radius: 3
        color: control.enabled ? (control.hovered ? "#132A47" : "#0B1830") : "#0A1628"
        border.width: 1
        border.color: control.enabled ? (control.hovered || control.popup.visible ? "#FBBF24" : "#B45309") : "#3A2E1A"
    }

    popup: Popup {
        y: control.height - 1
        width: control.width
        implicitHeight: contentItem.implicitHeight + 4
        padding: 2
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator { }
        }
        background: Rectangle {
            color: "#0B1830"
            border.color: "#F59E0B"
            radius: 3
        }
    }
}