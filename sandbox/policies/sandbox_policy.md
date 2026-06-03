# 沙箱策略

1. 沙箱脚本只能在当前 run 目录中读写文件。
2. 沙箱脚本不能修改 `src/`、`configs/`、`data/`、`output/` 中的正式文件。
3. 沙箱脚本不能读取 `chuangma/config.json`、环境变量中的 API key 或其他凭证。
4. 沙箱脚本不能联网、不能下单、不能执行破坏性命令。
5. 每次实验必须生成 `experiment_result.json`、`experiment_report.md` 和 `promotion_proposal.md`。
