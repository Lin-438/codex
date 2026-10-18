# 基于手部关键点的动态手势识别与演示控制系统

Python + OpenCV + MediaPipe Hand Landmarker，CPU 单手识别。默认只显示指令，不发送按键。源码中的英文界面避免 OpenCV 中文字体兼容问题。

## Windows 一键安装与运行

将整个项目文件夹下载或解压到电脑（路径中不要只复制 `app.py`）。使用 python.org 的 **64 位 Python 3.14、3.12 或 3.11**，安装时勾选 Python Launcher。已有 3.14 的电脑无需另装 3.12。双击 `install-windows.cmd`；它在本目录建立 `.venv`、安装固定依赖、下载模型并运行模型自检与测试。安装脚本会保留无法使用的旧 `.venv` 为 `.venv-backup-*`，重新创建可用环境；出现报错时命令窗口会停留，按提示排查。模型下载需要能访问官方 `storage.googleapis.com`；若被网络拦截，按下文手动下载放置模型，然后重跑安装脚本。

双击 `demo-windows.cmd` 进入不发送按键的演示模式。验证摄像头、动作和方向后，双击 `control-windows.cmd` 才启用前台 PPT 翻页。可从命令提示符运行 `demo-windows.cmd --camera 1` 切换摄像头。脚本只负责本机运行；电脑上的下载、权限、摄像头和 PPT 仍须在本机确认。

如果画面过亮，在项目目录的 PowerShell 中先按 `Q` 退出当前窗口，再用手动曝光重新启动演示模式（Python 3.14 的虚拟环境名称按实际创建的目录修改）：

```powershell
.\.venv314\Scripts\python.exe app.py --backend dshow --exposure -7
```

终端会打印 `accepted` 和 `readback`。若 `accepted=True` 且仍过亮，可依次试 `-8`、`-9`；若太暗则试 `-6`。这些值是摄像头驱动相关的示例，部分设备不支持 OpenCV 手动曝光。若返回 `accepted=False`，在 Windows「设置 → 蓝牙和设备 → 相机」中选择该摄像头调整亮度或曝光（若设备提供），并检查是否有强光直射或逆光。不要仅对画面做软件调暗：过曝丢失的手部细节无法恢复。

如果 `-6` 太暗，而 `-2` 帧率明显下降，先试 `-5`，并让台灯或室内灯从摄像头附近照向手掌。较长的摄像头曝光可能直接限制采集帧率；软件无法消除这段等待。新版程序也可在较短曝光下提亮中间亮度：

```powershell
.\.venv314\Scripts\python.exe app.py --backend dshow --exposure -5 --gamma 0.7
```

`--gamma` 默认 1.0；小于 1 变亮，例如 0.6 比 0.7 更亮。它用查找表处理已采集的帧，再送入手部检测，不会延长相机曝光；但无法恢复黑暗区域丢失的细节，太亮也可能让识别变差。若驱动支持增益，可另外试 `--gain 数值`；数值范围依设备而异，程序会打印是否接受及回读值，增益过高会增加噪声。建议先比较画面中的 `Capture` 和 `Detect` 耗时，再调整参数。

若开启 `--backend dshow --exposure` 后帧率下降，画面中的 `Capture` 是摄像头读取耗时，`Detect` 是关键点推理耗时（毫秒）。`Capture` 较大时先恢复默认后端并用 Windows 相机设置调曝光；`Detect` 较大时可降低推理宽度：

```powershell
.\.venv314\Scripts\python.exe app.py --width 640 --height 480 --inference-width 320
```

现在默认请求 640×480，并把推理图像缩到 320 像素宽；可用 `--width`、`--height`、`--inference-width` 覆盖。降低推理宽度可能让远处或很小的手难以识别；先在演示模式确认效果。实际采集分辨率以启动时终端输出为准。若不再需要手动曝光，请省略 `--backend` 和 `--exposure`。

## 安装与启动（Windows）

