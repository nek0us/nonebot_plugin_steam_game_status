from setuptools import setup, find_packages 

with open("README.md", "r",encoding="utf-8") as readme_file:
    readme = readme_file.read()

requirements = ["nonebot2","nonebot-adapter-onebot","nonebot-plugin-apscheduler","httpx"] # 这里填依赖包信息

setup(
    name="nonebot_plugin_steam_game_status",
    version="0.0.6",
    author="nek0us",
    author_email="nekouss@gmail.com",
    description="在群内播报steam游戏状态的Nonebot插件",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/nek0us/nonebot_plugin_steam_game_status",
    packages=find_packages(),
    # Single module也可以：
    # py_modules=['timedd']
    install_requires=requirements,
    classifiers=[
	"Programming Language :: Python :: 3.9",
	"License :: OSI Approved :: MIT License",
    ],
)