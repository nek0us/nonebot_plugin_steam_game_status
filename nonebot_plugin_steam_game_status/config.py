from pydantic import BaseModel,validator
from typing import Union, Optional, List
from nonebot.log import logger
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import version
else:
    from importlib.metadata import version

try:
    __version__ = version("nonebot_plugin_bilichat")
except Exception:
    __version__ = None

class Config(BaseModel):
    steam_web_key: Optional[Union[str, List[str]]] = None
    steam_command_priority: int = 5
    steam_proxy: Optional[str] = None
    steam_plugin_enabled: bool = True
    
    @validator("steam_web_key")
    def check_api_key(cls,v):
        if isinstance(v,str):
            logger.success("steam_web_key 读取成功")
            return v
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            logger.success("steam_web_key 列表读取成功")
            return v
    
    @validator("steam_command_priority")
    def check_priority(cls,v):
        if isinstance(v,int) and v >= 1:
            return v
        raise ValueError("命令优先级必须为大于1的整数")
    
    
    @validator("steam_proxy")
    def check_proxy(cls,v):
        if isinstance(v,str):
            logger.success(f"steam_proxy {v} 读取成功")
            return v
    