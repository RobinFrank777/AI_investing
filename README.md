# AI Investing

Python量化投资学习项目。

通过真实投资分析场景学习：

* Python编程
* Pandas数据分析
* Matplotlib数据可视化
* 股票风险分析
* 量化选股
* 策略研究

---

## 项目功能

### 1. 投资组合分析

* 收益统计
* 收益率排行
* 持仓分析
* HTML报告生成

文件：

```text
portfolio_v3.py
```

---

### 2. 均线优化分析

寻找历史表现最佳均线组合。

文件：

```text
heatmap.py
```

输出：

```text
ma_optimization.csv
optimization_heatmap.png
```

---

### 3. 持仓周期分析

研究不同持有时间的收益表现。

文件：

```text
holding_period.py
holding_chart.py
```

---

### 4. 风险分析

计算：

* 最大回撤
* 波动率

文件：

```text
risk_analysis.py
```

---

### 5. 夏普比率分析

计算风险调整后收益。

文件：

```text
sharpe_analysis.py
```

---

### 6. 股票画像分析

计算：

* 年化收益
* 波动率
* 最大回撤
* 夏普比率

文件：

```text
stock_personality.py
stock_personality_chart.py
```

---

### 7. 风险收益分析

构建风险收益散点图。

文件：

```text
risk_return_chart.py
```

---

### 8. 股票评分系统

综合：

* 收益率
* 夏普比率
* 最大回撤
* 波动率

自动生成股票排名。

文件：

```text
stock_score.py
```

---

## 技术栈

* Python
* Pandas
* NumPy
* Matplotlib

---

## 项目结构

```text
AI_investing
│
├── stock_loader.py
├── portfolio_v3.py
├── heatmap.py
├── holding_period.py
├── holding_chart.py
├── risk_analysis.py
├── sharpe_analysis.py
├── stock_personality.py
├── stock_personality_chart.py
├── risk_return_chart.py
├── stock_score.py
│
├── data/
├── charts/
├── report.html
└── README.md
```

---

## 学习目标

本项目用于学习：

* Python编程
* 数据分析
* 数据可视化
* 量化投资研究
* 自动化投资报告生成

---

作者：Robin
