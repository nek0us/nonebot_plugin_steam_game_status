
import json
import random

from nonebot import require
from nonebot.log import logger
from nonebot.adapters import Bot
from nonebot.internal.driver import Request
from nonebot_plugin_alconna import Image
from nonebot_plugin_alconna.uniseg import UniMessage, CustomNode, Reference, MsgTarget, Target

from bs4 import BeautifulSoup, Tag
from typing import Dict, List, Optional, Tuple

from .config import bot_name, get_steam_store_domain
from .model import SafeResponse, ModTarget
from .utils import config_steam, http_client, get_target, playwright_context, HTTPClientSession
from .source import (
    HTML_TEMPLATE,
    gameid2name,
    game_cache_file,
    group_list,
    steam_list,
    new_file_group,
    new_file_steam,
    exclude_game_file,
    exclude_game,
    game_free_cache_file,
    game_free_cache,
    game_discounted_cache,
    game_discounted_cache_file,
    game_discounted_subscribe,
    game_discounted_subscribe_file,
    inactive_groups,
    inactive_groups_file,
    )
require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import html_to_pic  # noqa: E402

async def steam_link_rule() -> bool:
    if config_steam.steam_plugin_enabled and config_steam.steam_link_enabled:
        return True
    return False


async def get_game_info(app_id: str) -> dict:
    error = {'success': False}
    async with http_client() as client:
        for location in ["cn", "hk", "tw", "jp", "us"] if config_steam.steam_area_game else ["cn"]:
            url = f"https://{get_steam_store_domain()}/api/appdetails?appids={app_id}&cc={location}"
            try:
                res = SafeResponse(await client.request(Request("GET", url)))
                if res.status_code == 200 and isinstance(res.content, bytes):
                    res_json: dict = json.loads(res.text)[str(app_id)]
                    if not res_json['success']:
                        logger.debug(f"{location}区域未找到steam游戏应用id: {app_id}")
                        continue
                    else:
                        logger.debug(f"{location}区域找到steam游戏应用id: {app_id}")
                        res_json["from"] = location
                        return res_json
                else:
                    error = {'error':f"{res.status_code}\n{res.headers}\n{res.content}"}
            except Exception as e:
                error = {'error':e}
    return error

async def generate_image(html_content: str, width: int = 500) -> bytes:
    """生成图片
    
    Args:
        html_content (str): HTML内容
        width (int): 内容宽度，默认500px
    
    Returns:
        bytes: 图片二进制数据
    """
    # 格式化模板，插入内容和宽度
    html = HTML_TEMPLATE.format(
        width=width,  # 插入宽度值
        content=html_content  # 插入HTML内容
    )
    
    # 使用html_to_pic生成图片
    return await html_to_pic(
        html=html,
        wait=1000,
        type="jpeg",
        quality=90,
        device_scale_factor=2,
        screenshot_timeout=30_000,
        viewport={"width": width, "height": 100}  # 使用相同的宽度
    )



def get_steam_key() -> str:
    if isinstance(config_steam.steam_web_key, List):
        return random.choice(config_steam.steam_web_key)
    elif isinstance(config_steam.steam_web_key, str):
        return config_steam.steam_web_key
    else:
        return str(config_steam.steam_web_key)


async def gameid_to_name(gameid: str,origin_name: Optional[str] = None) -> str:
    '''获取游戏中文名'''
    global gameid2name
    if gameid in gameid2name:
        return gameid2name[gameid]
    res_json = await get_game_info(gameid)
    if 'error' in res_json:
        logger.debug(f"get game name failed.{res_json['error']}")
        return ""
    if not res_json['success']:
        logger.debug(f"get game name no success.{res_json}")
        return ""
    name = res_json['data']['name']
    if origin_name is None and origin_name != name:
        gameid2name[gameid] = name
        gameid2name[name] = gameid
        game_cache_file.write_text(json.dumps(gameid2name))
    return name

