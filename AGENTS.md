# AGENTS.md

本文件用于约束 Codex / AI coding agent 在本仓库中的后续开发行为。

## 必读上下文

- 开始任何后续开发前，必须先阅读 [docs/progress.md](docs/progress.md)。
- `docs/progress.md` 是唯一项目级进度与资产总账。
- README 只作为入口文档，不要把阶段流水账写回 README。
- 不确定的信息必须标记为“待人工确认”，不要编造分支状态、功能完成度或识别效果。

## 文档规则

- 不要重复创建 README、progress、asset 相关文档，例如 `README_v2.md`、`progress_new.md`、`asset_new.md`。
- 如果需要更新项目状态，优先更新现有 `README.md`、`AGENTS.md`、`docs/progress.md`。
- 新功能开发完成后必须更新 `docs/progress.md`。
- 后续新增模块文档时，应放在 `docs/modules/` 下，并由 `docs/progress.md` 引用；当前阶段不要主动拆分过多文档。

## 模块边界

- `frontend`、`layout-crop`、`table-recognition`、`backend-integration` 等模块不要混改。
- 文档整理任务中不要修改功能代码、前端页面、模型调用、识别流程或图纸切割逻辑。
- 当前新的图纸切割重构分支是后续 table-recognition 的推荐基础。
- 旧版切割分支只作为历史验证资产，不作为后续主线。
- 前端分支当前主要作为流程展示/原型资产，后续需要与真实识别结果联调。

## 当前分支共识

- 当前分支 `feature/phase1-layout-governance-opus` 用于新版图纸版面检测和图片切割能力收尾。
- 当前分支完成文档收尾后，可作为 `feature/table-recognition` 的基础。
- 本地旧版切割/表格解析相关分支需要人工确认边界后再决定是否合并。

## Coding Workflow

- After every code change, the final response must include a concise "How to test" section.
- The test instructions should name the exact commands, working directory, and expected result when practical.
- If a test cannot be run in the current environment, explain why and provide the closest runnable alternative.
- Keep unrelated local changes untouched unless the user explicitly asks to modify them.
