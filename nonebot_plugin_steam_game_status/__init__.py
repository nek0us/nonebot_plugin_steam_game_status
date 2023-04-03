from nonebot import require,get_driver,get_bot,on_command
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot.adapters.onebot.v11 import Message,MessageEvent,Bot,GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.log import logger
from pathlib import Path
import json
import time
from httpx import AsyncClient


config_dev = get_driver().config
if "steam_web_key" not in config_dev:
    logger.error("steam_web_key未配置")
    raise ValueError("steam_web_key未配置")
steam_web_key = config_dev.steam_web_key
dirpath = Path() / "data" / "steam_group"
dirpath.mkdir(parents=True, exist_ok=True)
dirpath = Path() / "data" / "steam_group" / "group_list.json"
dirpath.touch()



@scheduler.scheduled_job("interval",minutes=1,id="steam")
async def now_steam():
    header = {
        "Host":"api.steampowered.com",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":"zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding":"gzip, deflate, br",
        "Connection":"keep-alive",
        "Referer":"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/",
        "TE":"trailers"
    }
    
    
    f = open(dirpath.__str__(),"r+")
    group_list = f.read()
    f.close()
    group_list = json.loads(group_list)
    for group_num in group_list:
        if group_num:
            for id in group_list[group_num]:
                async with AsyncClient() as client:
                    try:
                        url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + steam_web_key + "&steamids=" + id
                        res = await client.get(url,headers=header,timeout=30)
                        res_info = json.loads(res.text)["response"]["players"][0]
                        gama_info = []
                        bot = get_bot()
                        if "gameextrainfo" in res_info and group_list[group_num][id][1] == "":
                            #如果发现开始玩了而之前未玩
                            timestamp = int(time.time()/60)
                            gama_info.append(timestamp)
                            gama_info.append(res_info["gameextrainfo"])
                            group_list[group_num][id] = gama_info
                            await bot.send_group_msg(group_id=int(group_num),message=Message(f"{res_info['personaname']} 开始玩 {res_info['gameextrainfo']} 。"))
                            f = open(dirpath.__str__(),"w")
                            f.write(json.dumps(group_list))
                            f.close()
                            pass
                        elif "gameextrainfo" in res_info and group_list[group_num][id][1] != "":
                            #如果发现开始玩了而之前也在玩
                            pass
                        elif "gameextrainfo" not in res_info and group_list[group_num][id][1] != "":
                            # 之前有玩，现在没玩
                            timestamp = int(time.time()/60)
                            gama_info.append(timestamp)
                            gama_info.append("")
                            game_time = timestamp - group_list[group_num][id][0]
                            await bot.send_group_msg(group_id=int(group_num),message=Message(f"{res_info['personaname']} 玩了 {game_time} 分钟 {group_list[group_num][id][1]} 后不玩了。"))
                            group_list[group_num][id] = gama_info
                            f = open(dirpath.__str__(),"w")
                            f.write(json.dumps(group_list))
                            f.close() 
                            pass
                        elif "gameextrainfo" not in res_info and group_list[group_num][id][1] == "":
                            # 一直没玩
                            pass
                    except:
                        return None
                    
                    
steam_bind = on_command("steam绑定",aliases={"steam.add","steam添加"},priority=5)
@steam_bind.handle()
async def steam_bind_handle(bot: Bot,event: MessageEvent,matcher: Matcher,arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        f = open(dirpath.__str__(),"r+")
        group_list = f.read()
        f.close()
        group_list = json.loads(group_list)
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {}
        group_list[str(event.group_id)][arg.extract_plain_text()] = [0,""]
        f = open(dirpath.__str__(),"w")
        f.write(json.dumps(group_list))
        f.close()
        await steam_bind.finish(arg + " 绑定成功")
                            
steam_del = on_command("steam删除",aliases={"steam.del","steam解绑"},priority=5)
@steam_del.handle()
async def steam_del_handle(bot: Bot,event: MessageEvent,matcher: Matcher,arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        f = open(dirpath.__str__(),"r+")
        group_list = f.read()
        f.close()
        group_list = json.loads(group_list)
        group_list[str(event.group_id)].pop(arg.extract_plain_text()) 
        f = open(dirpath.__str__(),"w")
        f.write(json.dumps(group_list))
        f.close()
        await steam_bind.finish(arg + " 删除成功")