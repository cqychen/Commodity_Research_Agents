from __future__ import annotations

from pathlib import Path
from typing import Any

from ..tools.io import write_json, write_markdown


def build_scorecard(state: dict[str, Any]) -> dict[str, Any]:
    leakage_ok = state.get("leakage_audit", {}).get("leakage_ok", False)
    latest_trade = state.get("latest_trade", {})
    existing = state.get("existing_outputs", {})
    feature_count = len(state.get("feature_spec", []))
    real_data_used = state.get("outright_model", {}).get("data_source", "").endswith(".csv")
    tushare_ok = bool(latest_trade.get("market_data_metadata")) or bool(
        state.get("latest_trade", {}).get("tushare_refresh", {}).get("success")
    )
    data_quality = 85 if real_data_used and tushare_ok else 75 if real_data_used else 75 if existing.get("available") else 55

    scores = {
        "data_quality": data_quality,
        "feature_explainability": min(90, 50 + feature_count * 8),
        "leakage_reliability": 85 if leakage_ok else 40,
        "outright_model_stability": 70 if state.get("outright_model") else 50,
        "calendar_model_stability": 70 if state.get("calendar_model") else 50,
        "signal_quality": 72 if state.get("signal_synthesis") else 50,
        "tradability": 80 if latest_trade.get("actionable") else 60,
        "risk_control": 70,
        "latest_signal_confidence": 72 if latest_trade else 50,
        "maintainability": 80,
    }
    total = round(sum(scores.values()) / len(scores), 2)
    if total >= 80:
        verdict = "可上线或小规模实盘观察"
    elif total >= 65:
        verdict = "有条件通过，需要记录风险并继续观察"
    elif total >= 50:
        verdict = "研究质量不足，建议继续优化特征或模型"
    else:
        verdict = "不建议上线，优先修复数据、目标、穿越或可执行性问题"
    return {"total_score": total, "scores": scores, "verdict": verdict}


SCORE_LABELS = {
    "data_quality": "数据质量",
    "feature_explainability": "特征解释力",
    "leakage_reliability": "防穿越可信度",
    "outright_model_stability": "单边模型稳定性",
    "calendar_model_stability": "跨期模型稳定性",
    "signal_quality": "组合信号质量",
    "tradability": "交易可执行性",
    "risk_control": "风险控制",
    "latest_signal_confidence": "最新信号可信度",
    "maintainability": "可维护性",
}


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _write_pdf(path: Path, content: str) -> None:
    import hashlib

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfdoc
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    # Some Python/OpenSSL builds do not accept hashlib.md5(usedforsecurity=False),
    # while newer ReportLab passes that keyword. Normalize it here for this process.
    pdfdoc.md5 = lambda *args, **kwargs: hashlib.md5(*args)
    font_name = "STSong-Light"
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    page_width, page_height = A4
    pdf = canvas.Canvas(str(path), pagesize=A4)
    left_margin = 42
    top_margin = 42
    bottom_margin = 42
    line_height = 14
    max_chars = 58

    text = pdf.beginText(left_margin, page_height - top_margin)
    text.setFont(font_name, 10)
    for raw_line in content.splitlines():
        wrapped = _wrap_cjk_line(raw_line, max_chars=max_chars)
        for line in wrapped:
            if text.getY() <= bottom_margin:
                pdf.drawText(text)
                pdf.showPage()
                text = pdf.beginText(left_margin, page_height - top_margin)
                text.setFont(font_name, 10)
            text.textLine(line)
            text.moveCursor(0, line_height - 12)
    pdf.drawText(text)
    pdf.save()


def _wrap_cjk_line(line: str, max_chars: int) -> list[str]:
    if not line:
        return [""]
    chunks: list[str] = []
    current = line
    while len(current) > max_chars:
        chunks.append(current[:max_chars])
        current = current[max_chars:]
    chunks.append(current)
    return chunks