async def gameid_to_price(game_id: str,game_data: Dict,location: str = "CN") -> Dict[str, str]:
    '''获取价格信息
    - status: 推出状态
    - original: 原价
    - now: 现价
    - history: 史低
    - percent: 折扣
    - free: 免费
    - currency: 货币
    '''
    price_data = {
        "status": "",
        "original": "",
        "now": "",
        "history": "",
        "percent": "",
        "free": "",
        "currency": ""
    }
    if game_data['is_free'] and 'price_overview' not in game_data:
        price_data["free"] = price_data["status"] = '免费' 
    elif not game_data['is_free'] and 'price_overview' not in game_data:
        price_data["status"] = random.choice(['即将推出','还没推出','还没发售'])
    else:
        price_data["now"] = game_data['price_overview']['final_formatted']
        price_data["currency"] = game_data['price_overview']["currency"]
        if 'initial_formatted' in game_data['price_overview']:
            price_data["original"] = game_data['price_overview']['initial_formatted']
            price_data["percent"] = f"-{game_data['price_overview']['discount_percent']}%"
        if config_steam.steam_isthereanydeal_key:
            async with http_client() as client:
                uuid = await gameid_to_uuid(game_id, client)
                history_price = await get_history_price(uuid,client)
                if history_price:
                    price_data["history"] = history_price

    return price_data

def get_isthereanydeal_key() -> str:
    if config_steam.steam_isthereanydeal_key:
        if isinstance(config_steam.steam_isthereanydeal_key, List):
            return random.choice(config_steam.steam_isthereanydeal_key)
        elif isinstance(config_steam.steam_isthereanydeal_key, str):
            return config_steam.steam_isthereanydeal_key
        else:
            return str(config_steam.steam_isthereanydeal_key)
    raise ValueError("steam_isthereanydeal_key 未配置")

async def gameid_to_uuid(game_id: str, client: HTTPClientSession):
    res = SafeResponse(await client.request(Request("GET", f"https://api.isthereanydeal.com/games/lookup/v1?appid={game_id}&key={get_isthereanydeal_key()}")))
    if res.status_code == 200:
        game_uuid = json.loads(res.text)["game"]["id"]
        return game_uuid
    else:
        raise ConnectionError(f"gameid_to_uuid 获取失败，game_id:{game_id}，res code:{res.status_code}，res text:{res.text}")

async def get_history_price(game_uuid: str, client: HTTPClientSession, location: str = "CN"):
    res = SafeResponse(await client.request(Request(
        "POST", 
        f"https://api.isthereanydeal.com/games/prices/v3?country={location}&key={get_isthereanydeal_key()}",
        headers={"Content-Type":"application/json"},
        json=[game_uuid]
        )))
    if res.status_code == 200:
        data = res.json()
        if data:
            if data[0] and data[0]["historyLow"] and data[0]["historyLow"]["all"] and data[0]["historyLow"]["all"]["amount"]:
                history_price = data[0]["historyLow"]["all"]["amount"]
                return history_price
    else:
        raise ConnectionError(f"gameid_to_uuid 获取失败，game_uuid_id:{game_uuid}，res code:{res.status_code}，res text:{res.text}")

def save_data():
    global steam_list, group_list, exclude_game, inactive_groups,game_discounted_cache,game_discounted_subscribe
    new_file_group.write_text(json.dumps(group_list)) 
    new_file_steam.write_text(json.dumps(steam_list))
    exclude_game_file.write_text(json.dumps(exclude_game))
    inactive_groups_file.write_text(json.dumps(inactive_groups))
    game_discounted_cache_file.write_text(json.dumps(game_discounted_cache))
    game_discounted_subscribe_file.write_text(json.dumps(game_discounted_subscribe))
    
async def no_private_rule(target: MsgTarget) -> bool:
    return not target.private
        
async def bot_right(target: Target):
    group_id = target.id

