import json
import os
import sys

DEFAULT_DATA = {
    "groups": [
        {
            "name": "开心",
            "items": [
                {"symbol": "(・∀・)"}, {"symbol": "( ´∀`)"}, {"symbol": "(*´▽`*)"},
                {"symbol": "(◕‿◕✿)"}, {"symbol": "ヽ(>∀<☆)ノ"}, {"symbol": "＼(＾▽＾)／"},
                {"symbol": "(✿◠‿◠)"}, {"symbol": "(*≧▽≦)"}, {"symbol": "(ﾉ◕ヮ◕)ﾉ*:・ﾟ✧"},
                {"symbol": "(⌒‿⌒)"}, {"symbol": "٩(◕‿◕｡)۶"}, {"symbol": "(★‿★)"},
            ]
        },
        {
            "name": "悲伤",
            "items": [
                {"symbol": "(;´Д`)"}, {"symbol": "( TдT)"}, {"symbol": "(╥_╥)"},
                {"symbol": "(;ω;)"}, {"symbol": "(个_个)"}, {"symbol": "(´；ω；`)"},
                {"symbol": "(ノ_<。)"}, {"symbol": "(T_T)"},
            ]
        },
        {
            "name": "可爱",
            "items": [
                {"symbol": "(=^-ω-^=)"}, {"symbol": "(⁄ ⁄•⁄ω⁄•⁄ ⁄)"}, {"symbol": "(｡♥‿♥｡)"},
                {"symbol": "ʕ•ᴥ•ʔ"}, {"symbol": "(ᵔᴥᵔ)"}, {"symbol": "₍ᐢ..ᐢ₎"},
                {"symbol": "꒰ᐢ. .ᐢ꒱"}, {"symbol": "(◕ᴗ◕✿)"}, {"symbol": "ᓚᘏᗢ"},
                {"symbol": "( ˘ᴗ˘ )"},
            ]
        },
        {
            "name": "动作",
            "items": [
                {"symbol": "(╯°□°）╯︵ ┻━┻"}, {"symbol": "┬─┬ノ( º _ ºノ)"},
                {"symbol": "(ノ´ー`)ノ"}, {"symbol": "(ง •_•)ง"},
                {"symbol": "( •̀ᄇ• ́)ﻭ✧"}, {"symbol": "(つ≧▽≦)つ"},
                {"symbol": "ヾ(⌐■_■)ノ♪"}, {"symbol": "(ノ°∀°)ノ⌒・*:.。"},
                {"symbol": "_(┐「ε:)_"}, {"symbol": "(¬‿¬)"},
            ]
        },
        {
            "name": "符号",
            "items": [
                {"symbol": "★"}, {"symbol": "☆"}, {"symbol": "♠"}, {"symbol": "♣"},
                {"symbol": "♥"}, {"symbol": "♦"}, {"symbol": "♪"}, {"symbol": "♫"},
                {"symbol": "✿"}, {"symbol": "❀"}, {"symbol": "✦"}, {"symbol": "✧"},
                {"symbol": "⚡"}, {"symbol": "☀"}, {"symbol": "☁"}, {"symbol": "❄"},
                {"symbol": "→"}, {"symbol": "←"}, {"symbol": "↑"}, {"symbol": "↓"},
                {"symbol": "✓"}, {"symbol": "✗"}, {"symbol": "•"}, {"symbol": "◆"},
                {"symbol": "※"}, {"symbol": "☾"}, {"symbol": "♬"}, {"symbol": "∞"},
            ]
        }
    ]
}


class DataManager:
    def __init__(self, filepath=None):
        if filepath is None:
            base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            self.filepath = os.path.join(base_dir, 'data.json')
        else:
            self.filepath = filepath
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        data = json.loads(json.dumps(DEFAULT_DATA))
        self._save_data(data)
        return data

    def _save_data(self, data=None):
        if data is None:
            data = self.data
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save(self):
        self._save_data()

    def get_groups(self):
        return self.data.get('groups', [])

    def add_items(self, group_name, symbols):
        for group in self.data['groups']:
            if group['name'] == group_name:
                for symbol in symbols:
                    s = symbol.strip()
                    if s:
                        group['items'].append({"symbol": s})
                self.save()
                return True
        return False

    def delete_item(self, group_name, symbol):
        for group in self.data['groups']:
            if group['name'] == group_name:
                group['items'] = [i for i in group['items'] if i['symbol'] != symbol]
                self.save()
                return True
        return False

    def move_item(self, source_group_name, target_group_name, symbol):
        if source_group_name == target_group_name:
            return False

        source_group = None
        target_group = None
        for group in self.data['groups']:
            if group['name'] == source_group_name:
                source_group = group
            elif group['name'] == target_group_name:
                target_group = group

        if source_group is None or target_group is None:
            return False

        for index, item in enumerate(source_group.get('items', [])):
            if item.get('symbol') == symbol:
                moved_item = source_group['items'].pop(index)
                target_group.setdefault('items', []).append(moved_item)
                self.save()
                return True
        return False

    def move_item_by_index(self, source_group_index, source_item_index, target_group_index, target_item_index=None):
        groups = self.data.get('groups', [])
        if not (0 <= source_group_index < len(groups)) or not (0 <= target_group_index < len(groups)):
            return False

        source_items = groups[source_group_index].setdefault('items', [])
        target_items = groups[target_group_index].setdefault('items', [])
        if not (0 <= source_item_index < len(source_items)):
            return False

        item = source_items.pop(source_item_index)
        if target_item_index is None:
            target_item_index = len(target_items)
        if source_group_index == target_group_index and target_item_index > source_item_index:
            target_item_index -= 1
        target_item_index = max(0, min(target_item_index, len(target_items)))
        target_items.insert(target_item_index, item)
        self.save()
        return True

    def add_group(self, name):
        for group in self.data['groups']:
            if group['name'] == name:
                return False
        self.data['groups'].append({"name": name, "items": []})
        self.save()
        return True

    def delete_group(self, name):
        self.data['groups'] = [g for g in self.data['groups'] if g['name'] != name]
        self.save()
        return True

    def rename_group(self, old_name, new_name):
        for group in self.data['groups']:
            if group['name'] == old_name:
                group['name'] = new_name
                self.save()
                return True
        return False

    def reorder_groups(self, group_names):
        name_to_group = {g['name']: g for g in self.data['groups']}
        new_groups = []
        for name in group_names:
            if name in name_to_group:
                new_groups.append(name_to_group[name])
        for g in self.data['groups']:
            if g['name'] not in group_names:
                new_groups.append(g)
        self.data['groups'] = new_groups
        self.save()
        return True