推荐 Windows 10/11 64 位、Python 3.14/3.12/3.11 64 位、普通内置摄像头。3.11/3.12 使用 `requirements.txt`（MediaPipe 0.10.21 / OpenCV contrib 4.11.0.86 / NumPy 1.26.4）；3.14 使用 `requirements-py314.txt`（MediaPipe 0.10.35 / OpenCV contrib 4.13.0.92 / NumPy 2.3.5），由安装脚本自动选择。前者在 Linux Python 3.12 已验证；后者已核对 Windows 3.14 wheel，并在 Linux 上验证安装、导入与逻辑测试。两者均使用 Tasks Hand Landmarker API。Windows ARM 尚未验证。

在项目根目录打开 PowerShell：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-py314.txt
.\.venv\Scripts\python.exe tools.py download-model
.\.venv\Scripts\python.exe app.py
```

手动命令以 Python 3.14 为例；使用 3.12 或 3.11 时，将第一条分别改为 `py -3.12` 或 `py -3.11`，第二条改用 `requirements.txt`。PowerShell 执行当前目录程序，路径前必须有 `.\`。不需要激活虚拟环境。Linux 对应解释器为 `.venv/bin/python`，需要桌面图形环境；无显示器的服务器不能直接显示摄像头窗口。不要安装 opencv-python-headless 或同时安装多个 OpenCV 包。

```powershell
.\.venv\Scripts\python.exe app.py --camera 1
.\.venv\Scripts\python.exe app.py --control
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`--camera` 临时覆盖配置的摄像头编号，内置摄像头一般是 0。打不开时检查系统相机权限、是否被其他软件占用，尝试 1 或 2。Q、Esc 或关闭窗口退出，finally 释放摄像头。实际控制时摄像头窗口失去焦点，需切回窗口才能使用退出键；控制台 Ctrl+C 也会释放资源。

## 模型

官方下载地址：
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

默认保存 `models/hand_landmarker.task`，文件不提交 Git。可通过浏览器从官方 HTTPS 地址下载，放入该位置；已有本地模型时，在 `config.json` 设置 `model` 为绝对路径或项目根目录的相对路径。下载工具保留 TLS 验证、拒绝覆盖已有文件，并打印 SHA256；可加 `--sha256 <可信摘要>` 校验从独立可信来源获得的摘要，打印摘要本身不构成独立真实性验证。不需要 API Key。

云环境需要允许访问 `storage.googleapis.com`。网络配置草稿已加入该域名，需在环境设置中审阅、保存并发布；草稿保存不等于当前运行实例网络已更新。

## 演示与 PPT 控制

1. 默认 PAUSED；将一只手置于画面中，尽量张开四指并保持约 0.8 秒，状态变为 ENABLED。
2. 张掌静止约 0.18 秒后水平挥动，随后停住约 0.18 秒：屏幕向左对应上一页，向右对应下一页。
3. 握拳保持约 0.8 秒暂停。演讲时不用控制请先暂停，避免自然摆手被接受。
4. 默认 DEMO 只显示 left/right 指令。`--control` 为 Windows 实际按键模式，经 SendInput 发送方向键。请先演示模式调好再使用。
5. 在 PowerPoint/WPS 中启动放映后，使用 Alt+Tab 或鼠标将放映窗口置于前台。程序不会自动切换窗口。方向键发送给**当前前台应用**，可能影响其他软件；应用与程序应使用相同权限级别。不要以管理员身份运行 PPT 而以普通身份运行本程序。

如果 `CONTROL / ENABLED / READY` 下 PPT 仍无响应，`Last event: enabled` 只表示控制已启用。先观察手掌水平移动时是否进入 `MOVING`，然后停住，确认 `Last event` 出现 `left/right`。新版会一直保留最近一次 `Last motion` 失败原因，并在终端打印 `Motion:`、`Gesture:`；成功调用 Windows 按键接口后还会打印 `Key: ... accepted by Windows`。Windows 接受事件并不证明 PPT 已翻页。

可独立测试按键通路，无需摄像头或更新源码：先按 Q 退出摄像头程序，将 PPT 打开放映到中间一页，确认实体右方向键可以翻页。再回到 PowerShell 执行下方命令，在打印提示后的 5 秒内用 Alt+Tab 切回 PPT 放映窗口。命令只发送一次右方向键，Ctrl+C 可在倒计时内取消：

