# nonebot_plugin_steam_game_status
在群内播报steam游戏状态的Nonebot插件
==========

## 安装

```bash
pip install nonebot_plugin_steam_game_status
```

## 配置
### 获取steam_web_api_key

获取steam_web_key[steam_web_key](https://steamcommunity.com/dev/apikey)

配置文件内填写：
```bash
steam_web_key="your key"
```
### 获取Steam ID

    打开 Steam 客户端，点击<商店> <库> <社区> 右侧的个人昵称，
    在打开的页面中，右键 -> 复制网页URL，
    任意找个地方粘贴，“profiles” 后两个 “/” 之间的数字即为个人 ID，

## 指令表

| 指令 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|
| steam绑定/添加/.add | 否 | 群聊 | 后加个人Steam ID |    
|:-----:|:----:|:----:|:----:|
| steam解绑/删除/.del | 否 | 群聊 | 后加个人Steam ID |   

## 创意来源

群友的koishi bot的该效果插件