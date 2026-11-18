# 前端：多风险特征预警系统

按《前端交接文档》实现的 13 个页面。后端未就绪时用前端内置的模拟数据运行，数据逐行取自 `sql/risk_alert_示例库.sql`。

技术栈：Vue 3 + Vite + Element Plus + ECharts + Vue Router + Pinia。

## 启动

需要 Node.js 18 及以上。

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。

### 演示账号

口令统一为 `123456`，与建库脚本一致。登录页上点账号即可填入。

| 用户名 | 角色 | 能看到的页面 |
|---|---|---|
| analyst1 | 研判员 + 教师 | A1 B1 B2 B3 C1 C2 D1 D2 D3 E1 E2 E4（线索可操作） |
| analyst2 | 研判员 | A1 B1 B2 B3 C1 C2（线索可操作） |
| featop | 特征管理员 | A1 D1 D2 D3 E4（特征、版本、批次可操作） |
| admin | 系统管理员 | A1 D3 E2 E3（批次、参数可操作） |
| teacher | 教师/评审 | 除 E3 外全部，只读 |
| dataop | 数据管理员 | 仅 A1（见缺口 #13） |

`guest` 在示例库里是停用状态，登录会被拒绝。

### 切换到真实后端

修改 `frontend/.env.development`：

```
VITE_API_MODE=real
VITE_API_BASE=http://127.0.0.1:5000
```

改完重启 `npm run dev`。前端在请求头里带 `Authorization: Bearer <token>`，后端需要开启 CORS。

### 模拟数据说明

- **改动会保存在本浏览器**（localStorage），刷新后不会丢。右上角用户菜单 →「重置演示数据」可恢复为示例库初始状态。
- **规则照搬建库脚本**：状态机、`ck_clue_close`、触发器 `trg_feedback_close_clue` / `trg_clue_audit` / `trg_weight_audit`、存储过程 `sp_calc_feature_weight` / `sp_upsert_score`、`uk_version_current` 都在 `src/api/mock/server.js` 里按同样的规则实现。
- **演示时钟**：示例数据的日期在 2026 年 11 月。模拟服务记录"当前时间"时，取电脑时间与"最近一条审计记录之后 1 分钟"中较晚的那个，避免新记录早于示例数据。
- **研判引擎（接口 16）是简化版**，只用于演示"执行中 → 结果"：
  - 时间窗统一用批次数据窗，没有逐特征使用 `time_window_min`；
  - 样本量 = 归集到的流水条数。

  正式算法以后端为准（《前端交接文档》第七节）。

## 答辩演示路线

1. 用 `analyst1` 登录，打开**首页**：数字卡、热力图、最新线索。
2. 点热力图里"老城餐饮街 · 周末 · 23 点"进入 **B2**，回答"为什么提示"：
   - 逐条特征判定；
   - 公式 `1.2098 + 2.9667 + 1.9725 = 6.1490 ≈ 6.15`。
3. 打开**线索列表**，点 `CL2026110704`（核查中）走一遍 **C2** 闭环：
   - 点「排除」，填写核查方式和说明，勾选被否定的特征，提交；
   - 线索变为"已排除"，核查记录里出现被否定的特征。
4. 打开**特征清单**，看双口径：训练源 `case_info` 与研判源分列，中间有竖线分隔。进入被否定的特征，「核查否定记录」里能看到刚才那条。
5. 打开**评估报告**（E1），回答"怎么证明有效"：混淆矩阵 32/12/8/70，精确率 0.73，召回率 0.80，误报率 0.15，F1 0.76。
6. 换 `featop` 登录，在**版本与批次**创建批次并执行研判。也可以重新执行失败的 `B2026110706`：它使用的草稿版本没有权重，会再次失败并说明原因。
7. 页脚的"数据健康"小绿灯：鼠标悬停可看 4 项检查结果。

## 目录

```
src/
  api/index.js           请求封装（mock / real 同一路径）+ 25 个接口
  api/mock/seed.js       示例库 26 张表、6477 行数据（与 SQL 逐行同源）
  api/mock/server.js     模拟后端：路由、视图、触发器、存储过程、研判引擎
  constants/enums.js     枚举中文映射（页面不出现裸数字）
  constants/permissions.js  角色 → 页面 / 操作 权限矩阵
  components/            布局、等级/状态标签、特征判定表、线索抽屉、核查表单、图表、健康灯
  views/                 13 个页面 + 登录 + 无权访问
```

## 与交接文档的对应

