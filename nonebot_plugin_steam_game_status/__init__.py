import random
from nonebot import require,get_driver,on_command
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN,GROUP_OWNER
from nonebot.adapters.onebot.v11 import Message,MessageEvent,Bot,GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot.exception import MatcherException
from nonebot.plugin import PluginMetadata
from nonebot_plugin_sendmsg_by_bots import tools
from pathlib import Path
import json
import time
from httpx import AsyncClient
import asyncio
from .config import Config,__version__

config_dev = Config.parse_obj(get_driver().config)
bot_name = list(get_driver().config.nickname)
if not config_dev.steam_web_key:
    logger.warning("steam_web_key未配置")

__plugin_meta__ = PluginMetadata(
    name="Steam游戏状态",
    description="播报群友的Steam游戏状态",
    usage="""首先获取自己的Steam ID，
        获取方法：
            获取SteamID64
                Steam 桌面网站或桌面客户端：点开右上角昵称下拉菜单，点击账户明细，即可看到 Steam ID
                Steam 应用：点击右上角头像，点击账户明细，即可看到 Steam ID
            获取Steam好友代码
                Steam 桌面网站或桌面客户端：点开导航栏 好友 选项卡，点击添加好友，即可看到 Steam 好友代码
                Steam 应用：点击右上角头像，点击好友，点击添加好友，即可看到 Steam 好友代码
        (如果有命令前缀，需要加上，一般为 / )    
        
        绑定方法：
            steam绑定/steam添加/steam.add [个人ID数值] 
            
        删除方法：
            steam解绑/steam删除/steam.del [个人ID数值] 
            
        管理员命令：
            steam列表/steam绑定列表 	    
            steam播报开启/steam播报打开  
            steam播报关闭/steam播报停止 	
    """,
    type="application",
    config=Config,
    homepage="https://github.com/nek0us/nonebot_plugin_steam_game_status",
    supported_adapters={"~onebot.v11"},
    extra={
        "author":"nek0us",
        "version":__version__,
        "priority":config_dev.steam_command_priority
    }
)

dirpath = Path() / "data" / "steam_group"
dirpath.mkdir(parents=True, exist_ok=True)
dirpath = Path() / "data" / "steam_group" / "group_list.json"
dirpath.touch()
if not dirpath.stat().st_size:
    dirpath.write_text("{}")

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
driver = get_driver()
status = True

@driver.on_startup
async def _():
    # 当bot启动时，忽略所有未播报的游戏
    with dirpath.open('r') as file:
        data = json.load(file)

    for group in data.values():
        for _, user_info in group.items():
            if isinstance(user_info, list) and user_info[0] != 0:
                user_info[0] = -1  # -1 为特殊时间用来判断是否重启

    with dirpath.open('w') as file:
        json.dump(data, file)