```powershell
.\.venv314\Scripts\python.exe -c "import time; from gesture.runtime import send_key; print('Switch to the slideshow now; RIGHT in 5 seconds', flush=True); time.sleep(5); send_key('right'); print('Windows accepted RIGHT')"
```

若此测试能翻页而手势不能，继续根据 `Last motion` 查动作识别；若测试不能翻页，检查终端报错、放映窗口焦点，以及 PPT 与 Python 是否以相同权限级别运行。测试期间不需挥手。虚拟环境名称按实际目录修改。

默认 `mirror: true`，先镜像再提取关键点，方向相对于你看到的自拍画面。关闭镜像后方向相对于原始画面，体感左右可能相反。不要在摄像头驱动中再做一次镜像。只跟踪一只手，演示时避免第二只手进入画面；多人交替、快速换手可能产生关键点身份切换。

## 配置与方法

编辑 `config.json`，从项目根目录启动，或 `--config 路径`。时间单位秒，距离为归一化图像宽高坐标：

| 参数 | 含义 |
| --- | --- |
| camera / model / mirror | 摄像头、本地模型、镜像 |
| camera_backend / camera_exposure | Windows 可选的 DirectShow 后端与手动曝光；默认为 auto/null，不修改驱动曝光 |
| camera_gain / image_gamma | 可选摄像头硬件增益 / 图像伽马；默认为 null/1.0，后者小于 1 可提亮 |
| width / height / inference_width | 请求的采集宽高与推理宽度；默认 640/480/320，单位像素 |
| max_frame_gap_seconds | 超过此时间没有下一帧则取消当前动作；默认 0.6 秒，兼容较慢 CPU |
| min_detection_confidence / min_tracking_confidence | 检测与跟踪阈值 |
| hold_seconds | 张掌/握拳连续保持时间 |
| stable_seconds | 起手和结束所需稳定时长 |
| cooldown_seconds | 翻页后冷却 |
| motion_start / motion_end | 离开稳定起点幅度 / 结束稳定容差 |
| min_swipe / max_vertical | 最小水平幅度 / 最大纵向摆动 |
| max_action_seconds | 动作最长时间，超时取消 |
| method / templates / dtw_threshold | rule 或 dtw、训练模板路径、匹配拒绝阈值 |

关键点提取保存两种表示：掌心（腕与四个掌指关节均值）在画面中的**绝对位置轨迹**，以及以腕为原点、掌长归一化的 21 点**相对形状**。因此归一化手形不会抹去挥手位移。张掌/握拳由四指指尖到腕距离相对中间关节距离判断，拇指不参与；允许其中一指短暂弯曲。该判断属于简化姿态规则。

控制器：暂停 → 张掌保持 → 启用 → 稳定起手 → 水平运动 → 稳定结束 → 单次输出 → 冷却后重新稳定。手消失、时间断档超过 0.6 秒、动作超时均取消未完成动作。手消失不会自动改变启用状态，返回后需要重新稳定。只有张掌可开始挥手，动作中允许不超过 0.15 秒的短暂姿态波动；方向一致性需达到 0.8，减少抖动与往返误触。

允许一次小幅反向准备动作：仅在整段方向一致性不足时，以最终方向的反向极值为分界，要求准备段幅度严格小于 `min_swipe`，准备段和主挥动段的方向一致性都至少为 0.8，主段至少有 3 帧。整段净位移仍须达到 `min_swipe`，纵向限制检查完整动作；已经达到指令幅度的反向摆动、多次往返和原地抖动继续拒绝。诊断出现 `prep=...` 表示使用了准备动作容错，此时 `straight` 是主段的一致性。原始轨迹完整保存；DTW 仍匹配完整轨迹，规则与 DTW 共用接受门限。自然水平摆手若满足全部条件仍可能误触，不能保证理解人的意图；改进后仍需用无意图录制评价。

