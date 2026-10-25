# Imperial Dev Team（三省六部开发团队）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 `imperial-dev-team` skill：SKILL.md（尚书省总调度）+ 8 份省/部 subagent 提示词 + 6 份工件模板，实现从需求到可部署 MVP 的并行流水线。

**Architecture:** SKILL.md 是唯一入口与流程状态机，按「中书→门下→皇帝→户→吏→皇帝(开工)→礼→刑预审→兵(并行产码)→刑审→工(部署冒烟)→皇帝(验收)」推进。派发时主 agent 读取 `agents/<部>.md` 作为该 subagent 的角色 prompt，连同输入工件路径一起下发。所有交接只走目标项目 `docs/imperial/` 下的固定工件；每份工件唯一 owner；问题回退经 SKILL.md 路由表回到 owner 部。

**Tech Stack:** 纯 Markdown skill 文件（ZCode skill 格式，仅 SKILL.md 带 YAML frontmatter）；无运行时依赖。

**Spec:** docs/superpowers/specs/2026-10-25-imperial-dev-team-design.md

## Global Constraints

- skill 位于仓库根 `imperial-dev-team/`；正文中文，文件名英文 kebab-case；吏部/礼部分别为 `libu-ui.md` / `libu-plan.md`（避免拼音撞名）
- 目标项目工件固定路径：`docs/imperial/00-prd.md`、`01-architecture.md`、`02-ui-spec.md`（+ `mockups/*.html`）、`03-tasks.md`、`04-reviews/*.md` + `04-evals.md`、`05-release.md`
- 每份 agent 提示词固定章节顺序：【身份与职责】【输入】【产出】【工作流程】【禁区】【齿轮规则】【完成标准】
- 兵部六维红线（spec 逐字）：健壮性 / 可读性 / 可复用性 / 可维护性 / 规范性 / 安全性边界
- 三处皇帝门禁（①PRD 批准 ②开工批准 ③最终验收）一律用 AskUserQuestion；门下省驳回 PRD 最多 2 轮、刑部驳回任务卡每卡最多 2 轮，第 3 轮带分歧呈皇帝
- 任务卡状态枚举：`pending / coding / reviewing / rejected / done`
- 并行规则：同批任务卡文件范围互斥；任务看板首卡固定为「工程脚手架卡」；DAG 分层串行、同层并行、同一工作树直写；末端固定「集成卡」
- SKILL.md 只做派活与路由，不含任何设计决策
- 首版仅绿地项目（空仓库从零搭建）

## Review Focus

1. agent 提示词缺「禁区」章节 → 越权打滑。Test: Task 4–7 验证步骤 `grep -l '## 禁区'` 命中全部 8 份文件。
2. SKILL.md 引用不存在的 agents/templates 路径 → 派发时读不到文件。Test: Task 9 引用完整性校验全部命中。
3. 工件 owner 未标注 → 多部同改一份文件。Test: Task 1–3 每份模板头部含 `Owner：`；Task 8 路由表覆盖 spec 回退表全部 6 行。
4. 断点续跑未落地 → 长流程中断无法恢复。Test: Task 2 模板含状态枚举五值；Task 8 SKILL.md 含「扫描 `docs/imperial/` 推断进度」开场逻辑。
5. 质量红线与审查脱钩 → 兵部写红线、刑部不查。Test: Task 3 review-report 模板含六维逐项 checklist；Task 7 xingbu.md 审查维度与六维一一对应。

---

### Task 1: 需求侧齿轮模板（PRD + 架构决策书）

**Files:**
- Create: `imperial-dev-team/templates/prd.md`
- Create: `imperial-dev-team/templates/architecture.md`

**Interfaces:**
- Produces: 需求 ID 格式 `REQ-001`（吏部/礼部/刑部引用溯源）；API 契约端点表与依赖白名单结构（礼部拆卡挂端点、兵部编码依据、刑部查一致性）。

- [ ] **Step 1: 创建 `templates/prd.md`**，章节骨架：元信息表（含 `Owner：中书省`/日期/状态）/ 背景与目标 / 用户画像 / 竞品分析（含来源链接）/ 功能需求表（需求 ID `REQ-xxx`、描述、**可测验收标准**、优先级 P0–P2）/ 非功能需求（性能、安全）/ 明确不做。
- [ ] **Step 2: 创建 `templates/architecture.md`**，章节骨架：元信息表（`Owner：户部`）/ 技术栈决策表（每项含：选择、理由、备选；前端框架、后端语言与框架、数据库）/ API 契约（端点表：方法、路径、请求、响应、错误码 + 通用错误响应结构）/ 数据模型（实体与关系）/ 部署拓扑（本地 | docker | 云，注明默认本地）/ 工程目录结构规范 / 依赖白名单（仅允许清单内主流库）。
- [ ] **Step 3: 验证结构**

