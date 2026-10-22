# 通用自动化测试软件平台 - 原型验证版（Windows / 无服务器阶段）

按 `docs/架构建议.md` 的“六层”架构搭建的原理验证原型，当前链路：
**QML 界面（示波器仿真屏）→ PySide6 桥接 → 执行引擎 → HAL(网口仪器) → SQLite 落库 → HTML 报告**。

- 首个真机仪器：**Rigol（普源精电）DHO924S 四通道网口示波器**（LAN raw SCPI，TCP 5555）。
- 无真机时默认用 `mock`（DHO924S 仿真器）+ 界面仿真波形，可离线演示全链路。
- 服务器通信层：本阶段暂不实现。

分层改动与协议核对的详细说明见：`docs/接入DHO924S变更说明.md`。

## 目录结构

```
autotest/
  core/      应用与算法层：域模型、测试方法库、执行引擎
  hal/       硬件抽象层：仪器抽象、TCP SCPI 驱动、Rigol DHO900 驱动、mock 仿真器、工厂
  data/      本地数据层：SQLite 存储
  ui/        表示层 + 胶合层：QML + 桥接控制器 + 示波器仿真数据源
  report/    报告：HTML 报告生成
config/      应用配置与测试流程示例
tests/       pytest 自动化测试
scripts/     dho_selftest.py（真机协议自检）、pdf_extract.py（官方手册正文提取）
docs/        架构建议、DHO900 官方编程手册/数据手册（用户下载）、变更说明
run.py       应用入口
```

## 环境准备（Windows + Python 3.12）

