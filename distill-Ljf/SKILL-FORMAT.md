# DSH Skill 格式规范（源码级）

> 依据：`@deepseek-ai/dsh-skill-filesystem`、`@deepseek-ai/dsh-skill`、`@deepseek-ai/dsh-tool-skill`
> 版本：dsh 0.1.0-rc.6

---

## 0. 先分清两条路：「我」不是一个 skill

把自己蒸馏进去，实际要拆成两个不同机制的产物：

| | **persona**（常驻身份） | **skill**（按需能力包） |
|---|---|---|
| 载体 | `preset.yml` 里 `dsh-persona` 行的 `text` 字段 | `SKILL.md` + YAML frontmatter |
| 生效方式 | 每次对话**无条件**进 system prompt | 命中后才由模型 `skill` 工具加载 |
| 成本 | 每轮都占 token | 只在用到时占 token |
| 适合 | 我是谁、价值观、语气、铁律、绝对禁区 | "遇到 X 类任务，按这套流程/判据做" |

**蒸馏原则**：身份（我是谁 + 我绝不做什么）→ persona；方法论（我怎么做事 + 判据 + 模板）→ skill。
不要把人设塞进 skill 当成正文——skill 是懒加载的，你不主动触发它就不生效。

你现有的 `~/.claude/skills/cheat-*` 就是 15 个 skill 的现成范例（含 `cheat-persona` 自己）。

---

## 1. 目录布局（二选一）

**A. 目录包（推荐）** —— 可以带附属资源：

```
<root>/<name>/SKILL.md          ← 必需，文件名必须全大写 SKILL.md
<root>/<name>/templates/*.md    ← 可选，正文用相对路径引用
<root>/<name>/scripts/*.ps1     ← 可选
```

**B. 单文件** —— 只写正文：

```
<root>/<name>.md
```

> **坑**：目录包的文件名**必须**是 `SKILL.md`。写成 `skill.md` / `README.md` 一律不被发现，且**没有任何报错**。

---

## 2. 发现路径与优先级

启动时按以下 roots 扫描；**同名 skill 由 rank 小者胜出**（不是合并）：

| rank | 路径 | source |
|---|---|---|
| 100 | `<projectRoot>/.dsh/skills/` | project-dsh |
| 200 | `<projectRoot>/.agents/skills/` | project-agents |
| 300 | `customSkillDirs`（配置项，默认空） | custom |
| 400 | `<DSH_HOME>/skills/` | user-dsh |
| 500 | `<DSH_AGENTS_HOME 或 ~/.agents>/skills/` | user-agents |
| 600 | DSH 内置 bundled 目录 | bundled |

- `projectRoot` = 从 cwd 逐级向上找到的第一个含 `.git` 的目录；**找不到就是 cwd 本身**。
- 本机实测：`DSH_HOME` = `C:\Users\20931\Desktop\deepseek_harness\.dsh`，cwd = `C:\Users\20931\Desktop\Ljf-Skill`（无 `.git`），
  所以当前可用的 root 是 `C:\Users\20931\Desktop\Ljf-Skill\.dsh\skills\`（rank 100）。

> ⚠️ **`~/.claude/skills/` 不是 DSH 的扫描路径。** 已实测：本会话调用 `skill` 工具加载 `cheat-persona` 返回
> `skill "cheat-persona" is unknown or no longer available`。那 15 个 skill 要在 DSH 里可用，必须复制/软链到上面任一 root
> （或把 `~/.claude/skills` 配成 `customSkillDirs`）。

---

## 3. frontmatter 语法（逐字要求）

```markdown
---
name: my-method
description: 一句话路由说明……
---