如果画面仍只有三行状态（没有 `Pose`、`Capture`），正在运行旧版代码；请下载最新源码并更新 `app.py`、`gesture/core.py`、`gesture/runtime.py`、`config.json`。如果长时间没有 `left/right`，先看 `ENABLED`、`Hand: tracked`、`Pose: open` 和阶段提示。`HOLD STILL` 表示还没稳定起手，`READY` 表示可以开始挥手，`MOVING` 表示正在跟踪动作。默认最小水平位移为画面宽度的 12%（640 像素宽约 77 像素），应在手掌正对摄像头时从一侧直线挥到另一侧，停约 0.2 秒后再收回。`Last event` 保留上次指令；`Last motion` 显示最近动作的位移、纵向偏移和直线程度，或被取消的原因。若姿态经常变成 `idle`，先改善光线和手掌朝向。调小 `min_swipe` 会提高触发率，也会增加自然动作误触风险，实际演示前请用 `idle` 片段评价。

按诊断值逐项调参，每次只改一个参数并重启：

| 日志 | 含义及处理 |
| --- | --- |
| `idle dx=+0.17/0.12 y=0.17/0.14` | 水平幅度足够，但纵向范围超过阈值；可在本机试 `max_vertical: 0.20`，随后检查自然摆手误触 |
| `idle dx=+0.09/0.12` | 当前分段位移不足；可能是挥动幅度小，也可能是慢动作提前结束，需要完整轨迹才能区分 |
| `straight=0.04` | 水平净位移远小于走过的路径，常见于来回摆动；单向挥动后先停住，等指令再收手 |
| `motion timeout` / `tracking lost` | 动作超过时间限制 / 手部追踪中断，当前动作已取消；重新等待 READY 再开始 |

若缓慢挥动经常分成数段小位移，先将本机 `stable_seconds` 从 `0.18` 调为 `0.30`，保持 `min_swipe` 为 `0.12`。结束时需要稳定至少 0.3 秒，建议实际停约 0.5 秒；起手等待也会相应延长。合成轨迹检查显示这能避免一个 1.8 秒慢挥被提前截断，但不能证明真实漏识别都由此导致；若仍失败，应采集一次完整挥手的关键点序列。现场配置与实验基线分别保存，实验调参使用验证集，最终固定参数再测测试集。

如果反复调参仍漏识别，先记录真实轨迹。白色 `PALM` 圆圈表示参与识别的掌心；`READY` 或 `MOVING` 时出现的 `L/R` 短竖线是相对起点的左右幅度门槛。将整只手向一侧平移，使掌心圆圈越过相应竖线，再停住。只转动手腕、摆动指尖时，掌心可能几乎没动。越过线只满足幅度条件，仍需通过手形、稳定结束、纵向范围等检查；标线不是额外的触发按钮。

诊断录制保留当前配置和启动参数，在通常的演示窗口记录每帧关键点及判断结果：

```powershell
.\.venv314\Scripts\python.exe app.py --backend dshow --exposure -5 --gamma 0.6 --trace left-debug.jsonl
```

保持现有 `config.json`，更新 `app.py` 即可使用该开关。先张掌启用、等 READY，只做 3 次左挥，每次结束停约半秒，最后按 Q。上述命令使用 DEMO，不发送按键；加 `--control` 可同时测试控制。文件保存在当前项目目录，包含参数、原始关键点、相对时间、识别事件和新产生的诊断，不含摄像头图像；已有同名文件会被拒绝覆盖，请换文件名。录制中按 Ctrl+C 也会关闭文件和摄像头。

更新后的 `tools.py` 可直接检查录制，无需摄像头：

```powershell
.\.venv314\Scripts\python.exe tools.py inspect-trace --input left-debug.jsonl --output reports/left-debug-summary.json
```

报告包含时长、帧率、丢手比例、连续跟踪段的掌心坐标范围、事件计数及诊断时间；整段坐标范围不能视为一次有效挥手。诊断文件没有动作意图标签，不用于计算准确率，正式实验继续使用下方采集工具。出现 `portable_clearcut_uploader` 上传失败但画面和 Motion 日志仍继续时，应按实际手势诊断判断；此类后台日志不能解释 `dx` 不足或轨迹往返导致的拒绝。

