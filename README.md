# 颜文字输入器

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

一个适用于 Windows 的桌面颜文字与符号快速输入工具。程序常驻系统托盘，可通过全局快捷键在鼠标附近唤起浮动面板，点击颜文字后自动粘贴到原本正在输入的位置。

## 直接使用发布版

前往 [Releases](../../releases) 页面，下载最新版本的压缩包，解压后双击 `KaomojiPicker.exe` 即可运行，无需安装 Python 环境。

## 使用方式

1. 启动程序后，它会常驻系统托盘。
2. 按 `Ctrl + Q` 在鼠标附近唤起颜文字面板。
3. 点击颜文字块，将内容粘贴到唤起面板前的输入窗口。
4. 短时间内连续按两次快捷键可进入固定模式，连续选择多个颜文字。

面板支持直接编辑：

- 可直接拖动分组，调整分组顺序。
- 可直接拖动颜文字块，调整顺序或移动到其他分组。
- 右键颜文字块，可删除或移动颜文字。
- 右键分组，可新建、重命名或删除分组。
- 在输入框中输入多个颜文字或符号，可批量添加到当前分组。

鼠标滚轮和非小键盘数字键可切换分组。

设置页可以修改全局快捷键、切换开机启动。


## 从源码运行

环境要求：

- Windows
- Python 3.10+

双击`start.bat`

或

安装依赖：

```powershell
pip install -r requirements.txt
```

运行：

```powershell
python main.py
```

## 打包

项目使用 PyInstaller 生成 Windows 发布包：

```powershell
.\build_exe.bat
```

完成后，发布目录位于：

```text
dist\KaomojiPicker\
```

其中 `KaomojiPicker.exe` 可直接双击运行。打包脚本会自动复制默认 `data.json` 和 `icon/` 资源目录。

发布前不要将源码运行时产生的 `config.json`、`*.log`、`__pycache__/`、`build/` 或 PyInstaller `*.spec` 文件放入发布包。

## 项目结构

```text
main.py          # 源码启动入口
kaomoji_picker/  # 应用源码包
tests/           # 核心逻辑测试
icon/            # 程序图标和标题栏 SVG 图标
data.json        # 默认颜文字包
build_exe.bat    # Windows 打包脚本
```

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