# 正文从这里开始
```

**硬性规则：**

1. 文件**第 1 行**必须恰好是 `---`（前面不能有空行、BOM、注释）。
2. 必须有闭合的 `---`，其后的内容全部作为正文。
3. `name` 与 `description` **必填**，且必须是非空字符串。
4. `name` 必须匹配正则 `^[a-z0-9]+(?:-[a-z0-9]+)*$`
   —— 全小写、只允许 `-` 分隔、不能有下划线/大写/点/连续或首尾连字符。
5. 正文会被 `.trim()` 后嵌入 `<skill_instructions>`。

**字段表：**

| 字段 | 类型 | 必填 | 作用 |
|---|---|---|---|
| `name` | string | ✅ | 唯一标识，也是 `/name` 命令名 |
| `description` | string | ✅ | **唯一的路由依据**，catalog 里给模型看的那句话 |
| `whenToUse` | string | ✖ | 会被解析保留，但**当前版本不渲染进 catalog，也不进正文** → 别只写这里 |
| `disable-model-invocation` | bool | ✖ | `true` = 模型看不见、`skill` 工具拒绝加载；仍可被用户 `/name` 调用 |
| `user-invocable` | bool | ✖ | `false` = 用户 `/name` 手势不注入；模型仍可加载 |
| `metadata` | object | ✖ | 自由透传对象，加载器不解释 |
| 其他任意键 | — | ✖ | 被静默忽略（`argument-hint`、`allowed-tools` 属于此类，写了没用但无害） |

**❌ 三个旧字段名会让整个文件被丢弃**（不是忽略该字段，是整个 skill 不加载）：

- `disableModelInvocation` → 用 `disable-model-invocation`
- `modelInvocable` → 用 `disable-model-invocation`
- `userInvocable` → 用 `user-invocable`

布尔值接受 `true/false`、`1/0`、`yes/no`、`on/off`（字符串也可）。

---

## 4. 静默失败清单（最容易踩）

以下情况 skill **不出现、不报错**，只在服务端日志写一行 warn：

| 情况 | 日志 |
|---|---|
| YAML frontmatter 语法错误 | `ignored: invalid YAML frontmatter` |
| 没有 frontmatter | `ignored: missing YAML frontmatter` |
| 缺 `name` 或 `description` | `ignored: frontmatter requires name and description` |
| `name` 不合法（如 `My_Skill`） | `ignored: invalid skill name` |
| 用了上面三个旧字段名 | `ignored: invalid invocation frontmatter` |
| 目录里文件名不是 `SKILL.md` | 无日志，直接跳过 |

排查顺序：文件名 → 第 1 行是否 `---` → YAML 能否解析 → `name` 正则 → 旧字段名。

---

## 5. 运行时硬约束（写的时候就要考虑）

1. **`description` 会被压平 + 截断到 500 字符**
   （`catalogDescription()`：空白符全部折叠为单空格、`trim()`，超长则切到 497 字符加 `...`）。
   → 触发词、适用场景、边界**全部前置**；别把关键信息写在 500 字之后。

2. **catalog 只渲染 `name` 和 `description`**，形如：
   ```
   - `my-method`: <description 压平后的内容>
   ```

3. **`/name` 手势识别**：正则 `(^|\s)\/([a-z0-9]+(?:-[a-z0-9]+)*)(?=\s|$)`
   —— 即 `/my-method` 必须**独立成词**（前面是行首或空白，后面是空白或行尾）。
   `/my-method的用法` 不会被识别。

4. **正文里的相对路径按 base directory 解析**。目录包加载后模型会收到：
   `Base directory for this skill: <目录绝对路径>`
   → 正文里写 `templates/x.md` 即可，不要写死绝对路径。

5. **热重载**：DSH 用 chokidar 监听这些 root。用 `write`/`edit` 工具改动 skill 文件会主动失效缓存，
   **不需要重启**；catalog 变动会以新 `<system-reminder>` 完整替换旧的 available_skills 列表。

6. **`description` 用第三人称陈述句**。它是给模型做路由决策用的，不是给你自己看的简介。

---

## 6. 正文骨架（蒸馏的实质在这）

格式只是壳。真正决定 skill 质量的是正文密度：

| 段 | 内容 | 反例 |
|---|---|---|
| 定位 | 2-3 行说清它是什么、和相邻 skill 的边界 | 长篇背景介绍 |
| Overview | 用代码块画流程/数据流 | 散文描述 |
| Constants | 关键阈值、文件路径、魔法数字集中定义 | 散落正文各处 |
| Workflow | 分 Phase，每步是**动作**不是描述 | "需要考虑……" |
| 决策规则 | `if/then` 表格：什么情况走哪条路 | 模糊的"视情况而定" |
| Key Rules | 带编号的铁律 | 泛泛的"注意质量" |
| **Refusals** | 明确拒绝哪些请求 + 拒绝理由 | 省略（**这段最像"人格"**） |
| Known limitations | 诚实写清做不到什么 | 假装万能 |

写作要点：

- **断言式**，不科普。写"必须/禁止/永远不"，不写"建议可能"。
- **判据要可执行**：不写"内容要好"，写"一条验证特征至少 3 条评论证据，不够就降级到假设段"。
- **写禁区比写流程更有价值**。流程模型本来就会，禁区才是你的独有信息。
- 参考密度标准：`~/.claude/skills/cheat-persona/SKILL.md`（179 行，含 Refusals + Known limitations）。

---

## 7. 安装与自检

```powershell
# 1. 放进当前项目的 rank 100 root
New-Item -ItemType Directory -Force "C:\Users\20931\Desktop\Ljf-Skill\.dsh\skills\my-method" | Out-Null
Copy-Item "C:\Users\20931\Desktop\Ljf-Skill\distill-self\SKILL.md" `
          "C:\Users\20931\Desktop\Ljf-Skill\.dsh\skills\my-method\SKILL.md" -Force

# 2. 自检：文件名、首行、name 正则
$p = "C:\Users\20931\Desktop\Ljf-Skill\.dsh\skills\my-method\SKILL.md"
(Get-Content $p -First 1) -eq '---'
```

自检清单：

- [ ] 文件路径以 `\<name>\SKILL.md` 结尾
- [ ] 第 1 行是 `---`
- [ ] `name` 匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`，且与目录名一致
- [ ] `description` ≤ 500 字符，触发词前置
- [ ] 没有出现 `disableModelInvocation` / `modelInvocable` / `userInvocable`
- [ ] 装好后在对话里发 `/my-method`，确认正文被注入
