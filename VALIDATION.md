# 验证记录

## 云端实际执行

环境：Linux x86_64、Python 3.12.14。空仓库上新建项目，未替换已有用户代码。

- `.venv/bin/python -m pip install -r requirements.txt`：成功。
- `.venv/bin/python -m pip check`：成功，无依赖冲突。
- 通过 pip 的跨平台解析/下载核对 Windows 64 位 CPython 3.12 与 3.14：各自固定版本及依赖均有相应 wheel。此项仅证明发行包可取得，未在 Windows 实际安装或运行。
- 在独立 Linux Python 3.12 环境中安装 MediaPipe 0.10.35 / OpenCV 4.13.0 / NumPy 2.3.5：`pip check`、Tasks API 导入及 7 项测试通过。此项不等于在 Windows Python 3.14 上实际运行。
- 导入：MediaPipe 0.10.21 / OpenCV 4.11.0 / NumPy 1.26.4 成功。
- `.venv/bin/python -m unittest discover -s tests -v`：7 项通过。
  - 张掌与握拳形状、保持后暂停。
  - 单次连续挥手只触发一次。
  - 轻微抖动不翻页、初始暂停时不翻页。
  - 左右规则方向、DTW 距离与模板分类。
  - 丢手取消进行中的动作。
  - 临时目录合成片段完整通过分组、模板构建、双方法评价，检查按人员隔离及拒绝测试集训练。
- 编译检查及 app/tools 帮助入口：成功。
- 已打包 Windows 安装与启动脚本；云端无法执行 `.cmd`，需用户电脑验证。
- 手动曝光参数与 DirectShow 后端已加入程序；云端没有 Windows 摄像头，因此驱动是否接受 `--exposure` 仍需看本机输出的 `accepted/readback`。
- `/dev/video*`：无设备。未执行摄像头采集、可视窗口交互、Windows SendInput 或 PPT 翻页。
- 官方模型下载：代理 CONNECT 返回 403。未下载模型、未执行实际 Hand Landmarker 推理。模型域名已保存至环境网络配置草稿，保存不是当前实例已放行的证据。
- 导入时 Matplotlib 的只读 HOME 缓存警告不影响上述测试；云端可设置 `MPLCONFIGDIR=/tmp/gesture-mpl` 后运行。

合成测试结果只用于软件回归验证，不作为真实数据实验报告。无真实受试人员、准确率或响应延迟结果。

## 本地逐项验收

1. 安装依赖、下载官方模型；执行 `python smoke_model.py`，检查 CPU 模型初始化和 3 次空白图像 VIDEO 推理。空图通过不证明真人关键点检测效果。
2. 执行 `python app.py --camera 0`：检查画面、21 个关键点、FPS 与状态。若失败检查权限并换摄像头编号。
3. 暂停状态左右挥动应无指令；张掌保持后应启用；握拳保持后应暂停。
4. 左右各挥动 10 次，按屏幕方向计数，分别记录应触发数、实际指令数、漏触与重复；结束后保持原位不应重复翻页。
5. 动作中途遮挡或移出画面，返回静止应无遗留指令；试上下移动、小幅抖动、快速往返、自然讲演。
6. Windows 运行 `python app.py --control`，将 PPT 放映置前台，验证左上一页、右下一页。分别记录指令出现与页面实际变化，检查权限级别一致。此项是系统控制成功验证，离线指标不能代替。
7. Q/Esc/关闭窗口/控制台 Ctrl+C 后，用系统相机确认摄像头已释放。
8. 按 README 采集真实、独立分组数据，先验证集调参再固定参数跑测试集；报告样本数、分组方式及无意图录制分钟数。

尚未验证：Windows 依赖安装、摄像头驱动、GUI、真人检测和识别效果、CPU 实时帧率、系统按键/PPT 行为。模型网络访问恢复后可运行自检，但仍不能取代实机验收。
