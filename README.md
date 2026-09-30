# 网易云抓取功能

把 **抖音热歌榜** 自动匹配到网易云音乐，并加入你指定的网易云歌单。

## 功能

- 自动读取抖音热歌榜（默认 Top 50）
- 按「歌曲名 + 歌手 + 时长」在网易云搜索匹配
- 自动规避明显的 DJ、伴奏、翻唱、加速等错误版本
- 读取目标网易云歌单，已有歌曲不重复添加
- 默认只新增，不会因为歌曲掉出抖音榜单就删除旧歌
- 匹配置信度不足时跳过，不乱加
- GitHub Actions 云端自动运行，不依赖本地电脑开机
- 每次同步生成报告，可在 Actions 日志/Artifact 查看

## 默认运行时间

GitHub Actions 默认每天运行两次：

- 新加坡/北京时间 12:00
- 新加坡/北京时间 18:00

也可以在 GitHub 的 **Actions → 抖音热歌同步到网易云 → Run workflow** 手动运行。

## 第一次配置

### 1. 找到网易云目标歌单 ID

打开网易云网页版的目标歌单。

地址一般类似：

```
https://music.163.com/#/playlist?id=123456789
```

其中 `123456789` 就是歌单 ID。

### 2. 获取网易云 Cookie

登录网易云网页版后，在浏览器开发者工具中复制请求里的完整 `Cookie`。

至少应包含登录态字段（通常有 `MUSIC_U`，并建议包含 `__csrf`）。

> ⚠️ Cookie 相当于登录凭据。不要发到 Issue、README、聊天截图或提交到仓库代码。

### 3. 添加 GitHub Actions Secrets

进入当前仓库：

**Settings → Secrets and variables → Actions → New repository secret**

创建：

| Secret | 内容 |
| --- | --- |
| `NETEASE_COOKIE` | 网易云网页版完整 Cookie |
| `NETEASE_PLAYLIST_ID` | 可选；默认已设为 `18422386676` |

这个仓库即使是公开仓库，Actions Secrets 也不会显示在代码里。

## 手动运行

进入：

**Actions → 抖音热歌同步到网易云 → Run workflow**

可选择抓取 Top 10 / 30 / 50 / 100。

## 本地运行（可选）

```bash
python -m pip install -r requirements.txt

export NETEASE_COOKIE='你的网易云Cookie'
export NETEASE_PLAYLIST_ID='18422386676'
export TOP_N=50

python sync.py
```

Windows PowerShell：

```powershell
$env:NETEASE_COOKIE="你的网易云Cookie"
$env:NETEASE_PLAYLIST_ID="18422386676"
$env:TOP_N="50"
python sync.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | ---: | --- |
| `NETEASE_COOKIE` | 必填 | 网易云登录 Cookie |
| `NETEASE_PLAYLIST_ID` | `18422386676` | 写入的歌单 ID；可覆盖 |
| `TOP_N` | `50` | 抖音榜单取前多少首 |
| `MATCH_THRESHOLD` | `0.68` | 匹配阈值，越高越保守 |
| `DRY_RUN` | `false` | true 时只匹配，不真正加歌 |
| `SYNC_MODE` | `append` | 当前仅支持 append，只新增不删除 |

## 匹配逻辑

每一首抖音热歌会在网易云搜索多个候选版本，并根据以下信息综合判断：

1. 歌名相似度
2. 歌手相似度
3. 歌曲时长接近程度
4. 是否出现 DJ / 伴奏 / 翻唱 / Cover / 加速 / 慢速等版本词

只有达到匹配阈值才会写入歌单。

## 安全说明

- 本项目不会把网易云 Cookie 保存到仓库文件。
- 不要把 `NETEASE_COOKIE` 写进 `.env` 后提交。
- Cookie 失效后，只需要更新 GitHub Secret，不需要修改代码。
- 网易云和抖音接口可能调整；如果某天同步失败，可通过 Actions 日志判断是数据源、登录态还是匹配接口发生变化。

## 后续扩展

预留的方向：

- 王焓直播「古风热歌池」
- 男声适配筛选
- 新上榜歌曲优先级
- 榜单升降趋势
- 直播试唱池
- 自动输出每日新增歌曲报告

