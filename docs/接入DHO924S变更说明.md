# 接入 Rigol DHO924S 示波器 —— 分层改动说明与协议核对

> 阶段：Windows 本地原型验证；仅网口仪器；不含服务器。
> 日期：2026-09；依据官方文档：`docs/DHO800900_ProgrammingGuide_CN.pdf`（V20250429 版，Rigol 官网下载）、`docs/dho900系列数据手册.pdf`。

## 一、协议核对结论（依据官方编程手册）

已用 `scripts/pdf_extract.py` 从官方《DHO800/900 编程手册（中文版）》正文中提取并核对到：

| 协议点 | 手册证据（提取到的正文） | 结论 |
|---|---|---|
| 自动测量命令族 | `:MEASure:ITEM <item>,<src>`；示例 `:MEASure:ITEM RTIMe,CHANnel2` | 写入/查询语法正确 |
| 统计测量 | `:MEASure:STATistic:ITEM VPP,CHANnel2`；查询 `:MEASure:STATistic:ITEM? CURRent/MAXimum/MINimum/AVERages/DEViation,...` | 统计族存在 |
| 通道源名 | `{CHANnel1|CHANnel2|CHANnel3|CHANnel4|...}` | 源名拼写正确 |
| 通道配置 | `:CHANnel<n>:SCALe / :COUPling / :OFFSet / :LABel / :UNIT` | 可做后续自动设置 |
| 识别命令 | 3.12.1 `*IDN?` | 存在，返回 `RIGOL TECHNOLOGIES,<model>,<SN>,<fw>` |

**仍需“真机一次裁决”的点（这几项编程手册正文未直接写出 / 表格字体不可提取，来自多源交叉验证）：**
1. 网口 SCPI 端口 **5555**（Rigol 全系惯例，见 ngscopeclient 文档及多个真机驱动；编程手册未提及端口，端口配置一般在用户手册 IO 设置章节）。
2. 无效测量返回值 **≈9.9E+37**（驱动已按“绝对值 ≥ 1e36 视为无效”处理）。
3. `*IDN?` 实测返回的型号字符串应为 `DHO924S`。
4. 换行终止符 `\n`（多数实现采用；已做成配置项，若需 `\r\n` 只改 config）。

以上 4 点请用 `python scripts/dho_selftest.py --host <示波器IP>` 连真机一次确认；脚本会打印原始返回，与驱动解析结果对照。

## 二、分层改动矩阵

| 层 | 文件 | 改动内容 |
|---|---|---|
| HAL 仪器驱动 | `autotest/hal/rigol_dho.py`（新增） | `RigolDhoInstrument(TcpScpiInstrument)`：默认 TCP 5555 / `\n` 终止；`measure_item(item, channel)` 拼 `:MEASure:ITEM?` 并过滤无效值；`parse_measure_value()` 处理 9.9E+37/nan；item→单位表 |
| HAL 工厂 | `autotest/hal/factory.py` | 注册仪器类型 `rigol_dho`（host/port/timeout/terminator/channels/model 均可配置） |
| HAL 模拟器 | `autotest/hal/mock.py` | 升级为 DHO924S 仿真器：响应 `*IDN?`（SN 带 MOCK 前缀）与 `:MEASure:ITEM? ...`；CH1/CH2 有信号、CH3/CH4 返回 9.9E+37 |
| 方法层 | `autotest/core/methods.py` | 新增 `measure_item` 方法（item/channel/单位；支持 vpp、freq 等短名）；`query` 改用统一无效值解析 |
| 配置层 | `config/app_config.json` | 默认保持 `mock`（离线演示/UI 自检） |
| 配置层 | `config/app_config.rigol_dho.example.json`（新增） | 真机配置模板：`type=rigol_dho`、IP 占位、端口 5555 |
| 配置层 | `config/flow_sample.json` | 示例流程改为“示波器自动测量”：识别 + CH1 VPP(×3)/频率/VRMS + CH2 VPP + CH3 VPP(无效演示) |
| 胶合层 | `autotest/ui/controller.py` | 暴露只读 `instrumentInfo`（当前仪器摘要）；原有 Signal/Slot/Property 桥接不变 |
| 表示层 | `autotest/ui/scope_panel.py`（新增，原名 `scope_sim.py`） | 示波器面板模型：保存面板设置、生成 SCPI、**真机测量轮询**（早期版本曾含仿真波形，已移除） |
| 表示层 | `autotest/ui/app.py` | 创建并桥接 `ScopePanel`（context property: `scope`），注入命令下发与测量查询两个回调 |
| 表示层 | `autotest/ui/qml/main.qml` | 重写：示波器仿真屏（栅格/波形/通道/时基/RUN-STOP 指示）+ 右侧通道自动测量读数 + 原流程控制/结果列表 |
| 测试 | `tests/test_hal.py`、`tests/test_engine.py` | 覆盖新驱动、工厂、mock 测量、无效值解析、示波器流程（13 项） |
| 验证工具 | `scripts/dho_selftest.py`（新增） | 真机协议自检：IDN、逐通道 VPP/VRMS/FREQ/PER/RTIME、错误队列 |
| 工具 | `scripts/pdf_extract.py`（新增） | 纯标准库 PDF 正文提取（含 ObjStm/ToUnicode），用于复现本核对 |

