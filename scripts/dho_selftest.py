"""DHO924S 真机协议自检脚本（无需 PySide6/UI）。

用途：接好网线并填对示波器 IP 后，运行本脚本一次性核验：
  1. TCP 5555 raw SCPI 是否可达、*IDN? 返回的型号/序列号/固件；
  2. :MEASure:ITEM? <item>,CHANnel<n> 查询语法与返回格式（科学计数）；
  3. 无效测量（无信号通道）是否返回 ~9.9E+37（驱动将其解析为 None）；
  4. SCPI 错误队列是否干净。

用法：
  python scripts/dho_selftest.py --host 192.168.1.100
  python scripts/dho_selftest.py --host 192.168.1.100 --items VPP,VRMS,FREQuency
  python scripts/dho_selftest.py --host 192.168.1.100 --channel 1 --channel 2
"""
from __future__ import annotations

import argparse
import os
import sys

# 允许以 `python scripts/dho_selftest.py` 方式直接运行：
# 把项目根目录加入模块搜索路径，确保能 import autotest 包。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rigol DHO924S 网口 SCPI 协议自检")
    parser.add_argument("--host", default="192.168.1.100", help="示波器 IP（Utility->IO Setting->LAN 中查看）")
    parser.add_argument("--port", type=int, default=5555, help="SCPI socket 端口（Rigol 默认 5555）")
    parser.add_argument("--timeout", type=float, default=3.0, help="单条命令超时（秒）")
    parser.add_argument("--items", default="VPP,VRMS,FREQuency,PERiod,RTIMe", help="逗号分隔的测量项")
    parser.add_argument("--channels", default="1,2,3", help="逗号分隔的待测通道")
    args = parser.parse_args()

    from autotest.hal.rigol_dho import RigolDhoInstrument, parse_measure_value

    inst = RigolDhoInstrument(host=args.host, port=args.port, timeout=args.timeout)
    print("==> 连接 %s:%s (raw SCPI socket) ..." % (args.host, args.port), flush=True)
    try:
        inst.initialize()
    except Exception as exc:  # noqa: BLE001
        print("!! 连接失败: %s" % exc, flush=True)
        print("   请确认：网线已接、示波器 LAN 已启用、IP/端口正确、电脑与示波器同网段。")
        return 2

    try:
        # 1) 识别
        idn = inst.query("*IDN?").strip()
        print("==> *IDN? => %s" % idn, flush=True)
        parts = [s.strip() for s in idn.split(",")]
        if len(parts) >= 4 and parts[0].upper().startswith("RIGOL"):
            print("    厂商=%s 型号=%s 序列号=%s 固件=%s" % (parts[0], parts[1], parts[2], parts[3]), flush=True)
        else:
            print("    (注意：返回格式与预期 RIGOL TECHNOLOGIES,DHO924S,... 不一致，请人工核对)", flush=True)

        # 2) 逐通道测量
        items = [s.strip() for s in args.items.split(",") if s.strip()]
        channels = [int(s) for s in args.channels.split(",") if s.strip()]
        print("==> 自动测量项: %s  通道: %s" % (items, channels), flush=True)
        for ch in channels:
            for item in items:
                try:
                    value, raw = inst.measure_item(item, ch)
                except Exception as exc:  # noqa: BLE001
                    print("    CH%d %-9s -> 查询异常: %s" % (ch, item, exc), flush=True)
                    continue
                if value is None:
                    print("    CH%d %-9s -> raw=%s  (驱动判定为无效/无信号 ~9.9E+37)" % (ch, item, raw), flush=True)
                else:
                    print("    CH%d %-9s -> %s  (raw=%s)" % (ch, item, value, raw), flush=True)

        # 3) 错误队列（可选，若仪器支持）
        try:
            err = inst.query(":SYSTem:ERRor?").strip()
            print("==> :SYSTem:ERRor? => %s" % err, flush=True)
        except Exception as exc:  # noqa: BLE001
            print("    (查询 :SYSTem:ERRor? 失败: %s)" % exc, flush=True)

        print("==> 完成。若上方均正常，说明协议与驱动一致，可切换 config 到 rigol_dho 真机模式。")
        return 0
    finally:
        inst.close()


if __name__ == "__main__":
    raise SystemExit(main())

