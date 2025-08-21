
import json
import random
from typing import List, Optional

from nonebot import require
from nonebot.log import logger
from nonebot.internal.driver import Request
from nonebot_plugin_alconna.uniseg import MsgTarget

from .model import SafeResponse
from .utils import config_steam,http_client
from .source import (
    HTML_TEMPLATE,
    gameid2name,
    game_cache_file,
    group_list,
    steam_list,
    new_file_group,
    new_file_steam,
    exclude_game_file,
    exclude_game
    )
require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import html_to_pic

async def steam_link_rule() -> bool:
    if config_steam.steam_plugin_enabled and config_steam.steam_link_enabled:
        return True
    return False


async def get_game_info(app_id: str) -> dict:
    error = {'success': False}
    async with http_client() as client:
        for location in ["cn", "hk", "tw", "jp", "us"] if config_steam.steam_area_game else ["cn"]:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc={location}"
            try:
                res = SafeResponse(await client.request(Request("GET", url)))
                if res.status_code == 200 and isinstance(res.content, bytes):
                    res_json: dict = json.loads(res.text)[str(app_id)]
                    if not res_json['success']:
                        logger.debug(f"{location}区域未找到steam游戏应用id{app_id}")
                        continue
                    else:
                        logger.debug(f"{location}区域找到steam游戏应用id{app_id}")
                        res_json["from"] = location
                        return res_json
                else:
                    error = {'error':f"{res.status_code}\n{res.headers}\n{res.content}"}
            except Exception as e:
                error = {'error':e}
    return error

async def generate_image(html_content: str, width: int = 500) -> bytes:
    """生成图片
    
    Args:
        html_content (str): HTML内容
        width (int): 内容宽度，默认500px
    
    Returns:
        bytes: 图片二进制数据
    """
    # 格式化模板，插入内容和宽度
    html = HTML_TEMPLATE.format(
        width=width,  # 插入宽度值
        content=html_content  # 插入HTML内容
    )
    
    # 使用html_to_pic生成图片
    return await html_to_pic(
        html=html,
        wait=1000,
        type="jpeg",
        quality=90,
        device_scale_factor=2,
        screenshot_timeout=30_000,
        viewport={"width": width, "height": 100}  # 使用相同的宽度
    )



def get_steam_key() -> str:
    if isinstance(config_steam.steam_web_key, List):
        return random.choice(config_steam.steam_web_key)
    elif isinstance(config_steam.steam_web_key, str):
        return config_steam.steam_web_key
    else:
        return str(config_steam.steam_web_key)


async def gameid_to_name(gameid: str,origin_name: Optional[str] = None) -> str:
    '''获取游戏中文名'''
    global gameid2name
    if gameid in gameid2name:
        return gameid2name[gameid]
    res_json = await get_game_info(gameid)
    if 'error' in res_json:
        logger.debug(f"get game name failed.{res_json['error']}")
        return ""
    if not res_json['success']:
        logger.debug(f"get game name no success.{res_json}")
        return ""
    name = res_json['data']['name']
    if origin_name is None and origin_name != name:
        gameid2name[gameid] = name
        gameid2name[name] = gameid
        game_cache_file.write_text(json.dumps(gameid2name))
    return name
        
def save_data():
    global steam_list,group_list,exclude_game
    new_file_group.write_text(json.dumps(group_list)) 
    new_file_steam.write_text(json.dumps(steam_list))
    exclude_game_file.write_text(json.dumps(exclude_game))
    
async def no_private_rule(target: MsgTarget) -> bool:
    return not target.private
        