## 三、运行与切换真机

默认（无真机，演示仿真屏 + mock 流程）：
```powershell
cd D:\Projects\Codex004_AutoTestAI
.venv\Scripts\Activate.ps1
python run.py
```
界面：示波器仿真屏（可开/关 CH1..CH4、RUN/STOP）→ 点击“加载示例流程” → “运行流程”→ “保存报告”。

切换真机 DHO924S：
1. 示波器 Utility → IO Setting → LAN，记录 IP（建议设静态 IP，与电脑同网段）。
2. 复制配置：`Copy-Item config\app_config.rigol_dho.example.json config\app_config.json`
3. 编辑 `config/app_config.json` 中 `host` 为示波器 IP。
4. 先跑协议自检：`python scripts/dho_selftest.py --host <IP>`
5. 通过后再 `python run.py` → 运行流程即对真机测量。

## 四、待真机确认 / 后续
- [ ] 运行 `dho_selftest.py`，记录 `*IDN?` 型号串与 9.9E+37 行为；
- [ ] 确认终止符（若需 `\r\n` 改 config 即可，无需改代码）；
- [ ] 后续：波形下载（`:WAVeform`）接入仿真屏替换为真机波形；通道量程/时基自动设置（`:CHANnel<n>:SCALe` 等已确认存在）。

## 五、示波器操作面板（本轮优化）

界面在“波形屏 + 右侧自动测量读数”基础上，新增 6 个设置页（点击切换）：

| 页 | 可设置项 | 对应 SCPI（官方手册已确认者标 ✔） |
|---|---|---|
| 垂直 | 通道选择、开启/关闭、反相、V/div、偏移、耦合(DC/AC/GND)、探头(1x/10x/100x)、20MHz 带宽限制 | ✔`:CHANnel<n>:SCALe/OFFSet/COUPling/BWLimit`；标准拼写待确认：`:CHANnel<n>:DISPlay/INVert/PROBe` |
| 水平 | 时基 s/div（5ns~1s）、水平位置(µs) | ✔`:TIMebase:MAIN:SCALe`、✔`:TIMebase:MAIN:OFFSet` |
| 触发 | 模式(AUTO/NORMal/SINGle)、源(CH1~4)、斜率(上升/下降/任意)、电平(mV)、强制触发 | ✔`:TRIGger:SWEep`、✔`:TRIGger:EDGE:SLOPe/LEVel`；标准拼写待确认：`:TRIGger:EDGE:SOURce`、`:TFORce` |
| 采集 | RUN / STOP / SINGLE / AUTO 自动设置 / 清除显示 | ✔`:RUN`、✔`:STOP`、✔`:AUToset`、✔`:CLEar`、✔`:TRIGger:SWEep SINGle` |
| 测量 | Vpp/Vrms/Vavg/Freq/Period/Rise/Fall/Duty 勾选、统计开关、复位统计 | ✔`:MEASure:ITEM`、✔`:MEASure:CLEar`、✔`:MEASure:STATistic:DISPlay/RESet` |
| 信号源(AFG) | 波形(正弦/方波/斜坡/脉冲/直流)、频率、幅度(mVpp)、偏移、输出 | ✔`:SOURce:FREQuency`、✔`:SOURce:VOLTage:AMPLitude`、✔`:SOURce:FUNCtion:RAMP:SYMMetry`；标准拼写待确认：`:SOURce:FUNCtion`、`:SOURce:OUTPut`、`:SOURce:VOLTage:OFFSet` |

工作机制：
- 面板每一处改动 → `autotest/core/scope_commands.py` 生成 SCPI → `TestController.sendScopeCommand()` 下发；
- 配置为 `rigol_dho` 时**下发真机**（自动连接），配置为 `mock` 时只回显“已应用(仿真)”；
- 界面底部“最近命令”栏实时显示下发的命令与结果，便于对照手册排查；
- 面板设置实时下发真机；界面不回显假波形（波形区显示“波形未接入”，真机波形下载 :WAVeform 待接入）。

