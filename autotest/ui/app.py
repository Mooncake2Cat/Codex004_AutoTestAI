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

    app = QGuiApplication(sys.argv)
    app.setApplicationName("AutoTestAI-Prototype")

    controller = TestController()
    scope = ScopePanel()
    # 持有 Python 引用，避免被 GC
    controller._scope = scope
    scope.setCommandSink(controller.sendScopeCommand)
    scope.setMeasureSink(controller.queryScopeItem)
    scope.setWaveformSink(controller.readScopeWaveform)
    # 数据源：配置为 mock 时用仿真波形/仿真读数（无真机调试）
    scope.setSimulationMode(controller.usesSimulation)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.rootContext().setContextProperty("scope", scope)

    qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        return 1

    scope.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())




