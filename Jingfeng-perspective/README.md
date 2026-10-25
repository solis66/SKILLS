# Jingfeng-perspective（刘竞峰 · 认知框架）

一个自蒸馏（self-distilled）人格分析 skill：把刘竞峰处理技术判断、证据与
自我管理的动作，做成可以套在任意问题上的"质检镜片"。用法与触发词见
[SKILL.md](SKILL.md)。

## 公开版说明（重要）

本仓库为**公开分发版**，与本地完整版的差别只有一处：

| 内容 | 本仓库 | 本地完整版 |
|---|---|---|
| SKILL.md（框架本体，v0.2.2，双语域） | ✅ | ✅ |
| references/research/（13 份研究底稿） | ✅ | ✅ |
| references/sources/articles/（本人文章与笔记） | ✅ | ✅ |
| references/sources/transcripts/（本人与 AI 对话发言） | ✅ | ✅ |
| **references/sources/wechat/（16 位联系人的原始聊天语料）** | ❌ 已排除 | ✅ 保留 |

排除原因：语料含他人隐私，遵循 SKILL.md 元数据中
`privacy: 仅本地使用，不得外部分发` 的约束。因此：

- SKILL.md 与研究底稿中的 `文件名#行号` 引用（如 `user-turns#L84`、
  `wechat/大学/xxx.jsonl#L123`）指向**本地语料文件**，公开版中
  wechat 部分无法直接回查，属预期行为；
- `scripts/_val_*.py` 校验脚本需要在本地完整版目录下运行；
- 语料采集方式见 `scripts/extract_corpus.py`、`extract_docs.py`。

## 目录结构

```
SKILL.md                      框架本体（含触发词、双语域工单、验收清单）
references/
  about-author.md             关于语料主体
  extraction-framework.md     蒸馏方法论
  fidelity-scorecard.md       保真度记分卡
  research/                   研究底稿（综合、写作、对话、时间线、复核…）
  sources/articles/           本人文章/笔记（一手文档）
  sources/transcripts/        本人在 AI 会话中的真实发言（jsonl）
  sources/wechat/             [仅本地] 16 位联系人聊天语料
scripts/                      采集、合并、质检、回查脚本
```
