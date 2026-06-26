# 00｜Codex能力中心｜Skills-Agents-SOP

这是深圳职旅 AI 数字员工系统的 Codex 能力中心，用于统一管理可复用的执行规则、skills、agents、prompts、checklists、playbooks、scripts 和 references。

## 项目边界

- 只沉淀 Codex 能力资产，不开发业务主系统功能。
- 不连接真实密码、付款权限、生产数据库或客户隐私数据。
- 所有业务事实、价格、库存、政策、成本和利润结论必须有证据；没有证据时使用 `待补充`、`待核价`、`待人工确认`。

## 目录说明

- `AGENTS.md`：深圳职旅 Codex 总规则，后续可同步到相关工作区作为最高执行规范。
- `skills/`：按任务类型拆分的 Codex skill，每个 skill 都包含触发、流程、禁止事项和完成标准。
- `agents/`：面向角色的数字员工说明书，用于明确 CEO、销售、产品、财务等角色边界。
- `prompts/`：新任务、Review、Bugfix、PR、上下文交接等可复用提示词模板。
- `checklists/`：代码质量、数据库迁移、API、安全、业务逻辑和上线前验收清单。
- `playbooks/`：销售、产品、供应商、财务、投诉、合同等运营 SOP。
- `scripts/`：本地辅助脚本，用于环境检查、skill 安装和同步到目标仓库。
- `references/`：系统地图、业务边界、编码标准和风控红线。

## 使用建议

1. 新任务先查 `AGENTS.md` 与对应 skill。
2. 工程任务使用 `prompts/codex-new-task-template.md` 发起，结束时用对应 checklist 验收。
3. 业务任务先查 `references/company-business-boundaries.md` 和 `references/risk-control-redlines.md`。
4. 成熟 skill 经人工验收后，只能先用 dry-run 预演同步，不得直接修改主项目。

## 同步流程安全规则

能力中心资产同步到主项目前，必须按以下标准流程执行：

1. 先 dry-run，只预览将复制的目录、文件和覆盖风险。
2. 人工检查 dry-run 输出，确认没有敏感资料、客户隐私、合同原件、财务敏感数据或供应商底价。
3. 人工确认目标仓库路径，确认确实是目标 Git 仓库且包含 `.git`。
4. 人工确认允许同步的 skill 范围，未成熟或含敏感内容的文件不得同步。
5. 只有在人工确认后，才允许显式使用 `--apply`。
6. 同步后进入主项目检查 git diff，确认只包含预期能力资产。
7. 运行相关测试或至少完成文档/脚本结构检查。
8. 人工确认后才允许 commit。
9. commit 后由人工决定是否 push。
10. PR 和 merge 必须人工确认，不能由本项目自动执行。

强制边界：

- 本项目不能自动修改主项目。
- 本项目不能自动 commit。
- 本项目不能自动 push。
- 本项目不能自动 merge。
- 本项目不能自动发布。
- 涉及真实业务资料、客户隐私、合同、财务、供应商底价、付款审批的内容不能直接同步到主项目。
- `scripts/install_skills.sh` 和 `scripts/sync_agents_to_repo.sh` 默认都是 dry-run；只有显式传入 `--apply` 才会真实复制。

## 第一版状态

本版本为能力中心初始化版本，所有内容均为可迭代草案，不包含真实生产凭据、客户隐私或付款权限。
