<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-steam-game-status

_✨ 在群内播报 Steam 游戏状态的 Nonebot 插件 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/nek0us/nonebot_plugin_steam_game_status.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot_plugin_steam_game_status">
    <img src="https://img.shields.io/pypi/v/nonebot_plugin_steam_game_status.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>


## 📖 介绍

在群内播报群友的 Steam 游戏状态

## 💿 安装

<details>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-steam-game-status

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-steam-game-status
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-steam-game-status
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-steam-game-status
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-steam-game-status
</details>
<details>
<summary>uv</summary>

    uv add nonebot-plugin-steam-game-status
</details>
<details>
<summary>更新</summary>

    pip install nonebot-plugin-steam-game-status --upgrade
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = [
        "nonebot_plugin_steam_game_status"
        ]

</details>

## ⚙️ 配置

获取 [steam_web_key](https://steamcommunity.com/dev/apikey)

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 类型 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| steam_web_key | 是 | 无 | str 或 list | Steam Api Key |
| steam_isthereanydeal_key | 否 | 无 | str 或 list | isthereanydeal Api Key 查询史低 |
| steam_command_priority | 否 | 5 | int | 事件处理函数优先级 |
| steam_interval | 否 | 1 | int | steam查询间隔，单位分钟 |
| steam_tail_tone | 否 | "" | str | bot尾音口癖 |
| steam_proxy | 否 | None | str | 代理 |
| steam_api_proxy | 否 | None | str | Steam API 反代域名 |
| steam_store_proxy | 否 | None | str | Steam Store 反代域名 |
| steam_link_enabled | 否 | true | bool | 链接识别全局开关 |
| steam_area_game | 否 | false | bool/list | 识别其它区游戏 |
| steam_link_r18_game | 否 | false | bool/list | 识别r18游戏 |
| steam_tail_tone | 否 | "" | str | bot尾音 |
| steam_subscribe_time | 否 | ["08:00"] | str/List[str] | 喜加一订阅检索推送时间 |
---
steam_tail_tone 示例
```.env
# .env.xxx
steam_tail_tone=" 喵"
```

steam_subscribe_time 示例
```.env
# .env.xxx
steam_subscribe_time="20:30"
# 或者多个时间
steam_subscribe_time=["08:00","20:30"]
```

steam_proxy 示例
```.env
# .env.xxx
steam_proxy="http://ip:port"
```

steam_api_proxy 和 steam_store_proxy 反代域名配置示例
```.env
# .env.xxx
# 用于替代 api.steampowered.com
steam_api_proxy="api.proxy.example.com"

# 用于替代 store.steampowered.com
steam_store_proxy="store.proxy.example.com"
```

单个 steam key 配置示例 (`steam_isthereanydeal_key` 同理)
```.env
# .env.xxx
steam_web_key=123456789QWERTYUII123456789

# or 引号包裹
steam_web_key="123456789QWERTYUII123456789"

# 若字符串形式key绑定失败，请改写为以下多key配置
```

多个 steam key 配置示例 (`steam_isthereanydeal_key` 同理)
```.env
# .env.xxx
# 注意最后一行key后面不能有逗号
steam_web_key='[
    "123456789QWERTYUII123456789",
    "123456789",
    "987654321"
]'

# or 无引号包裹
steam_web_key=["123456789QWERTYUII123456789","123456789","987654321"]

```

steam_area_game 识别其它区游戏
```.env
# .env.xxx
# 使用布尔值开启或关闭
steam_area_game=false

# 使用群聊/私聊白名单列表
steam_area_game='["群号1","群号2"]'
# or 
steam_area_game='
[
    "群号1",
    "群号2"
]'

```


steam_link_r18_game 识别r18游戏
```.env
# .env.xxx
# 使用布尔值开启或关闭
steam_link_r18_game=false

# 使用群聊/私聊白名单列表
steam_link_r18_game='["群号1","群号2"]'
# or 
steam_link_r18_game='
[
    "群号1",
    "群号2"
]'

```


### 插件依赖于 客户端驱动器
请确保安装了客户端驱动器,如
```bash
# 使用官方命令
nb driver install aiohttp
# 或
pip install nonebot2[aiohttp]
# 或
pip install nonebot2[httpx]
 ```
并配置`DRIVER=~aiohttp`等

### 史低查询依赖于 IsThereAnyDeal
1. 首先打开并登录 [IsThereAnyDeal](https://isthereanydeal.com/)，可使用steam登录
2. 访问 [app页](https://isthereanydeal.com/apps/) 并注册app
3. 注册完成后，右侧会出现`API Keys`，点击key即可复制
4. `.env.xxx`配置文件种添加steam_isthereanydeal_key

## 🎉 使用
### 获取SteamID64
    Steam 桌面网站或桌面客户端：点开右上角昵称下拉菜单，点击账户明细，即可看到 Steam ID
    Steam 应用：点击右上角头像，点击账户明细，即可看到 Steam ID
### 获取Steam好友代码
    Steam 桌面网站或桌面客户端：点开导航栏 好友 选项卡，点击添加好友，即可看到 Steam 好友代码
    Steam 应用：点击右上角头像，点击好友，点击添加好友，即可看到 Steam 好友代码
### 指令表
| 指令 | 需要@ | 范围 | 权限 |         说明         |
|:-----:|:----:|:----:|:----:|:------------------:|
| steam绑定/steam添加/steam.add | 否 | 群聊 | 群员 | 后加个人SteamID64或好友代码 |    
| steam解绑/steam删除/steam.del | 否 | 群聊 | 群员 |   后加个人SteamID64    |   
| steam列表/steam绑定列表 | 否 | 群聊 | 群员 |       展示群内播报列表        |    
| steam屏蔽 | 否 | 群聊 | 群员 |       后加完整游戏名称        |    
| steam恢复 | 否 | 群聊 | 群员 |       后加完整游戏名称         |    
| steam排除列表 | 否 | 群聊 | 群员 |       展示屏蔽的游戏列表        |    
| steam播报开启/steam播报打开 | 否 | 群聊 | 群员 |       开启本群播报        |    
| steam播报关闭/steam播报停止 | 否 | 群聊 | 群员 |       关闭本群播报        |  
| steam喜加一 | 否 | 群聊 | 群员 |       主动获取喜加一资讯        |    
| steam喜加一订阅 | 否 | 群聊 | 群员 |       开启本群喜加一推送        |    
| steam喜加一退订 | 否 | 群聊 | 群员 |       关闭本群喜加一推送        |  
| steam折扣订阅 | 否 | 群聊 | 群员 |       后加游戏id，开启本群折扣推送        |    
| steam折扣退订 | 否 | 群聊 | 群员 |       后加游戏id，开启本群折扣推送        |    
| steam墙 | 否 | 群聊 | 群员 |       后加用户id，展示steam游玩时长拼图        |  
| steam失联群列表 | 否 | 群聊/私聊 | 超管 |       展示与bot失联群聊列表        |    
| steam失联群清理 | 否 | 群聊/私聊 | 超管 |       从存储中删除失联群聊相关绑定订阅(慎用)        |  
| 任意steam商店链接 | 否 | 群聊/私聊 | 群员/好友 |       获取游戏信息        |  

### 默认屏蔽游戏/工具名
["Wallpaper Engine：壁纸引擎","虚拟桌宠模拟器","OVR Toolkit","OVR Advanced Settings","OBS Studio","VTube Studio","Live2DViewerEX","Blender","LIV"]

> 目前建议手动添加 `Dead Lock` ，待发售完善后再移除，否则容易刷屏


## 创意来源

群友的 koishi bot 的该效果插件

## 注意事项

1. 不支持播报非 Steam 游戏
2. 不支持播报 Steam 隐身状态下进行的游戏
3. 在屏蔽游戏间切换的非屏蔽游戏也不会播报
4. 屏蔽游戏列表以群区分管理
5. 0.2版本已知问题：多个同适配器bot（如多个OneBot）目前还存在选择错误而推送群消息失败的问题，后续修复



## 更新记录
2025.11.30 0.3.0
1. 添加steam游戏时长拼图获取
2. 添加bot失联群管理(慎用)
3. 添加游戏折扣订阅
4. 添加多时间订阅能力
5. 添加steam域名反代
6. 修复部分问题


2025.09.18 0.2.6
1. 兼容回 pydantic v1 版本
2. 去除工具插件依赖，添加回 OneBot 依赖
3. 修复新装插件处理文件bug


2025.09.15 0.2.3
1. 添加喜加一及其订阅功能
2. 增加游戏史低显示
3. 修复屏蔽游戏指令对带空格的游戏名不生效的问题
4. 修复OneBot适配器推送不在群聊的消息问题（多bot问题）


2025.09.04 0.2.1
1. 修复部分预发布游戏没有标签导致识别失败
2. 修复跨平台多适配器下消息推送失败
3. 0.2版本已知问题：多个同适配器bot（如多个OneBot）目前还存在选择错误而推送群消息失败的问题，后续修复


2025.08.21 0.2.0
1. 改用alconna插件实现，支持跨平台适配器
2. 为链接识别增加白名单配置
3. 使用驱动器实现，解决代理参数和依赖问题
4. 小幅度优化数据存储，更新后会自动进行迁移


2025.07.27
1. 修复onebot适配器故障导致无法推送消息
2. 优化游戏链接识别显示效果
3. 修复`httpx 0.28.1`版本代理参数

2024.10.21
1. 修复用户id数据异常


2024.09.16
1. 优化`steam链接识别`，降低失败可能性
2. 增加`steam列表`展示当前游戏
3. 优化重启后不再播报仍在继续的游戏


2024.06.30
1. 优化游戏中文名获取


2024.06.27
1. 修复添加新群时数据未保存的bug


2024.06.26
1. 优化播报后数据同步优先级
2. 添加链接识别功能
3. 优化日志等级


2024.06.23
1. 添加`屏蔽游戏`相关功能
2. 修复steam列表问题


2024.04.28
1. steam列表 合并消息优化


2024.02.29
1. 新增游戏中文名播报，感谢 [6DDUU6](https://github.com/6DDUU6) 的 [PR](https://github.com/nek0us/nonebot_plugin_steam_game_status/pull/18)
2. 顺应 Nonebot 规范，缓存文件迁移至用户目录下，详见 [plugin-localstore](https://github.com/nonebot/plugin-localstore)
3. 调整数据结构，节省 key 
4. 变更原缓存记录从 每次读取文件 更改为 持续在内存中