def generate_reports(state: dict[str, Any], output_dirs: dict[str, Path]) -> dict[str, str]:
    reports_dir = output_dirs["reports"]
    metadata_dir = output_dirs["metadata"]

    scorecard = build_scorecard(state)
    state["scorecard"] = scorecard

    commodity = state.get("commodity_meta", {}).get("display_name", state.get("commodity_id", "commodity"))
    synthesis = state.get("signal_synthesis", {})
    latest_trade = state.get("latest_trade", {})
    sandbox = state.get("sandbox_result", {})

    research_md = f"""# {commodity} 单品种期货研究报告

## 执行摘要

- 研究模式：`{state.get("mode")}`
- 最新方向：`{synthesis.get("direction", "neutral")}`
- 最佳表达：`{synthesis.get("selected_expression", "observe")}`
- 降级等级：`{synthesis.get("degrade_level", "只观察")}`
- 品种评分：`{scorecard["total_score"]}`，结论：{scorecard["verdict"]}

## 交易假设库

{_bullet([item.get("hypothesis", "") for item in state.get("hypothesis_db", [])])}

## 数据和特征

- as-of 规则：{state.get("data_dict", {}).get("asof_rules", "待确认")}
- FeatureSpec 数量：{len(state.get("feature_spec", []))}
- 特征门禁：{state.get("feature_gate", {}).get("accepted")}

## 最新交易

- 最新指令：`{latest_trade.get("latest_instruction", "")}`
- 当前可执行交易：`{latest_trade.get("latest_actionable_trade", "")}`
- 执行阻塞数量：{len(latest_trade.get("execution_blockers", []))}

## 沙箱实验

- 沙箱 run：`{sandbox.get("run_dir", "未执行")}`
- 实验代码：`{sandbox.get("experiment_result", "未生成")}`
- 实验报告：`{sandbox.get("experiment_report", "未生成")}`
- 提升建议：`{sandbox.get("promotion_proposal", "未生成")}`
- 是否建议提升：{sandbox.get("recommend_promotion", False)}

## 下一步优化建议

{_bullet(state.get("feature_gap_recommendations", ["补充更多可按公布日追踪的库存、利润、仓单和期限结构数据。"]))}
"""

    signal_md = f"""# 最新信号解释和反证

## 交易结论

- 方向：{synthesis.get("direction", "neutral")}
- 入场评级：{synthesis.get("entry_rating", "observe")}
- 最佳表达：{synthesis.get("selected_expression", "observe")}

## 证据

- 客观赔率：{synthesis.get("objective_payoff", "基差、期限结构和真实合约可执行性待持续跟踪。")}
- 胜率证据：{synthesis.get("win_rate_evidence", "供需、库存、利润和季节特征需要逐月更新。")}
- 估值驱动矩阵：{synthesis.get("valuation_driver_matrix", "估值和驱动未完全同向时保持降级。")}

## 验证与反证

- 确认变量：库存、基差、期限结构、成交持仓、波动率。
- 失效变量：核心数据缺失、合约流动性不足、样本外衰减、信号与基本面冲突。
- 数据缺口：{", ".join(state.get("feature_gap_recommendations", ["待补充"]))}
"""

    acceptance = state.get("acceptance", {})
    acceptance_md = f"""# 上线验收报告

- 验收结论：{acceptance.get("verdict", "有条件通过")}
- 防穿越通过：{state.get("leakage_audit", {}).get("leakage_ok")}
- 输出契约通过：{acceptance.get("output_contract_ok")}
- 品种评分：{scorecard["total_score"]}

## 风险

{_bullet(acceptance.get("risks", ["第一版主要复用既有鸡蛋输出，后续需要把 RF 与 Calendar 逻辑模块化。"]))}
"""

    scorecard_md = "# 品种评分卡\n\n"
    scorecard_md += f"- 总分：{scorecard['total_score']}\n"
    scorecard_md += f"- 结论：{scorecard['verdict']}\n\n"
    for key, value in scorecard["scores"].items():
        scorecard_md += f"- {SCORE_LABELS.get(key, key)}（`{key}`）：{value}\n"

    paths = {
        "research_report": str(reports_dir / "research_report.md"),
        "signal_explain": str(reports_dir / "signal_explain.md"),
        "acceptance_report": str(reports_dir / "acceptance_report.md"),
        "commodity_scorecard": str(reports_dir / "commodity_scorecard.md"),
        "scorecard_json": str(metadata_dir / "commodity_scorecard.json"),
    }
    write_markdown(Path(paths["research_report"]), research_md)
    write_markdown(Path(paths["signal_explain"]), signal_md)
    write_markdown(Path(paths["acceptance_report"]), acceptance_md)
    write_markdown(Path(paths["commodity_scorecard"]), scorecard_md)
    write_markdown(reports_dir / "commodity_research_report_source.md", research_md + "\n\n" + scorecard_md)
    write_json(Path(paths["scorecard_json"]), scorecard)

    pdf_path = reports_dir / "commodity_research_report.pdf"
    _write_pdf(pdf_path, research_md + "\n\n" + scorecard_md)
    paths["commodity_research_report_pdf"] = str(pdf_path)

    return paths
