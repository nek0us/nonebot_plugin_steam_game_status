from nonebot.log import logger
from typing import Union, Optional, List
from pydantic import BaseModel,field_validator
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
    steam_plugin_enabled: bool = True
    steam_link_enabled: bool = True
    steam_area_game: Union[bool, List[str]]= False
    steam_link_r18_game: Union[bool, List[str]] = False
    steam_tail_tone: str = ""
    
    @field_validator("steam_isthereanydeal_key")
    @classmethod
    def check_isthereanydeal_key(cls,v: Union[str, List[str]]) -> Union[str, List[str]]:
        if isinstance(v,str):
            logger.success("steam_isthereanydeal_key 读取成功")
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_isthereanydeal_key 列表读取成功")
        else:
            logger.error("steam_isthereanydeal_key 配置错误")
            raise ValueError("steam_isthereanydeal_key 配置错误")
        return v
    
    @field_validator("steam_web_key")
    @classmethod
    def check_api_key(cls,v: Union[str, List[str]]) -> Union[str, List[str]]:
        if isinstance(v,str):
            logger.success("steam_web_key 读取成功")
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_web_key 列表读取成功")
        else:
            logger.error("steam_web_key 配置错误")
            raise ValueError("steam_web_key 配置错误")
        return v
            
    @field_validator("steam_command_priority")
    @classmethod
    def check_priority(cls,v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("命令优先级必须为大于0的整数")
    
    @field_validator("steam_interval")
    @classmethod
    def check_steam_interval(cls,v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("steam查询间隔必须为大于0的整数")    
    
    @field_validator("steam_proxy")
    @classmethod
    def check_proxy(cls,v:Union[str, None]) -> Union[str, None]:
        if isinstance(v,str):
            logger.success(f"steam_proxy {v} 读取成功")
            return v

        
    @field_validator("steam_plugin_enabled")
    @classmethod
    def check_steam_plugin_enabled(cls,v: bool) -> bool:
        return v
        
    @field_validator("steam_link_enabled")
    @classmethod
    def check_steam_link_enabled(cls,v: bool) -> bool:
        if v:
            logger.success("steam_link_enabled 链接识别 已开启")
        else:
            logger.success("steam_link_enabled 链接识别 已关闭")
        return v
        
    @field_validator("steam_area_game")
    @classmethod
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
        
    @field_validator("steam_link_r18_game")
    @classmethod
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
        
    @field_validator("steam_tail_tone")
    @classmethod
    def check_tail_tone(cls,v: str) -> str:
        if v:
            logger.success("steam_tail_tone 读取成功")
        else:
            logger.success("steam_tail_tone未配置")
        return v

config_steam = get_plugin_config(Config)
bot_name = list(get_driver().config.nickname)