| 交接文档要求 | 实现位置 |
|---|---|
| 12 个页面、路由 | `src/router/index.js`（C2 用抽屉挂在 `/clues/:clueId`；另有 B3 风险地图 `/risk-map`） |
| 枚举中文映射 | `src/constants/enums.js` |
| 按角色隐藏菜单与按钮（不是禁用） | `src/constants/permissions.js`、`AppLayout.vue`、各页面 `auth.can()` |
| 未登录跳登录页、401 统一跳转 | `src/router/index.js`、`src/main.js` |
| B2 命中高亮、`is_missing` 显示"数据不足"、总分公式 | `components/FeatureJudgeTable.vue` |
| C2 只显示合法流转按钮、核查时勾选被否定的特征 | `components/ClueDrawer.vue`、`components/FeedbackDialog.vue` |
| D1 训练源 / 研判源并排，用竖线分隔 | `views/FeatureListView.vue` |
| E1 指标取接口返回值，分母为 0 显示"—" | `views/EvalView.vue` |
| B3 风险地图（红色深浅 + 可拖动时间轴） | `views/RiskMapView.vue`、`api/mock/server.js` 的 `/api/risk-map` |
| 加载中 / 空数据 / 报错三种状态 | `components/AsyncState.vue` |
| 日期半开区间传参 | `utils/format.js` 的 `halfOpenRange` |
| 页脚声明 + 数据健康灯 | `components/AppLayout.vue`、`components/HealthLight.vue` |
| 不出现身份证、手机号、车牌明文 | 模拟库里不存姓名、手机号、车牌；个人对象只显示编号 |

## 文档缺口与矛盾（请后端 / 数据库同学确认）

| # | 问题 | 前端的处理 / 建议 |
|---|---|---|
| 1 | 24 个接口里没有登录接口，但第十节要求未登录跳转登录页 | 前端按 `POST /api/login` 调用：请求体 `{username, password}`，返回 `{token, user: {user_id, username, real_name, roles}}`。请后端补上 |
| 2 | 系统管理员"不直接看线索"，但 A1 有"最新线索 Top5" | 对管理员、数据管理员、特征管理员隐藏线索区块，改为显示可进入的模块 |
| 3 | 枚举表缺 `check_method`、`feature_cat`、`value_type`、`area_type`、`op_type` 等 | 按建库脚本字段注释补齐 |
| 4 | 接口 4 的 SQL 用中文 `status_name` 过滤，而参数是数字 `status` | 前端传数字，建议 SQL 改为 `clue_status = ?` |
| 5 | 接口 19（审计）的 SQL 用 `BETWEEN`，与 5.1 的半开区间约定矛盾 | 前端传半开区间 `from` / `to`，建议 SQL 改为 `op_time >= ? AND op_time < ?` |
| 6 | 接口 1 没有热力图和 Top5 所需的数据 | A1 另调接口 2 和接口 4；接口 4 多加参数 `order=latest`（按生成时间倒序） |
| 7 | 视图缺少前端跳转和筛选要用的字段 | 建议：`v_region_risk` 加 `score_id`、`risk_level`、`day_type`（B1 → B2 跳转、按等级筛选）；`v_clue_list` 加 `clue_status`、`score_id`、`object_type`、`object_id`、`risk_level`（个人线索没有区域，需要显示对象编号） |
| 8 | 区域、规则等下拉选项没有接口 | 前端调用 `GET /api/dicts`，返回 `{areas, rules, history_cutoff}`。请后端补上 |
| 9 | 部分接口返回字段不够页面用 | 前端额外使用的字段：<br>· 接口 9：`negations`（核查否定记录）、`versions`<br>· 接口 11：`weight_cnt`、`published_by_name`<br>· 接口 14：`rule_name`、`area_name`、`operator_name`<br>· 接口 16：`skipped_cnt`、`message`<br>· 接口 1：`clue_checking`<br>· 接口 23：`history_cutoff`、`case_info_total` |
| 10 | 接口 21 的 SQL 按 `param_group` 排序，但 `param_config` 表没有这一列 | 前端按 `param_key` 排序 |
| 11 | 第七节研判第 2 步写 `start_at`，但 `judge_batch` 表没有这一列 | 不影响前端，请后端注意 |
| 12 | 接口 7 说演示时"评估页误报率变化"，但第八节的评估 SQL 用 `risk_score.is_clue` 判定，与核查结论无关，提交"不属实"后误报率**不会变** | 前端按第八节的 SQL 实现。需要组里决定：改演示话术，还是改评估口径 |
| 13 | 数据管理员（R_DATA）的"信息库明细 / 导入质量报告"不在 12 个页面里 | 数据管理员目前只能看 A1 和页脚健康检查 |
| 14 | 评估报告只给教师看（第四节），特征管理员调权时看不到 | 暂按文档执行；如需开放，改 `PAGE_ROLES.eval` |
| 15 | 接口 1 的示例 `clue_open: 1` 与示例数据不符：按 SQL 统计，待核查为 0、核查中为 1 | 首页"待核查"按 SQL 统计 `clue_status=0`，另外单独显示"核查中"数量 |
| 16 | "直接排除"该走接口 6（状态改为 3）还是接口 7 | 前端走接口 7（核查结论 = 不属实），这样能留下排除理由和被否定的特征，状态由触发器推进 |


## 前端显示优化（2026-11-18）

本轮按首页热力、首页布局、风险列表、风险地图、线索详情、全局视觉的顺序优化。