async def get_status(group_list, group_num,id):
    async with AsyncClient(verify=False,proxies=config_dev.steam_proxy) as client:
        try:
            url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + id
            res = await client.get(url,headers=header,timeout=30)
            res_info = json.loads(res.text)["response"]["players"][0]
            user_info = []
            if "gameextrainfo" in res_info and group_list[group_num][id][1] == "":
                # 如果发现开始玩了而之前未玩
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                user_info.append(res_info["gameextrainfo"])
                user_info.append(res_info['personaname'])
                group_list[group_num][id] = user_info
                await tools.send_group_msg_by_bots(group_id=int(group_num),msg=Message(f"{res_info['personaname']} 开始玩 {res_info['gameextrainfo']} 了。"))
                dirpath.write_text(json.dumps(group_list))
            elif "gameextrainfo" in res_info and group_list[group_num][id][0] != -1 and group_list[group_num][id][1] != "":
                # 如果发现开始玩了而之前也在玩(bot一直在线)
                if res_info["gameextrainfo"] != group_list[group_num][id][1]:
                    # 如果发现玩的是新游戏
                    timestamp = int(time.time()/60)
                    user_info.append(timestamp)
                    user_info.append(res_info["gameextrainfo"])
                    user_info.append(res_info['personaname'])
                    group_list[group_num][id] = user_info
                    await tools.send_group_msg_by_bots(group_id=int(group_num),msg=Message(f"{res_info['personaname']} 又开始玩 {res_info['gameextrainfo']} 了。"))
                    dirpath.write_text(json.dumps(group_list))
            elif "gameextrainfo" not in res_info and group_list[group_num][id][1] != "":
                # 之前有玩，现在没玩
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                user_info.append("")
                user_info.append(res_info['personaname'])
                game_time = timestamp - group_list[group_num][id][0]
                # 判断是否是重启后的结束游戏
                if group_list[group_num][id][0] == -1:
                    await tools.send_group_msg_by_bots(group_id=int(group_num),msg=Message(f"{res_info['personaname']} 不再玩 {group_list[group_num][id][1]} 了。但{random.choice(bot_name)}忘了，不记得玩了多久了。"))
                else:
                    await tools.send_group_msg_by_bots(group_id=int(group_num),msg=Message(f"{res_info['personaname']} 玩了 {game_time} 分钟 {group_list[group_num][id][1]} 后不玩了。"))
                group_list[group_num][id] = user_info
                dirpath.write_text(json.dumps(group_list))
                
            elif  "gameextrainfo" in res_info and group_list[group_num][id][0] == -1 and group_list[group_num][id][1] != "":
                # 之前有在玩 A，但bot重启了，现在在玩 B
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                user_info.append(res_info["gameextrainfo"])
                user_info.append(res_info['personaname'])
                group_list[group_num][id] = user_info
                await tools.send_group_msg_by_bots(group_id=int(group_num),msg=Message(f"{res_info['personaname']} 开始玩 {res_info['gameextrainfo']} 了。"))
                dirpath.write_text(json.dumps(group_list))
                
            elif "gameextrainfo" not in res_info and group_list[group_num][id][1] == "":
                # 一直没玩
                pass
        except Exception as e:
            logger.debug(f"steam id:{id} 查询状态失败，{e}")


@scheduler.scheduled_job("interval", minutes=1, id="steam", misfire_grace_time=59)
async def now_steam():
    if config_dev.steam_web_key:
        task_list = []
        group_list = json.loads(dirpath.read_text("utf8"))
        for group_num in group_list:
            if group_num and group_list[group_num]["status"] == "on":
                for id in group_list[group_num]:
                    if id != "status":
                        task_list.append(get_status(group_list,group_num,id))
        asyncio.gather(*task_list)

         
