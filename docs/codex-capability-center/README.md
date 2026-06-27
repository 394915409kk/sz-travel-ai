# Codex 能力中心

## 定位

本目录是深圳职旅 AI 数字员工系统的 Codex 能力中心，用于统一管理 Skills、Agents、SOP、安装流程、GitHub / PR 审计、上下文交接、故障复盘、安全边界和版本记录。

能力中心只负责能力治理与协作规范，不直接承载旅游业务代码、生产数据或真实密钥。

## 目录导航

| 文件 | 用途 |
|---|---|
| `00-control-console.md` | 统一任务入口、路由和状态总览 |
| `01-skills-center.md` | Skills 登记、验收和生命周期管理 |
| `02-agents-center.md` | Agents 角色、权限和协作边界 |
| `03-sop-library.md` | 标准作业流程目录与模板 |
| `04-installation-archive.md` | 安装、升级、验证和回滚记录 |
| `05-github-pr-audit.md` | GitHub 分支与 PR 审计清单 |
| `06-context-handoff.md` | 上下文压缩、恢复和任务交接 |
| `07-incident-review.md` | 故障记录、根因分析和改进闭环 |
| `08-safety-boundary.md` | 数据、代码、Git 和生产操作红线 |
| `09-version-log.md` | 能力中心版本与变更记录 |

## 使用流程

1. 从总控台登记任务和目标。
2. 选择对应 Skill、Agent 或 SOP。
3. 执行前确认安全边界和所需权限。
4. 执行后记录验证证据、交接信息和版本变化。
5. 涉及 GitHub、数据库或生产环境时，必须保留人工确认节点。

## 基本原则

- 事实优先，不编造配置、数据或验证结果。
- 最小权限，不默认执行 commit、push、merge、发布或生产写入。
- 先检查后执行，所有高风险动作必须可追踪、可中止、可复核。
- 文档先行，能力变更应同步更新入口、SOP、安全边界和版本记录。
- 人工负责最终业务决策和生产操作。
