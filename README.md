<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-steam-game-status

_✨ 在群内播报 Steam 游戏状态的 Nonebot 插件 ✨_


<a href="./LICENSE">
    <img src="https://camo.githubusercontent.com/9add6b327f8f49a33a5a0e485009666d2dd8cb698d30333b4e4467717a851d52/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4c6963656e73652d47504c25323076332532422d626c75652e737667" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot_plugin_steam_game_status">
    <img src="https://img.shields.io/pypi/v/nonebot_plugin_steam_game_status.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">

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
<summary>更新</summary>

    pip install nonebot-plugin-steam-game-status --upgrade
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_steam_game_status"]

</details>

## ⚙️ 配置

获取 [steam_web_key](https://steamcommunity.com/dev/apikey)

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 类型 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| steam_web_key | 是 | 无 | str 或 list | Steam Api Key |
| steam_command_priority | 否 | 5 | int | 事件处理函数优先级 |
| steam_proxy | 否 | None | str | 代理 |

steam_proxy 示例
```bash
# .env.xxx
steam_proxy="http://ip:port"
```

单个 steam key 配置示例
```bash
# .env.xxx
steam_web_key=123456789QWERTYUII123456789

# or 引号包裹
steam_web_key="123456789QWERTYUII123456789"

# 若字符串形式key绑定失败，请改写为以下多key配置
```

多个 steam key 配置示例
```bash
# .env.xxx
steam_web_key='[
    "123456789QWERTYUII123456789",
    "123456789",
    "987654321",
]'

# or 无引号包裹
steam_web_key=["123456789QWERTYUII123456789","123456789","987654321"]


```

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
| steam列表/steam绑定列表 | 否 | 群聊 | 超管/群管 |       管理员命令        |    
| steam播报开启/steam播报打开 | 否 | 群聊 | 超管/群管 |       管理员命令        |    
| steam播报关闭/steam播报停止 | 否 | 群聊 | 超管/群管 |       管理员命令        |  

## 创意来源

群友的 koishi bot 的该效果插件

## 注意事项

1.不支持播报非 Steam 游戏

2.不支持播报 Steam 隐身状态下进行的游戏

## 更新记录
2024.02.29
1. 新增游戏中文名播报，感谢 [6DDUU6](https://github.com/6DDUU6) 的 [PR](https://github.com/nek0us/nonebot_plugin_steam_game_status/pull/18)
2. 顺应 Nonebot 规范，缓存文件迁移至用户目录下，详见 [plugin-localstore](https://github.com/nonebot/plugin-localstore)
3. 调整数据结构，节省 key 
4. 变更原缓存记录从 每次读取文件 更改为 持续在内存中