Run: `grep -c '^#' imperial-dev-team/templates/prd.md imperial-dev-team/templates/architecture.md && grep -l 'Owner：' imperial-dev-team/templates/*.md`
Expected: 两文件标题数 ≥ 6；两文件均含 Owner 行。

- [ ] **Step 4: Commit** `git add imperial-dev-team/templates/ && git commit -m "feat(imperial-dev-team): PRD 与架构决策书模板"`

### Task 2: 设计侧齿轮模板（UI 规范 + 任务看板）

**Files:**
- Create: `imperial-dev-team/templates/ui-spec.md`
- Create: `imperial-dev-team/templates/task-board.md`

**Interfaces:**
- Consumes: `REQ-xxx`（Task 1）、户部技术栈（架构决策书）。
- Produces: 页面 ID `PG-xx`、组件 ID `UI-xx`（礼部拆卡溯源、刑部查 UI 完整度）；任务卡 ID `T-xx`、缺陷引用格式、状态枚举五值（SKILL.md 断点续跑与刑部开票消费）。

- [ ] **Step 1: 创建 `templates/ui-spec.md`**，章节骨架：元信息表（`Owner：吏部`，注明「技术栈以架构决策书为准，本部不选型」）/ 设计 token（色/字/距）/ 页面清单（`PG-xx`）/ 每页组件清单（`UI-xx`，状态列必含：默认/加载/空/错误/边界）/ 交互说明 / 原型索引（`mockups/*.html`，核心页 2–3 个）。
- [ ] **Step 2: 创建 `templates/task-board.md`**，章节骨架：元信息表（`Owner：礼部`）/ 任务卡字段说明（ID `T-xx`、范围、**文件范围**、负责角色、验收标准→溯源 `REQ-`/`UI-` ID、涉及契约端点、依赖）/ 状态机说明（`pending / coding / reviewing / rejected / done` 五值逐一定义）/ DAG 分层视图（首卡固定「工程脚手架卡」、末端固定「集成卡」的占位与说明）。
- [ ] **Step 3: 验证结构**

Run: `grep -l 'pending / coding / reviewing / rejected / done' imperial-dev-team/templates/task-board.md && grep -l 'UI-' imperial-dev-team/templates/ui-spec.md`
Expected: 两文件均命中。

- [ ] **Step 4: Commit** `git commit -am "feat(imperial-dev-team): UI 规范与任务看板模板"`

### Task 3: 质量交付侧模板（审查报告 + 评测集 + 交付清单）

**Files:**
- Create: `imperial-dev-team/templates/review-report.md`
- Create: `imperial-dev-team/templates/evals.md`
- Create: `imperial-dev-team/templates/release.md`

**Interfaces:**
- Consumes: `T-xx`（Task 2）、六维红线（spec）、契约端点表（Task 1）、PRD 验收标准（评测集来源）。
- Produces: 缺陷票 ID `D-xx`（兵部修复报告引用）；pass 信号（工部放行依据）。

- [ ] **Step 1: 创建 `templates/review-report.md`**，章节骨架：元信息表（`Owner：刑部`）/ 逐卡结论表（`T-xx`、pass/reject、轮次）/ **六维红线 checklist**（健壮性/可读性/可复用性/可维护性/规范性/安全性边界，逐项勾选栏）/ 前后端与 API 契约一致性 / 缺陷票表（`D-xx`、文件、严重度、修法、状态）/ 机械验证记录（构建、测试、lint 的命令与结果，注明「必须复跑」）。
- [ ] **Step 2: 创建 `templates/evals.md`**，章节骨架：元信息表（`Owner：刑部`，注明「用例从 PRD 验收标准逐条生成，跨迭代累积回归」）/ 评测用例表（用例 ID `E-xx`、溯源 `REQ-` ID、前置条件、操作步骤、期望结果、最近一次结果）/ 回归说明。
- [ ] **Step 3: 创建 `templates/release.md`**，章节骨架：元信息表（`Owner：工部`）/ 环境与拓扑落地记录（对照架构决策书）/ 部署步骤 / 冒烟结果表（对照评测集核心用例 `E-xx`）/ 发布说明（能干什么/已知问题/如何运行）/ 回滚。
- [ ] **Step 4: 验证结构**

Run: `grep -c '健壮性\|可读性\|可复用性\|可维护性\|规范性\|安全性' imperial-dev-team/templates/review-report.md && grep -c 'E-' imperial-dev-team/templates/evals.md`
Expected: review-report 计数 ≥ 6；evals 含 `E-` 用例 ID。

- [ ] **Step 5: Commit** `git commit -am "feat(imperial-dev-team): 审查报告、评测集与交付清单模板"`

