"""Steam 状态播报的纯状态逻辑。

本模块不依赖 NoneBot，便于验证状态转换与持久化顺序。
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple


UserState = Dict[str, Any]
ReportedState = Dict[str, Dict[str, UserState]]


class HandledStatePersistenceError(Exception):
    """事件已在内存中标记但无法持久化；内存状态已被恢复。"""


@dataclass(frozen=True)
class StatusTransition:
    action_type: Optional[str]
    pending_stop_count: int
    clear_handled: bool = False
    reason: str = ""


def is_valid_reported_state_record(record: object) -> bool:
    """校验持久化的已处理状态记录，避免坏数据卡住单个用户。"""
    return (
        isinstance(record, dict)
        and type(record.get("time")) is int
        and isinstance(record.get("game_name"), str)
        and isinstance(record.get("nickname"), str)
        and isinstance(record.get("game_id"), str)
    )


def sanitize_reported_state(groups: object) -> Tuple[ReportedState, List[Tuple[str, str]]]:
    """保留合法记录，返回被丢弃的 ``(group_id, steam_id)``。"""
    if not isinstance(groups, dict):
        raise ValueError("groups 不是对象")

    cleaned: ReportedState = {}
    invalid_records: List[Tuple[str, str]] = []
    for group_id, group_state in groups.items():
        if not isinstance(group_id, str) or not isinstance(group_state, dict):
            raise ValueError("群状态不是以群号为键的对象")
        cleaned_group: Dict[str, UserState] = {}
        for steam_id, user_data in group_state.items():
            if isinstance(steam_id, str) and is_valid_reported_state_record(user_data):
                cleaned_group[steam_id] = dict(user_data)
            else:
                invalid_records.append((str(group_id), str(steam_id)))
        if cleaned_group:
            cleaned[group_id] = cleaned_group
    return cleaned, invalid_records


def build_conservative_reported_state(
    steam_list: Dict[str, UserState],
    group_list: Dict[str, Dict[str, Any]],
    exclude_game: Dict[str, List[str]],
    exclude_game_default: Iterable[str],
) -> ReportedState:
    """按现有原始观测建立保守 handled 基线，避免升级/恢复后批量补报。"""
    state: ReportedState = {}
    for group_id, group_data in group_list.items():
        group_state: Dict[str, UserState] = {}
        excluded = exclude_game.get(group_id, list(exclude_game_default))
        for steam_id in group_data.get("user_list", []):
            user_data = steam_list.get(steam_id)
            if (
                isinstance(steam_id, str)
                and user_data
                and isinstance(user_data.get("game_name"), str)
                and user_data["game_name"]
                and user_data["game_name"] not in excluded
            ):
                group_state[steam_id] = dict(user_data)
        if group_state:
            state[group_id] = group_state
    return state


def build_steam_id_to_groups(
    group_list: Dict[str, Dict[str, Any]],
) -> Dict[str, List[str]]:
    """建立状态轮询索引。

    ``inactive_groups`` 只记录上一次投递时未找到目标 bot 的群，不能作为
    轮询过滤条件：bot 恢复后若无人发送 Steam 命令，过滤会让该群永久漏播。
    因此这里仅以群播报开关和绑定关系决定是否查询。
    """
    steam_id_to_groups: Dict[str, List[str]] = {}
    for group_id, group_data in group_list.items():
        if not group_data.get("status", False):
            continue
        for steam_id in group_data.get("user_list", []):
            if isinstance(steam_id, str):
                steam_id_to_groups.setdefault(steam_id, []).append(group_id)
    return steam_id_to_groups


def decide_status_transition(
    *,
    is_playing: bool,
    game_name: str,
    game_id: str,
    reported: Optional[UserState],
    excluded_games: Iterable[str],
    pending_stop_count: int,
    stop_confirmations: int,
) -> StatusTransition:
    """判定某群某用户的下一步状态转换，不处理网络或持久化。"""
    excluded = set(excluded_games)
    if is_playing and game_name in excluded:
        return StatusTransition(None, 0, reason="excluded_game")
    if not is_playing and reported and reported.get("game_name") in excluded:
        return StatusTransition(None, 0, clear_handled=True, reason="legacy_excluded_stop")
    if is_playing and reported and str(reported.get("game_id", "")) == game_id:
        return StatusTransition(None, 0, reason="same_game")
    if not is_playing and not reported:
        return StatusTransition(None, 0, reason="no_reported_game")
    if not is_playing:
        next_count = pending_stop_count + 1
        if next_count < stop_confirmations:
            return StatusTransition(None, next_count, reason="await_stop_confirmation")
        return StatusTransition("stop", 0)
    return StatusTransition("start" if not reported else "switch", 0)


def delivery_snapshot_is_current(
    group_data: Optional[Dict[str, Any]],
    steam_id: str,
    expected_reported: Optional[UserState],
    actual_reported: Optional[UserState],
    expected_generation: int,
    actual_generation: int,
) -> bool:
    """判断解绑、重绑或开关后，一个在途投递任务是否仍有效。"""
    return bool(
        group_data
        and group_data.get("status", False)
        and steam_id in group_data.get("user_list", [])
        and expected_generation == actual_generation
        and expected_reported == actual_reported
    )


def mark_group_event_handled(
    reported_state: ReportedState,
    group_id: str,
    steam_id: str,
    action_type: str,
    current_game: UserState,
) -> None:
    """消费一个事件；调用方负责并发保护和持久化。"""
    group_state = reported_state.setdefault(group_id, {})
    if action_type == "stop":
        group_state.pop(steam_id, None)
        if not group_state:
            reported_state.pop(group_id, None)
    else:
        group_state[steam_id] = dict(current_game)


def persist_handled_event(
    reported_state: ReportedState,
    group_id: str,
    steam_id: str,
    action_type: str,
    current_game: UserState,
    persist: Callable[[], None],
) -> None:
    """先消费并落盘；持久化失败时恢复内存状态并抛出原异常。"""
    group_existed = group_id in reported_state
    previous_group = dict(reported_state.get(group_id, {}))
    mark_group_event_handled(reported_state, group_id, steam_id, action_type, current_game)
    try:
        persist()
    except Exception:
        if group_existed:
            reported_state[group_id] = previous_group
        else:
            reported_state.pop(group_id, None)
        raise


async def persist_then_send(
    reported_state: ReportedState,
    group_id: str,
    steam_id: str,
    action_type: str,
    current_game: UserState,
    persist: Callable[[], None],
    send: Callable[[], Awaitable[None]],
) -> None:
    """严格保证 handled 已成功持久化后才调用发送。"""
    try:
        persist_handled_event(
            reported_state, group_id, steam_id, action_type, current_game, persist
        )
    except Exception as error:
        raise HandledStatePersistenceError() from error
    await send()
