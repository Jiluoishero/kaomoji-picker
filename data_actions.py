from dialogs import ConfirmDialog, SimpleInputDialog


class DataActionController:
    def __init__(self, window):
        self.window = window

    @property
    def data(self):
        return self.window.data

    def delete_symbol(self, symbol):
        groups = self.data.get_groups()
        if groups:
            self.data.delete_item(groups[self.window.current_group_index]["name"], symbol)
            self.window._render_symbols()

    def move_symbol(self, symbol, target_group_name):
        groups = self.data.get_groups()
        if not groups:
            return
        source_group_name = groups[self.window.current_group_index]["name"]
        if self.data.move_item(source_group_name, target_group_name, symbol):
            self.window._render_symbols()

    def confirm_delete_group(self, group_name):
        ok = ConfirmDialog.ask(
            self.window,
            "删除分组",
            f"确定删除分组「{group_name}」？\n组内表情会一并删除。",
            confirm_text="删除",
            cancel_text="取消",
        )
        if not ok:
            return
        self.data.delete_group(group_name)
        self.window.current_group_index = 0
        self.window._reload_tabs()

    def add_group(self):
        name, ok = SimpleInputDialog.get_text(self.window, "新分组", "输入分组名称")
        if ok and name.strip():
            self.data.add_group(name.strip())
            self.window._reload_tabs()

    def rename_group(self, group_name):
        name, ok = SimpleInputDialog.get_text(self.window, "重命名分组", "输入新的分组名称", group_name)
        new_name = name.strip()
        if ok and new_name and new_name != group_name:
            self.data.rename_group(group_name, new_name)
            self.window._reload_tabs()

    def reorder_groups(self, from_index, to_index):
        groups = self.data.get_groups()
        names = [g["name"] for g in groups]
        moved = names.pop(from_index)
        names.insert(to_index, moved)
        self.data.reorder_groups(names)
        self.window.current_group_index = to_index
        self.data.save()