> 命令拼写集中在 `autotest/core/scope_commands.py` 一处；若真机某条命令不被接受，
> 只需改这一个文件，界面无需改动。`scripts/dho_selftest.py` 可继续用于验证测量类命令。

待真机确认清单（在原有 4 项之外补充）：
- [ ] `:CHANnel<n>:DISPlay / INVert / PROBe`（本手册正文未提取到，按 Rigol 标准拼写实现）
- [ ] `:TRIGger:EDGE:SOURce` / `:TFORce`（同上）
- [ ] `:SOURce:FUNCtion` / `:SOURce:OUTPut` / `:SOURce:VOLTage:OFFSet`（AFG，DHO924S 内置信号源）

## 六、实机连通记录（2026-09-13）

| 项 | 值 |
|---|---|
| 示波器 IP | 192.168.10.16（静态） |
| 示波器掩码 / 网关 | 255.255.255.0 / 留空 |
| 电脑网卡 | “以太网 3”（Realtek USB GbE）静态 192.168.10.10/24，无网关 |
| 端口 | TCP 5555 raw SCPI |

**关键经验：Rigol DHO 系列在 Utility → IO Setting → LAN 修改 IP/掩码后，必须点“应用/Apply”才会生效**，
否则示波器仍按旧配置（或 DHCP 失败后的地址）工作，表现为 ping/端口都不通。

配置切换：
- 真机：`config/app_config.json`（type=rigol_dho, host=192.168.10.16）——已设为默认；
- 离线仿真：`Copy-Item config\app_config.mock.json config\app_config.json`。

## 七、真机协议核验结果（2026-09-13，DHO924S @192.168.10.16）

运行 `python scripts/dho_selftest.py --host 192.168.10.16`，实测输出要点：

| 核验项 | 实测结果 | 结论 |
|---|---|---|
| `*IDN?` | `RIGOL TECHNOLOGIES,DHO924S,DHO9S275006837,00.01.04` | 型号串确认为 `DHO924S`；序列号 `DHO9S275006837`，固件 `00.01.04` |
| 端口/终止符 | 5555 + `\n` 全程通信正常 | 驱动默认配置正确 |
| `:MEASure:ITEM?` 语法 | CH2 实测 VPP=3.0197V、VRMS=2.0968V、FREQuency=1000.0Hz、PERiod=1.0ms、RTIMe=4.4µs | 语法与“科学计数”返回格式正确 |
| 无效值哨兵 | 返回 `9.9000E+37`，驱动解析为 `None` | 原 `>=1e36 视为无效` 的判定正确 |
| 命令接受度 | `:SYSTem:ERRor?` → `0,"No error"` | 上述命令示波器全部正常接受 |

**实测补充的重要行为（无信号时）**：
- `VPP`、`VRMS` 这类**幅度类**测量仍会返回**噪声底数值**（本次 CH1/CH3 约 2.4mV / 1.3mV），不会返回 9.9E+37；
- `FREQuency`、`PERiod`、`RTIMe` 这类**时间/边沿类**测量在无有效信号时返回 `9.9E+37`。
- 因此“判断无信号”应按测量项类别区分：时间类可直接用 9.9E+37 判定，幅度类需结合幅值门限（后续可在方法层加门限判断）。

**连通性踩坑记录**：Rigol DHO 系列在 Utility → IO Setting → LAN 修改 IP/掩码/网关后，**必须点“应用(Apply)”才生效**；
未点应用时示波器仍按旧配置工作，现象是 ping/端口均不通，极易误判为网线或驱动问题。

## 八、真机上机联调修正（2026-09-13）

### 1. AFG 输出命令拼写修正（实机报 -100 Command error）
- 原写法（错）：`:SOURce:OUTPut ON`
- 官方手册 3.25.1（对）：**`:SOURce:OUTPut:STATe ON`**
- 已修正于 `autotest/core/scope_commands.py::afg_output()`；其余面板命令经实机验证全部通过。

### 2. 官方命令总目录已存档
`docs/DHO900命令索引.txt`（370 条，来自官方编程手册 TOC）——包含：
`:CHANnel<n>:` 通道族、`:TIMebase:` 时基族、`:TRIGger:` 触发族、`:MEASure:` 测量族、
`:SOURce:` AFG 族（3.25.x）、`:WAVeform:` 波形族（3.28.x）、`:ACQuire:`、`:AUToset` 等。
后续新增面板功能时，先在此索引里核对命令名，避免再次出现 -100/-113 错误。

