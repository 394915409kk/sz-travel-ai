# SZ Travel AI System Map

## 能力中心位置

`00｜Codex能力中心｜Skills-Agents-SOP` 是 Codex 能力资产仓，不是业务主系统。

## 主要资产流向

- `AGENTS.md`：同步到主项目或业务工作区，作为 Codex 总规则。
- `skills/`：成熟后可同步到主项目 `.codex/skills/` 或用户 Codex skills 目录。
- `agents/`：同步为数字员工角色说明，供任务入口和自动化引用。
- `prompts/`：作为发起任务、review、bugfix、PR 和上下文交接模板。
- `checklists/`：作为验收标准。
- `playbooks/`：作为业务 SOP。
- `references/`：作为业务边界、系统边界和风险红线。

## 与主项目边界

- 主项目 `394915409kk/sz-travel-ai` 承载业务系统代码。
- 本项目只提供 Codex 执行规范和模板。
- 同步前必须人工确认目标路径、分支、工作区状态和是否允许 commit/push。
