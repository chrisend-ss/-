# 杭州租房筛选器（rent-finder）

这个分支独立承载租房工具，不改动网易云抓取功能的 main 分支。

## 已写入的上游项目

- LianjiaRentSpider-Visualization
  - 来源：https://github.com/ljqdemi/LianjiaRentSpider-Visualization
  - 用途：链家租房抓取、SQLite 存储、数据分析/可视化
- BeiKeZuFangSpider
  - 来源：https://github.com/sunhailin-Leo/BeiKeZuFangSpider
  - 用途：Scrapy 抓取贝壳租房、CSV/MongoDB 输出
- rentHouseSpider
  - 来源：https://github.com/zonezoen/rentHouseSpider
  - 用途：requests + BeautifulSoup 抓取、MongoDB、基础分析

三者以 git submodule 方式固定版本，避免直接复制第三方代码导致来源和版本混乱。

## 当前筛选条件

- 工作地点：杭州地铁 2 号线 钱江世纪城站
- 方向：只看钱江世纪城往杭州主城区方向
- 优先站点：钱江路、庆春广场、庆菱路、建国北路、中河北路、凤起路、武林门
- 租赁方式：整租优先
- 面积：>= 70㎡
- 目标租金：约 3000 元/月
- 硬上限：3300 元/月
- 通勤：优先 2 号线直达
- 地铁步行：优先 <= 1000m
- 排除：合租、办公/商铺、明显引流低价、面积信息异常、重复房源

## 使用

克隆本分支并拉取上游：

```bash
git clone -b rent-finder --recurse-submodules https://github.com/chrisend-ss/-.git
```

筛选器接收标准化 JSON 房源列表：

```bash
python rent_finder/filter.py input.json
```

后续可以分别给三个上游写 adapter，把抓取结果统一转换为同一字段，再交给 filter.py 去重、筛选、排序。

> 说明：三个上游项目年代和站点结构不同，网页结构也可能已经变化。这里先保留可复用抓取思路与源码版本，不承诺旧爬虫无需修改即可直接跑通当前网站。
