import sys
import json
import time
import random
import asyncio
import io
import hashlib
from pathlib import Path

from typing import Dict, List, Optional, Literal
from nonebot import require
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.internal.driver import Request
from nonebot.exception import MatcherException
from nonebot.plugin import inherit_supported_adapters

from arclet.alconna import Alconna, Option, Args, CommandMeta, AllParam

from .utils import http_client, driver, HTTPClientSession, to_enum, playwright_context
from .card import (
    STEAM_CARD_ANIMATION_FRAME_COUNT,
    build_steam_card_cache_key,
    is_animated_image_url,
    render_steam_card_template,
)
from .model import UserData, SafeResponse, create_group_data
from .config import Config, __version__, config_steam, bot_name, get_steam_api_domain
from .api import (
    clear_inactive_groups_list,
    gameid_to_name,
    get_inactive_groups_list,
    steam_link_rule,
    get_game_info,
    get_steam_key,
    save_data,
    no_private_rule,
    get_game_data_msg,
    make_game_data_node_msg,
    send_node_msg,
    get_free_games_info,
    game_discounted_subscribe,
    get_group_target_bot,
    test_group_active,
    get_steam_playtime,
    get_discounted_games_info,
    get_owned_games,
    get_animated_avatar_url,
)
from .source import (
    new_file_group,
    new_file_steam,
    exclude_game_file,
    exclude_game_default,
    steam_list,
    group_list,
    exclude_game,
    game_discounted_cache,
    owned_games,
    dynamic_card_cache_dir,
)

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Arparma, on_alconna, Match  # noqa: E402
from nonebot_plugin_alconna.uniseg import UniMessage, CustomNode, Reference, MsgTarget  # noqa: E402

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import template_to_pic  # noqa: E402

from PIL import Image as PILImage  # noqa: E402

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
            steam图片播报开启/steam图片播报关闭
            steam结束图片播报开启/steam结束图片播报关闭
                默认开始/切换游戏使用图片播报，结束游戏使用文字播报。
            steam入库播报开启/steam入库播报关闭
                默认关闭。按 steam_owned_game_interval 检查公开游戏库，只播报新增游戏。
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
        "author": "nek0us",
        "version": __version__,
        "priority": config_steam.steam_command_priority
    }
)


async def render_steam_card(avatar_url: str, player_name: str, game_name: str, action_text: str) -> Optional[bytes]:
    """
    使用 nonebot_plugin_htmlrender 渲染 Steam 状态卡片
    """
    try:
        template_path = str(Path(__file__).parent / "templates")

        if not (Path(__file__).parent / "templates" / "steam_card.html").exists():
            logger.warning("Steam卡片模板文件 steam_card.html 不存在，跳过渲染")
            return None

        pic_data = await template_to_pic(
            template_path=template_path,
            template_name="steam_card.html",
            templates={
                "avatar_url": avatar_url,
                "player_name": player_name,
                "action_text": action_text,
                "game_name": game_name,
            },
            pages={
                "viewport": {"width": 426, "height": 100},
                "base_url": f"file://{template_path}",
            },
            wait=1,  # 等待1秒确保图片加载？可以核实一下有必要没
        )
        return pic_data
    except Exception as e:
        logger.error(f"渲染 Steam 卡片失败: {e}")
        return None


async def render_dynamic_steam_card(avatar_url: str, player_name: str, game_name: str, action_text: str) -> Optional[bytes]:
    if not config_steam.steam_dynamic_avatar_card or not is_animated_image_url(avatar_url):
        return None

    try:
        template_path = Path(__file__).parent / "templates"
        template_file = template_path / "steam_card.html"
        if not template_file.exists():
            logger.warning("Steam卡片模板文件 steam_card.html 不存在，跳过动态渲染")
            return None

        template_html = template_file.read_text("utf8")
        template_digest = hashlib.sha256(template_html.encode("utf8")).hexdigest()
        cache_key = build_steam_card_cache_key(
            avatar_url=avatar_url,
            player_name=player_name,
            action_text=action_text,
            game_name=game_name,
            template_digest=template_digest,
            frame_duration_ms=config_steam.steam_dynamic_card_frame_duration_ms,
            capture_interval_ms=config_steam.steam_dynamic_card_capture_interval_ms,
        )
        cache_file = dynamic_card_cache_dir / f"{cache_key}.gif"
        if config_steam.steam_dynamic_card_cache and cache_file.exists():
            logger.debug(f"Steam 动态卡片缓存命中: {cache_key}")
            return cache_file.read_bytes()

        html_content = render_steam_card_template(
            template_html=template_html,
            avatar_url=avatar_url,
            player_name=player_name,
            action_text=action_text,
            game_name=game_name,
        )
        frames = []
        async with playwright_context() as pc:
            page = await pc.new_page()
            await page.set_viewport_size({"width": 426, "height": 100})
            await page.set_content(
                html_content,
                wait_until="networkidle",
                timeout=config_steam.steam_dynamic_card_timeout_ms,
            )
            await page.wait_for_selector(
                ".steam-card",
                state="visible",
                timeout=config_steam.steam_dynamic_card_timeout_ms,
            )
            await page.wait_for_timeout(200)
            card = await page.query_selector(".steam-card")
            if not card:
                return None

            for _ in range(STEAM_CARD_ANIMATION_FRAME_COUNT):
                frame_bytes = await card.screenshot(type="png", omit_background=True)
                frames.append(PILImage.open(io.BytesIO(frame_bytes)).convert("RGBA"))
                await page.wait_for_timeout(config_steam.steam_dynamic_card_capture_interval_ms)

        if not frames:
            return None

        output = io.BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=config_steam.steam_dynamic_card_frame_duration_ms,
            loop=0,
            disposal=2,
        )
        gif_data = output.getvalue()
        if config_steam.steam_dynamic_card_cache:
            cache_file.write_bytes(gif_data)
            logger.debug(f"Steam 动态卡片缓存写入: {cache_key}")
        return gif_data
    except Exception as e:
        logger.error(f"渲染 Steam 动态卡片失败: {e}")
        return None


