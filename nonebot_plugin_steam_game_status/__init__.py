import sys
import json
import time
import random
import asyncio

from typing import Dict, List
from nonebot import require
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.internal.driver import Request
from nonebot.exception import MatcherException
from nonebot.plugin import inherit_supported_adapters

from arclet.alconna import Alconna, Option, Args, CommandMeta, AllParam

from .utils import http_client, get_target, driver, HTTPClientSession, to_enum
from .model import UserData, GroupData2, SafeResponse
from .config import Config,__version__, config_steam, bot_name
from .api import (
    gameid_to_name, 
    steam_link_rule,
    get_game_info,
    generate_image,
    get_steam_key,
    save_data,
    no_private_rule,
    gameid_to_price
    )
from .source import (
    new_file_group,
    new_file_steam,
    exclude_game_file,
    exclude_game_default,
    steam_list,
    group_list,
    exclude_game
    )




require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Arparma, on_alconna, Match,Image
from nonebot_plugin_alconna.uniseg import UniMessage,CustomNode,Reference,Target,MsgTarget

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler


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
            steam屏蔽 xx/steam恢复 xx
            steam排除列表	
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

    forward_name = ["预览","名称","价格","分级","介绍","语言","标签","发售时间","","截图","DLC"]

    png = await generate_image(game_data['detailed_description'], 400)
    screenshots_url = [screenshots["path_full"] for screenshots in game_data["screenshots"]]
    screenshots_img = []
    dlc_img = []
    from random import randint
    random_int = str(randint(100000,9999999))
    async with http_client() as client:
        logger.debug(f"steam app_id:{app_id} 开始获取图片")
        res = await client.request(Request("GET", game_data['header_image']))
        header_image = res.content  + random_int.encode() if isinstance(res.content, bytes) else None
        for url in screenshots_url:
            res = await client.request(Request("GET", url))
            screenshots_img.append(res.content + random_int.encode() if isinstance(res.content, bytes) else None)
        if "dlc" in game_data:
            if game_data["dlc"]:
                logger.debug(f"steam app_id:{app_id} 存在dlc: {game_data['dlc']}")
                for id in game_data["dlc"]:
                    dlc_res_json = await get_game_info(str(id))
                    if dlc_res_json['success'] and "error" not in res_json:
                        res = await client.request(Request("GET", dlc_res_json["data"]["header_image"]))
                        dlc_img.append(res.content  + random_int.encode() if isinstance(res.content, bytes) else None)
    Image()
    price = await gameid_to_price(app_id, game_data, res_json["from"])
    if price["status"]:
        # 暂未推出 或 免费
        price_text = price["status"]
    else:
        price_text = f"现价：{price['now']} {price['currency']}"
        if price["history"]:
            price_text = f"史低：{price['history']} {price['currency']}\n" + price_text
        if price["original"]:
            price_text = f"原价：{price['original']} {price['currency']}\n折扣：{price['percent']}\n" + price_text
    msgs = [
        UniMessage.image(raw = header_image if header_image else b""),
        UniMessage.text(game_data['name']),
        UniMessage.text(price_text),
        UniMessage.text(f"分级：{game_data['ratings']['dejus']['rating']}" if "ratings" in game_data and "dejus" in game_data["ratings"] and "rating" in game_data["ratings"]["dejus"] else "暂无分级"),
        UniMessage.image(raw = png),
        UniMessage.text(game_data["supported_languages"].replace("<strong>","").replace("</strong>","").replace("<br>","") if "supported_languages" in game_data else "支持语言：未知"),
        UniMessage.text("，".join([x["description"] for x in game_data["genres"]]) if "genres" in game_data else "暂无分类描述"),
        UniMessage.text(game_data["release_date"]["date"] if game_data["release_date"]["date"] else "未知发售时间"),
        UniMessage.text((f"{random.choice(bot_name)}也想玩" if game_data['is_free'] else f"要送给{random.choice(bot_name)}吗？") if 'price_overview' in game_data else (f"{random.choice(bot_name)}也想玩" if game_data['is_free'] else f"迫不及待想玩啦，发售时会送给{random.choice(bot_name)}吗？")),
        
        [UniMessage.image(raw=img) for img in screenshots_img],
        [UniMessage.image(raw=img) for img in dlc_img] if dlc_img else UniMessage.text("无DLC"),
        
    ]
    # msgs += msis
    messages = []
    for name,msg in zip(forward_name,msgs):
        if name == "截图" and isinstance(msg, list):
            for x in msg:
                messages.append(CustomNode(uid=str(target.self_id),name="截图",content=x))
        elif name == "DLC":
            for x in msg:
                messages.append(CustomNode(uid=str(target.self_id),name="DLC",content=x))
        else:
            messages.append(CustomNode(uid=str(target.self_id),name=name,content=msg))
    try:
        await UniMessage(Reference(nodes=messages)).send()
    except Exception as e:
        logger.debug(f"steam app_id: {app_id} 消息发送异常 {e}，准备删除DLC后重试")
        try:
            new_msg = [x for x in messages if x.name != "DLC"]
            await UniMessage(Reference(nodes=new_msg)).send()
        except Exception as e:
            logger.debug(f"steam app_id: {app_id} 消息再次发送异常 {e}，准备删除DLC和截图后重试")
            new_new_msg = [x for x in messages if x.name not in ("DLC", "截图")]
            try:
                await UniMessage(Reference(nodes=new_new_msg)).send()
            except Exception as e:
                logger.debug(f"steam app_id: {app_id} 消息再再次发送异常 {e}")
                await UniMessage(f"steam app_id: {app_id} 似乎发不出去...").send(reply_to=True)
    logger.debug(f"steam app_id: {app_id} 解析完成")


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
                    target = get_target(group_id)
                    bot = await target.select()
                    logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的游戏 {game_name}。使用适配器{bot}")
                    await UniMessage(f"{res_info['personaname']} 开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target,bot=bot)

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
                        target = get_target(group_id)
                        bot = await target.select()
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 正在玩的新游戏 {game_name}。使用适配器{bot}")
                        await UniMessage(f"{res_info['personaname']} 又开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target,bot=bot)

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
                    target = get_target(group_id)
                    bot = await target.select()
                    if game_time_old == -1:
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之前停止的游戏： {game_name_old}。使用适配器{bot}")
                        await UniMessage(f"{res_info['personaname']} 不再玩 {game_name_old} 。但{random.choice(bot_name)}忘了，不记得玩了多久了{config_steam.steam_tail_tone}。").send(target=target,bot=bot)
                    else:
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 停止的游戏： {game_name_old}。使用适配器{bot}")
                        await UniMessage(f"{res_info['personaname']} 玩了 {game_time} 分钟 {game_name_old} 后不玩了{config_steam.steam_tail_tone}。").send(target=target,bot=bot)
                    
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
                        target = get_target(group_id)
                        bot = await target.select()
                        logger.trace(f"群 {group_id} 准备发送 steam id {steam_id},name {res_info['personaname']} 重启之后的游戏： {game_name}。使用适配器{bot}")
                        await UniMessage(f"{res_info['personaname']} 又开始玩 {game_name}{config_steam.steam_tail_tone} 。").send(target=target,bot=bot)
                else:
                    logger.trace(f"用户 {steam_id} 重启后还在玩 {game_name_old}，所以跳过播报")    
                    
            elif "gameextrainfo" not in res_info and steam_list[steam_id]["game_name"] == "":
                # 一直没玩
                pass
        else:
            logger.debug(f"steam id:{steam_id} 查询状态失败，{res.status_code} \n{res.text}")
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
        group_list[str(target.id)] = GroupData2(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else ""
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
        group_list[str(target.id)] = GroupData2(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else ""
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
        group_list[str(target.id)] = GroupData2(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else ""
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
        group_list[str(target.id)] = GroupData2(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else ""
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
            group_list[str(target.id)] = GroupData2(
            status = True,
            user_list = [],
            adapter = to_enum(target.adapter).value if target.adapter else ""
            )
        group_list[str(target.id)]["status"] = True if status.result == "开启" else False
        save_data()
        await UniMessage(f"Steam 播报已{status.result}{config_steam.steam_tail_tone}").send(reply_to=True)