async def get_game_data_msg(res_json, xijiayi = False):
    game_data = res_json['data']
    app_id = game_data["steam_appid"]
    dlc = game_data["type"] == "dlc" 
    forward_name = []
    if xijiayi:
        forward_name = [f"{'DLC 'if dlc else ''}喜加一"]
    forward_name += ["预览",f"{'DLC 'if dlc else ''}名称","链接","价格","分级","介绍","语言","标签","发售时间","","截图","DLC"]

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
        price_text = f"现价：{price['now']} {price['currency'] if price['now'] != '免费' else ''}"
        if price["history"]:
            price_text = f"史低：{price['history']} {price['currency']}\n" + price_text
        if price["original"]:
            price_text = f"原价：{price['original']} {price['currency']}\n折扣：{price['percent']}\n" + price_text

    rating = f"分级：{game_data['ratings']['dejus']['rating']}" if "ratings" in game_data and "dejus" in game_data["ratings"] and "rating" in game_data["ratings"]["dejus"] else "暂无分级"
    
    if rating == "分级：18":
        want = f"不可以玩这种{config_steam.steam_tail_tone}..."
    else:
        want = (f"{random.choice(bot_name)}也想玩" if game_data['is_free'] else f"要送给{random.choice(bot_name)}吗？") if 'price_overview' in game_data else (f"{random.choice(bot_name)}也想玩" if game_data['is_free'] else f"迫不及待想玩啦，发售时会送给{random.choice(bot_name)}吗？")
    msgs = []
    if xijiayi:
        msgs = [UniMessage.text(f"Steam DLC 喜加一{config_steam.steam_tail_tone}！" if dlc else f"Steam 喜加一{config_steam.steam_tail_tone}！")]
    msgs += [
        UniMessage.image(raw = header_image if header_image else b""),
        UniMessage.text(game_data['name']),
        UniMessage.text(f"https://store.steampowered.com/app/{app_id}"),
        UniMessage.text(price_text),
        UniMessage.text(rating),
        UniMessage.image(raw = png),
        UniMessage.text(game_data["supported_languages"].replace("<strong>","").replace("</strong>","").replace("<br>","") if "supported_languages" in game_data else "支持语言：未知"),
        UniMessage.text("，".join([x["description"] for x in game_data["genres"]]) if "genres" in game_data else "暂无分类描述"),
        UniMessage.text(game_data["release_date"]["date"] if "release_date" in game_data and "date" in game_data["release_date"] and game_data["release_date"]["date"] else "未知发售时间"),
        UniMessage.text(want),
        
        [UniMessage.image(raw=img) for img in screenshots_img],
        [UniMessage.image(raw=img) for img in dlc_img] if dlc_img else [UniMessage.text("无DLC")],
        
    ]
    return forward_name, msgs

async def make_game_data_node_msg(target: Target|MsgTarget, forward_name: List[str], msgs: List[UniMessage]) -> List[CustomNode]:
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
    return messages

async def send_node_msg(messages: List[CustomNode], app_id: str,target: Optional[ModTarget] = None,bot: Optional[Bot] = None):
    try:
        await UniMessage(Reference(nodes=messages)).send(target=target, bot=bot)
    except Exception as e:
        logger.debug(f"steam app_id: {app_id} 消息发送异常 {e}，准备删除DLC后重试")
        try:
            new_msg = [x for x in messages if x.name != "DLC"]
            await UniMessage(Reference(nodes=new_msg)).send(target=target, bot=bot)
        except Exception as e:
            logger.debug(f"steam app_id: {app_id} 消息再次发送异常 {e}，准备删除DLC和截图后重试")
            new_new_msg = [x for x in messages if x.name not in ("DLC", "截图")]
            try:
                await UniMessage(Reference(nodes=new_new_msg)).send(target=target, bot=bot)
            except Exception as e:
                logger.debug(f"steam app_id: {app_id} 消息再再次发送异常 {e}")
                await UniMessage(f"steam app_id: {app_id} 似乎发不出去...").send(target=target, bot=bot, reply_to=True)
    
async def get_free_games_list() -> List:
    game_appid_list = []
    steam_page_request = Request(
        "GET",
        f"https://{get_steam_store_domain()}/search/?maxprice=free&specials=1&ndl=1&cc=cn"
    )
    async with http_client() as client:
        res = SafeResponse(await client.request(steam_page_request))
        html = res.text
        soup = BeautifulSoup(html, "html.parser")
        div_container = soup.find("div", id="search_resultsRows")
        if div_container and isinstance(div_container, Tag):
            a_tags = div_container.find_all("a")
            for a in a_tags:
                if isinstance(a, Tag):
                    appid = a.get("data-ds-appid")
                    game_appid_list.append(str(appid))
    return game_appid_list

