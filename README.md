# 颜文字输入器

一个适用于 Windows 的桌面颜文字与符号快速输入工具。程序常驻系统托盘，可通过全局快捷键在鼠标附近唤起浮动面板，点击颜文字后自动粘贴到原本正在输入的位置。

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

设置页可以修改全局快捷键、切换开机启动，并进入排序模式。标题栏提供固定模式、深浅主题切换、设置和关闭按钮。

## 直接使用发布版

发布包采用 `onedir` 形式。运行：

```text
KaomojiPicker.exe
```

不要单独移动 exe。发布目录中的 `data.json`、`icon/` 和 `_internal/` 都需要与 exe 保持在同一目录。

`data.json` 是默认颜文字包，也会保存用户在界面中做出的编辑。首次运行后，程序会在 exe 同级目录生成本机配置文件 `config.json`。

## 从源码运行

环境要求：

- Windows
- Python 3.10+

安装依赖：

```powershell
pip install -r requirements.txt
```

运行：

```powershell
python main.py
```

也可以双击 `start.bat`。开发时可使用 `start_dev.bat`。

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
main.py              # 主窗口、Win32 热键、窗口焦点策略和应用入口
app_shell.py         # QApplication 与系统托盘生命周期
main_view.py         # 主面板 UI 组装
settings_view.py     # 设置页 UI 组装
data_manager.py      # 分组与颜文字数据读写
data_actions.py      # 数据编辑操作控制层
symbol_button.py     # 单个颜文字块的绘制和拖动
drag_widgets.py      # 分组与颜文字拖动相关控件
font_resolver.py     # 特殊字符字体 fallback
clipboard_util.py    # 剪贴板与模拟粘贴
autostart_manager.py # 开机启动注册表读写
icon/                # 程序图标和标题栏 SVG 图标
data.json            # 默认颜文字包
build_exe.bat        # Windows 打包脚本
项目状态.md           # 当前架构和 Windows 行为边界说明
```

更完整的技术栈、模块职责和重构注意事项见 `项目状态.md`。
