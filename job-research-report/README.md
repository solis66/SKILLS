# 岗位调研报告 Skill

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-6366f1)](https://github.com/openai/codex)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

一个 Codex Skill，通过**联网搜索**调研指定公司的指定岗位，自动生成标准 A4 版式的 PDF 调研报告。

## 功能特性

- **一键调研** — 只需输入"公司名 + 岗位名"即可启动全流程
- **联网搜索** — 多轮搜索覆盖公司概况、岗位职责、薪资范围、技能要求
- **标准 PDF** — 遵循中文公文排版规范，A4 纸张、宋体正文、黑体标题
- **灵活搜索源** — 默认 Codex 自由选择最优搜索源，支持用户指定网站
- **数据表格** — 薪资按城市 / 经验 / 职级三维度生成结构化表格
- **参考文献** — 自动记录搜索来源，遵循 GB/T 7714 标准

## 报告内容

| 章节     | 内容                                    |
| ------ | ------------------------------------- |
| 封面     | 报告标题、公司·岗位、调研日期                       |
| 一、公司概况 | （一）行业定位 — （二）公司规模 — （三）发展阶段 — （四）企业文化 |
| 二、岗位职责 | 岗位概述、具体职责、任职要求                        |
| 三、薪资范围 | 按城市划分、按经验划分、按职级划分（含表格）                |
| 四、技能要求 | 硬技能、软技能                               |
| 参考文献   | 所有搜索来源记录                              |

## 快速开始

### 前置条件

- Python 3.8+
- 已安装 [Codex CLI](https://github.com/openai/codex)

### 安装 Skill

1. 将 `job-research-report` 目录放入 `$CODEX_HOME/skills/`：
   
   ```bash
   # 克隆或复制 skill 目录到 Codex skills 路径
   cp -r job-research-report ~/.codex/skills/
   ```
   
   

2. 重启 Codex，Skill 将自动加载。

### 使用示例

在 Codex 中输入以下任一指令：

```text
调研字节跳动的产品经理岗位，生成一份 PDF 报告

帮我查一下腾讯后台开发的薪资情况，输出 PDF 调研报告

请调研小红书的用户运营岗位，限定搜索 BOSS 直聘，生成报告
```

Codex 将自动：

1. 解析公司名和岗位名
2. 多轮搜索收集数据
3. 构造结构化 JSON
4. 调用 `scripts/generate_report.py` 生成 PDF
5. 输出文件路径：`{公司名}_{岗位名}_调研报告.pdf`

## 项目结构

```
job-research-report/
│
├── SKILL.md                       # Skill 核心指令（工作流定义）
├── agents/
│   └── openai.yaml               # Skill UI 元数据
└── scripts/
    ├── generate_report.py         # PDF 报告生成器（ReportLab）
    └── sample.json               # 示例输入数据
```

## PDF 排版规范

| 项目    | 设置                                    |
| ----- | ------------------------------------- |
| 纸张    | A4                                    |
| 页边距   | 上 3.7cm / 下 3.5cm / 左 2.8cm / 右 2.8cm |
| 报告大标题 | 二号黑体，居中                               |
| 章节标题  | 三号黑体，居左                               |
| 正文    | 小四号宋体，首行缩进 2 字符，1.5 倍行距               |
| 页码    | 小五号 Times New Roman，底端居中              |

## 扩展与定制

### 修改 PDF 样式

编辑 `scripts/generate_report.py` 中的样式常量：

```python
SZ_TITLE = 22      # 报告大标题字号
SZ_H1 = 16         # 一级标题字号
SZ_BODY = 12       # 正文字号
TOP_M = 3.7 * cm   # 上边距
```

### 添加新的数据维度

1. 在 SKILL.md 中增加对应的搜索步骤
2. 扩展 JSON schema 添加新字段
3. 在 `generate_report.py` 的 `generate()` 函数中添加渲染逻辑





## License

MIT