### 3. 界面问题修正
| 问题 | 原因 | 修正 |
|---|---|---|
| 通道选择按钮“粘滞”、可能多个同时点亮 | 用 `highlighted` 属性做选中态，且按钮会保留键盘焦点；Qt 焦点态与高亮态同时绘制，视觉上像“多个同时亮” | 改为 `ButtonGroup{ exclusive: true }` + `checkable` 互斥按钮，并 `focusPolicy: Qt.NoFocus`；按钮前缀 ●/○ 明确选中态 |
| 切换通道后，V/div、耦合、探头、偏移等控件仍显示上一个通道的值 | ComboBox/Switch/SpinBox 的 `currentIndex/checked/value` 绑定在用户改过一次后会被破坏，切换通道时不再刷新 | 新增 `refreshVertical()`，在 `onSelectedChannelChanged` 与 `Component.onCompleted` 时统一从模型同步；开关改用 `onClicked`（程序赋值不会误触发下发命令） |
| “测量”页勾选按钮的 ●/○ 不刷新 | `scope.measureItemEnabled()` 是 Q_INVOKABLE 调用，无 notifying 依赖，绑定不会重算 | 模型新增 `stateSeq`（每次状态变化递增，notify=stateChanged），QML 绑定引用它作为刷新依赖 |

### 4. 波形屏说明（重要）
（本节为历史记录；**仿真波形已于 2026-09-13 按用户要求移除**，详见第九节。）早期版本的波形来自 `ScopeSimulator` 生成的仿真数据：
- **走真机的**：自动测量读数（`:MEASure:ITEM?`）与面板设置命令（`:CHANnel...`/`:TIMebase...` 等）；
- **尚未接真机的**：示波器屏幕波形本身。真机波形需要下载 `:WAVeform:DATA?`（官方手册 3.28 族，含 `:WAVeform:SOURce/FORMat/DATA/PREamble`），
  属下一步工作：HAL 增加二进制块读取与 preamble 换算，UI 用真机采样替换仿真采样即可（`samples()` 接口不变）。


## 九、取消仿真波形（2026-09-13）

按用户要求，界面**不再显示任何仿真波形**，避免与真机数据混淆：

| 项 | 改动前 | 改动后 |
|---|---|---|
| 波形曲线 | 由 `ScopeSimulator` 生成 4 通道仿真正弦/方波 | **不绘制**；波形区显示“波形未接入（真机波形下载 :WAVeform 待实现）” |
| 右侧“自动测量” | 由仿真采样计算 Vpp/Vrms/… | **真机轮询**：每秒对当前选中通道的勾选项查询 `:MEASure:ITEM? <item>,CHANnel<n>`，显示实测值；无信号/无效值显示 `—` |
| 面板设置 | 仿真 + 下发 | **只下发**（`ScopePanel` 不再产生任何波形数据） |
| 顶部徽标 | 仿真波形（非真机数据） | 波形未接入 |

代码改动：
- 新增 `autotest/ui/scope_panel.py`（`ScopePanel`，替换并删除 `autotest/ui/scope_sim.py`）；
- `autotest/ui/app.py` 注入 `setCommandSink(controller.sendScopeCommand)` 与 `setMeasureSink(controller.queryScopeItem)`；
- `autotest/ui/controller.py` 新增 `@Slot(str,int,result=str) queryScopeItem(item, channel)`（带锁、失败返回空串）；
- `autotest/core/scope_commands.py` 新增 `measure_item_query(item, channel)`（生成 `:MEASure:ITEM? ...` 查询命令）；
- QML：删除曲线绘制与 `frameReady` 依赖，读数绑定改为 `measureSeq`，切换通道时 `setPollChannel()` 让轮询跟随选中通道。

真机波形显示（可选后续）：HAL 增加 IEEE-488.2 定长块读取 + `:WAVeform:PREamble?` 电压换算，UI 把 `ScopePanel.samples()` 由“恒空”改为返回真机采样即可，画布代码无需改动。

## 十、真机波形读取（2026-09-13，可选、默认关闭）

左侧波形区此前空白，是因为按用户要求移除了仿真波形、而真机波形尚未下载。现补上**真机波形读取**：

- 界面顶部按钮行新增 **“波形读取”开关（默认关闭）**：
  - 关闭时：不发送任何 `:WAVeform` 命令（不影响你在示波器上单独测试），波形区显示提示文字；
  - 打开时：对**当前选中通道**按约 2.5 帧/秒读取真机屏幕波形并绘制真实曲线。