async def get_free_games_info(target: Optional[MsgTarget] = None):
    global game_free_cache
    game_appid_list = await get_free_games_list()
    if game_appid_list:
        for app_id in game_appid_list:
            if app_id not in game_free_cache or target:
                res_json = await get_game_info(app_id)
                forward_name, msgs = await get_game_data_msg(res_json, True)
                if target:
                    logger.debug(f"steam获取推送喜加一信息来源用户消息，app_id:{app_id} target:{target.id} {target.adapter}")
                    messages = await make_game_data_node_msg(target, forward_name, msgs)
                    await send_node_msg(messages, app_id)
                else:
                    game_free_cache.append(app_id)
                    if len(game_free_cache) > 10:
                        game_free_cache.pop(0)
                    game_free_cache_file.write_text(json.dumps(game_free_cache))

                    for group_id in group_list:
                        if group_list[group_id]["xijiayi"]:
                            send_target, bot = await get_group_target_bot(group_id)
                            if send_target:
                                logger.debug(f"steam获取推送喜加一信息来源用户订阅，app_id:{app_id} target:{send_target.id} {send_target.adapter}")
                                messages = await make_game_data_node_msg(send_target, forward_name, msgs)
                                await send_node_msg(messages, app_id, send_target, bot)
                            else:
                                await test_group_active(group_id)    
                        
    else:
        logger.info("steam喜加一暂无结果")
        return "steam喜加一暂无结果"

async def get_group_target_bot(id: str) -> Tuple[Optional[ModTarget], Optional[Bot]]:
    send_target = get_target(id)
    bots = await send_target.mod_select()
    if bots == []:
        logger.warning(f"目标id：{id}，适配器：{send_target.adapter} 不在当前适配器bot的群列表中，为避免风控停止对id发送。")
        return None, None
    else:
        if isinstance(bots, Bot):
            logger.trace(f"目标id：{id}，适配器：{send_target.adapter} 仅有一个bot，bot：{bots}")
            bot = bots
        else:
            bot = random.choice(bots)
        send_target.self_id = bot.self_id
        logger.trace(f"目标id：{id}，send_target: {send_target}，bot：{bot}")
        return send_target, bot

async def test_group_active(group_id: str):
    '''### 测试群组id是否还关联bot
    会自动加入和移出失联列表'''
    target, bot = await get_group_target_bot(group_id)
    if target and bot:
        await out_inactive_groups(group_id)
    else:
        await join_inactive_groups(group_id)
    save_data()

async def join_inactive_groups(group_id: str):
    '''将群组id加入失联列表'''
    global inactive_groups
    if group_id not in inactive_groups:
        inactive_groups.append(group_id)
        logger.info(f"群组id： {group_id} 已添加到失联群组列表")

async def out_inactive_groups(group_id: str):
    '''将群组id移出失联列表'''
    global inactive_groups
    if group_id in inactive_groups:
        inactive_groups.remove(group_id)
        logger.info(f"群组id： {group_id} 已从失联群组列表移除")

async def get_inactive_groups_list(target: Target) -> UniMessage:
    '''获取失联群组列表'''
    global inactive_groups,group_list
    try:
        msgs: List[CustomNode] = []
        msgs10: List[str] = []
        for i, group_id in enumerate(inactive_groups):
            if i % 10 == 0 and i != 0:
                msgs.append(
                    CustomNode(
                        uid=str(target.self_id),
                        name=str(i+1),
                        content='\n'.join(msgs10)
                        ))
                msgs10.clear()
            else:
                msgs10.append(f"{group_id} - {group_list[group_id]['adapter']}")
        if msgs10:
            msgs.append(
                CustomNode(
                    uid=str(target.self_id),
                    name=str(len(inactive_groups)),
                    content='\n'.join(msgs10)
                    ))
        if msgs:
            return UniMessage(Reference(nodes=msgs))
        else:
            return UniMessage(f"当前无失联群组{config_steam.steam_tail_tone}")
    except Exception as e:
        logger.warning(f"获取steam失联群组列表异常：{e}")
        return UniMessage(f"获取steam失联群组列表异常{config_steam.steam_tail_tone}：{e}")

async def clear_inactive_groups_list(target: Target) -> UniMessage:
    '''清理失联群组列表'''
    global inactive_groups, group_list
    try:
        inactive_groups_mirror = inactive_groups.copy()
        num = len(inactive_groups_mirror)
        for group_id in inactive_groups_mirror:
            if group_id in group_list:
                inactive_groups.remove(group_id)
                del group_list[group_id]
        save_data()
        logger.info(f"清理steam失联群组列表成功，清理数量：{num}")
        return UniMessage(f"清理steam失联群组列表成功{config_steam.steam_tail_tone}，清理数量：{num}")
    except Exception as e:
        logger.warning(f"清理steam失联群组列表异常：{e}")
        return UniMessage(f"清理steam失联群组列表异常{config_steam.steam_tail_tone}：{e}")

