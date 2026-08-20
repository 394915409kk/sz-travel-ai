# 工作区长期记忆（本项目：WorkBuddy 迭代主基地）

> 从每日日志提炼的长期有效事实。新会话先读这里，再按需查日志。

## 项目定位
本工作区（2026-08-20-11-16-17）是 WorkBuddy 长期学习型项目的主基地，承载治理体系搭建、自动化矩阵运维与「职旅AI成长计划」推进。

## 治理基线（2026-08-21 更新）

- **P0 三项全部清零**：飞书已连 ✅、职旅日报已重建 ✅、GitHub 已连 ✅
- **GitHub 基线更正**：记忆中的 5940d41 在仓库中不存在；codex 系统基线为 main 分支 `b86e7bf`（2026-06-27，PR #12）；WorkBuddy 独立基线在 `workbuddy/ops-baseline` 分支（2026-08-21 建立）
- **WorkBuddy 基线已锁库**：分支 `workbuddy/ops-baseline` @ `761c3a6`（2026-08-21），含教程+审核报告+双层记忆 6 文件，https://github.com/394915409kk/sz-travel-ai/tree/workbuddy/ops-baseline

## 自动化矩阵（当前有效）

| 任务 | 时间 | ID | 状态 |
|---|---|---|---|
| 职旅日报 | 每日 08:00 | automation-1787261750236 | ✅ ACTIVE，6 条文旅爆款推飞书群 |
| 每日 AI 新闻推送 | 每日 09:00 | automation-1787195938577 | ✅ ACTIVE（2026-08-20 重建修复空推送） |
| 投资四时段 | 09:00/10:00/14:30/15:05 工作日 | （挂投资工作区） | ✅ ACTIVE |
| 每日自动学习 | 每日 21:00 | （推荐先审后装） | ✅ ACTIVE |
| ~~跨境电商展会~~ | 08-02 已过期 | automation-1786197234949 | ⚠️ 待 KK 确认删除 |

## 关键操作参数

- 飞书推送：`lark-cli im +messages-send --as bot --chat-id oc_b2498b47caf0e8ea798a70d0927ac470 --markdown "..."`
- 飞书身份：user=陈桂芹（ou_82bfe7d80a7510d5ed4a14fc72c8ff44），bot=cli_aa0dcce6bc78dd1d 已进公司群
- GitHub 推送：**PAT 模式**（token 存 `~/.workbuddy/github_pat`，权限600，仅本机）。OAuth 连接器只读，写操作用 Python + GitHub REST API（Git Data API：blob→tree→commit→update ref）。分支 workbuddy/ops-baseline，目录 workbuddy/。**注意：github_pat 文件与日志中的 token 绝不推送到 GitHub**

## 已沉淀技能

- `workbuddy-automation-ops`（用户级）：空推送诊断五步法 + 自动化 prompt 五要素 + lark-cli 排障

## 待办（P1/P2）

- P1：44 次部署台账盘点（设置→数据管理→我发布的应用）
- P1：过期展会任务删除（待确认）
- P1：25 个空会话窗口清理（KK 界面操作：空间「⋯」→从列表中移除）
- P2：八大板块能力映射表、「超级金牌股神」专家固化、12+ 岗位试点启动
