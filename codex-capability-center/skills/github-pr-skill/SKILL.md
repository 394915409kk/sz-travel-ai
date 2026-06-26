---
name: github-pr-skill
description: Prepare, inspect, summarize, and manage GitHub branch and pull request workflows for Shenzhen Zhily repositories. Use when the task mentions GitHub, PR, branch, commit, push, merge, CI, review comments, or release notes.
---

# GitHub PR Skill

## 触发场景

- 创建分支、整理提交、准备 PR 描述、处理 review 意见。
- 查看 CI 失败、PR diff、合并前状态。
- 用户要求 commit、push、merge 或只执行其中某一步。

## 执行流程

1. 确认仓库根目录、远端、当前分支、工作区状态和用户授权边界。
2. 如果用户限制“只 commit / 不 push / 不 merge”，严格遵守。
3. 提交前梳理改动范围，避免夹带无关文件。
4. PR 描述包含背景、改动、验证、风险和回滚。
5. CI 或 review 失败时先读失败证据，再定向修复。

## 禁止事项

- 不自动 merge、push、发布或改写历史，除非用户明确授权。
- 不提交密钥、cookie、生产配置、客户隐私或付款数据。
- 不跨仓库误操作；尤其要确认 `394915409kk/sz-travel-ai` 与其他仓库边界。
- 不把未验证的业务数据写进 PR 结论。

## 完成标准

- 分支、提交、PR 或 CI 状态清楚。
- 用户授权范围内的 GitHub 操作已完成。
- PR 说明可供 reviewer 快速理解。
- 剩余风险和下一步动作明确。

## 输出格式

```markdown
## GitHub 状态
- 仓库：
- 分支：
- 操作：
- 验证：
- 下一步：
```
