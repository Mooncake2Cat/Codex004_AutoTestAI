"""PySide6 + QML 应用入口。"""
from __future__ import annotations

import os
import sys


def main() -> int:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    # 深蓝科技风：Fusion 样式 + 深色调色板（只影响外观，不影响业务逻辑）
    QQuickStyle.setStyle("Fusion")

    from .controller import TestController
    from .panels.power_panel import PowerPanel
    from .scope_panel import ScopePanel
    from .trace_view import TraceBridge

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AutoTestAI-Prototype")
    app.setFont(QFont("Microsoft YaHei UI", 9))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#050B1A"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#DCEBFF"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0B1830"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#0F1E3A"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#DCEBFF"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#0E2747"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#DCEBFF"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#1E90FF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#0B1830"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#DCEBFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#5F7FA8"))
    app.setPalette(palette)

    controller = TestController()
    scope = ScopePanel()
    power = PowerPanel(instrument_id="power1", channels=3)
    trace = TraceBridge()
    # 电源面板：命令/查询经控制器下发到 HAL 仪器（当前为虚拟电源）
    power.setCommandSink(lambda cmd: controller.sendInstrumentCommand("power1", cmd))
    power.setQuerySink(lambda cmd: controller.queryInstrument("power1", cmd))
    # 持有 Python 引用，避免被 GC
    controller._scope = scope
    controller._trace = trace
    controller._power = power
    scope.setCommandSink(controller.sendScopeCommand)
    scope.setMeasureSink(controller.queryScopeItem)
    scope.setWaveformSink(controller.readScopeWaveform)
    # 数据源：配置为 mock 时使用仿真波形/仿真读数（无真机调试）
    scope.setSimulationMode(controller.usesSimulation)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.rootContext().setContextProperty("scope", scope)
    engine.rootContext().setContextProperty("trace", trace)
    engine.rootContext().setContextProperty("power", power)

    qml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml")
    arch_path = os.path.join(qml_dir, "architecture.qml")
    console_path = os.path.join(qml_dir, "main.qml")

    # 先加载架构台（窗口2，最大化），再加载操作台（窗口1）——操作台默认在最前
    engine.load(QUrl.fromLocalFile(arch_path))
    engine.load(QUrl.fromLocalFile(console_path))

    roots = engine.rootObjects()
    if not roots:
        return 1

    # 把架构台窗口引用注入操作台，供“架构台 (F2)”按钮控制显隐
    arch_window = None
    console_window = None
    for obj in roots:
        if obj.objectName() == "architectureWindow":
            arch_window = obj
        else:
            console_window = obj
    if console_window is not None and arch_window is not None:
        console_window.setProperty("archWindow", arch_window)

    scope.start()
    power.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())