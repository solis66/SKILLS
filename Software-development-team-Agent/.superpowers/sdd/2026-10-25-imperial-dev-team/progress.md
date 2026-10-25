# SDD ledger — plan: docs/superpowers/plans/2026-10-25-imperial-dev-team.md

Setup: branch feat/imperial-dev-team (Ruling: worktree 脚本未安装，用特性分支替代 — 本仓库单人小型变更，无并行需求 — 若误判成本为合并时的一次 rebase)
Setup: Ruling: 配套脚本与 TDD 子技能未安装，台账手写、以计划内 grep/ls 验证步骤为每任务门禁 — 交付物为 Markdown 提示词，无可执行测试 — 若误判成本为验证力度弱于 TDD
Pre-flight: 接口冲突扫描 — T1 产 REQ-xxx/契约表 ↔ T2/T4-7 消费一致；T2 产 T-xx/状态枚举 ↔ T3/T6/T8 一致；T3 产 D-xx/E-xx ↔ T6/T7 一致；T8 消费全部文件且排最后。无未解决冲突。
Task 1: complete (grep 计数 8/10 均≥6；Owner： 命中全部模板)
Task 1: Ruling: git add 按文件而非目录，保持任务提交隔离 — 避免未验证文件混入 — 若误判成本为提交粒度略碎
Task 1: Ruling: 首版表格行写成 | Owner | 缺全角冒号被 grep 抓出，统一改为 | Owner： | — 计划钉的是字面匹配 — 若误判成本为无
Task 2: complete (状态枚举五值与 UI- 均命中；Ruling: 状态机补字面枚举串一行，表格式分行写法不满足计划钉死的 grep — 若误判成本为无)
Task 3: complete (六维计数≥6 实得 12；E- 计数≥1；三模板 Owner： 命中)
Task 4: complete (禁区章节两文件齐；七章节标题数 8/8)
Task 5: complete (禁区章节齐；标题数 8/8)
Task 6: complete (bingbu 健壮性命中、六维齐；禁区章节两文件齐；标题数 8/9)
Task 7: complete (预审命中；禁区章节两文件齐；标题数 10/8)
Task 7: Ruling: 设计要求刑部产出观测基线但计划未钉落点 — 最小修正为 evals 模板补「观测基线」章节（04-* 质量簇，工部冒烟与观测两处对照同一文件）— 若误判成本为工部需跨文件找基线
Task 8: complete (frontmatter 含 name/description；AskUserQuestion 4 处≥3；路由 5 处≥1)
