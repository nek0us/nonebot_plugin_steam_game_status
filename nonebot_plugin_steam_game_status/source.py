import json
import shutil
import os
from pathlib import Path
from typing import Dict, List
from nonebot import require,logger
from .model import GroupData, GroupData2, GroupData3, UserData
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
game_free_cache_file = data_dir / "game_free_cache.json"

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
        game_free_cache_file.write_text("{}")
    else:
        # 存在，准备好的新用户
        # 看看exclude在不在
        group_tmp = json.loads(new_file_group.read_text(encoding='utf8'))
        if not exclude_game_file.exists():
            game_cache_file.write_text("{}")
            if group_tmp == {}:
                exclude_game_file.write_text("{}")
            else:
                exclude_game_tmp = {}
                for group_id in group_tmp:
                    exclude_game_tmp[group_id] = exclude_game_default
                exclude_game_file.write_text(json.dumps(exclude_game_tmp))
        else:
            exclude_game_tmp = json.loads(exclude_game_file.read_text(encoding='utf8'))
            for group_id in group_tmp:
                if group_id not in exclude_game_tmp:
                    exclude_game_tmp[group_id] = exclude_game_default
            exclude_game_file.write_text(json.dumps(exclude_game_tmp))
        
        # 0.2.2 25.09.08 版本喜加一适配
        if not game_free_cache_file.exists():
            game_free_cache_file.write_text("[]")
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
            # 太久远版本没做迁移，懒得适配排除目录和喜加一目录了，直接删除重新旧数据比较快
            logger.success("steam 数据迁移完成")

# 25.08.21 UserData迁移
steam_list_tmp = json.loads(new_file_steam.read_text("utf8")) 
if isinstance(steam_list_tmp[next(iter(steam_list_tmp))],List):
    steam_list_dict = {}
    for steam_id in steam_list_tmp:
        steam_list_dict[steam_id] = UserData(
            time=steam_list_tmp[steam_id][0],
            game_name=steam_list_tmp[steam_id][1],
            nickname=steam_list_tmp[steam_id][2]
            )
    new_file_steam.write_text(json.dumps(steam_list_dict))
    logger.success("steam 0.2.0 数据迁移成功")

# 25.09.02 adapter更新
steam_group_25_09_02: Dict[str, GroupData] = json.loads(new_file_group.read_text("utf8")) 
value_25_09_02 = next(iter(steam_group_25_09_02.values()), None)
if value_25_09_02:
    if "adapter" not in value_25_09_02:
        steam_group_dict_25_09_02 = {}
        for group_id in steam_group_25_09_02:
            steam_group_dict_25_09_02[group_id] = GroupData2(
                status=steam_group_25_09_02[group_id]["status"],
                user_list=steam_group_25_09_02[group_id]["user_list"],
                adapter="OneBot v11"
            )
        new_file_group.write_text(json.dumps(steam_group_dict_25_09_02))
        logger.success("steam 0.2.1 25.09.02 adapter更新数据成功")


# 25.09.08 xijiayi更新
steam_group_25_09_08: Dict[str, GroupData2] = json.loads(new_file_group.read_text("utf8")) 
value_25_09_08 = next(iter(steam_group_25_09_08.values()), None)
if value_25_09_08:
    if "xijiayi" not in value_25_09_08:
        steam_group_dict_25_09_08 = {}
        for group_id in steam_group_25_09_08:
            steam_group_dict_25_09_08[group_id] = GroupData3(
                status=steam_group_25_09_08[group_id]["status"],
                user_list=steam_group_25_09_08[group_id]["user_list"],
                adapter=steam_group_25_09_08[group_id]["adapter"],
                xijiayi=False
            )
        new_file_group.write_text(json.dumps(steam_group_dict_25_09_08))
        logger.success("steam 0.2.2 25.09.08 xijiayi更新数据成功")


group_list: Dict[str, GroupData3] = json.loads(new_file_group.read_text("utf8"))  
steam_list: Dict[str, UserData] = json.loads(new_file_steam.read_text("utf8")) 
gameid2name = json.loads(game_cache_file.read_text("utf8"))
exclude_game: Dict[str, List[str]] = json.loads(exclude_game_file.read_text("utf8"))
game_free_cache: List[str] = json.loads(game_free_cache_file.read_text("utf8"))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width={width}, initial-scale=1.0">
    <style>
        /* 全局重置 */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        /* 页面容器 */
        html, body {{
            background-color: #fff;
            overflow-x: hidden;
            width: 100%;
            min-width: {width}px;
        }}
        
        /* 内容容器 - 关键修复 */
        .container {{
            width: {width}px;
            max-width: 100%;
            margin: 0 auto;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        
        /* 标题样式 */
        h1, h2, h3 {{
            margin: 1.5em 0 0.8em;
            padding-bottom: 0.3em;
            border-bottom: 1px solid #eee;
        }}
        
        /* 段落样式 */
        p {{
            margin: 1em 0;
            text-align: justify;
            word-wrap: break-word;
            overflow-wrap: break-word; /* 确保长单词换行 */
        }}
        
        /* 媒体容器 - 关键修复 */
        .bb_img_ctn {{
            margin: 1.5em auto;
            text-align: center;
            width: 100%;
            max-width: {width}px;
            overflow: hidden; /* 防止内容溢出 */
        }}
        
        /* 图片和视频样式 - 关键修复 */
        img.bb_img, video.bb_img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
        }}
        
        /* 列表样式 */
        ul.bb_ul {{
            padding-left: 2em;
            margin: 1em 0;
        }}
        
        li {{
            margin: 0.5em 0;
        }}
        
        /* 强调文本 */
        strong {{
            color: #e74c3c;
        }}
        
        /* 特殊元素处理 */
        br {{
            display: block;
            content: "";
            margin: 0.5em 0;
        }}
        
        /* 修复嵌套问题 */
        p > p {{
            margin: 0 !important;
            padding: 0 !important;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""