- 首页默认最近一次成功的**区域研判批次**，完整遍历分页；热力按工作日/周末切换，横轴 06 时至次日 05 时。颜色沿用评分返回的等级，图例使用所属规则阈值。可切换同一批次的区域分布（区域峰值），不混用不同批次。
- 顶部四项业务指标为全部批次累计；高风险卡只计区域时段对象，与点击后的列表保持同一口径。待处理区仅含待核查/核查中，按等级、分数、生成时间排序。评估摘要只向原有授权角色开放。
- 风险列表将批次、样本量等放进展开行；关键理由显示特征中文名；详情使用显式链接，支持区域/批次/等级查询参数，清空筛选回到全量结果。
- 地图的观察夜仍采用原接口口径（数据窗起始日期），每区域显示该夜峰值；加入日期选择、排行与联动详情。线索入口明确为“全部时段”，保留区域筛选。
- 线索抽屉显示状态进度、命中依据/核查记录两个标签页，来源信息可展开；核查提交后切到记录页，沿用原状态流转和权限。
- 窄屏提供侧栏切换与全宽抽屉；提高辅助文字对比度，补键盘焦点和减弱动画支持。页面中的技术说明及评估页展示口径本轮保留。

### 后端联调需要补充的返回字段

不新增接口，不改数据库结构，模拟接口只扩展以下字段：

| 接口 | 新增字段 | 用途 |
|---|---|---|
| `/api/dicts` | `rules[].low_threshold`、`rules[].high_threshold` | 首页图例和评分详情按所属规则显示阈值 |
| `/api/dicts` | `features: [{ feature_id, feature_name }]` | 列表显示中文命中理由 |
| `/api/risk-map` | `risk[].areas[].score_id` | 地图峰值评分直接跳到命中依据 |

若真实后端尚未提供这些字段，阈值不写死，理由回退编号，地图保留区域评分列表入口。

### 验证

```bash
npm run test:dashboard
npm run build
```

数据回归覆盖批次隔离、夜间小时连续、规则阈值、跨页完整性（含 451 条分页样例）、地图评分引用、区域线索过滤与角色权限。浏览器检查覆盖首页入口、列表展开与清空、地图区域联动、线索开始核查和记录页、教师只读、管理员概览及 390px 窄屏布局。


## A—E 工作台布局（2026-11-18）

- **A 导航**：宽屏72px图标轨，可展开文字；按原角色权限显示模块。悬停/键盘聚焦显示提示，窄屏以文字抽屉导航。标题旁范围选择由各页面提供。
- **B 首页**：12列主次布局，风险图占8列跨两行，4列辅助区放2×2指标；待处理线索与评估摘要位于下方。图内视图切换采用图标加当前项文字，过渡200ms，支持减少动画设置。
- **C 地图**：画布铺满内容区，观察夜、排行、详情、时间轴作为可操作面板；仅地图使用局部透明面板及右侧工具轨。刷新、排行、图例、恢复最近观察夜直接操作本页。保留虚构坐标及观察夜技术说明；面板支持收起，空间不足可滚动。
- **D 线索**：列表/四列看板可切换；看板按区域和等级筛选全部状态，列头统计全部筛选结果，列内首批20条、按需继续显示。看板卡片只打开详情，不直接拖拽修改状态。宽屏详情左侧独立滚动、右侧320px核查摘要与操作；窄屏摘要在上、操作在底部。原核查表单、状态约束、教师只读权限不变。
- **E 评估**：指标概览、诊断分析、样本明细依次通栏排列，层间48px，窄屏28px；保留原公式、SQL口径和模拟数据声明，不增加没有数据支持的趋势曲线。
- **F 批次泳道**不在本轮范围内。全站透明导航、右侧主导航、自由拖拽结案均未采用。

### 新增评估样本明细接口

`GET /api/eval/samples?batch_id=&result=&page=1&size=20`，仅原 `R_TEACHER` 授权角色可读（含兼任教师的账号）。

返回沿用 `{code,message,data}` 外层，`data` 包含：

- `list`、`total`、`page`、`size`：分页结果；`result` 可为 `tp/fp/fn/tn`，空值表示全部。
- `sample_total`：原始评估标签数量；`joined_total`：关联评分后的总行数。
- `result_counts: {tp,fp,fn,tn}`：当前批次范围的矩阵四格计数，不受结果筛选影响。
- 每行：`row_id`、`object_type`、`object_id`、`sample_type`、`label`、`case_cnt`、`score_id`、`batch_id`、`total_score`、`prediction`、`result`。无匹配评分时评分字段为 `null`，`prediction=0`。

模拟服务中的矩阵与明细共用 `evaluationRows`，保留原 `eval_label LEFT JOIN risk_score ON object_type + object_id` 口径：按选定批次限定评分集合，不丢弃未匹配标签；多批次匹配时逐条展开，不以 `DISTINCT` 改变现有计数。真实后端应保持相同口径实现该只读接口；本轮没有修改数据库表结构。

验证命令仍为 `npm run test:dashboard`、`npm run build`。数据回归新增看板全量状态计数、评估四格与明细逐项对账、结果筛选、未匹配评分、分页及权限检查。浏览器验证同时覆盖宽屏主次比例、导航展开、地图面板、四列看板和窄屏退化布局。
