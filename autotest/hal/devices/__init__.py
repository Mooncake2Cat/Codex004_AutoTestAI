"""仪器设备层（Device）：按品牌/型号实现的仪器语义。

分层规划（设计文档 §9）：
    设备层 Device  ← 本目录（示波器/电源/万用表/信号源/频谱仪/电子负载）
    协议层 Protocol（SCPI / Modbus / Raw）
    传输层 Transport（Socket / Serial / VISA）
本阶段先落地"电源"设备；其余仪器按同一模式扩展。
"""
