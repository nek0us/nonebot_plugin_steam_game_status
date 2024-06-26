from pydantic import BaseModel,validator
from typing import Union, Optional, List
from nonebot.log import logger
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import version
else:
    from importlib.metadata import version

try:
    __version__ = version("nonebot_plugin_steam_game_status")
except Exception:
    __version__ = None

class Config(BaseModel):
    steam_web_key: Optional[Union[str, List[str]]] = None
    steam_command_priority: int = 5
    steam_interval: int = 1
    steam_proxy: Optional[str] = None
    steam_plugin_enabled: bool = True
    steam_link_enabled: bool = True
    
    @validator("steam_web_key", always=True, pre=True)
    def check_api_key(cls,v):
        if isinstance(v,str):
            logger.success("steam_web_key 读取成功")
            return v
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_web_key 列表读取成功")
            return v
        else:
            logger.error("steam_web_key 未配置")
    
    @validator("steam_command_priority")
    def check_priority(cls,v):
        if isinstance(v,int) and v >= 1:
            return v
        raise ValueError("命令优先级必须为大于0的整数")
    
    @validator("steam_interval")
    def check_steam_interval(cls,v):
        if isinstance(v,int) and v >= 1:
            return v
        raise ValueError("steam查询间隔必须为大于0的整数")    
    
    @validator("steam_proxy")
    def check_proxy(cls,v):
        if isinstance(v,str):
            logger.success(f"steam_proxy {v} 读取成功")
            return v
        
    @validator("steam_plugin_enabled")
    def check_steam_plugin_enabled(cls,v):
        if isinstance(v,bool):
            return v
        
    @validator("steam_link_enabled", always=True, pre=True)
    def check_steam_link_enabled(cls,v):
        if isinstance(v,bool):
            if v:
                logger.success("steam 链接识别 已开启")
            else:
                logger.success("steam 链接识别 已关闭")
            return v
        
        