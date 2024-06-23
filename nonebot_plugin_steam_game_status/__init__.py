
import json
import time
import base64
import random
import asyncio
import blackboxprotobuf

from .config import Config,__version__
from .source import new_file_group,new_file_steam,game_cache_file,exclude_game_file,exclude_game_default

from httpx import AsyncClient
from nonebot.log import logger
from nonebot.matcher import Matcher
from collections import OrderedDict
from nonebot import get_plugin_config
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.exception import MatcherException
from nonebot import require,get_driver,on_command
from nonebot_plugin_sendmsg_by_bots import tools
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN,GROUP_OWNER
from nonebot.adapters.onebot.v11 import Message,MessageEvent,Bot,GroupMessageEvent,MessageSegment

config_dev = get_plugin_config(Config)
bot_name = list(get_driver().config.nickname)
if not config_dev.steam_web_key:
    logger.warning("steam_web_key 未配置")
    
group_list = json.loads(new_file_group.read_text("utf8"))  
steam_list = json.loads(new_file_steam.read_text("utf8")) 
gameid2name = json.loads(game_cache_file.read_text("utf8"))
exclude_game = json.loads(exclude_game_file.read_text("utf8"))

__plugin_meta__ = PluginMetadata(
    name="Steam游戏状态",
    description="播报群友的Steam游戏状态",
    usage="""首先获取自己的Steam ID，
        获取方法：
            获取Steam ID 64
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
    for steam_id in steam_list:
        if isinstance(steam_list[steam_id], list) and steam_list[steam_id][0] != 0:
            steam_list[steam_id][0] = -1  # -1 为特殊时间用来判断是否重启
    

async def get_status(steam_id_to_groups,steam_list,steam_id):
    async with AsyncClient(verify=False,proxies=config_dev.steam_proxy) as client:
        try:
            global exclude_game
            url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
            res = await client.get(url,headers=header,timeout=30)
            res_info = json.loads(res.text)["response"]["players"][0]
            user_info = []
            if "gameextrainfo" in res_info and steam_list[steam_id][1] == "":
                # 如果发现开始玩了而之前未玩
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                game_name = await gameid_to_name(res_info["gameid"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                user_info.append(game_name)
                user_info.append(res_info['personaname'])
                steam_list[steam_id] = user_info
                for group_id in steam_id_to_groups[steam_id]:
                    if game_name in exclude_game[str(group_id)]:
                        logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 正在玩的游戏 {game_name}")
                        continue
                    logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的游戏 {game_name}")
                    await tools.send_group_msg_by_bots_once(group_id=int(group_id),msg=Message(f"{res_info['personaname']} 开始玩 {game_name} 。"))
                    
            elif "gameextrainfo" in res_info and steam_list[steam_id][0] != -1 and steam_list[steam_id][1] != "":
                # 如果发现开始玩了而之前也在玩(bot一直在线)
                game_name = await gameid_to_name(res_info["gameid"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                if game_name != steam_list[steam_id][1]:
                    # 如果发现玩的是新游戏
                    game_name_old = steam_list[steam_id][1]
                    timestamp = int(time.time()/60)
                    user_info.append(timestamp)
                    user_info.append(game_name)
                    user_info.append(res_info['personaname'])
                    steam_list[steam_id] = user_info
                    for group_id in steam_id_to_groups[steam_id]:
                        if game_name in exclude_game[str(group_id)] or game_name_old in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 正在玩的新游戏 {game_name},旧游戏 {game_name_old}")
                            continue
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的新游戏 {game_name}")
                        await tools.send_group_msg_by_bots_once(group_id=int(group_id),msg=Message(f"{res_info['personaname']} 又开始玩 {game_name} 。"))
                    
            elif "gameextrainfo" not in res_info and steam_list[steam_id][1] != "":
                # 之前有玩，现在没玩
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                user_info.append("")
                user_info.append(res_info['personaname'])
                game_time = timestamp - steam_list[steam_id][0]
                # 判断是否是重启后的结束游戏
                if steam_list[steam_id][0] == -1:
                    for group_id in steam_id_to_groups[steam_id]:
                        if steam_list[steam_id][1] in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 重启之前停止的游戏： {steam_list[steam_id][1]}")
                            continue
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之前停止的游戏： {steam_list[steam_id][1]}")
                        await tools.send_group_msg_by_bots_once(group_id=int(group_id),msg=Message(f"{res_info['personaname']} 不再玩 {steam_list[steam_id][1]} 了。但{random.choice(bot_name)}忘了，不记得玩了多久了。"))
                else:
                    for group_id in steam_id_to_groups[steam_id]:
                        if steam_list[steam_id][1] in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 停止的游戏： {steam_list[steam_id][1]}")
                            continue
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 停止的游戏： {steam_list[steam_id][1]}")
                        await tools.send_group_msg_by_bots_once(group_id=int(group_id),msg=Message(f"{res_info['personaname']} 玩了 {game_time} 分钟 {steam_list[steam_id][1]} 后不玩了。"))
                steam_list[steam_id] = user_info
                
                
            elif  "gameextrainfo" in res_info and steam_list[steam_id][0] == -1 and steam_list[steam_id][1] != "":
                # 之前有在玩 A，但bot重启了，现在在玩 B
                game_name = await gameid_to_name(res_info["gameid"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                game_name_old = steam_list[steam_id][1]
                timestamp = int(time.time()/60)
                user_info.append(timestamp)
                user_info.append(game_name)
                user_info.append(res_info['personaname'])
                steam_list[steam_id] = user_info
                for group_id in steam_id_to_groups[steam_id]:
                    if game_name in exclude_game[str(group_id)] or game_name_old in exclude_game[str(group_id)]:
                        logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 重启之后的游戏： {game_name},重启之前的游戏 {game_name_old}")
                        continue
                    logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之后的游戏： {game_name}")
                    await tools.send_group_msg_by_bots_once(group_id=int(group_id),msg=Message(f"{res_info['personaname']} 开始玩 {game_name} 。"))
                
                
            elif "gameextrainfo" not in res_info and steam_list[steam_id][1] == "":
                # 一直没玩
                pass
        except Exception as e:
            logger.debug(f"steam id:{steam_id} 查询状态失败，{e}")


@scheduler.scheduled_job("interval", minutes=config_dev.steam_interval, id="steam", misfire_grace_time=(config_dev.steam_interval*60-1))
async def now_steam():
    if config_dev.steam_web_key:
        global steam_list
        task_list = []
        # 初始化最终的反向字典
        steam_id_to_groups = {}
        # 遍历group_list中的每个group_id及其数据
        for group_id, group_data in group_list.items():
            if group_data['status']:  # 只处理status为true的group
                user_list = group_data['user_list']
                for steam_id in user_list:
                    if steam_id not in steam_id_to_groups:
                        steam_id_to_groups[steam_id] = []
                    steam_id_to_groups[steam_id].append(group_id)
            
        for steam_id in steam_id_to_groups:
            task_list.append(get_status(steam_id_to_groups,steam_list,steam_id))
        await asyncio.wait_for(asyncio.gather(*task_list), timeout=50)
        
        new_file_steam.write_text(json.dumps(steam_list))

         
steam_bind = on_command("steam绑定", aliases={"steam.add", "steam添加","Steam绑定","Steam.add","Steam添加"}, priority=config_dev.steam_command_priority)
@steam_bind.handle()
async def steam_bind_handle(event: GroupMessageEvent, matcher: Matcher, arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        if not config_dev.steam_web_key:
            await matcher.finish("steam_web_key 未配置") 
        steam_id = arg.extract_plain_text()
        if len(steam_id) != 17:
            try:
                steam_id = int(steam_id)
                steam_id += 76561197960265728
                steam_id = str(steam_id)
            except Exception as e:
                logger.debug(f"Steam 绑定出错，输入值：{arg.extract_plain_text()}，错误：{e}")
                await matcher.finish("Steam ID格式错误")
        global steam_list,group_list,exclude_game
        if str(event.group_id) not in group_list:
            # 本群还没记录
            group_list[str(event.group_id)] = {"status":True,"user_list":[]}
            exclude_game[str(event.group_id)] = exclude_game_default
            
        
        if steam_id in group_list[str(event.group_id)]["user_list"]:
            await matcher.finish("已经绑定过了")
        steam_name: str = ""
        if steam_id in steam_list:
            steam_name = steam_list[steam_id][2]
        else:
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
            steam_list[steam_id] = [0,"",steam_name]
            
        group_list[str(event.group_id)]["user_list"].append(steam_id)
        
        
        save_data()
        await matcher.finish(f"Steam ID：{arg.extract_plain_text()}\nSteam ID64：{steam_id}\nSteam Name：{steam_name}\n 绑定成功了")

                    
steam_del = on_command("steam删除", aliases={"steam.del","steam解绑","Steam删除","Steam.del","Steam解绑"}, priority=config_dev.steam_command_priority)
@steam_del.handle()
async def steam_del_handle(event: MessageEvent,matcher: Matcher, arg: Message = CommandArg()):
    if isinstance(event,GroupMessageEvent):
        steam_id = arg.extract_plain_text()
        if len(steam_id) != 17:
            try:
                steam_id = int(steam_id)
                steam_id += 76561197960265728
                steam_id = str(steam_id)
            except Exception as e:
                logger.debug(f"Steam 绑定出错，输入值：{arg.extract_plain_text()}，错误：{e}")
                await matcher.finish("Steam ID格式错误")
        steam_name: str = ""
        global group_list
        
        if str(event.group_id) not in group_list:
            # 本群还没记录
            group_list[str(event.group_id)] = {"status":True,"user_list":[]}
            await matcher.finish("本群不存在 Steam 绑定记录")
        
        if steam_id not in group_list[str(event.group_id)]["user_list"]:
            await matcher.finish("本群尚未绑定该 Steam ID")
        steam_name = steam_list[steam_id][2]
        
        try:
            group_list[str(event.group_id)]["user_list"].remove(steam_id) 
        except Exception as e:
            logger.debug(f"删除steam id 失败，输入值：{arg.extract_plain_text()}，错误：{e}")
            await steam_del.finish(f"没有找到 Steam ID：{steam_id}")
        save_data()
        await steam_del.finish(f"Steam ID：{arg.extract_plain_text()}\nSteam Name：{steam_name}\n 删除成功了")    


steam_exclude = on_command("steam屏蔽", priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_exclude.handle()
async def steam_exclude_handle(matcher: Matcher,event: GroupMessageEvent,arg: Message = CommandArg()):
    global group_list,exclude_game
    if str(event.group_id) not in group_list:
        # 本群还没记录
        group_list[str(event.group_id)] = {"status":True,"user_list":[]}
        exclude_game[str(event.group_id)] = exclude_game_default
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    if arg.extract_plain_text == "":
        await matcher.finish("请输入要屏蔽的完整游戏名称")
    elif arg.extract_plain_text() in exclude_game[str(event.group_id)]:
        await matcher.finish(f"{arg.extract_plain_text} 已经被屏蔽过了")
    exclude_game[str(event.group_id)].append(arg.extract_plain_text())
    exclude_game_file.write_text(json.dumps(exclude_game))
    await matcher.finish(f"屏蔽游戏 {arg.extract_plain_text()} 完成")
    
steam_include = on_command("steam恢复", priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_include.handle()
async def steam_include_handle(matcher: Matcher,event: GroupMessageEvent,arg: Message = CommandArg()):
    global group_list,exclude_game
    if str(event.group_id) not in group_list:
        # 本群还没记录
        group_list[str(event.group_id)] = {"status":True,"user_list":[]}
        exclude_game[str(event.group_id)] = exclude_game_default
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    if arg.extract_plain_text == "":
        await matcher.finish("请输入要恢复的完整游戏名称")
    elif arg.extract_plain_text() not in exclude_game[str(event.group_id)]:
        await matcher.finish(f"{arg.extract_plain_text} 没有被屏蔽过")
    exclude_game[str(event.group_id)].remove(arg.extract_plain_text())
    exclude_game_file.write_text(json.dumps(exclude_game))
    await matcher.finish(f"恢复游戏 {arg.extract_plain_text()} 完成")
    
steam_exclude_list = on_command("steam排除列表", priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_exclude_list.handle()
async def steam_exclude_list_handle(event: GroupMessageEvent):
    global group_list,exclude_game
    if str(event.group_id) not in group_list:
        # 本群还没记录
        group_list[str(event.group_id)] = {"status":True,"user_list":[]}
        exclude_game[str(event.group_id)] = exclude_game_default
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    msg = []
    for index,game_name in enumerate(exclude_game[str(event.group_id)]):
        msg += MessageSegment.node_custom(
            user_id=event.user_id,
            nickname=str(index+1),
            content=Message(MessageSegment.text(game_name))
        )
    await tools.send_group_forward_msg_by_bots_once(group_id=event.group_id,node_msg=msg,bot_id=str(event.self_id))
    
steam_bind_list = on_command("steam列表", aliases={"steam绑定列表","steam播报列表","Steam列表","Steam绑定列表","Steam播报列表"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_bind_list.handle()
async def steam_bind_list_handle(bot: Bot, event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        try:
            msg = []
            for index,steam_id in enumerate(group_list[str(event.group_id)]["user_list"]):
                # msg += await node_msg(event.user_id,f"Steam ID：{steam_id}\nName：{steam_list[steam_id][2]}")
                msg += MessageSegment.node_custom(
                    user_id=event.user_id,
                    nickname=str(index+1),
                    content=Message(MessageSegment.text(f"Steam ID：{steam_id}\nName：{steam_list[steam_id][2]}"))
                )
            await bot.send_group_forward_msg(group_id=event.group_id,messages=msg)
        except Exception as e:
            logger.debug(f"Steam 列表合并消息发送出错，错误：{e}")
            await steam_bind_list.finish("本群尚未绑定任何 Steam ID，请先绑定。")


steam_on = on_command("steam播报开启", aliases={"steam播报打开","Steam播报开启","Steam播报打开"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_on.handle()
async def steam_on_handle(event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        global group_list
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {"status":True,"user_list":[]}
        group_list[str(event.group_id)]["status"] = True
        save_data()
        await steam_on.finish("Steam 播报已开启")


steam_off = on_command("steam播报关闭", aliases={"steam播报停止","Steam播报关闭","Steam播报停止"}, priority=config_dev.steam_command_priority, permission=SUPERUSER|GROUP_ADMIN|GROUP_OWNER)
@steam_off.handle()
async def steam_off_handle(event: MessageEvent):
    if isinstance(event,GroupMessageEvent):
        global group_list
        if str(event.group_id) not in group_list:
            group_list[str(event.group_id)] = {"status":False,"user_list":[]}
        group_list[str(event.group_id)]["status"] = False
        save_data()
        await steam_off.finish("Steam 播报已关闭")



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
        key = eval(config_dev.steam_web_key) # type: ignore
        return random.choice(key)
    except SyntaxError as SE:
        key = config_dev.steam_web_key
        return str(key)
    except TypeError as TE:
        return random.choice(config_dev.steam_web_key) # type: ignore
    except Exception as e:
        logger.warning(f"get steam web key error.{e}")
        return f"get steam web key error.{e}"


async def gameid_to_name(gameid: str) -> str:
    '''获取游戏中文名'''
    global gameid2name
    if gameid in gameid2name:
        return gameid2name[gameid]
    async with AsyncClient(verify=False,proxies=config_dev.steam_proxy) as client:
        try:
            typedef = OrderedDict([('1', OrderedDict([('name', ''), ('type', 'message'), ('field_order', ['1']), ('message_typedef', OrderedDict([('1', OrderedDict([('name', ''), ('type', 'int'), ('example_value_ignored', 0)]))]))])), ('2', OrderedDict([('name', ''), ('type', 'message'), ('field_order', ['1', '3', '4']), ('message_typedef', OrderedDict([('1', OrderedDict([('name', ''), ('type', 'string'), ('example_value_ignored', 'schinese')])), ('3', OrderedDict([('name', ''), ('type', 'string'), ('example_value_ignored', 'CN')])), ('4', OrderedDict([('name', ''), ('type', 'int'), ('example_value_ignored', 1)]))]))])), ('3', OrderedDict([('name', ''), ('type', 'message'), ('field_order', ['1', '5']), ('message_typedef', OrderedDict([('1', OrderedDict([('name', ''), ('type', 'int'), ('example_value_ignored', 1)])), ('5', OrderedDict([('name', ''), ('type', 'int'), ('example_value_ignored', 1)]))]))]))])
            jsonstr = '{"1":{"1":' + gameid + '},"2":{"1":"schinese","3":"CN","4":1},"3":{"1":1,"5":1}}'
            input_protobuf_encoded = blackboxprotobuf.protobuf_from_json(jsonstr,typedef) # type: ignore
            input_protobuf_encoded = base64.b64encode(input_protobuf_encoded).decode()
            url = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1?origin=https:%2F%2Fstore.steampowered.com&input_protobuf_encoded=" + input_protobuf_encoded
            res = await client.get(url,headers=header,timeout=30)
            message, typedef = blackboxprotobuf.protobuf_to_json(res.content)
            res_info = json.loads(message)
            name = res_info["1"]["6"]
            if name != "":
                gameid2name[gameid] = name
                gameid2name[name] = gameid
                game_cache_file.write_text(json.dumps(gameid2name))
            return name
        except Exception as e:
            logger.error(f"get game name failed.{e}")
            return ""
        
def save_data():
    global steam_list,group_list
    new_file_group.write_text(json.dumps(group_list)) 
    new_file_steam.write_text(json.dumps(steam_list))  
    