规则基线使用方向、净位移、纵向范围、水平路径一致性；DTW 使用减去首点后的二维掌心轨迹，保留幅度与方向，通过动态规划匹配训练片段。DTW 同样经过运动门限，比较的是共享门控后的规则方向与轨迹模板识别；不会声称是纯无门控 DTW。时间/空间复杂度 O(NM)，适合短片段，模板过多会影响帧率。所有计算默认 CPU。

## 采集与标注

每条 JSON 是一个完整独立片段：包括 label、person、recording、mirror、intent_start 和每帧时间、原始 21×3 点、掌心、相对坐标、姿态。丢手帧保留 points=null。只保存关键点，不保存人脸视频，但人员数据仍应征得同意。

```powershell
.\.venv\Scripts\python.exe tools.py collect --label right --person P01 --recording P01_session01 --output data/clips/P01_right_01.json
```

SPACE 开始、Q 结束。label 可选 left/right/open/fist/idle，由命令行指定即完成片段标签。每个动作片段只做一次目标动作，留约 0.3 秒稳定起点和终点。left/right 使用张掌；静态 open/fist 持续超过保持时间。idle 应录制长时间自然讲演、抓头、指点、轻微抖动、离开画面等，不能只录空画面。

recording 是**原始录制场次 ID**，同一连续录制裁出的所有片段必须用同一编号，不要为避免分组而逐片改号。人员编号也应全局一致。建议至少 5 人、多场次、每人每类多次，变化光照、距离与速度。工具不自动推断意图时间：可在 JSON 中填写 `intent_start`（SPACE 后的秒数），或录制命令加 `--intent-start`；需人工观察标注真实动作意图起点，未知时保持 null，响应时间不会被伪造为 0。

## 人员划分、DTW 与评价

```powershell
.\.venv\Scripts\python.exe tools.py split --data data/clips --group person
.\.venv\Scripts\python.exe tools.py train-dtw --split data/split.json
.\.venv\Scripts\python.exe tools.py evaluate --partition val --templates data/templates.json --output reports/validation.json
.\.venv\Scripts\python.exe tools.py evaluate --partition test --templates data/templates.json
```

默认随机种子 42，按组约 60/20/20 分 train/val/test，至少三个组；也可 `--group recording` 进行独立场次评估。同一人员若跨集合，必须明确这是跨场次而非跨人员泛化。禁止按相邻帧随机划分。训练集制作模板，验证集调阈值，最后固定配置再跑测试集。检查划分后各集合动作覆盖；分组随机分配不保证类别平衡，缺失类别结果为 null。

输出 JSON 包含同一测试集的规则与 DTW 混淆矩阵（行真值、列预测）、总体/各类准确率、指令成功率、响应时间、idle 每分钟误翻页数。片段分类和连续指令指标分别计算：静态分类要求连续保持，运动优先；存在任何丢手帧的片段分类保守地判 idle。流式控制则会取消当前动作并继续等待。

指令成功定义为动作片段中**恰好一条事件且匹配标签**，多次或额外事件均失败。挥手片段初始启用；open 片段初始暂停；fist 初始启用。idle 初始启用，以检测演讲时的误翻页。响应时间只统计成功且有有效意图时间标注的片段，报告样本数；不是端到端 PPT 渲染延迟。缺少 idle 时误触率为 null。离线事件成功不等于操作系统/PPT 确已翻页，需现场单独记录翻页尝试与实际页面变化。

## 项目结构与验证

- `app.py`：实时 UI、识别与可选按键。
- `gesture/runtime.py`：摄像头、Tasks API、绘制、Windows 按键。
- `gesture/core.py`：姿态、轨迹规则、DTW、控制状态机。
- `tools.py`：下载、采集、分组、训练、评价。
- `tests/`：可脱离摄像头运行的合成轨迹回归测试。
- `VALIDATION.md`：当前环境实际验证记录与实机验收步骤。

没有提供真实实验结果。合成测试只证明逻辑和工具能运行，不代表真实识别准确率。小手、遮挡、侧掌、背光和低帧率可能显著降低效果；帧率过低导致时间断档时会取消动作。MediaPipe 模型另遵循其发布方许可条款。

获得模型后，可先运行 `python smoke_model.py` 做无摄像头的 CPU 推理自检，再运行实时程序。
