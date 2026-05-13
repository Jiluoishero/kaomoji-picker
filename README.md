# 颜文字输入器

一个 Windows 桌面颜文字/符号快速输入工具。按全局快捷键唤起 Qt 原生浮动面板，点击符号后自动粘贴到唤起前的窗口。

## 功能

- 全局快捷键唤起面板，默认 ``Ctrl + ` ``，可在设置里修改。
- 单次模式：选择一个符号后自动关闭。
- 固定模式：短时间内连续按两次快捷键，可连续选择多个符号。
- 分组展示、批量添加、右键删除/移动表情、右键新增/重命名/删除分组、分组拖拽排序。
- 面板支持多屏定位、标题栏拖动、窗口大小保存。
- 系统托盘菜单：显示面板、退出。
- 默认表情数据保存在 `data.json`。
- 用户配置保存在运行时生成的 `config.json`，发布包不需要预置该文件。

## 环境

- Windows
- Python 3.10+
- PySide6 / Qt

安装依赖：

```powershell
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

或直接运行根目录的一键启动脚本：

```powershell
.\start.bat
```

程序启动后会进入系统托盘。按 ``Ctrl + ` `` 在鼠标附近显示面板。

## 数据与配置

- `data.json` 是默认表情数据，发布时随程序一起保留。
- `config.json` 是用户本机配置，首次启动时会自动生成，包含快捷键、窗口大小、开机自启等设置。
- 发布前不要打包 `config.json`、`*.log`、`__pycache__/`、`build/`、`dist/`。

## 文件结构

```text
main.py            # Qt 入口、窗口、热键、托盘生命周期
clipboard_util.py  # 剪贴板与粘贴模拟
data_manager.py    # data.json 读写
config_manager.py  # config.json 读写
data.json          # 默认表情数据
requirements.txt   # Python 依赖
start.bat          # 一键启动脚本
```
