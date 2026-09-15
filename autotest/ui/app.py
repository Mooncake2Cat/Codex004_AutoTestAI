"""PySide6 + QML 应用入口。"""
from __future__ import annotations

import os
import sys


def main() -> int:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    from .controller import TestController
    from .scope_panel import ScopePanel
    from .trace_view import TraceBridge

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AutoTestAI-Prototype")

    controller = TestController()
    scope = ScopePanel()
    trace = TraceBridge()
    # 持有 Python 引用，避免被 GC
    controller._scope = scope
    controller._trace = trace
    scope.setCommandSink(controller.sendScopeCommand)
    scope.setMeasureSink(controller.queryScopeItem)
    scope.setWaveformSink(controller.readScopeWaveform)
    # 数据源：配置为 mock 时用仿真波形/仿真读数（无真机调试）
    scope.setSimulationMode(controller.usesSimulation)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.rootContext().setContextProperty("scope", scope)
    engine.rootContext().setContextProperty("trace", trace)

    qml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml")
    arch_path = os.path.join(qml_dir, "architecture.qml")
    console_path = os.path.join(qml_dir, "main.qml")

    # 先加载架构台（窗口2，最大化），再加载操作台（窗口1）——操作台默认在最前
    engine.load(QUrl.fromLocalFile(arch_path))
    engine.load(QUrl.fromLocalFile(console_path))

    roots = engine.rootObjects()
    if not roots:
        return 1

    # 把架构台窗口引用注入操作台，供"架构台 (F2)"按钮控制显隐
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
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())