### Task 4: 决策层 agent 提示词（中书省 + 门下省）

**Files:**
- Create: `imperial-dev-team/agents/zhongshu.md`
- Create: `imperial-dev-team/agents/menxia.md`

**Interfaces:**
- Consumes: 用户原始需求；`templates/prd.md`。
- Produces: 按模板填充的 `docs/imperial/00-prd.md`（门下省、皇帝、六部消费）。

- [ ] **Step 1: 创建 `agents/zhongshu.md`**，按固定七章节。要点：竞品调研用 WebSearch 并附来源链接；每个功能需求必须带可判定验收标准与优先级；含「明确不做」；只产出 PRD 不做技术选型。
- [ ] **Step 2: 创建 `agents/menxia.md`**，按固定七章节。要点：四查清单——完整性（每功能有验收标准）/一致性（无自相矛盾）/可行性（MVP 范围内）/可测性（验收标准可判定）；驳回必须带缺陷清单回中书省；最多 2 轮，第 3 轮带双方分歧呈皇帝；通过时产出审核意见供皇帝裁决参考。
- [ ] **Step 3: 验证结构**

Run: `for f in imperial-dev-team/agents/zhongshu.md imperial-dev-team/agents/menxia.md; do grep -l '## 禁区' $f || echo "MISSING $f"; done`
Expected: 无 MISSING 输出。

- [ ] **Step 4: Commit** `git add imperial-dev-team/agents/ && git commit -m "feat(imperial-dev-team): 中书省与门下省提示词"`

### Task 5: 设计层 agent 提示词（户部 + 吏部）

**Files:**
- Create: `imperial-dev-team/agents/houbu.md`
- Create: `imperial-dev-team/agents/libu-ui.md`

**Interfaces:**
- Consumes: 已批准 PRD（`00-prd.md`）；`templates/architecture.md`、`templates/ui-spec.md`。
- Produces: `01-architecture.md`（含 API 契约——礼/兵/刑唯一对接面）；`02-ui-spec.md` + `mockups/*.html`（2–3 核心页）。

- [ ] **Step 1: 创建 `agents/houbu.md`**，按固定七章节。要点：技术栈按 PRD 非功能需求与竞品事实选型并写理由与备选；API 契约与数据模型必须完整到前后端可各自独立开发；依赖白名单（仅主流维护中的库）；部署拓扑默认本地；不做 UI、不拆任务、不写业务代码。
- [ ] **Step 2: 创建 `agents/libu-ui.md`**，按固定七章节。要点：在户部既定技术栈内设计；组件清单每项必含默认/加载/空/错误/边界五态；静态 HTML 原型仅是参照物，不是生产代码、不含业务逻辑；不定框架、不拆任务。
- [ ] **Step 3: 验证结构**：同 Task 4 Step 3 的 grep 方式，两文件无 MISSING。
- [ ] **Step 4: Commit** `git commit -am "feat(imperial-dev-team): 户部与吏部提示词"`

### Task 6: 执行层 agent 提示词（礼部 + 兵部）

**Files:**
- Create: `imperial-dev-team/agents/libu-plan.md`
- Create: `imperial-dev-team/agents/bingbu.md`

**Interfaces:**
- Consumes: `00-prd.md`、`01-architecture.md`、`02-ui-spec.md`；`templates/task-board.md`。
- Produces: `03-tasks.md`（任务卡 DAG，状态字段供 SKILL.md 续跑）；代码 + 逐卡完成报告（引用 `T-xx` 与缺陷票 `D-xx`）。

- [ ] **Step 1: 创建 `agents/libu-plan.md`**，按固定七章节。要点：拆卡硬规则——每卡声明文件范围、同批互斥；首卡固定工程脚手架卡（按户部目录规范初始化、落契约类型定义）；末端固定集成卡（拆 mock、真联调、端到端走契约）；验收标准全部溯源到 `REQ-`/`UI-` ID；不做技术决策、不改 PRD 范围（歧义上报）。
- [ ] **Step 2: 创建 `agents/bingbu.md`**，按固定七章节。要点：**六维质量红线逐字写入**（健壮性/可读性/可复用性/可维护性/规范性/安全性边界，含安全红线细则：密钥不硬编码、输入不可信、禁 eval/拼 SQL/未净化 innerHTML、仅白名单依赖、权限最小化）；按卡执行不重拆、不改契约、不改设计意图，发现问题上报；后端未就绪时前端按契约 mock；每卡完成报告格式（改动文件、实现/消费端点、自测结果）。
- [ ] **Step 3: 验证结构**

Run: `grep -c '健壮性' imperial-dev-team/agents/bingbu.md && grep -l '## 禁区' imperial-dev-team/agents/libu-plan.md imperial-dev-team/agents/bingbu.md`
Expected: bingbu.md 健壮性计数 ≥ 1；两文件含禁区章节。