async def get_steam_playtime(steam_id: str) -> bytes:
    '''通过steam_id获取游戏游玩时长拼图
    Args:
        steam_id (str): Steam ID
    Return:
        bytes: 渲染后的图片字节'''
    url = f"https://playtime-panorama.superserio.us/{steam_id}"
    logger.info(f"Steam 游戏时长拼图获取，ID:{steam_id}, url: {url}")
    async with playwright_context() as pc:
        page = await pc.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto(url=url, timeout=60000)
        try:
            await page.wait_for_load_state('networkidle')
            await page.wait_for_selector("#games-stage", state="visible", timeout=60000)
        except TimeoutError:
            logger.warning(f"Steam 游戏时长拼图获取，ID:{steam_id}, url: {url}, timeout")
        games_stage = await page.query_selector("#games-stage")
        if games_stage:
            return await games_stage.screenshot(type="png")
        raise Exception("no games_stage")

async def get_discounted_game_info(app_id: str) -> Tuple[dict, dict]:
    logger.info(f"steam开始检查游戏id{app_id}是否打折...")
    res_json = await get_game_info(app_id)
    if "error" in res_json:
        logger.debug(f"主动获取折扣信息出错，app_id: {app_id}，res_json: {res_json}")
        raise Exception(res_json["error"])
    price = await gameid_to_price(app_id, res_json["data"], res_json["from"])
    return res_json, price

async def get_discounted_games_info(target: Optional[MsgTarget] = None, game_id_from_cmd: str = ""):
    logger.info("开始检查已关注的游戏是否打折...")
    if game_id_from_cmd and target:
        res_json, price = await get_discounted_game_info(game_id_from_cmd)
        if price["status"]:
            # 免费游戏不许订阅
            return False
        if not price["original"]:
            # 没打折，提醒一下现价和史低
            price_text = f"现价：{price['now']} {price['currency'] if price['now'] != '免费' else ''}"
            if price["history"]:
                price_text = f"史低：{price['history']} {price['currency']}\n" + price_text
            return price_text
        else:
            # 当前有折扣，订阅就提醒
            forward_name, msgs = await get_game_data_msg(res_json)
            logger.debug(f"steam获取折扣订阅信息来源用户订阅消息，app_id:{game_id_from_cmd} target:{target.id} {target.adapter}")
            messages = await make_game_data_node_msg(target, forward_name, msgs)
            await send_node_msg(messages, game_id_from_cmd)
            return True

    for game_id in game_discounted_subscribe:
        try:
            logger.debug(f"steam准备尝试获取steam_id: {game_id} 折扣信息")
            res_json, price = await get_discounted_game_info(game_id)
        except Exception as e:
            logger.warning(f"主动获取折扣信息出错，跳过本次获取，game_id:{game_id}  :{e.args}")
            continue
        # 筛选出变免费的和有折扣的
        if price["status"] or price["original"]:
            if game_id in game_discounted_cache:
                # 冷却缓存列表中已存在，跳过
                logger.debug(f"steam 游戏id:{game_id} 冷却缓存列表中已存在，跳过")
                continue
            logger.info(f"steam 游戏id:{game_id} 存在折扣，尝试获取")
            forward_name, msgs = await get_game_data_msg(res_json)
            for group_id in game_discounted_subscribe[game_id]:
                send_target, bot = await get_group_target_bot(group_id)
                if send_target:
                    logger.debug(f"steam获取推送折扣信息来源用户订阅，app_id:{game_id} target:{send_target.id} {send_target.adapter}")
                    messages = await make_game_data_node_msg(send_target, forward_name, msgs)
                    await send_node_msg(messages, game_id, send_target, bot)
                else:
                    await test_group_active(group_id)   
            # 此game_id已打折并推送，加入缓存列表计入冷却        
            game_discounted_cache.append(game_id)
        else:
            if game_id in game_discounted_cache:
                # 已无折扣，从冷却缓存列表中删除
                logger.debug(f"steam 游戏id:{game_id} 已无折扣，从冷却缓存列表中删除")
                game_discounted_cache.remove(game_id)
            logger.debug(f"steam 游戏id:{game_id} 未折扣，跳过")
            continue
    save_data()
    logger.info("steam打折检查任务完成")