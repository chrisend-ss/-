# 杭州租房筛选器（rent-finder）

独立分支，不改网易云抓取功能的 main。

## 目标条件

- 工作地点：杭州地铁 2 号线「钱江世纪城」
- 方向：只往杭州主城区方向
- 站点顺序：钱江路 → 庆春广场 → 庆菱路 → 建国北路 → 中河北路 → 凤起路 → 武林门
- 整租优先
- 面积 >= 70㎡
- 目标租金约 3000 元/月
- 硬上限 3300 元/月
- 优先 2 号线直达
- 已知地铁步行距离时要求 <= 1000m
- 自动排除合租、办公室、商铺、写字楼，并去重

## 三个上游项目

1. **LianjiaRentSpider-Visualization**
   - 链家 HTML 抓取、SQLite、数据分析
2. **BeiKeZuFangSpider**
   - Scrapy 贝壳抓取、CSV/MongoDB
3. **rentHouseSpider**
   - requests + BeautifulSoup、MongoDB、基础分析

三者保留为 git submodule，当前主程序只提取可复用思路和字段，不直接依赖老环境运行。

## 现在已经能做什么

主入口：`rent_finder/collect.py`

它可以：

1. 抓取你配置的链家地铁站租房页面；
2. 自动翻页；
3. 把三个来源统一成同一字段；
4. 按你的价格、面积、方向、整租条件过滤；
5. URL/房源特征去重；
6. 按「面积 + 租金接近3000 + 站点距离 + 步行距离」排序；
7. 输出 JSON 和 Excel 可直接打开的 UTF-8 BOM CSV。

## 第一次使用

```bash
git clone -b rent-finder --recurse-submodules https://github.com/chrisend-ss/-.git
cd -
python -m pip install -r requirements-rent.txt
```

复制来源模板：

```bash
cp rent_finder/sources.example.json rent_finder/sources.json
```

然后把链家对应的「地铁租房」页面链接粘进 `sources.json`。

运行：

```bash
python -m rent_finder.collect --sources rent_finder/sources.json
```

结果会生成：

```text
rent_finder/output/all.json
rent_finder/output/matches.json
rent_finder/output/matches.csv
```

其中 **matches.csv 就是最终候选房源清单**。

## 合并旧爬虫数据

贝壳旧项目导出的 CSV：

```bash
python -m rent_finder.collect \
  --sources rent_finder/sources.json \
  --beike-csv ExportData/export_xxx.csv
```

rentHouseSpider 如果导出为 JSON：

```bash
python -m rent_finder.collect \
  --sources rent_finder/sources.json \
  --fang-json houses.json
```

也可以两种同时加。

## 说明

- 不绕验证码、不绕登录风控、不做高频攻击式请求。
- 默认每个页面请求间隔 2 秒、每个站只抓前 3 页。
- 网站 DOM 变化时只需要更新对应 adapter，不需要改筛选器。
- 下一阶段：自动生成站点 URL、GitHub Actions 定时运行、新房源增量通知。