```powershell
cd D:\Projects\Codex004_AutoTestAI
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 运行（默认 mock，可离线演示）

```powershell
python run.py
```

界面说明：
1. 主区域为**示波器操作界面**：波形栅格 + 触发电平虚线 + RUN/STOP 指示 + 右侧自动测量读数（真机轮询）。
   左侧波形默认空白（**无任何仿真数据**），点击顶部 **“波形读取”** 开关后，按约 2.5 帧/秒从示波器下载 `:WAVeform:DATA?` 并绘制真实波形；关闭开关则不发送任何波形命令。
2. 下方为**示波器设置面板**（6 个页签），可直接操作真机参数：
   - 垂直：通道开关、反相、V/div、偏移、耦合(DC/AC/GND)、探头(1x/10x/100x)、20MHz 带宽限制
   - 水平：时基 s/div（5ns~1s）、水平位置
   - 触发：模式(AUTO/NORMal/SINGle)、源、斜率、电平、强制触发
   - 采集：RUN / STOP / SINGLE / AUTO 自动设置 / 清除显示
   - 测量：Vpp/Vrms/Vavg/Freq/Period/Rise/Fall/Duty 勾选、统计开关、复位统计
   - 信号源(AFG，DHO924S 内置)：波形、频率、幅度、偏移、输出
3. 面板每次改动都会生成 SCPI 命令：真机模式下发示波器，mock 模式仅仿真；底部“最近命令”栏显示命令与结果。
4. **流程编辑器**（阶段4）：左区可添加/删除/上移/下移/保存流程，参数由能力模型自动生成；运行时只读并高亮当前步骤；支持 **暂停（不动作）/ 停止（自动回安全态）/ 单步**。
5. **双窗口**（阶段2）：
   - **窗口1 操作台**（约半屏、居中、可拖拽缩放）：左侧=流程控制 + 流程编辑（只读展示）+ 最近命令；中间=**仪器坞**（上下分栏：示波器仪器格 + 直流电源仪器格，可勾选显示/隐藏、可拖拽调整；两格设有最小高度并裁剪自身内容，拖拽时不会互相遮挡。示波器参数面板为**稠密网格**布局（标签+控件成对、固定列宽、控件高 22px），高度 56~84px 按页自适应；点标题栏"参数"开关可收起面板、把空间全部让给波形）；右侧=测试报表总表 + 导出 HTML。
   - **窗口2 架构台**（最大化、只读）：7 张层卡片（表示/胶合/应用与算法/HAL/数据/报告 + 服务器层"范围外"），每张卡片显示关键文件、层间关系、该层**真实事件日志**（来自事件总线）。日志**全量保留**、最新在最下方、自动滚动到底部（可勾选关闭）、始终显示滚动条。
   - 操作台顶部 **"架构台 (F2)"** 按钮或 **F2** 键可隐藏/显示窗口2。
4. 流程按钮：**加载示例流程** → **运行流程** → **保存报告**（`reports/report.html`）。

## 报表输出（阶段5）

- 报表结构由 `config/report_template.json` 配置（表头信息 + 分组/分项/明细 + 技术指标 + 结果变量）；
- **是否合格**由技术指标自动判定（支持 `≤` / `≥` / `±` / 区间 / 文本型指标），
  也可由流程 `limit_check` 步骤给出；
- 输出 **HTML 验收记录表**（全框线、合并单元格、判定着色、汇总），样式参考 `Codex005_ExcelToReport` 的示例模板；
- **Excel 输出接口已预留**（`autotest/report/xlsx_export.py`，当前未实现）；
- 产品名称/编号/测试地点/测试时间：**要求用户填写**，现阶段为演示占位值。

## 流程与能力模型（阶段4）

测试流程支持 **9 类步骤**：`action`（能力动作，含加电/断电简写）、`set_param`、`measure`、`wait`、`compute`（波形算法）、`limit_check`（上下限判定）、`store`、`report`、`loop`/`branch`。
参数中可用 `$变量名` 引用前面步骤的结果。能力模型见 `autotest/core/capabilities.py`（电源 6 个动作 + 示波器 6 个动作，含安全动作）。
演示流程：`config/flows/flow_phase4_demo.json`（加电→测量→计算→判定→报表→断电）。


## 三级抽象与仪器发现（阶段6）

- **传输层**：TCP Socket / 串口(pyserial) / VISA(pyvisa，USB·LAN·VXI-11·USBTMC)；
- **协议层**：SCPI（含二进制块）/ Raw；Modbus 为预留接口；
- **设备层**：示波器、电源驱动；新增仪器只需组合已有传输/协议 + 设备驱动；
- 界面顶部 **“发现仪器”** 按钮：
  1. **TCP 手工添加**：填 IP/端口 → 连接测试（`*IDN?`）→ 添加；
  2. **网段扫描**：扫描 5555/5025 端口并识别仪器；
  3. **VISA 枚举**：列出本机可见的 VISA 资源并识别；
  4. 结果可逐条写入 `config/instruments.json`。

> Modbus/CAN 为预留接口；新发现仪器的面板（QML/面板模型）需按设备类型实现。

## 仪器注册表（多仪器）

仪器统一在 `config/instruments.json` 中登记（id/name/model/type/panel/simulate/visible/capabilities/transport/options）：

| id | 型号 | 类型 | 当前模式 |
|---|---|---|---|
| `scope1` | Rigol DHO924S | `rigol_dho` | 仿真（`simulate: true`，改 false 接真机） |
| `power1` | Siglent SPD3303X-E | `siglent_spd3303x` | 虚拟电源（阶段3 占位，SCPI 待真机核对） |

新增仪器只需在注册表追加一条 + 提供对应设备驱动/面板；界面（仪器坞）与流程编辑会自动出现该仪器。

## 使用真实 DHO924S

1. 示波器 Utility → IO Setting → LAN，记录 IP（与电脑同网段，建议静态 IP）。
2. 复制真机配置为默认：
   ```powershell
   Copy-Item config\app_config.rigol_dho.example.json config\app_config.json
   ```
3. 编辑 `config/app_config.json`，把 `host` 改成示波器 IP（端口默认 5555）。
4. **先做真机协议自检**（一次性核对 IDN/测量语法/无效值）：
   ```powershell
   python scripts/dho_selftest.py --host <示波器IP>
   ```
5. 自检通过后 `python run.py`，加载示例流程并运行，即对真机测量并落库、出报告。

> 换回离线演示：`Copy-Item config\app_config.json config\_bak.json` 后把 `app_config.json` 里
> `"type": "rigol_dho"` 改为 `"type": "mock"`；或直接保留一份 mock 配置副本随时切换。

## 测试

```powershell
pytest -q
```
覆盖：HAL（mock 仿真器、rigol_dho 驱动、无效值解析）、方法层 measure_item、引擎流程、模型、SQLite 存储。

## 协议来源与核验

- 官方手册（用户已放入 `docs/`）：`DHO800900_ProgrammingGuide_CN.pdf`、`dho900系列数据手册.pdf`。
- 提取核对命令：`python scripts/pdf_extract.py docs/DHO800900_ProgrammingGuide_CN.pdf --grep "MEASure:ITEM"`
- 结论、分层改动与踩坑记录见 `docs/接入DHO924S变更说明.md`。
- **2026-09-13 真机核验通过**（DHO924S @192.168.10.16）：
  - `*IDN?` → `RIGOL TECHNOLOGIES,DHO924S,DHO9S275006837,00.01.04`
  - `:MEASure:ITEM?`（CH2 接信号）：VPP=3.0197V、VRMS=2.0968V、FREQuency=1000.0Hz、PERiod=1.0ms、RTIMe=4.4µs
  - 无信号时：时间类（FREQuency/PERiod/RTIMe）返回 `9.9E+37`（驱动解析为 None）；幅度类（VPP/VRMS）返回噪声底数值
  - `:SYSTem:ERRor?` → `0,"No error"`
  - 真机自检命令：`python scripts/dho_selftest.py --host <示波器IP>`

## 当前原型边界（不在本阶段范围）

- 服务器通信层（Push/Pull/分析回传）
- 真机波形下载显示（`:WAVeform`，界面已预留数据源接口，后续替换）
- 数据加密、双网隔离、离线授权/升级
- C++ HAL 与国产操作系统适配














