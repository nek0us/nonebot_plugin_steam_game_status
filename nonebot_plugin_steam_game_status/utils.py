from nonebot import get_driver
from typing import AsyncIterator
from contextlib import asynccontextmanager
from nonebot.internal.driver import HTTPClientMixin,HTTPClientSession

from .config import config_steam

driver = get_driver()

@asynccontextmanager
async def http_client(**kwargs) -> AsyncIterator[HTTPClientSession]:
    header = {
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":"zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding":"gzip, deflate, br",
        "Connection":"keep-alive",
        "Referer":"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/",
        "TE":"trailers"
    }
    if isinstance(driver, HTTPClientMixin):
        session = driver.get_session(headers=header, proxy=config_steam.steam_proxy, **kwargs)
        try:
            await session.__aenter__()
            yield session
        finally:
            await session.__aexit__(None, None, None)
    else:
        raise TypeError("Current driver does not support http client")


