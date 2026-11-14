# AnimeList v4.4

AnimeList 是一个面向 Bangumi 用户的 Windows 桌面番剧榜单与追番管理工具，基于 Python、pywebview 和本地归档数据构建。

从 [Releases](https://github.com/crimsonAries/AnimeList/releases) 下载 `AnimeList_v4.4-full-win64.zip`，解压后直接运行 `AnimeList_v4.exe`。完整包已包含截止 2026-11-10 的本地榜单数据，无需首次下载归档。仓库只提供源码，程序与数据统一通过 Releases 分发。

## 功能

- 综合排名、评分排名、热度排名三张季度榜单
- 已看 / 追更 / 完成率统计
- 作品详情：简介、标签、制作人员、角色声优
- 详情页人物搜索与标记：主役作品红色实线、配角/客串红色虚线
- 六维面板与详细数据可独立开关，提示框底部显示较上周评分变动与热度增长
- 新番时间表：自动更新、播出时间编辑、按周几折叠
- 补番计划：拖拽添加、推荐一部/十部
- 支持 Bangumi 用户追番状态同步

## 环境要求

- Windows 10 / 11 x64
- Microsoft Edge WebView2 Runtime
- Python 3.12（仅源码运行或自行打包时需要）

## 源码运行

```powershell
git clone https://github.com/crimsonAries/AnimeList.git
cd AnimeList

python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt

.\.venv\Scripts\python main.py
```

## 构建 Windows exe

```powershell
.\.venv\Scripts\pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物位于 `dist\AnimeList_v4.exe`。如在新目录运行，请把 `date\` 数据目录一并复制过去。

## 发布完整包

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\package_release.ps1
```

生成 `dist\AnimeList_v4.4-full-win64.zip`，包含 exe、清洁后的本地数据、README、LICENSE 和第三方声明。

## 数据说明

- 榜单、人物与角色数据来自 [bangumi/Archive](https://github.com/bangumi/Archive)。
- 新番排期数据来自 Bangumi 日历与 Yuc.wiki。
- 仓库本身不包含榜单数据、用户观看记录或个人补番计划；完整数据包仅随 GitHub Release 发布。
- 使用完整包时数据已就绪；源码运行时，首次启动或点击“更新数据”会下载约 450 MB 的归档包，并在软件同目录生成 `date/`。
- 完整包中的 `date/local_data.json` 已移除个人补番计划与手动排期，`app_state.json` 已移除用户名。
- 本项目与 Bangumi 官方无隶属关系；数据版权归 Bangumi 及贡献者所有。

## 目录

```text
main.py                 Python 主程序与后端接口
index.html              前端界面
build.ps1               一键打包 exe
package_release.py      生成带清洁数据的完整发布包
package_release.ps1     完整发布包快捷脚本
requirements.txt        运行时依赖
requirements-dev.txt    开发/打包依赖
bgm.ico                 项目图标
date/                   本地运行时数据（不提交）
dist/                   打包产物（不提交）
```

## 许可证

本项目使用 **GNU General Public License v3.0** 开源，详见 [LICENSE](LICENSE)。

Copyright (C) 2026 AnimeList contributors

## 第三方组件

依赖、运行时组件与数据来源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