- [ ] **Step 4: Commit** `git commit -am "feat(imperial-dev-team): 礼部与兵部提示词"`

### Task 7: 质量交付层 agent 提示词（刑部 + 工部）

**Files:**
- Create: `imperial-dev-team/agents/xingbu.md`
- Create: `imperial-dev-team/agents/gongbu.md`

**Interfaces:**
- Consumes: 完成报告 + diff + 各上游工件；`templates/review-report.md`、`templates/release.md`。
- Produces: `04-reviews/*.md`（pass 信号 = 工部放行票）+ `04-evals.md`（评测集）+ 观测基线；`05-release.md` + 可运行 MVP。

- [ ] **Step 1: 创建 `agents/xingbu.md`**，按固定七章节。要点：三个职责时点——开工前计划预审（对照契约与 UI 规范查任务缺口）/逐卡审查/放行判定；机械验证必须复跑（构建、测试、lint）；审查维度 = 六维红线逐维 + 前后端契约一致性；**只开缺陷票（`D-xx`）不修码**；每卡驳回最多 2 轮第 3 轮呈皇帝；评测集从 PRD 验收标准逐条生成并跨迭代累积；观测基线（错误率/时延/关键漏斗）交工部作门槛。
- [ ] **Step 2: 创建 `agents/gongbu.md`**，按固定七章节。要点：严格按户部拓扑部署（默认本地）；只写部署/构建粘合层不写业务代码；无刑部 pass 不部署；冒烟对照评测集核心用例；失败开票经刑部回兵部；发布说明（能干什么/已知问题/如何运行）。
- [ ] **Step 3: 验证结构**：同 Task 4 Step 3 方式，两文件无 MISSING；`grep -c '预审' xingbu.md` ≥ 1。
- [ ] **Step 4: Commit** `git commit -am "feat(imperial-dev-team): 刑部与工部提示词"`

### Task 8: SKILL.md（尚书省总调度）

**Files:**
- Create: `imperial-dev-team/SKILL.md`

**Interfaces:**
- Consumes: 全部 8 份 `agents/*.md`、6 份 `templates/*.md`、spec 的流程/门禁/路由规则。
- Produces: skill 入口——YAML frontmatter（`name: imperial-dev-team` + 中文 description 触发词：软件开发团队/需求分析/PRD/架构选型/UI 设计/任务拆解/前后端/代码审查/部署/三省六部等）。

- [ ] **Step 1: 创建 SKILL.md**，章节骨架：frontmatter / 触发场景（含「仅绿地项目」边界声明）/ **开场续跑扫描**（读 `docs/imperial/` 现场工件推断进度，从断点续跑）/ 流程状态机（十二步时序，含三处皇帝门禁的 AskUserQuestion 指令）/ 派发模式（每步：读对应 `agents/<部>.md` 全文 + 输入工件路径 → 作为 subagent prompt 派发；兵部按 DAG 分层并行派发，每批 2–3 个）/ 回退路由表（spec 回退表全部 6 行：需求歧义变更/任务拆错/契约变更/设计变更/代码缺陷/部署故障）/ 循环上限 / 尚书省自律条款（只派活路由，不做任何设计决策）。
- [ ] **Step 2: 验证结构**

Run: `head -5 imperial-dev-team/SKILL.md && grep -c 'AskUserQuestion' imperial-dev-team/SKILL.md && grep -c '路由' imperial-dev-team/SKILL.md`
Expected: frontmatter 含 name 与 description；AskUserQuestion 计数 ≥ 3；路由计数 ≥ 1。

- [ ] **Step 3: Commit** `git add imperial-dev-team/SKILL.md && git commit -m "feat(imperial-dev-team): 尚书省总调度 SKILL.md"`

### Task 9: 整体校验

**Files:**
- Test: 全 `imperial-dev-team/` 目录

- [ ] **Step 1: 文件齐全**

Run: `ls imperial-dev-team/SKILL.md imperial-dev-team/agents/ imperial-dev-team/templates/ | wc -l`
Expected: agents 8 份、templates 6 份（prd/architecture/ui-spec/task-board/review-report/release）+ SKILL.md 齐全。

- [ ] **Step 2: 引用完整性**（Review Focus #2）：提取 SKILL.md 与各 agent 文件中引用的 `agents/`、`templates/` 相对路径，逐一验证存在。
- [ ] **Step 3: 红线-审查挂钩复查**（Review Focus #5）：`grep -l '安全性' agents/bingbu.md templates/review-report.md` 两文件均命中。
- [ ] **Step 4: Commit** `git commit -am "chore(imperial-dev-team): 整体校验通过"`
