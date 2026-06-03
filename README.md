# 单品种期货研究多 Agent

本项目把单品种商品期货研究拆成一套可控、可审计、可复跑的多 Agent 流程。第一版以鸡蛋 `JD` 为样例，读取现有鸡蛋交易系统输出，并按统一契约生成研究报告、最新交易文件、回测图表、品种评分卡和验收报告。

## 设计原则

- 先交易假设，再做数据字典、FeatureSpec、建模和回测。
- LangGraph 风格的状态机负责编排和门禁，Python 工具负责可复现计算。
- 大模型只负责研究判断、解释、反证和报告，不直接替代标签构造、回测和可执行性检查。
- 单边和跨期目标必须来自真实可交易合约或真实合约对。
- 最新交易模块只输出交易建议，不自动下单。

## 安装

```bash
python -m pip install -e .
```

可选安装 Agent / PDF 依赖：

```bash
python -m pip install -e ".[agent,pdf]"
```

## 运行

一键从头到尾执行鸡蛋 full 流程：读取本项目数据、刷新 Tushare 行情缓存、调用大模型生成沙箱实验代码并执行评估、训练并固化模型、生成信号、独立逐日真实合约回测、生成报告和最新交易文件。

```bash
bash run.sh
```

等价命令：

```bash
PYTHONPATH=src python -m futures_research_agents.cli --commodity egg --mode full --refresh-market --print-summary
```

只跑研究骨架：

```bash
python -m futures_research_agents.cli --commodity egg --mode research-only
```

只生成线上执行前置文件：

```bash
python -m futures_research_agents.cli --commodity egg --mode latest-trade --refresh-market
```

## 数据输入

正式输入放在 `data/`：

```text
data/fundamentals/egg/raw/        # 钢联、产业、人工 CSV
data/fundamentals/egg/latest/     # 当前正式最新基本面文件
data/fundamentals/egg/processed/  # as-of 对齐后的月频面板
data/market/egg/                  # 全合约、连续、基差、仓单等行情数据
data/cache/egg/                   # Tushare 或其他行情缓存
```

## 输出

每个品种独立输出：

```text
output/egg/latest/
output/egg/tables/
output/egg/figures/
output/egg/reports/
output/egg/metadata/
output/egg/models/
```

优先阅读：

1. `output/egg/latest/latest_instruction.csv`
2. `output/egg/latest/latest_actionable_trade.csv`
3. `output/egg/reports/research_report.md`
4. `output/egg/reports/signal_explain.md`
5. `output/egg/reports/commodity_scorecard.md`
6. `output/egg/reports/acceptance_report.md`

模型固化产物位于：

```text
output/egg/models/
├── outright_model.pkl
├── outright_model_feature_params.json
├── outright_model_selected_features.json
├── outright_model_metadata.json
├── outright_model_manifest.json
├── calendar_model.pkl
├── calendar_model_feature_params.json
├── calendar_model_selected_features.json
├── calendar_model_metadata.json
└── calendar_model_manifest.json
```

训练阶段会保存模型对象、训练集拟合出的特征均值/标准差、入选特征、目标定义和数据区间。后续使用时只能加载 bundle 后执行 `transform + predict`，不能重新 fit。

## Agent 职责

- `ProjectIntakeAgent`：读取品种配置、流程文档和运行模式。
- `HypothesisAgent`：生成交易假设库和反证变量。
- `DataDictionaryAgent`：固定数据字典、公布日和 as-of 规则。
- `FeatureStudyAgent`：生成 FeatureSpec、字段卡和特征缺口建议。
- `TargetBuilderAgent`：声明真实单边和跨期目标、波动率和流动性规则。
- `OutrightModelAgent`：适配或生成单边预测结果。
- `CalendarModelAgent`：适配或生成跨期预测结果。
- `LeakageAuditAgent`：检查未来函数、测试集调参和合约选择穿越。
- `SignalSynthesisAgent`：合成单边和跨期信号并输出降级等级。
- `LatestTradeExecutionAgent`：抽取最新行情、筛选可交易合约或合约对，输出最新交易文件。
- `BacktestReportAgent`：生成回测表格和收益率、回撤等图表。
- `CommodityScorecardAgent`：对品种研究质量打分。
- `ReportAndAcceptanceAgent`：生成研究报告、信号解释、PDF/备用报告和验收结论。

## 中文 Prompt

每个 Agent 的中文 Prompt 模板位于：

```text
src/futures_research_agents/prompts/
```

模板统一包含角色、输入、任务、输出格式、约束、禁止事项和质量检查。当前系统即使没有 LLM 依赖，也会使用规则节点兜底；后续接入 LLM 时，可以通过 `PromptLoader` 加载模板并注入当前 state、品种配置和流程文档摘要。

## 从训练到线上使用

`full` 模式会完整执行：

```text
生成或读取本项目 data/ 内特征面板
-> 训练单边/跨期模型
-> 保存模型 bundle 到 output/egg/models/
-> 重新加载已保存模型
-> 对最新特征执行 predict
-> 生成 signal.csv 和 latest_instruction.csv
-> 执行 latest trade 检查
-> 输出报告和验收结果
```

线上使用时应直接读取 `*_manifest.json`，加载 `*.pkl` 和保存的特征参数，对最新基本面和行情特征做同口径转换后预测。

## 沙箱实验

沙箱用于让 Agent 在受控目录中自动生成和执行实验代码，但不直接修改正式项目代码。`bash run.sh` 的 full 流程会自动执行一次 `model_experiment` 沙箱实验；如果 Qwen/`langchain-openai` 可用，会优先使用大模型生成 `experiment.py`，否则回退到内置模板，保证一键流程不中断。

```bash
python -m futures_research_agents.cli --commodity egg --mode sandbox-feature --experiment-name inventory_cross_test
python -m futures_research_agents.cli --commodity egg --mode sandbox-model --experiment-name ridge_vs_rf_test
```

输出目录：

```text
sandbox/runs/[run_id]/
├── experiment.py
├── input_state.json
├── stdout.txt
├── stderr.txt
├── experiment_result.json
├── experiment_report.md
└── promotion_proposal.md
```

本轮沙箱是否使用大模型可查看：

```text
sandbox/runs/[run_id]/run_metadata.json
```

沙箱只允许写入当前 run 目录，不允许读取 API key、不允许自动下单、不允许直接修改 `src/` 正式代码。实验通过后只生成提升建议，是否合并仍需人工确认。

## 新增品种

1. 复制 `configs/commodities/egg.yaml` 为新文件，例如 `methanol.yaml`。
2. 修改品种代码、交易所、合约乘数、手续费、流动性阈值和现有系统路径。
3. 把产业 CSV 放入 `data/fundamentals/[commodity]/raw/`。
4. 运行 `research-only`，先检查假设、数据字典和 FeatureSpec。
5. 接入真实标签和模型后，再运行 `explain-existing` 或 `full`。
