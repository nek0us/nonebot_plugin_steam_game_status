import json
import shutil
import os
from pathlib import Path
from nonebot import require,logger
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

nb_project = os.path.basename(os.getcwd())

plugin_data_dir: Path = store.get_data_dir("nonebot_plugin_steam_game_status")
data_dir = plugin_data_dir / nb_project

# Ensure the new directories exist
data_dir.mkdir(parents=True, exist_ok=True)

# 兼容性检测

# 需要移动的文件夹列表
dirs_to_move = ["steam_user_list.json", "steam_group_list.json"]
if os.name == 'nt':
    incorrect_dir = Path(os.getcwd())
    if incorrect_dir.exists() and incorrect_dir.is_dir():
        for dir_name in dirs_to_move:
            src_dir = incorrect_dir / dir_name
            dest_dir = data_dir / dir_name
            if src_dir.exists() and src_dir.is_dir():
                shutil.move(str(src_dir), str(dest_dir))

# 旧文件路径
old_dirpath = Path() / "data" / "steam_group" / "group_list.json"

# 新文件路径
new_file_steam = data_dir / "steam_user_list.json"
new_file_group = data_dir / "steam_group_list.json"
game_cache_file = data_dir / "game_cache.json"
exclude_game_file = data_dir / "exclude_game"

exclude_game_default = ["Wallpaper Engine：壁纸引擎","虚拟桌宠模拟器","OVR Toolkit","OVR Advanced Settings","OBS Studio","VTube Studio","Live2DViewerEX","Blender","LIV"]

# 判断旧文件存不存在
if not old_dirpath.exists():
    # 不存在，看看新的在不在
    if not new_file_steam.exists():
        # 也不存在，新用户，直接创建
        logger.info("初次启动，创建 steam 缓存文件")
        new_file_steam.write_text("{}")
        new_file_group.write_text("{}")
        game_cache_file.write_text("{}")
        exclude_game_file.write_text("{}")
    else:
        # 存在，准备好的新用户
        # 看看exclude在不在
        if not exclude_game_file.exists():
            game_cache_file.write_text("{}")
            group_tmp = json.loads(new_file_group.read_text(encoding='utf8'))
            if group_tmp == {}:
                
                exclude_game_file.write_text("{}")
            else:
                exclude_game_tmp = {}
                for group_id in group_tmp:
                    exclude_game_tmp[group_id] = exclude_game_default
                exclude_game_file.write_text(json.dumps(exclude_game_tmp))
else:
    # 存在旧文件，看看新的在不在
    if not new_file_steam.exists():
        # 不存在新文件，准备迁移
        
        old_json = json.loads(old_dirpath.read_text())
        
        new_json_steam = {}
        new_json_group = {}
        
        if old_json != {}:
            # 不为空，有内容迁移
            logger.info(f"版本更新，steam 数据迁移中：{data_dir}")
            for group_id, data in old_json.items():
                # Update group information in new_json_group
                new_json_group[group_id] = {
                    "status": data["status"] == "on",
                    "user_list": list(data.keys())[1:]  # Skip the "status" key
                }
                
                # Update user information in new_json_steam
                for steam_id, user_data in data.items():
                    if steam_id != "status":  # Skip the "status" entry
                        new_json_steam[steam_id] = user_data
            
            # 写入新文件
            new_file_steam.write_text(json.dumps(new_json_steam))
            new_file_group.write_text(json.dumps(new_json_group))
            logger.success("steam 数据迁移完成")