steam_bind = on_command("steam绑定", aliases={"steam.add", "steam添加"}, priority=config_dev.steam_command_priority)
@steam_bind.handle()
async def steam_bind_handle(event: MessageEvent, matcher: Matcher, arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        if not config_dev.steam_web_key:
            await matcher.finish("steam_web_key 未配置") 
        steam_id = arg.extract_plain_text()
        if len(steam_id) != 17:
            try:
                steam_id = int(steam_id)
                steam_id += 76561197960265728
                steam_id = str(steam_id)
            except:
                await matcher.finish("steam id格式错误")
        steam_name: str = ""
        try:
            async with AsyncClient(verify=False,proxies=config_dev.steam_proxy) as client:
                url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
                res = await client.get(url,headers=header,timeout=30)
            if res.status_code != 200:
                logger.debug(f"{arg.extract_plain_text()} 绑定失败，{res.status_code} {res.text}")
                await matcher.finish(f"{arg.extract_plain_text()} 绑定失败，{res.status_code} {res.text}") 
            if json.loads(res.text)["response"]["players"] == []:
                logger.debug(f"{arg.extract_plain_text()} 绑定失败，查无此人，请检查输入的id")
                await matcher.finish(f"{arg.extract_plain_text()} 绑定失败，查无此人，请检查输入的id") 
            steam_name = json.loads(res.text)["response"]["players"][0]['personaname']
        except MatcherException:
            raise
        except Exception as e:
            logger.debug(f"{arg.extract_plain_text()} 绑定失败，{e}")
            await matcher.finish(f"{arg.extract_plain_text()} 绑定失败，{e}")
        
        group_list = json.loads(dirpath.read_text("utf8"))
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {"status":"on"}
        group_list[str(event.group_id)][steam_id] = [0,"",steam_name]
        dirpath.write_text(json.dumps(group_list))
        await matcher.finish(f"Steam ID：{arg.extract_plain_text()}\nsteamID64：{steam_id}\nSteam Name：{steam_name}\n 绑定成功了")

                    
steam_del = on_command("steam删除", aliases={"steam.del","steam解绑"}, priority=config_dev.steam_command_priority)
@steam_del.handle()
async def steam_del_handle(event: MessageEvent, arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        if len(arg.extract_plain_text()) != 17:
            await steam_del.finish("steam id格式错误") 
        steam_name: str = ""
        group_list = json.loads(dirpath.read_text("utf8"))
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {}
        try:
            steam_name = group_list[str(event.group_id)][arg.extract_plain_text()][2]
            group_list[str(event.group_id)].pop(arg.extract_plain_text()) 
        except:
            await steam_del.finish(f"没有找到Steam ID：{arg.extract_plain_text()}")
        dirpath.write_text(json.dumps(group_list))
        await steam_del.finish(f"Steam ID：{arg.extract_plain_text()}\nSteam Name：{steam_name}\n 删除成功了")    


steam_bind_list = on_command("steam列表", aliases={"steam绑定列表","steam播报列表"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_bind_list.handle()
async def steam_bind_list_handle(bot: Bot, event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        try:
            id_list = json.loads(dirpath.read_text("utf8"))[str(event.group_id)]
            msg = []
            for id in id_list:
                if "status" not in id:
                    msg += await node_msg(event.user_id,f"id：{id}\nname：{id_list[id][2]}")
                    
            await bot.send_group_forward_msg(group_id=event.group_id,messages=msg)
        except:
            await steam_bind_list.finish(f"本群尚未绑定任何steam ID，请先绑定。")


steam_on = on_command("steam播报开启", aliases={"steam播报打开"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_on.handle()
async def steam_on_handle(event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        group_list = json.loads(dirpath.read_text("utf8"))
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {}
        group_list[str(event.group_id)]["status"] = "on"
        f = open(dirpath.__str__(),"w")
        f.write(json.dumps(group_list))
        f.close()
        await steam_on.finish("steam播报已开启")


steam_off = on_command("steam播报关闭", aliases={"steam播报停止"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_off.handle()
async def steam_off_handle(event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        f = open(dirpath.__str__(),"r+")
        group_list = f.read()
        f.close()
        group_list = json.loads(group_list)
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {}
        group_list[str(event.group_id)]["status"] = "off"
        dirpath.write_text(json.dumps(group_list))
        await steam_off.finish("steam播报已关闭")


async def node_msg(user_id, plain_text):
    if not plain_text:
        plain_text = "无"
    node = [
	{
		"type": "node",
		"data": {
			"name": "steam user info",
			"uin": int(user_id),
			"content": [
				{
					"type": "text",
					"data": {
						"text": plain_text
					}
				}
			]
		}
	}
]
    return node


def get_steam_key() -> str:
    try:
        key = eval(config_dev.steam_web_key)
        return random.choice(key)
    except SyntaxError as SE:
        key = config_dev.steam_web_key
        return key
    except TypeError as TE:
        return random.choice(config_dev.steam_web_key)
    except Exception as e:
        logger.warning(f"get steam web key error.{e}")
        return f"get steam web key error.{e}"