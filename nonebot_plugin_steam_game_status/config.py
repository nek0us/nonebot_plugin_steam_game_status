from nonebot.log import logger
from typing import Union, Optional, List
from pydantic import BaseModel,validator
from nonebot import get_plugin_config, get_driver

from importlib.metadata import version

try:
    __version__ = version("nonebot_plugin_steam_game_status")
except Exception:
    __version__ = None

class Config(BaseModel):
    steam_web_key: Union[str, List[str]] = []
    steam_isthereanydeal_key: Union[str, List[str]] = []
    steam_command_priority: int = 5
    steam_interval: int = 1
    steam_proxy: Optional[str] = None
    steam_api_proxy: Optional[str] = None
    steam_store_proxy: Optional[str] = None
    steam_plugin_enabled: bool = True
    steam_link_enabled: bool = True
    steam_area_game: Union[bool, List[str]]= False
    steam_link_r18_game: Union[bool, List[str]] = False
    steam_tail_tone: str = ""
    steam_subscribe_time: Union[str, List[str]] = ["08:00"]
    
    @validator("steam_isthereanydeal_key")
    def check_isthereanydeal_key(cls,v: Union[str, List[str]]) -> Union[str, List[str]]:
        if isinstance(v,str):
            logger.success("steam_isthereanydeal_key 读取成功")
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_isthereanydeal_key 列表读取成功")
        else:
            logger.error("steam_isthereanydeal_key 配置错误")
            # raise ValueError("steam_isthereanydeal_key 配置错误")
        return v
    
    @validator("steam_web_key")
    def check_api_key(cls,v: Union[str, List[str]]) -> Union[str, List[str]]:
        if isinstance(v,str):
            logger.success("steam_web_key 读取成功")
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_web_key 列表读取成功")
        else:
            logger.error("steam_web_key 配置错误")
            # raise ValueError("steam_web_key 配置错误")
        return v
            
    @validator("steam_command_priority")
    def check_priority(cls,v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("命令优先级必须为大于0的整数")
    
    @validator("steam_interval")
    def check_steam_interval(cls,v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("steam查询间隔必须为大于0的整数")    
    
    @validator("steam_proxy")
    def check_proxy(cls,v:Union[str, None]) -> Union[str, None]:
        if isinstance(v,str):
            logger.success(f"steam_proxy {v} 读取成功")
            return v

        
    @validator("steam_plugin_enabled")
    def check_steam_plugin_enabled(cls,v: bool) -> bool:
        return v
        
    @validator("steam_link_enabled")
    def check_steam_link_enabled(cls,v: bool) -> bool:
        if v:
            logger.success("steam_link_enabled 链接识别 已开启")
        else:
            logger.success("steam_link_enabled 链接识别 已关闭")
        return v
        
    @validator("steam_area_game")
    def check_steam_area_game(cls,v: Union[bool, List[str]]) -> Union[bool, List[str]]:
        if isinstance(v, bool):
            if v:
                logger.success("steam_area_game 其它区游戏识别 已开启")
            else:
                logger.success("steam_area_game 其它区游戏识别 已关闭")
            return v      
        elif isinstance(v, list) and all(isinstance(i, str) for i in v):
            logger.success(f"steam_area_game 其它区游戏识别 已为部分群开启：{' '.join(v)}")
            return v
        else:
            logger.error("steam_area_game 其它区游戏识别 配置错误")
            raise ValueError("steam_area_game 其它区游戏识别 配置错误")
        
    @validator("steam_link_r18_game")
    def check_steam_link_r18_game(cls,v: Union[bool, List[str]]) -> Union[bool, List[str]]:
        if isinstance(v, bool):
            if v:
                logger.success("steam_link_r18_game 识别 已开启")
            else:
                logger.success("steam_link_r18_game 识别 已关闭")
            return v
        elif isinstance(v, list) and all(isinstance(i, str) for i in v):
            logger.success(f"steam_link_r18_game 识别 已为部分群开启：{' '.join(v)}")
            return v
        else:
            logger.error("steam_link_r18_game 识别 配置错误")
            raise ValueError("steam_link_r18_game 识别 配置错误")
        
    @validator("steam_tail_tone")
    def check_tail_tone(cls,v: str) -> str:
        if v:
            logger.success("steam_tail_tone 读取成功")
        else:
            logger.success("steam_tail_tone未配置")
        return v
        
    @validator("steam_subscribe_time")
    def check_subscribe_time(cls,v: Union[str, List[str]]) -> List[str]:
        if v:
            if isinstance(v, str):
                if ":" in v:
                    logger.success(f"steam_subscribe_time 订阅时间 {v} 读取成功")
                    return [v]
                else:
                    logger.exception(f"steam_subscribe_time 订阅时间 {v} 设置格式错误，将使用默认时间 08:00 ")
                    return ["08:00"]
            elif isinstance(v, list) and all(isinstance(i, str) for i in v):
                if all(":" in i for i in v):
                    logger.success(f"steam_subscribe_time 订阅时间 {v} 读取成功")
                else:
                    logger.exception(f"steam_subscribe_time 订阅时间 {v} 配置错误，将使用默认时间 08:00 ")
                    return ["08:00"]
            else:
                logger.warning("steam_subscribe_time配置错误，将使用默认时间 08:00 ")
                return ["08:00"]
        else:
            logger.info("steam_subscribe_time未配置，将使用默认时间 08:00 ")
            return ["08:00"]
        return v
    
config_steam = get_plugin_config(Config)
bot_name = list(get_driver().config.nickname)

def get_steam_api_domain() -> str:
    """获取Steam API域名，如果配置了代理则使用代理域名"""
    return config_steam.steam_api_proxy if config_steam.steam_api_proxy else "api.steampowered.com"

def get_steam_store_domain() -> str:
    """获取Steam Store域名，如果配置了代理则使用代理域名"""
    return config_steam.steam_store_proxy if config_steam.steam_store_proxy else "store.steampowered.com"