async def render_bind_card(avatar_url: str, player_name: str, steam_id: str) -> Optional[bytes]:
    """
    使用 nonebot_plugin_htmlrender 渲染 Steam 绑定成功卡片
    """
    try:
        template_path = str(Path(__file__).parent / "templates")

        if not (Path(__file__).parent / "templates" / "steam_bind_card.html").exists():
            logger.warning("Steam绑定模板文件 steam_bind_card.html 不存在，跳过渲染")
            return None

        pic_data = await template_to_pic(
            template_path=template_path,
            template_name="steam_bind_card.html",
            templates={
                "avatar_url": avatar_url,
                "player_name": player_name,
                "steam_id": steam_id,
            },
            pages={
                "viewport": {"width": 342, "height": 330},
                "base_url": f"file://{template_path}",
            },
            wait=1,  # 同132行注释
        )
        return pic_data
    except Exception as e:
        logger.error(f"渲染 Steam 绑定卡片失败: {e}")
        return None


async def resolve_avatar_url(steam_id: str, fallback_avatar_url: str) -> str:
    if not config_steam.steam_dynamic_avatar_card:
        return fallback_avatar_url

    try:
        animated_avatar_url = await get_animated_avatar_url(steam_id)
    except Exception as e:
        logger.debug(f"Steam 动态头像获取异常，steam_id:{steam_id}，使用静态头像：{e.args}")
        return fallback_avatar_url

    if animated_avatar_url:
        logger.debug(f"Steam 动态头像已获取，steam_id:{steam_id}")
        return animated_avatar_url
    return fallback_avatar_url



