import sys
import json
import time
import random
import asyncio

from typing import Dict, List, Optional, Literal
from nonebot import require
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.internal.driver import Request
from nonebot.exception import MatcherException
from nonebot.plugin import inherit_supported_adapters

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Arparma, on_alconna, Match
from nonebot_plugin_alconna.uniseg import UniMessage,CustomNode,Reference,Target,MsgTarget

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


from arclet.alconna import Alconna, Option, Args, CommandMeta, AllParam

from .utils import http_client, get_target, driver, HTTPClientSession, to_enum
from .model import UserData, GroupData3, SafeResponse
from .config import Config,__version__, config_steam, bot_name
from .api import (
    gameid_to_name, 
    steam_link_rule,
    get_game_info,
    get_steam_key,
    save_data,
    no_private_rule,
    get_game_data_msg,
    make_game_data_node_msg,
    send_node_msg,
    get_free_games_info,
    get_group_target_bot,
    )
from .source import (
    new_file_group,
    new_file_steam,
    exclude_game_file,
    exclude_game_default,
    steam_list,
    group_list,
    exclude_game,
    inactive_groups_file
    )






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
            
        命令：
            steam列表/steam绑定列表 	   
            steam屏蔽 [游戏名]
            steam恢复 [游戏名]
            steam排除列表
            steam播报开启/steam播报打开  
            steam播报关闭/steam播报停止 
            steam喜加一
            steam喜加一订阅
            steam喜加一退订
            
        链接识别：
            从商店复制链接
    """,
    type="application",
    config=Config,
    homepage="https://github.com/nek0us/nonebot_plugin_steam_game_status",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "author":"nek0us",
        "version":__version__,
        "priority":config_steam.steam_command_priority
    }
)

steam_link_re_alc = Alconna(
    "steam_open",
    Args["appid", int],
    meta=CommandMeta(compact=True,strict=False)
)
steam_link_re_alc.shortcut(
    r".*https?://store\.steampowered\.com/app/(\d+).*", 
    {"args": ["{0}"], "prefix": False}
)
steam_link_re = on_alconna(
    steam_link_re_alc,
    rule=steam_link_rule,
    block=False,
    priority=config_steam.steam_command_priority
)
@steam_link_re.handle()
async def steam_link_handle(target: MsgTarget,matcher: Matcher, appid: Match[str]):
    app_id = str(appid.result)
    try:
        res_json = await get_game_info(app_id)
        if 'error' in res_json:
            logger.warning(f"steam链接识别失败，异常为：{res_json['error']}")
            await matcher.finish("steam链接失败，请检查日志输出")
        if not res_json['success']:
            logger.info(f"steam链接游戏信息获取失败，疑似appid错误：{app_id}")
            await matcher.finish("没有找到这个游戏",reply_message=True)
        id = str(target.id)
        if res_json["from"] != "cn":
            if isinstance(config_steam.steam_area_game, bool):
                if not config_steam.steam_area_game:
                    await matcher.finish("没有找到这个游戏",reply_message=True)
            else:
                if id not in config_steam.steam_area_game:
                    await matcher.finish("没有找到这个游戏",reply_message=True)
        game_data = res_json['data']
        if "ratings" in game_data:
            if "steam_germany" in game_data["ratings"]:
                if game_data["ratings"]["steam_germany"]['rating'] == "BANNED":
                    if isinstance(config_steam.steam_link_r18_game, bool):
                        if not config_steam.steam_link_r18_game:
                            logger.info(f"steam appid:{app_id} 根据r18设置被过滤")
                            await matcher.finish("这个禁止！",reply_message=True)
                    else:
                        if id not in config_steam.steam_link_r18_game:
                            logger.info(f"steam appid:{app_id} 根据r18设置被过滤，{id} 不在白名单内")
                            await matcher.finish("这个禁止！",reply_message=True)
        forward_name, msgs = await get_game_data_msg(res_json)
        messages = await make_game_data_node_msg(target, forward_name, msgs)
        await send_node_msg(messages, app_id)
        logger.debug(f"steam app_id: {app_id} 解析完成")
    except Exception as e:
        logger.warning(f"steam app_id: {app_id} 解析失败：{e}")
        await matcher.send(f"steam app_id：{app_id} 解析失败 {config_steam.steam_tail_tone}")


@driver.on_startup
async def _():
    # 当bot启动时，忽略所有未播报的游戏
    for steam_id in steam_list:
        if steam_list[steam_id] and steam_list[steam_id]["time"]!= 0:
            steam_list[steam_id]["time"]= -1  # -1 为特殊时间用来判断是否重启

        # 修复用户id异常
        if isinstance(steam_list[steam_id],list) and steam_list[steam_id] == [-1]:
            steam_name: str = ""
            try:
                async with http_client() as client:
                    url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
                    res = SafeResponse(await client.request(Request("GET", url, timeout=30)))
                    if res.status_code != 200:
                        logger.warning(f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 http状态码不为200: {res.status_code}")
                        continue
                    if json.loads(res.text)["response"]["players"] == []:
                        logger.warning(f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 获取到的用户信息为空")
                        continue
                    steam_name = json.loads(res.text)["response"]["players"][0]['personaname']
            except Exception as e:
                logger.warning(f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 : {e}")
                continue
            steam_list[steam_id] = UserData(time=0,game_name="",nickname=steam_name)
            logger.debug(f"Steam id: {steam_id},name: {steam_name} 异常，修复成功")

async def get_status(client: HTTPClientSession, steam_id_to_groups: Dict[str, List[str]], steam_list: Dict[str, UserData], steam_id: str):
    global exclude_game
    user_info = []
    res = None
    try:
        # async with http_client() as client:
        url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
        
        res = SafeResponse(await client.request(Request("GET", url, timeout=30)))
        if res.status_code == 200:
            
            res_info = json.loads(res.text)["response"]["players"][0]
            
            if "gameextrainfo" in res_info and steam_list[steam_id]["game_name"] == "":
                # 如果发现开始玩了而之前未玩
                timestamp = int(time.time()/60)
                game_name = await gameid_to_name(res_info["gameid"],res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                
                for group_id in steam_id_to_groups[steam_id]:
                    if game_name in exclude_game[str(group_id)]:
                        logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 正在玩的游戏 {game_name}")
                        continue
                    target = await get_group_target_bot(group_id)
                    if target:
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的游戏 {game_name}。使用适配器 {target.adapter}，Bot id {target.self_id}")
                        await UniMessage(f"{res_info['personaname']} 开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target)
                    else:
                        # bot 不在群内，记录无效群
                        if group_id not in inactive_groups:
                            logger.info(f"Group {group_id} added to inactive_groups (no bot available) for steam_id {steam_id}, game {game_name}")
                            inactive_groups.append(group_id)
                            inactive_groups_file.write_text(json.dumps(inactive_groups))

            elif "gameextrainfo" in res_info and steam_list[steam_id]["time"]!= -1 and steam_list[steam_id]["game_name"] != "":
                # 如果发现开始玩了而之前也在玩(bot一直在线)
                game_name = await gameid_to_name(res_info["gameid"],res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                if game_name != steam_list[steam_id]["game_name"]:
                    # 如果发现玩的是新游戏
                    game_name_old = steam_list[steam_id]["game_name"]
                    timestamp = int(time.time()/60)
                    user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                    for group_id in steam_id_to_groups[steam_id]:
                        if game_name in exclude_game[str(group_id)] or game_name_old in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 正在玩的新游戏 {game_name},旧游戏 {game_name_old}")
                            continue
                        target = await get_group_target_bot(group_id)
                        if target:
                            logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的新游戏 {game_name}。使用适配器{target.adapter}，Bot id {target.self_id}")
                            await UniMessage(f"{res_info['personaname']} 又开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target)
                        else:
                            if group_id not in inactive_groups:
                                logger.info(f"Group {group_id} added to inactive_groups (no bot available) for steam_id {steam_id}, game {game_name}")
                                inactive_groups.append(group_id)
                                inactive_groups_file.write_text(json.dumps(inactive_groups))

            elif "gameextrainfo" not in res_info and steam_list[steam_id]["game_name"] != "":
                # 之前有玩，现在没玩
                timestamp = int(time.time()/60)
                game_name_old = steam_list[steam_id]["game_name"]
                game_time_old = steam_list[steam_id]["time"]
                user_info = UserData(time=timestamp, game_name="", nickname=res_info['personaname'])
                game_time = timestamp - game_time_old 
                # 判断是否是重启后的结束游戏
                for group_id in steam_id_to_groups[steam_id]:
                    if game_name_old in exclude_game[str(group_id)]:
                        logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 重启之前停止的游戏： {game_name_old}")
                        continue
                    target = await get_group_target_bot(group_id)
                    if target:
                        if game_time_old == -1:
                            logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之前停止的游戏： {game_name_old}。使用适配器{target.adapter}，Bot id {target.self_id}")
                            await UniMessage(f"{res_info['personaname']} 不再玩 {game_name_old} 。但{random.choice(bot_name)}忘了，不记得玩了多久了{config_steam.steam_tail_tone}。").send(target=target)
                        else:
                            logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 停止的游戏： {game_name_old}。使用适配器{target.adapter}，Bot id {target.self_id}")
                            await UniMessage(f"{res_info['personaname']} 玩了 {game_time} 分钟 {game_name_old} 后不玩了{config_steam.steam_tail_tone}。").send(target=target)
                    else:
                        if group_id not in inactive_groups:
                            logger.info(f"Group {group_id} added to inactive_groups (no bot available) for steam_id {steam_id}, game {game_name}")
                            inactive_groups.append(group_id)
                            inactive_groups_file.write_text(json.dumps(inactive_groups))
                    
            elif  "gameextrainfo" in res_info and steam_list[steam_id]["time"]== -1 and steam_list[steam_id]["game_name"] != "":
                # 之前有在玩 A，但bot重启了，现在在玩 B
                game_name = await gameid_to_name(res_info["gameid"],res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                game_name_old = steam_list[steam_id]["game_name"]
                if game_name != game_name_old:
                    # 还是原来的游戏，就不播了，所以这里只播变了的
                    logger.trace(f"用户 {steam_id} 重启后开始玩新游戏 {game_name}，之前的游戏是 {game_name_old}，所以播报")
                    timestamp = int(time.time()/60)
                    user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                    for group_id in steam_id_to_groups[steam_id]:
                        if game_name in exclude_game[str(group_id)] or game_name_old in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 因游戏名单跳过发送 steam id {steam_id},name {res_info['personaname']} 重启之后的游戏： {game_name},重启之前的游戏 {game_name_old}")
                            continue
                        target = await get_group_target_bot(group_id)
                        if target:
                            logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之后的游戏： {game_name}。使用适配器{target.adapter}，Bot id {target.self_id}")
                            await UniMessage(f"{res_info['personaname']} 又开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target)
                        else:
                            # bot 不在群内，记录无效群
                            if group_id not in inactive_groups:
                                logger.info(f"Group {group_id} added to inactive_groups (no bot available) for steam_id {steam_id}, game {game_name}")
                                inactive_groups.append(group_id)
                                inactive_groups_file.write_text(json.dumps(inactive_groups))
                else:
                    logger.trace(f"用户 {steam_id} 重启后还在玩 {game_name_old}，所以跳过播报")    
                    
            elif "gameextrainfo" not in res_info and steam_list[steam_id]["game_name"] == "":
                # 一直没玩
                pass
        else:
            logger.debug(f"steam id:{steam_id} 查询状态不是200，{res.status_code} \n{res.text}")
    except Exception as e:
        a, b, exc_traceback = sys.exc_info()
        logger.debug(f"steam id:{steam_id} 查询状态失败,line: {exc_traceback.tb_lineno if exc_traceback else ''}，{e} \n{res.text if res else None}")
    finally:
        if not isinstance(user_info, List):
            steam_list[steam_id] = user_info


@scheduler.scheduled_job("interval", minutes=config_steam.steam_interval, id="steam", misfire_grace_time=(config_steam.steam_interval*60-1))
async def now_steam():
    if config_steam.steam_web_key:
        global steam_list
        logger.debug("steam准备开始生成查询字典")
        task_list = []
        # 初始化最终的反向字典
        steam_id_to_groups: Dict[str, List[str]] = {}
        # 遍历group_list中的每个group_id及其数据
        for group_id, group_data in group_list.items():
            if group_data['status']:  # 只处理status为true的group
                user_list: List[str] = group_data['user_list']
                for steam_id in user_list:
                    if steam_id not in steam_id_to_groups:
                        steam_id_to_groups[steam_id] = []
                    steam_id_to_groups[steam_id].append(group_id)
        logger.debug("steam生成查询字典完成，准备添加任务")
        async with http_client() as client:
            for steam_id in steam_id_to_groups:
                task_list.append(get_status(client, steam_id_to_groups, steam_list, steam_id))
            try:
                logger.debug("steam添加任务完成，准备运行并等待任务")
                await asyncio.wait_for(asyncio.gather(*task_list), timeout=(config_steam.steam_interval*60-20))
                logger.debug("steam自动查询任务完成")
            except Exception as e:
                logger.debug(f"steam新异常:{e}")
            finally:
                new_file_steam.write_text(json.dumps(steam_list))
                logger.debug("steam finally保存完成")
steam_command_alc = Alconna(
    "steam",
    # Subcommand("add", Args["steam_id", str], alias=["绑定", "添加", ".add"],separators=""),
    Option("add", Args["id", str], alias=["绑定", "添加", ".add"],separators="",compact=True),
    Option("del", Args["id", str], alias=["解绑", "删除", ".del"],separators="",compact=True),
    Option("屏蔽", Args["game", AllParam(str)],separators="",compact=True),
    Option("恢复", Args["game", AllParam(str)],separators="",compact=True),
    Option("排除列表",separators="",compact=True),
    Option("list", alias=["列表", "绑定列表", "播报列表"],separators="",compact=True),
    Option("播报", Args["status", str],separators="",compact=True),
    Option("喜加一", Args["action", Optional[Literal["订阅", "退订"]]], separators="", compact=True),

    separators="",
    meta=CommandMeta(compact=True)
)
steam_cmd = on_alconna(steam_command_alc, priority=config_steam.steam_command_priority, rule=no_private_rule)        
@steam_cmd.assign("add")
async def steam_bind_handle(target: MsgTarget,matcher: Matcher, id: Match[str]):
    steam_id = id.result
    if len(steam_id) != 17:
        try:
            steam_id = int(steam_id)
            steam_id += 76561197960265728
            steam_id = str(steam_id)
        except Exception as e:
            logger.debug(f"Steam 绑定出错，输入值：{steam_id}，错误：{e}")
            await matcher.finish(f"Steam ID格式错误{config_steam.steam_tail_tone}")
    global steam_list,group_list,exclude_game
    if str(target.id) not in group_list:
        # 本群还没记录
        group_list[str(target.id)] = GroupData3(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else "",
            xijiayi= False,
            )
        exclude_game[str(target.id)] = exclude_game_default
        
    
    if steam_id in group_list[str(target.id)]["user_list"]:
        await matcher.finish(f"已经绑定过了{config_steam.steam_tail_tone}")
    steam_name: str = ""
    if steam_id in steam_list:
        steam_name = steam_list[steam_id]["nickname"]
    else:
        try:
            async with http_client() as client:
                url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
                res = SafeResponse(await client.request(Request("GET", url, timeout=30)))
            if res.status_code != 200:
                logger.debug(f"{steam_id} 绑定失败，{res.status_code} {res.text}")
                await matcher.finish(f"{steam_id} 绑定失败，{res.status_code} {res.text}") 
            if json.loads(res.text)["response"]["players"] == []:
                logger.debug(f"{steam_id} 绑定失败，查无此人，请检查输入的id")
                await matcher.finish(f"{steam_id} 绑定失败，查无此人，请检查输入的id{config_steam.steam_tail_tone}") 
            steam_name = json.loads(res.text)["response"]["players"][0]['personaname']
        except MatcherException:
            raise
        except Exception as e:
            logger.debug(f"{steam_id} 绑定失败，{e}")
            await matcher.finish(f"{steam_id} 绑定失败{config_steam.steam_tail_tone}，{e}")
        steam_list[steam_id] = UserData(time=0,game_name="",nickname=steam_name)
        
    group_list[str(target.id)]["user_list"].append(steam_id)
    save_data()
    await matcher.finish(f"Steam ID：{steam_id}\nSteam ID64：{steam_id}\nSteam Name：{steam_name}\n 绑定成功了{config_steam.steam_tail_tone}")

                    
@steam_cmd.assign("del")
async def steam_del_handle(target: MsgTarget,matcher: Matcher, id: Match[str]):
    steam_id = id.result
    if len(steam_id) != 17:
        try:
            steam_id = int(steam_id)
            steam_id += 76561197960265728
            steam_id = str(steam_id)
        except Exception as e:
            logger.debug(f"Steam 绑定出错，输入值：{steam_id}，错误：{e}")
            await matcher.finish(f"Steam ID格式错误{config_steam.steam_tail_tone}")
    steam_name: str = ""
    global group_list
    
    if str(target.id) not in group_list:
        # 本群还没记录
        group_list[str(target.id)] = GroupData3(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else "",
            xijiayi= False,
            )
        await matcher.finish(f"本群不存在 Steam 绑定记录{config_steam.steam_tail_tone}")
    
    if steam_id not in group_list[str(target.id)]["user_list"]:
        await matcher.finish(f"本群尚未绑定该 Steam ID{config_steam.steam_tail_tone}")
    steam_name = steam_list[steam_id]["nickname"]
    
    try:
        group_list[str(target.id)]["user_list"].remove(steam_id) 
    except Exception as e:
        logger.debug(f"删除steam id 失败，输入值：{steam_id}，错误：{e}")
        await matcher.finish(f"没有找到 Steam ID：{steam_id}{config_steam.steam_tail_tone}")
    save_data()
    await matcher.finish(f"Steam ID：{steam_id}\nSteam Name：{steam_name}\n 删除成功了{config_steam.steam_tail_tone}")    

steam_cmd_scr = steam_cmd.dispatch("屏蔽")
steam_cmd_rec = steam_cmd.dispatch("恢复")

@steam_cmd_scr.handle()
@steam_cmd_rec.handle()
async def steam_clude_handle(target: MsgTarget,arp: Arparma,matcher: Matcher, game: Match[str]):
    global group_list,exclude_game
    handle = next(iter(arp.components))
    game_name = game.result
    if str(target.id) not in group_list:
        # 本群还没记录
        group_list[str(target.id)] = GroupData3(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else "",
            xijiayi= False,
            )
        exclude_game[str(target.id)] = exclude_game_default
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    if game_name == "":
        await matcher.finish(f"请输入要{handle}的完整游戏名称{config_steam.steam_tail_tone}")
    elif handle == "屏蔽":
        if game_name in exclude_game[str(target.id)]:
            await matcher.finish(f"{game_name} 已经被屏蔽过了{config_steam.steam_tail_tone}")
        exclude_game[str(target.id)].append(game_name)
    elif handle == "恢复":
        if game_name not in exclude_game[str(target.id)]:
            await matcher.finish(f"{game_name} 没有被屏蔽过{config_steam.steam_tail_tone}")
        exclude_game[str(target.id)].remove(game_name)
    exclude_game_file.write_text(json.dumps(exclude_game))
    await matcher.finish(f"{handle}游戏 {game_name} 完成{config_steam.steam_tail_tone}")
    
    
@steam_cmd.assign("排除列表")
async def steam_exclude_list_handle(target: MsgTarget):
    global group_list,exclude_game
    if str(target.id) not in group_list:
        # 本群还没记录
        group_list[str(target.id)] = GroupData3(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else "",
            xijiayi= False,
            )
        exclude_game[str(target.id)] = exclude_game_default
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    
    nodes = [
        CustomNode(
            uid=str(target.self_id),
            name=str(index+1),
            content=UniMessage.text(game_name)
        ) 
        for index,game_name in enumerate(exclude_game[str(target.id)])
        ]
    await UniMessage(Reference(nodes=nodes)).send()
    
@steam_cmd.assign("list")
async def steam_bind_list_handle(target: MsgTarget):
    try:
        nodes = [
            CustomNode(
                uid=str(target.self_id),
                name=str(index+1),
                content= UniMessage.text(f"Steam ID：{steam_id}\n昵称：{steam_list[steam_id]['nickname']}\n{'正在玩：' + steam_list[steam_id]['game_name'] if steam_list[steam_id]['game_name'] != '' else ''}")
                )
            for index,steam_id in enumerate(group_list[str(target.id)]["user_list"]) 
            ]
        await UniMessage(Reference(nodes=nodes)).send()
    except Exception as e:
        logger.debug(f"Steam 列表合并消息发送出错，错误：{e}")
        await UniMessage(f"本群尚未绑定任何 Steam ID，请先绑定{config_steam.steam_tail_tone}。").send()


@steam_cmd.assign("播报")
async def steam_on_handle(target: MsgTarget, status: Match[str]):
    if status.result not in ("开启", "关闭"):
        await UniMessage(f"仅允许设置播报开启或关闭{config_steam.steam_tail_tone}").send(reply_to=True)
    else:
        global group_list
        if str(target.id) not in group_list:
            group_list[str(target.id)] = GroupData3(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else "",
            xijiayi= False,
            )
        group_list[str(target.id)]["status"] = True if status.result == "开启" else False
        save_data()
        await UniMessage(f"Steam 播报已{status.result}{config_steam.steam_tail_tone}").send(reply_to=True)

@steam_cmd.assign("喜加一")
async def steam_free_handle(target: MsgTarget, matcher: Matcher, action: Match[str]):
    if action.result:
        group_list[target.id]["xijiayi"] = True if action.result == "订阅" else False
        save_data()
        await matcher.finish(f"steam 喜加一 已{action.result}{config_steam.steam_tail_tone}")
    res = await get_free_games_info(target)
    if res:
        await matcher.finish(res)

steam_cmd = on_alconna(
    steam_command_alc,
    priority=config_steam.steam_command_priority,
    rule=no_private_rule
)

# 新的超管指令 Alconna
steam_admin_alc = Alconna(
    "steam_admin",
    Option("无效群列表", alias=["list_inactive"], separators="", compact=True),
    Option("清理无效群", alias=["clear_inactive"], separators="", compact=True),
    separators="",
    meta=CommandMeta(compact=True, description="Steam 超管指令，仅限超管使用")
)

# 新的超管指令响应器
steam_admin_cmd = on_alconna(
    steam_admin_alc,
    priority=config_steam.steam_command_priority + 1,  # 优先级略高于普通命令
    permission=SUPERUSER  # 仅限超管
)

@steam_admin_cmd.assign("无效群列表")
async def steam_inactive_groups_handle(target: MsgTarget):
    global inactive_groups
    if not inactive_groups:
        await UniMessage(f"当前没有无效群（无 bot 的群）{config_steam.steam_tail_tone}").send()
    else:
        nodes = [
            CustomNode(
                uid=str(target.self_id),
                name=str(index + 1),
                content=UniMessage.text(f"群号: {group_id}")
            )
            for index, group_id in enumerate(inactive_groups)
        ]
        await UniMessage(Reference(nodes=nodes)).send()
        logger.info(f"Superuser requested inactive groups list: {inactive_groups}")

@steam_admin_cmd.assign("清理无效群")
async def steam_clear_inactive_groups_handle(target: MsgTarget):
    global group_list, exclude_game, inactive_groups
    if not inactive_groups:
        await UniMessage(f"当前没有无效群需要清理{config_steam.steam_tail_tone}").send()
        return
    
    removed_groups = []
    for group_id in inactive_groups[:]:  # 使用副本避免修改时迭代
        send_target = await get_group_target_bot(group_id)
        if send_target:
            logger.info(f"Group {group_id} is active again, removing from inactive_groups")
            inactive_groups.remove(group_id)
            continue
        if group_id in group_list:
            removed_groups.append(group_id)
            del group_list[group_id]
            if group_id in exclude_game:
                del exclude_game[group_id]
    
    inactive_groups.clear()
    inactive_groups_file.write_text(json.dumps(inactive_groups))
    save_data()
    
    if removed_groups:
        nodes = [
            CustomNode(
                uid=str(target.self_id),
                name=str(index + 1),
                content=UniMessage.text(f"已删除群号: {group_id}")
            )
            for index, group_id in enumerate(removed_groups)
        ]
        await UniMessage(Reference(nodes=nodes)).send()
        logger.info(f"Superuser cleared inactive groups: {removed_groups}")
    else:
        await UniMessage(f"无效群已清空，但未找到匹配的群数据{config_steam.steam_tail_tone}").send()
@scheduler.scheduled_job("cron", hour=config_steam.steam_subscribe_time.split(":")[0], minute=config_steam.steam_subscribe_time.split(":")[1])
async def steam_subscribe():
    logger.info("steam定时尝试获取推送喜加一")
    await get_free_games_info()
    logger.info("steam定时尝试获取推送喜加一结束")