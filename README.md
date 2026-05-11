# 颜文字输入器

一个 Windows 桌面颜文字/符号快速输入工具。按全局快捷键唤起浮动面板，点击符号后自动粘贴到唤起前的窗口。

## 功能

- 全局快捷键唤起面板，默认 ``Ctrl + ` ``。
- 单次模式：选择一个符号后自动关闭。
- 固定模式：短时间内连续按两次快捷键，可连续选择多个符号。
- 分组展示、批量添加、编辑模式、分组拖拽排序。
- 系统托盘菜单：显示面板、退出。
- 配置和符号数据保存在项目目录下的 `config.json`、`data.json`。

## 环境

- Windows
- Python 3.10+
- Microsoft Edge WebView2 Runtime

安装依赖：

```powershell
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

程序启动后会进入系统托盘。按 ``Ctrl + ` `` 在鼠标附近显示面板。

## 文件结构

```text
main.py            # 入口、窗口、热键、托盘生命周期
api.py             # pywebview JS-Python 桥接
clipboard_util.py  # 剪贴板与粘贴模拟
data_manager.py    # data.json 读写
config_manager.py  # config.json 读写
tray.py            # 系统托盘
web/               # 前端界面
```
