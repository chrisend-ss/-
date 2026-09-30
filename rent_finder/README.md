# 杭州租房筛选器（rent-finder）

独立分支，不改网易云抓取功能的 main。

## 你的固定找房条件

- 工作地点：杭州地铁 2 号线「钱江世纪城」
- **只往杭州主城区方向**
- 搜索顺序：钱江路 → 庆春广场 → 庆菱路 → 建国北路 → 中河北路 → 凤起路 → 武林门
- 整租优先
- 面积 >= 70㎡
- 目标租金约 3000 元/月
- 硬上限 3300 元/月
- 优先 2 号线直达
- 已知地铁步行距离时要求 <= 1000m
- 自动排除合租、办公室、商铺、写字楼，并去重

## 已整合的三个上游项目

1. **LianjiaRentSpider-Visualization**：链家 HTML 抓取 / SQLite / 分析思路
2. **BeiKeZuFangSpider**：Scrapy 贝壳抓取 / CSV / MongoDB 字段
3. **rentHouseSpider**：requests + BeautifulSoup / MongoDB 字段

三者保留为 git submodule，当前主程序使用新的 adapter 统一字段，不要求运行老项目的旧 Python 环境。

## 现在已经实现

主入口：

```text
rent_finder/collect.py
```

运行时会自动访问杭州链家的站点地图，寻找你的目标站点「地铁租房」入口，因此**不再需要手工粘贴每个站的 URL**。

随后程序会：

1. 按目标站点抓取链家租房列表；
2. 每站默认抓前 3 页，并控制请求间隔；
3. 统一租金、面积、户型、整租类型、地铁站、链接等字段；
4. 合并贝壳旧 CSV / rentHouseSpider JSON（如有）；
5. 去重；
6. 严格筛选面积 >=70㎡、租金 <=3300；
7. 按面积、租金接近 3000、站点顺序、地铁步行距离综合排序；
8. 输出最终候选 CSV。

## 使用

```bash
git clone -b rent-finder --recurse-submodules https://github.com/chrisend-ss/-.git
cd -
python -m pip install -r requirements-rent.txt
python -m rent_finder.collect
```

最终看这个：

```text
rent_finder/output/matches.csv
```

同时保留：

```text
rent_finder/output/all.json
rent_finder/output/matches.json
rent_finder/output/lianjia_sources.json
```

### 合并旧贝壳 CSV

```bash
python -m rent_finder.collect --beike-csv ExportData/export_xxx.csv
```

### 合并 rentHouseSpider JSON

```bash
python -m rent_finder.collect --fang-json houses.json
```

### 手工补充链家入口

如果自动发现某个站失效，可复制 `sources.example.json` 修改后：

```bash
python -m rent_finder.collect --sources rent_finder/sources.json
```

## 网络和站点规则

- 不绕过验证码或登录风控。
- 不做高频请求，默认页面间隔 2 秒。
- 网站 DOM 改版时只更新 adapter，不影响你的筛选规则。
- 如果站点明确限制自动抓取，应停止该来源并改用允许的数据获取方式。

## 下一阶段

- 新旧房源差异比较（只通知新出现的房源）
- GitHub Actions / 服务器定时执行
- 将最新候选房源推送给 ChatGPT 或其他通知入口