- 使用的 SCPI（官方手册 3.28 族）：
  `:WAVeform:SOURce CHANnel<n>` → `:WAVeform:MODE NORMal` → `:WAVeform:FORMat BYTE`
  → `:WAVeform:PREamble?`（10 字段标定） → `:WAVeform:DATA?`（IEEE-488.2 定长块 `#<n><len><data>`）
- 电压换算：`V = (raw − YORigin − YREFerence) × YINCrement`（NORMal 模式约 1000 点）。
- 说明：垂直偏移（`:CHANnel<n>:OFFSet`）在 NORMal 模式下已由示波器换算进标定值，界面按 `V/(V/div)` 直接绘制，不再二次平移。

代码改动：
| 文件 | 改动 |
|---|---|
| `autotest/hal/scpi.py` | 新增 `parse_ieee_block()`、`query_binary()`、`_recv_exact()`（IEEE-488.2 定长块读取 + 消费块尾换行） |
| `autotest/hal/rigol_dho.py` | 新增 `parse_preamble()`、`convert_waveform()`、`RigolDhoInstrument.read_waveform(channel)` |
| `autotest/ui/controller.py` | 新增 `readScopeWaveform(channel)`（带锁；失败返回空列表） |
| `autotest/ui/scope_panel.py` | 新增 `setWaveformOn/waveformOn`、`setWaveformSink`、`_poll_wave()`（400ms 定时器）、`samples()` 返回真机采样、`frameReady` 信号 |
| `autotest/ui/app.py` | 注入 `setWaveformSink(controller.readScopeWaveform)` |
| `autotest/ui/qml/main.qml` | 恢复真机曲线绘制 + “波形读取”开关 + `onFrameReady` 重绘；无数据时显示提示 |
| `tests/test_waveform.py`（新增） | 定长块解析、preamble 解析、BYTE/WORD 电压换算（7 项） |

离线校验：30 个文件编译通过、27 项测试通过。

### 补充（多通道同屏显示）
用户反馈“希望各通道波形在同一界面显示”，已改为：
- `_poll_wave()`：一次抓取**所有已开启通道**（`_enabled_channels()`）的波形，同屏叠加绘制，各自使用自己的 V/div 与颜色（CH1 黄 / CH2 青 / CH3 品红 / CH4 绿），与真实示波器一致；
- `_poll()`：测量读数同样对**所有已开启通道**轮询，右侧按通道分块显示；
- 波形刷新周期 500ms（多通道抓取时降低总线负载）；通道开关变化后立即生效；
- 通道是否显示由“垂直”页的“开启”开关决定（`:CHANnel<n>:DISPlay ON/OFF`），关掉的通道不抓取、不绘制。

## 十一、切回仿真数据源（2026-09-13，无真机调试）

按用户要求，当前**不连接真实示波器**，波形与读数暂由仿真替代，但既有功能全部保留：

| 项 | 仿真模式（当前默认） | 真机模式（保留） |
|---|---|---|
| 触发条件 | `config/app_config.json` 里 `scope.type = "mock"` | `scope.type = "rigol_dho"`（见 `app_config.rigol_dho.example.json`） |
| 波形来源 | `ScopePanel._tick_sim()` 生成（25 fps，601 点，按 V/div·耦合·反相·时基·AFG 变化） | `:WAVeform` 下载（约 2 fps，所有已开启通道） |
| 读数来源 | 由仿真采样计算（Vpp/Vrms/Vavg/Freq/Period/Rise/Fall/Duty，约 5 Hz 刷新） | `:MEASure:ITEM?` 轮询（1 Hz） |
| 面板命令 | 只更新界面状态，由 `mock` 吸收，界面提示“命令未下发” | 通过 SCPI 真机下发并回读错误队列 |
| 切换 | — | 改配置为 rigol_dho 即可，**代码无需改动** |

实现要点：
- `ScopePanel` 增加 `_sim_mode`（由 `controller.usesSimulation` 在启动时注入）、`setSimulationMode()`、`_tick_sim()`、`_update_sim_readouts()`；
- 波形开关按钮在仿真模式显示“仿真波形”，真机模式显示“波形读取”；
- 通道是否参与仿真/显示，仍由“垂直”页的“开启”开关控制；
- 面板设置（V/div、偏移、耦合、反相、时基、触发源/电平、测量项、AFG）在仿真模式下即时反映到波形上，便于调试界面与流程。