steam_link_re_alc = Alconna(
    "steam_open",
    Args["appid", int],
    meta=CommandMeta(compact=True, strict=False)
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
async def steam_link_handle(target: MsgTarget, matcher: Matcher, appid: Match[str]):
    app_id = str(appid.result)
    try:
        res_json = await get_game_info(app_id)
        if 'error' in res_json:
            logger.warning(f"steam链接识别失败，异常为：{res_json['error']}")
            await matcher.finish("steam链接失败，请检查日志输出")
        if not res_json['success']:
            logger.info(f"steam链接游戏信息获取失败，疑似appid错误：{app_id}")
            await matcher.finish("没有找到这个游戏", reply_message=True)
        id = str(target.id)
        if res_json["from"] != "cn":
            if isinstance(config_steam.steam_area_game, bool):
                if not config_steam.steam_area_game:
                    await matcher.finish("没有找到这个游戏", reply_message=True)
            else:
                if id not in config_steam.steam_area_game:
                    await matcher.finish("没有找到这个游戏", reply_message=True)
        game_data = res_json['data']
        if "ratings" in game_data:
            if "steam_germany" in game_data["ratings"]:
                if game_data["ratings"]["steam_germany"]['rating'] == "BANNED":
                    if isinstance(config_steam.steam_link_r18_game, bool):
                        if not config_steam.steam_link_r18_game:
                            logger.info(f"steam appid:{app_id} 根据r18设置被过滤")
                            await matcher.finish("这个禁止！", reply_message=True)
                    else:
                        if id not in config_steam.steam_link_r18_game:
                            logger.info(f"steam appid:{app_id} 根据r18设置被过滤，{id} 不在白名单内")
                            await matcher.finish("这个禁止！", reply_message=True)
        forward_name, msgs = await get_game_data_msg(res_json)
        messages = await make_game_data_node_msg(target, forward_name, msgs)
        await send_node_msg(messages, app_id)
        logger.debug(f"steam app_id: {app_id} 解析完成")
    except Exception as e:
        logger.warning(f"steam app_id: {app_id} 解析失败：{e.args}")
        await matcher.send(f"steam app_id：{app_id} 解析失败 {config_steam.steam_tail_tone}")


@driver.on_startup
async def _():
    # 当bot启动时，忽略所有未播报的游戏
    for steam_id in steam_list:
        if steam_list[steam_id] and steam_list[steam_id]["time"] != 0:
            steam_list[steam_id]["time"] = -1  # -1 为特殊时间用来判断是否重启

        # 修复用户id异常
        if isinstance(steam_list[steam_id], list) and steam_list[steam_id] == [-1]:
            steam_name: str = ""
            try:
                async with http_client() as client:
                    url = f"https://{get_steam_api_domain()}/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
                    res = SafeResponse(await client.request(Request("GET", url, timeout=30)))
                    if res.status_code != 200:
                        logger.warning(
                            f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 http状态码不为200: {res.status_code}")
                        continue
                    if json.loads(res.text)["response"]["players"] == []:
                        logger.warning(f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 获取到的用户信息为空")
                        continue
                    steam_name = json.loads(res.text)["response"]["players"][0]['personaname']
            except Exception as e:
                logger.warning(f"Steam id: {steam_id} 修复失败，下次重启时重试。失败原因 : {e.args}")
                continue
            steam_list[steam_id] = UserData(time=0, game_name="", nickname=steam_name)
            logger.debug(f"Steam id: {steam_id},name: {steam_name} 异常，修复成功")


async def get_status(client: HTTPClientSession, steam_id_to_groups: Dict[str, List[str]],
                     steam_list: Dict[str, UserData], steam_id: str):
    global exclude_game
    user_info = []
    res = None
    try:
        url = f"https://{get_steam_api_domain()}/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id

        res = SafeResponse(await client.request(Request("GET", url, timeout=30)))
        if res.status_code == 200:

            res_info = json.loads(res.text)["response"]["players"][0]

            should_notify = False
            action_type = ""
            game_name_for_msg = ""
            action_text_for_card = ""
            game_name_old = ""
            game_time_old = 0

            if "gameextrainfo" in res_info and steam_list[steam_id]["game_name"] == "":
                timestamp = int(time.time() / 60)
                game_name = await gameid_to_name(res_info["gameid"], res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]

                user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                should_notify = True
                action_type = "start"
                game_name_for_msg = game_name
                action_text_for_card = "开始玩"

            elif "gameextrainfo" in res_info and steam_list[steam_id]["time"] != -1 and steam_list[steam_id][
                "game_name"] != "":
                game_name = await gameid_to_name(res_info["gameid"], res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]

                if game_name != steam_list[steam_id]["game_name"]:
                    game_name_old = steam_list[steam_id]["game_name"]
                    timestamp = int(time.time() / 60)
                    user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                    should_notify = True
                    action_type = "switch"
                    game_name_for_msg = game_name
                    action_text_for_card = "开始玩"

            elif "gameextrainfo" not in res_info and steam_list[steam_id]["game_name"] != "":
                timestamp = int(time.time() / 60)
                game_name_old = steam_list[steam_id]["game_name"]
                game_time_old = steam_list[steam_id]["time"]
                user_info = UserData(time=timestamp, game_name="", nickname=res_info['personaname'])
                game_time = timestamp - game_time_old
                should_notify = True
                action_type = "stop"
                game_name_for_msg = game_name_old
                if game_time_old == -1:
                    action_text_for_card = "结束了游戏"
                else:
                    action_text_for_card = f"玩了 {game_time} 分钟后停止"

            elif "gameextrainfo" in res_info and steam_list[steam_id]["time"] == -1 and steam_list[steam_id][
                "game_name"] != "":
                game_name = await gameid_to_name(res_info["gameid"], res_info["gameextrainfo"])
                if game_name == "":
                    game_name = res_info["gameextrainfo"]
                game_name_old = steam_list[steam_id]["game_name"]

                if game_name != game_name_old:
                    timestamp = int(time.time() / 60)
                    user_info = UserData(time=timestamp, game_name=game_name, nickname=res_info['personaname'])
                    should_notify = True
                    action_type = "restart_switch"
                    game_name_for_msg = game_name
                    action_text_for_card = "开始玩"

            if should_notify:
                card_image_bytes = None
                avatar_url = await resolve_avatar_url(steam_id, res_info.get("avatarfull", ""))
                image_enabled_group_ids = [
                    group_id
                    for group_id in steam_id_to_groups[steam_id]
                    if (
                        group_list.get(str(group_id), {}).get("stop_image", False)
                        if action_type == "stop"
                        else group_list.get(str(group_id), {}).get("image", True)
                    )
                ]
                should_render_card = bool(image_enabled_group_ids)

                if should_render_card:
                    try:
                        card_image_bytes = await render_dynamic_steam_card(
                            avatar_url=avatar_url,
                            player_name=res_info['personaname'],
                            game_name=game_name_for_msg,
                            action_text=action_text_for_card
                        )
                        if not card_image_bytes:
                            card_image_bytes = await render_steam_card(
                                avatar_url=avatar_url,
                                player_name=res_info['personaname'],
                                game_name=game_name_for_msg,
                                action_text=action_text_for_card
                            )
                    except Exception as e:
                        logger.error(f"Steam卡片预渲染失败: {e}")

                for group_id in steam_id_to_groups[steam_id]:
                    if game_name_for_msg in exclude_game[str(group_id)]:
                        logger.trace(f"群 {group_id} 屏蔽游戏 {game_name_for_msg}，跳过")
                        continue

                    if action_type == "switch" or action_type == "restart_switch":
                        if game_name_old and game_name_old in exclude_game[str(group_id)]:
                            logger.trace(f"群 {group_id} 屏蔽旧游戏 {game_name_old}，跳过")
                            continue

                    target, bot = await get_group_target_bot(group_id)

                    if target:
                        msg_to_send = None
                        use_image_broadcast = group_id in image_enabled_group_ids
                        if use_image_broadcast and card_image_bytes:
                            msg_to_send = UniMessage.image(raw=card_image_bytes)
                        else:
                            tone = config_steam.steam_tail_tone
                            name = res_info['personaname']
                            if action_type in ["start", "restart_switch"]:
                                msg_to_send = UniMessage(f"{name} 开始玩 {game_name_for_msg}{tone} 。")
                            elif action_type == "switch":
                                msg_to_send = UniMessage(f"{name} 又开始玩 {game_name_for_msg}{tone} 。")
                            elif action_type == "stop":
                                if game_time_old == -1:
                                    msg_to_send = UniMessage(
                                        f"{name} 不再玩 {game_name_for_msg} 。但{random.choice(bot_name)}忘了，不记得玩了多久了{tone}。")
                                else:
                                    game_time = int(time.time() / 60) - game_time_old
                                    msg_to_send = UniMessage(
                                        f"{name} 玩了 {game_time} 分钟 {game_name_for_msg} 后不玩了{tone}。")

                        if msg_to_send:
                            try:
                                logger.trace(
                                    f"群 {group_id} 发送 Steam 状态: {res_info['personaname']} -> {game_name_for_msg}")
                                await msg_to_send.send(target=target, bot=bot)
                            except Exception as send_e:
                                logger.warning(f"群 {group_id} 发送消息失败: {send_e}")
                    else:
                        await test_group_active(group_id)

            elif "gameextrainfo" not in res_info and steam_list[steam_id]["game_name"] == "":
                pass
        else:
            logger.debug(f"steam id:{steam_id} 查询状态不是200，{res.status_code} \n{res.text}")
    except Exception as e:
        a, b, exc_traceback = sys.exc_info()
        logger.debug(
            f"steam id:{steam_id} 查询状态失败,line: {exc_traceback.tb_lineno if exc_traceback else ''}，{e.args} \n{res.text if res else None}\n{a}\n{b}")
    finally:
        if not isinstance(user_info, list):
            steam_list[steam_id] = user_info


@scheduler.scheduled_job("interval", minutes=config_steam.steam_interval, id="steam",
                         misfire_grace_time=(config_steam.steam_interval * 60 - 1))
async def now_steam():
    if config_steam.steam_web_key:
        global steam_list
        logger.debug("steam准备开始生成查询字典")
        task_list = []
        steam_id_to_groups: Dict[str, List[str]] = {}
        for group_id, group_data in group_list.items():
            if group_data['status']:
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
                await asyncio.wait_for(asyncio.gather(*task_list), timeout=(config_steam.steam_interval * 60 - 20))
                logger.debug("steam自动查询任务完成")
            except Exception as e:
                logger.debug(f"steam新异常:{e.args}")
            finally:
                new_file_steam.write_text(json.dumps(steam_list))
                logger.debug("steam finally保存完成")


@scheduler.scheduled_job(
    "interval",
    minutes=config_steam.steam_owned_game_interval,
    id="steam_owned_games",
    misfire_grace_time=(config_steam.steam_owned_game_interval * 60 - 1),
)
async def now_steam_owned_games():
    if not config_steam.steam_web_key:
        return

    global owned_games
    steam_id_to_groups: Dict[str, List[str]] = {}
    for group_id, group_data in group_list.items():
        if group_data.get("status") and group_data.get("owned_game", False):
            for steam_id in group_data["user_list"]:
                if steam_id not in steam_id_to_groups:
                    steam_id_to_groups[steam_id] = []
                steam_id_to_groups[steam_id].append(group_id)

    if not steam_id_to_groups:
        logger.debug("steam游戏库入库播报未开启，跳过本次检查")
        return

    logger.info(f"steam开始检查游戏库入库变更，用户数：{len(steam_id_to_groups)}")
    for steam_id, group_ids in steam_id_to_groups.items():
        try:
            current_games = await get_owned_games(steam_id)
        except Exception as e:
            logger.warning(f"steam游戏库获取异常，steam_id:{steam_id}，跳过本次更新：{e.args}")
            continue

        if current_games is None:
            continue

        if steam_id not in owned_games:
            owned_games[steam_id] = current_games
            logger.info(f"steam游戏库入库播报建立基准，steam_id:{steam_id}，游戏数：{len(current_games)}")
            continue

        old_games = owned_games[steam_id]
        new_appids = sorted(set(current_games) - set(old_games))

        if not new_appids:
            owned_games[steam_id] = current_games
            continue

        player_name = steam_list.get(steam_id, {}).get("nickname", steam_id)
        game_lines = [f"《{current_games[appid]}》" for appid in new_appids]
        message_text = f"{player_name} 的 Steam 游戏库新增了：\n" + "\n".join(game_lines)
        sent = False

        for group_id in group_ids:
            target, bot = await get_group_target_bot(group_id)
            if target:
                try:
                    logger.info(f"群 {group_id} 发送 Steam 游戏库入库播报: {player_name} -> {new_appids}")
                    await UniMessage(message_text).send(target=target, bot=bot)
                    sent = True
                except Exception as e:
                    logger.warning(f"群 {group_id} 发送 Steam 游戏库入库播报失败: {e}")
            else:
                await test_group_active(group_id)

        if sent:
            owned_games[steam_id] = current_games
        else:
            logger.warning(f"Steam 游戏库入库播报全部发送失败，保留旧基准等待下次重试，steam_id:{steam_id}")

    save_data()
    logger.info("steam游戏库入库检查任务完成")


steam_command_alc = Alconna(
    "steam",
    Option("add", Args["id", str], alias=["绑定", "添加", ".add"], separators="", compact=True),
    Option("del", Args["id", str], alias=["解绑", "删除", ".del"], separators="", compact=True),
    Option("屏蔽", Args["game", AllParam(str)], separators="", compact=True),
    Option("恢复", Args["game", AllParam(str)], separators="", compact=True),
    Option("打折订阅", Args["game", AllParam(str)], alias=["折扣订阅", "促销订阅", "低价订阅"], separators="",
           compact=True),
    Option("打折退订", Args["game", AllParam(str)], alias=["折扣退订", "促销退订", "低价退订"], separators="",
           compact=True),
    Option("排除列表", separators="", compact=True),
    Option("list", alias=["列表", "绑定列表", "播报列表"], separators="", compact=True),
    Option("播报", Args["status", str], separators="", compact=True),
    Option("图片播报", Args["status", str], separators="", compact=True),
    Option("结束图片播报", Args["status", str], separators="", compact=True),
    Option("入库播报", Args["status", str], alias=["游戏库播报"], separators="", compact=True),
    Option("墙", Args["user", str], separators="", compact=True),
    Option("喜加一", Args["action", Optional[Literal["订阅", "退订"]]], separators="", compact=True),
    Option("失联群列表", separators="", compact=True),
    Option("失联群清理", separators="", compact=True),
    separators="",
    meta=CommandMeta(compact=True)
)
steam_cmd = on_alconna(steam_command_alc, priority=config_steam.steam_command_priority, rule=no_private_rule)


def ensure_group_data(target: MsgTarget) -> str:
    group_id = str(target.id)
    if group_id not in group_list:
        group_list[group_id] = create_group_data(adapter=to_enum(target.adapter).value if target.adapter else "")
    if group_id not in exclude_game:
        exclude_game[group_id] = list(exclude_game_default)
    return group_id


async def initialize_owned_games_baseline(steam_ids: List[str]) -> tuple[int, List[str]]:
    created = 0
    failed_steam_ids = []
    for steam_id in set(steam_ids):
        if steam_id in owned_games:
            continue
        try:
            current_games = await get_owned_games(steam_id)
        except Exception as e:
            failed_steam_ids.append(steam_id)
            logger.warning(f"steam游戏库基准建立异常，steam_id:{steam_id}：{e.args}")
            continue
        if current_games is None:
            failed_steam_ids.append(steam_id)
            nickname = steam_list.get(steam_id, {}).get("nickname", "")
            logger.warning(f"steam游戏库基准建立失败，steam_id:{steam_id}，昵称:{nickname}，可能游戏库不可见或接口返回为空")
            continue
        owned_games[steam_id] = current_games
        created += 1
        logger.info(f"steam游戏库入库播报建立基准，steam_id:{steam_id}，游戏数：{len(current_games)}")
    return created, failed_steam_ids


@steam_cmd.assign("add")
async def steam_bind_handle(target: MsgTarget, matcher: Matcher, id: Match[str]):
    steam_id = str(id.result)
    if len(steam_id) != 17:
        try:
            steam_id = int(steam_id)
            steam_id += 76561197960265728
            steam_id = str(steam_id)
        except Exception as e:
            logger.debug(f"Steam 绑定出错，输入值：{steam_id}，错误：{e.args}")
            await matcher.finish(f"Steam ID格式错误{config_steam.steam_tail_tone}")
    global steam_list, group_list, exclude_game
    group_id = ensure_group_data(target)

    if steam_id in group_list[group_id]["user_list"]:
        await matcher.finish(f"已经绑定过了{config_steam.steam_tail_tone}")

    steam_name: str = ""
    avatar_url: str = ""

    try:
        async with http_client() as client:
            url = f"https://{get_steam_api_domain()}/ISteamUser/GetPlayerSummaries/v0002/?key=" + get_steam_key() + "&steamids=" + steam_id
            res = SafeResponse(await client.request(Request("GET", url, timeout=30)))

            if res.status_code != 200:
                logger.debug(f"{steam_id} 绑定失败，{res.status_code} {res.text}")
                await matcher.finish(f"{steam_id} 绑定失败，{res.status_code} {res.text}")

            players = json.loads(res.text)["response"]["players"]
            if players == []:
                logger.debug(f"{steam_id} 绑定失败，查无此人，请检查输入的id")
                await matcher.finish(f"{steam_id} 绑定失败，查无此人，请检查输入的id{config_steam.steam_tail_tone}")

            steam_name = players[0]['personaname']
            avatar_url = await resolve_avatar_url(steam_id, players[0].get('avatarfull', ''))

    except MatcherException:
        raise
    except Exception as e:
        logger.debug(f"{steam_id} 绑定失败，{e.args}")
        await matcher.finish(f"{steam_id} 绑定失败{config_steam.steam_tail_tone}，{e}")

    # 更新缓存
    steam_list[steam_id] = UserData(time=0, game_name="", nickname=steam_name)

    group_list[group_id]["user_list"].append(steam_id)
    if group_list[group_id].get("owned_game", False):
        await initialize_owned_games_baseline([steam_id])
    save_data()

    # 渲染发送绑定成功
    bind_img = None
    if avatar_url:
        bind_img = await render_bind_card(avatar_url, steam_name, steam_id)

    if bind_img:
        await matcher.finish(UniMessage.image(raw=bind_img))
    else:
        # 降级：有问题则发送纯文本
        await matcher.finish(
            f"Steam ID：{steam_id}\nSteam ID64：{steam_id}\nSteam Name：{steam_name}\n 绑定成功了{config_steam.steam_tail_tone}")


@steam_cmd.assign("del")
async def steam_del_handle(target: MsgTarget, matcher: Matcher, id: Match[str]):
    steam_id = str(id.result)
    if len(steam_id) != 17:
        try:
            steam_id = int(steam_id)
            steam_id += 76561197960265728
            steam_id = str(steam_id)
        except Exception as e:
            logger.debug(f"Steam 绑定出错，输入值：{steam_id}，错误：{e.args}")
            await matcher.finish(f"Steam ID格式错误{config_steam.steam_tail_tone}")
    steam_name: str = ""
    global group_list

    if str(target.id) not in group_list:
        await matcher.finish(f"本群不存在 Steam 绑定记录{config_steam.steam_tail_tone}")

    if steam_id not in group_list[str(target.id)]["user_list"]:
        await matcher.finish(f"本群尚未绑定该 Steam ID{config_steam.steam_tail_tone}")
    steam_name = steam_list[steam_id]["nickname"]

    try:
        group_list[str(target.id)]["user_list"].remove(steam_id)
    except Exception as e:
        logger.debug(f"删除steam id 失败，输入值：{steam_id}，错误：{e.args}")
        await matcher.finish(f"没有找到 Steam ID：{steam_id}{config_steam.steam_tail_tone}")
    save_data()
    await matcher.finish(f"Steam ID：{steam_id}\nSteam Name：{steam_name}\n 删除成功了{config_steam.steam_tail_tone}")


steam_cmd_scr = steam_cmd.dispatch("屏蔽")
steam_cmd_rec = steam_cmd.dispatch("恢复")


@steam_cmd_scr.handle()
@steam_cmd_rec.handle()
async def steam_clude_handle(target: MsgTarget, arp: Arparma, matcher: Matcher, game: Match[str]):
    global group_list, exclude_game
    handle = next(iter(arp.components))
    game_name = str(game.result)
    needs_save = str(target.id) not in group_list or str(target.id) not in exclude_game
    group_id = ensure_group_data(target)
    if needs_save:
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))
    if game_name == "":
        await matcher.finish(f"请输入要{handle}的完整游戏名称{config_steam.steam_tail_tone}")
    elif handle == "屏蔽":
        if game_name in exclude_game[group_id]:
            await matcher.finish(f"{game_name} 已经被屏蔽过了{config_steam.steam_tail_tone}")
        exclude_game[group_id].append(game_name)
    elif handle == "恢复":
        if game_name not in exclude_game[group_id]:
            await matcher.finish(f"{game_name} 没有被屏蔽过{config_steam.steam_tail_tone}")
        exclude_game[group_id].remove(game_name)
    exclude_game_file.write_text(json.dumps(exclude_game))
    await matcher.finish(f"{handle}游戏 {game_name} 完成{config_steam.steam_tail_tone}")


@steam_cmd.assign("排除列表")
async def steam_exclude_list_handle(target: MsgTarget):
    global group_list, exclude_game
    needs_save = str(target.id) not in group_list or str(target.id) not in exclude_game
    group_id = ensure_group_data(target)
    if needs_save:
        exclude_game_file.write_text(json.dumps(exclude_game))
        new_file_group.write_text(json.dumps(group_list))

    nodes = [
        CustomNode(
            uid=str(target.self_id),
            name=str(index + 1),
            content=UniMessage.text(game_name)
        )
        for index, game_name in enumerate(exclude_game[group_id])
    ]
    await UniMessage(Reference(nodes=nodes)).send()


@steam_cmd.assign("list")
async def steam_bind_list_handle(target: MsgTarget):
    try:
        nodes = [
            CustomNode(
                uid=str(target.self_id),
                name=str(index + 1),
                content=UniMessage.text(
                    f"Steam ID：{steam_id}\n昵称：{steam_list[steam_id]['nickname']}\n{'正在玩：' + steam_list[steam_id]['game_name'] if steam_list[steam_id]['game_name'] != '' else ''}")
            )
            for index, steam_id in enumerate(group_list[str(target.id)]["user_list"])
        ]
        await UniMessage(Reference(nodes=nodes)).send()
    except Exception as e:
        logger.debug(f"Steam 列表合并消息发送出错，错误：{e.args}")
        await UniMessage(f"本群尚未绑定任何 Steam ID，请先绑定{config_steam.steam_tail_tone}。").send()


@steam_cmd.assign("播报")
async def steam_on_handle(target: MsgTarget, status: Match[str]):
    if str(status.result) not in ("开启", "关闭"):
        await UniMessage(f"仅允许设置播报开启或关闭{config_steam.steam_tail_tone}").send(reply_to=True)
    else:
        global group_list
        group_id = ensure_group_data(target)
        group_list[group_id]["status"] = True if str(status.result) == "开启" else False
        save_data()
        await UniMessage(f"Steam 播报已{str(status.result)}{config_steam.steam_tail_tone}").send(reply_to=True)


@steam_cmd.assign("图片播报")
async def steam_image_handle(target: MsgTarget, status: Match[str]):
    if str(status.result) not in ("开启", "关闭"):
        await UniMessage(f"仅允许设置图片播报开启或关闭{config_steam.steam_tail_tone}").send(reply_to=True)
    else:
        global group_list
        group_id = ensure_group_data(target)
        group_list[group_id]["image"] = True if str(status.result) == "开启" else False
        save_data()
        await UniMessage(f"Steam 图片播报已{str(status.result)}{config_steam.steam_tail_tone}").send(reply_to=True)


@steam_cmd.assign("结束图片播报")
async def steam_stop_image_handle(target: MsgTarget, status: Match[str]):
    if str(status.result) not in ("开启", "关闭"):
        await UniMessage(f"仅允许设置结束图片播报开启或关闭{config_steam.steam_tail_tone}").send(reply_to=True)
    else:
        global group_list
        group_id = ensure_group_data(target)
        group_list[group_id]["stop_image"] = True if str(status.result) == "开启" else False
        save_data()
        await UniMessage(f"Steam 结束图片播报已{str(status.result)}{config_steam.steam_tail_tone}").send(reply_to=True)


@steam_cmd.assign("入库播报")
async def steam_owned_game_handle(target: MsgTarget, status: Match[str]):
    if str(status.result) not in ("开启", "关闭"):
        await UniMessage(f"仅允许设置入库播报开启或关闭{config_steam.steam_tail_tone}").send(reply_to=True)
    else:
        global group_list
        group_id = ensure_group_data(target)
        owned_game_enabled = str(status.result) == "开启"
        group_list[group_id]["owned_game"] = owned_game_enabled
        created = 0
        failed_steam_ids = []
        if owned_game_enabled:
            created, failed_steam_ids = await initialize_owned_games_baseline(group_list[group_id]["user_list"])
        save_data()
        baseline_text = f"，已建立 {created} 个游戏库基准"
        if failed_steam_ids:
            failed_names = [
                steam_list.get(steam_id, {}).get("nickname") or steam_id
                for steam_id in failed_steam_ids[:3]
            ]
            baseline_text += f"，{len(failed_steam_ids)} 个失败：{'、'.join(failed_names)}"
            if len(failed_steam_ids) > 3:
                baseline_text += " 等"
        await UniMessage(f"Steam 入库播报已{str(status.result)}{baseline_text if owned_game_enabled else ''}{config_steam.steam_tail_tone}").send(reply_to=True)


@steam_cmd.assign("喜加一")
async def steam_free_handle(target: MsgTarget, matcher: Matcher, action: Match[str]):
    if action.result:
        group_id = ensure_group_data(target)
        group_list[group_id]["xijiayi"] = True if str(action.result) == "订阅" else False
        save_data()
        await matcher.finish(f"steam 喜加一 已{str(action.result)}{config_steam.steam_tail_tone}")
    res = await get_free_games_info(target)
    if res:
        await matcher.finish(res)


@steam_cmd.assign("墙")
async def steam_wall(matcher: Matcher, user: Match[str]):
    try:
        screenshot = await get_steam_playtime(str(user.result))
        await UniMessage.image(raw=screenshot).send()
    except Exception as e:
        logger.warning(f"获取 Steam 游戏时长拼图出错：{e.args}")
        await UniMessage.text(f"获取 Steam 游戏时长拼图出错{config_steam.steam_tail_tone} ：{e.args}").send()
    await matcher.finish()


@steam_cmd.assign("打折订阅")
async def steam_discounted_games_bind(target: MsgTarget, matcher: Matcher, game: Match[str]):
    global game_discounted_subscribe
    group_id = ensure_group_data(target)
    game_id = str(game.result)
    if group_id in game_discounted_subscribe.get(game_id, []):
        await matcher.finish(f"已订阅过 {config_steam.steam_tail_tone}", reply_message=True)
    try:
        info = await get_discounted_games_info(target, game_id)
    except Exception as e:
        await matcher.finish(f"订阅出错了{config_steam.steam_tail_tone}, {e.args}")

    if not info:
        await matcher.finish(f"免费或未推出游戏不能订阅{config_steam.steam_tail_tone}", reply_message=True)
    else:
        game_discounted_subscribe.setdefault(game_id, []).append(group_id)
        save_data()
        if isinstance(info, str):
            await matcher.finish(f"已订阅折扣提醒{config_steam.steam_tail_tone},\n{info}", reply_message=True)
        else:
            await matcher.finish(f"该游戏正在打折{config_steam.steam_tail_tone}", reply_message=True)


@steam_cmd.assign("打折退订")
async def steam_discounted_games_del(target: MsgTarget, matcher: Matcher, game: Match[str]):
    global game_discounted_subscribe
    group_id = str(target.id)
    game_id = str(game.result)
    if game_id not in game_discounted_subscribe or group_id not in game_discounted_subscribe[game_id]:
        await matcher.finish(f"未订阅过 {config_steam.steam_tail_tone}", reply_message=True)
    game_discounted_subscribe[game_id].remove(group_id)
    if not game_discounted_subscribe[game_id]:
        del game_discounted_subscribe[game_id]
        if game_id in game_discounted_cache:
            game_discounted_cache.remove(game_id)
    save_data()
    await matcher.finish(f"已退订折扣提醒{config_steam.steam_tail_tone}", reply_message=True)


steam_admin_cmd = on_alconna(
    steam_command_alc,
    priority=config_steam.steam_command_priority,
    permission=SUPERUSER
)


@steam_admin_cmd.assign("失联群列表")
async def steam_inactive_groups_handle(target: MsgTarget):
    unimsg = await get_inactive_groups_list(target)
    await unimsg.send()


@steam_admin_cmd.assign("失联群清理")
async def steam_clear_inactive_groups_handle(target: MsgTarget):
    unimsg = await clear_inactive_groups_list(target)
    await unimsg.send()


@driver.on_startup
async def _init_steam_subscribe_jobs():
    times = config_steam.steam_subscribe_time

    for idx, t in enumerate(times):
        hour_str, minute_str = t.split(":")
        hour = int(hour_str)
        minute = int(minute_str)

        job_xijiayi_id = f"steam_xijiayi_subscribe_{idx}"
        logger.info(f"注册 steam 订阅定时任务: {job_xijiayi_id} -> {hour:02d}:{minute:02d}")
        job_discounted_id = f"steam_discounted_subscribe_{idx}"
        logger.info(f"注册 steam 订阅定时任务: {job_discounted_id} -> {hour:02d}:{minute:02d}")

        scheduler.add_job(
            steam_subscribe,
            "cron",
            hour=hour,
            minute=minute,
            id=job_xijiayi_id,
            replace_existing=True,
        )
        scheduler.add_job(
            sbeam_subscribe,
            "cron",
            hour=hour,
            minute=minute,
            id=job_discounted_id,
            replace_existing=True,
        )


async def steam_subscribe():
    logger.info("steam定时尝试获取推送喜加一")
    await get_free_games_info()
    logger.info("steam定时尝试获取推送喜加一结束")


async def sbeam_subscribe():
    logger.info("steam定时尝试获取推送打折")
    await get_discounted_games_info()
    logger.info("steam定时尝试获取推送打折结束")
