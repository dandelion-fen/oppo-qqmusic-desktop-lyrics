# OPPO QQ Music Desktop Lyrics

**手机听 QQ 音乐，Windows 桌面同步显示透明歌词。**

声音继续从手机或手机连接的耳机播放。电脑只显示歌词，可自定义颜色、透明度、字号、位置和窗口大小。
手机无需安装辅助 App、无需 root，使用 Android 官方 ADB 读取系统媒体信息。

## 功能

- **直接同步手机通知歌词**：跟随 QQ 音乐发布的当前句，不必再匹配歌词源。
- **透明无边框**：调整和显示模式都没有系统标题栏，背景可以完全透明。
- **自定义外观**：歌词颜色、辅助信息颜色、整体透明度、字号、置顶与鼠标穿透。
- **移动和缩放**：编辑模式提供拖动、缩放手柄；支持 Ctrl + 滚轮修改字号。
- **USB / 无线连接**：自动选择已授权的手机，忽略离线模拟器。
- **备用歌词模式**：按歌名联网匹配 QQ / 网易云歌词，或加载本地 LRC。
- **自动保存**：记住窗口位置、宽高和外观设置。

## 快速开始

### 1. 获取电脑程序

前往 [Releases](https://github.com/dandelion-fen/oppo-qqmusic-desktop-lyrics/releases)，下载 Windows ZIP 并**完整解压**。
双击 `QQPhoneLyrics.exe`。不要只复制 EXE，旁边的 `_internal` 文件夹也是程序的一部分。

如果暂时没有发布安装包，可按照下方「源码运行」启动。

### 2. 开启手机 USB 调试并授权

1. OPPO 手机进入 **设置 → 关于本机 → 版本信息**，连续点击版本号开启开发者选项。
2. 进入 **其他设置 / 系统设置 → 开发者选项**，开启 **USB 调试**。
3. 用支持数据传输的 USB 线连接电脑，保持手机解锁。
4. 手机上弹出「允许 USB 调试」时点击 **允许**。

菜单名称可能因 ColorOS 版本而不同。只对自己的电脑授予调试权限，不使用时可以关闭 USB 调试。

### 3. 开启 QQ 音乐通知栏歌词

在手机 QQ 音乐设置中寻找并开启 **通知栏歌词**（名称或位置以当前版本为准），然后播放歌曲。
在电脑程序中勾选 **直接显示手机通知歌词**。

当手机将当前歌词句发布到系统媒体信息后，电脑会直接显示这一句。
**如果只看到歌名，请先检查手机是否开启通知栏歌词；部分版本可能不向媒体信息发布歌词。**

### 4. 调整透明度、位置与大小

| 想调整什么 | 操作 |
|---|---|
| 透明背景 | 勾选「背景完全透明（只留下歌词）」 |
| 文字透明度 | 调整「整体透明度」滑块 |
| 歌词颜色 | 点击「歌词颜色」 |
| 位置 | 点「调整位置和大小」，拖动左上角 **✥ 拖动** |
| 窗口宽高 | 在调整模式拖动右下角 **↘** |
| 文字大小 | 字号滑块，或在歌词上按住 **Ctrl + 鼠标滚轮** |
| 完成调整 | 点控制台「完成调整」，隐藏操作手柄 |
| 不挡鼠标 | 完成调整后勾选「鼠标穿透」 |
| 穿透后再调整 | 按 **Ctrl + Alt + L** 进入调整模式 |
| 窗口找不到 | 点击「恢复歌词位置」 |

窗口宽高和字号是独立设置。调整模式暂时取消鼠标穿透、提高文字可见度；完成后恢复原设置，背景始终按透明选项显示。

更完整的连接、无线使用和排错步骤请看 **[使用教程](docs/使用教程.md)**。

## 两种歌词模式

| 模式 | 数据来源 | 注意事项 |
|---|---|---|
| 手机通知歌词（推荐） | 手机 QQ 音乐发布的当前句 | 不联网匹配，约每 0.4 秒采样；没有提前的下一句，不支持时间偏移 |
| 电脑匹配歌词 | 歌名、歌手 → QQ / 网易云歌词，或本地 LRC | 手机应提供真实歌名而不是通知歌词；约每 0.8 秒采样，可调整时间偏移 |

两种模式都只支持**逐行显示**，不支持逐字卡拉 OK 高亮。
直接模式只需要 ADB 连接；备用联网匹配会把歌名、歌手等查询信息发送给相应歌词服务。

## 兼容性

- Windows 10/11，发布包面向 Windows x64。
- 已通过 USB 在 **OPPO Reno10 Pro+ 5G（PHU110）** 上读取真实 QQ 音乐歌词和播放进度。
- 其他 Android 手机理论上也可使用，尚未逐一验证。
- 无线调试需要 Android 11+ 且系统提供对应功能。
- 锁屏、后台管理、蓝牙耳机和长期连接表现仍需更多实机验证。

本项目依赖标准 Android MediaSession，而非界面抓取或 QQ 音乐 Hook，可以减少对 ColorOS 界面变化的依赖，**但不保证所有系统或 QQ 音乐更新都无需适配**。
详见 [验证记录](VALIDATION.md)。

## 源码运行

需要 Python 3.10+（包含 Tkinter）以及 [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)。
运行程序不需要安装第三方 Python 包。

```powershell
git clone https://github.com/dandelion-fen/oppo-qqmusic-desktop-lyrics.git
cd oppo-qqmusic-desktop-lyrics
python app.py
```

点击「选择 adb.exe」指定解压后的 Platform-Tools 中的 `adb.exe`，或将 Platform-Tools 加入 PATH。
也可将 `adb.exe`、`AdbWinApi.dll`、`AdbWinUsbApi.dll` 及官方 `NOTICE.txt` 放进项目的 `tools/` 文件夹。
源码仓库不包含这些第三方二进制文件。

## 测试与打包

```powershell
python -m unittest test_core -v        # 核心逻辑，不需要连接手机
python -m unittest test_window -v      # Windows 桌面会话中的窗口交互测试
python -m py_compile app.py core.py
python -m pip install pyinstaller
.\build.bat                           # 先按上方说明准备 tools/
```

输出目录：`dist/QQPhoneLyrics/`。命令行加 `--edit` 可直接进入调整模式。
GitHub Actions 提供 Windows 构建；推送 `v*` 标签会生成对应 Release 及 ZIP。

## 配置与隐私

设置保存在 `%LOCALAPPDATA%\QQPhoneLyrics\settings.json`，备用模式的歌词缓存保存在同目录的 `cache/`。
程序不要求 QQ 账号登录，不上传完整媒体会话、手机通知或账户数据。
ADB 是调试接口，仅授权可信电脑。发布包中的 ADB 由 Android Platform-Tools 提供，相关声明见包内 `NOTICE.txt`。

## 许可与反馈

项目源代码使用 [MIT License](LICENSE)。第三方组件及歌词内容遵守各自许可和权利要求。
本项目与 OPPO、腾讯、网易不存在隶属或合作关系。
反馈问题时请提供 Windows、ColorOS、QQ 音乐版本和复现步骤；日志中请去除设备序列号等个人信息。
