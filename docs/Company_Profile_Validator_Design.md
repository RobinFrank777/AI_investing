# Company Profile Validator Design

## AI_investing V3.8.0

## 1. 文档目的

本文档定义 AI_investing V3.8.0 中 `company_profile.csv` 的数据验证规则。

Company Profile 是 V3.8.0 Investment Profile 系统的基础数据层之一。

在 Company Profile 数据进入后续 Fundamental、Valuation、Trend、Investment Score 以及 AI Research 模块之前，必须首先完成数据完整性和 Schema 合规性检查。

本验证器的核心目标是：

确保进入 AI_investing 后续分析流程的 Company Profile 数据结构正确、字段完整、关键字段符合定义。

---

## 2. 验证对象

当前验证文件：

`data/company_profile.csv`

当前 Company Profile Schema 共包含 14 个字段：

1. ticker
2. company
3. sector
4. industry
5. country
6. business_model
7. investment_thesis
8. moat_score
9. valuation_type
10. growth_driver
11. risk_factor
12. investment_stage
13. investor_rating
14. last_update

字段的详细定义以：

`docs/Investment_Profile_Data_Dictionary.md`

为准。

系统设计原则以：

`docs/Investment_Profile_Design.md`

为准。

---

## 3. Validator 的系统位置

Company Profile Validator 位于 Investment Profile 数据进入后续分析系统之前。

基本数据流程：

Company Research

↓

company_profile.csv

↓

Company Profile Validator

↓

Validated Company Profile

↓

Fundamental Analysis

↓

Valuation Analysis

↓

Trend Analysis

↓

Investment Score

↓

AI Research / Daily Report

因此：

Company Profile Validator 属于数据质量控制层。

它不负责投资评分。

它不负责 BUY / SELL / HOLD 判断。

它不负责交易信号生成。

---

## 4. 第一阶段验证范围

V3.8.0 Phase 1 采用最小可验证设计。

当前验证器只检查已经正式定义并实际需要的数据质量规则。

第一阶段包括以下八项检查：

1. 14-column schema
2. no missing values
3. ticker unique
4. moat_score valid
5. investor_rating valid
6. valuation_type valid
7. investment_stage valid
8. last_update valid

只有全部检查通过：

Company Profile Validation 才返回 PASS。

---

## 5. Schema Validation

### 5.1 Column Count

Company Profile 必须包含：

14 个字段。

验证目标：

防止字段缺失、字段增加或 CSV Schema 意外变化。

正常输出：

PASS: 14-column schema

如果字段数量不是 14：

Validator 应返回失败。

---

## 6. Missing Value Validation

Company Profile 当前第一阶段要求所有字段均存在有效数据。

Validator 检查整个 DataFrame 是否存在缺失值。

验证目标：

防止不完整的公司研究记录进入后续系统。

正常输出：

PASS: no missing values

如果存在缺失值：

Company Profile Validation 应返回失败。

注意：

未来版本如果部分字段允许为空，应通过 Schema 规则单独定义，而不是直接取消数据完整性检查。

---

## 7. Ticker Validation

`ticker` 是 Company Profile 的核心公司标识字段。

当前验证规则：

ticker 必须唯一。

不允许同一个 ticker 在 Company Profile 中重复出现。

例如：

MSFT

NVDA

RKLB

属于三个独立 Company Profile。

正常输出：

PASS: ticker unique

如果出现重复 ticker：

Validator 应返回失败。

---

## 8. Moat Score Validation

字段：

`moat_score`

定义：

公司长期竞争优势的人工研究评分。

当前合法范围：

0–5

Validator 必须检查所有 moat_score 是否位于合法范围。

正常输出：

PASS: moat_score valid

重要：

moat_score 属于 Company Profile 的研究输入字段。

它不是系统最终 Investment Score。

---

## 9. Investor Rating Validation

字段：

`investor_rating`

定义：

投资者长期研究评分。

该字段记录投资者基于当前研究，对公司长期投资质量所做的人工综合判断。

合法范围：

0–100

当前示例：

MSFT = 90

NVDA = 90

RKLB = 75

评分解释：

90–100：极高质量长期研究对象

80–89：优秀长期研究对象

70–79：具备较强投资研究价值

60–69：需要进一步研究或存在明显风险

0–59：当前长期投资吸引力较低

正常输出：

PASS: investor_rating valid

重要规则：

investor_rating 属于人工研究判断。

未来 Fundamental Score、Valuation Score、Trend Score 和 Investment Score 将由独立模型计算。

不得使用 investor_rating 替代系统模型评分。

---

## 10. Valuation Type Validation

字段：

`valuation_type`

用于描述公司主要适用的估值框架。

当前允许值：

Growth

Value

Cyclical

Asset-Based

Not Applicable

Validator 应检查 valuation_type 是否属于允许集合。

正常输出：

PASS: valuation_type valid

该字段用于未来估值模型选择。

它本身不是估值结果。

---

## 11. Investment Stage Validation

字段：

`investment_stage`

用于描述公司当前所处的投资研究阶段。

当前允许值：

MATURE

GROWTH

EARLY_GROWTH

SPECULATIVE

CYCLICAL

Validator 应检查 investment_stage 是否属于允许集合。

正常输出：

PASS: investment_stage valid

该字段主要用于：

公司分类

风险理解

估值框架选择

投资研究分层

它不直接产生交易信号。

---

## 12. Last Update Validation

字段：

`last_update`

记录 Company Profile 最近一次研究更新时间。

标准格式：

YYYY-MM-DD

例如：

2026-08-10

Validator 应使用日期解析检查该字段是否合法。

正常输出：

PASS: last_update valid

该字段未来可以进一步用于：

研究资料过期检查

自动提醒更新

AI Research freshness control

定期 Company Profile Review

---

## 13. Validation Result

当所有检查全部通过时：

Validator 输出：

COMPANY PROFILE VALIDATION: PASS

并显示：

Companies: N

Errors: 0

其中：

N = 当前 Company Profile 中公司数量。

例如当前 Seed Data：

Companies: 3

Errors: 0

---

## 14. Failure Principle

任何关键验证失败时：

Company Profile 不应被视为 Validated Data。

后续模块不应默认这些数据可靠。

Validator 的基本原则是：

Fail Early

即：

尽可能在数据进入评分模型、AI分析和报告系统之前发现问题。

这样可以避免错误数据继续向后传播。

---

## 15. Validator 与人工研究的关系

Validator 不判断：

公司是否值得投资

估值是否合理

股价是否会上涨

是否应该买入

是否应该卖出

Validator 只判断：

Company Profile 数据是否符合系统定义。

因此必须严格区分：

Data Validation

和：

Investment Judgment

这是 V3.8.0 架构的重要边界。

---

## 16. Validator 与评分系统的关系

未来 AI_investing 将逐步建立：

Fundamental Score

Valuation Score

Trend Score

Investment Score

这些属于系统模型评分层。

Company Profile Validator 位于这些评分模块之前。

正确关系：

Company Profile

↓

Validation

↓

Feature / Fundamental Data

↓

Scoring Models

↓

Investment Score

↓

AI Research

而不是：

Company Profile

↓

investor_rating

↓

Investment Score

因此：

investor_rating 不得直接作为系统最终评分。

---

## 17. 当前 Seed Data

V3.8.0 Phase 1 当前 Company Profile Seed Data 包含：

MSFT

NVDA

RKLB

Seed Data 的目的不是建立完整股票数据库。

其主要作用是：

验证 Schema

验证字段设计

验证 Validator

验证后续模块接口

在系统架构稳定之后，再逐步扩大 Company Profile Universe。

---

## 18. 当前验证状态

V3.8.0 Phase 1 已经实际完成以下验证：

PASS: 14-column schema

PASS: no missing values

PASS: ticker unique

PASS: moat_score valid

PASS: investor_rating valid

PASS: valuation_type valid

PASS: investment_stage valid

PASS: last_update valid

最终结果：

COMPANY PROFILE VALIDATION: PASS

Companies: 3

Errors: 0

这意味着当前 Company Profile Seed Data 已满足 Phase 1 数据结构要求。

---

## 19. Phase 1 范围控制

Phase 1 不增加复杂数据验证框架。

暂不引入：

JSON Schema

Pydantic

数据库 Schema

自动数据修复

复杂异常检测

AI 数据纠错

外部数据源交叉验证

当前阶段继续保持：

简单

可解释

可验证

可维护

---

## 20. 后续开发方向

在 Company Profile Schema 和 Validator 稳定以后，可以逐步增加：

字段类型验证

文本长度检查

Ticker 标准化

Country 标准化

Sector / Industry 标准化

研究数据 freshness 检查

自动 Company Profile 更新

Fundamental Data 接入

Valuation Model 接入

Trend Model 接入

Investment Score 接入

AI Research 接入

这些功能必须分阶段开发。

不得在 Phase 1 一次性加入。

---

## 21. V3.8.0 Phase 1 设计结论

Company Profile Validator 是 AI_investing Investment Profile 系统的数据质量入口。

其职责可以概括为：

Research Data

↓

Schema

↓

Validation

↓

Trusted Input

↓

Scoring / AI Analysis

V3.8.0 Phase 1 的目标不是建立复杂的数据治理系统。

当前目标是建立一个：

结构明确

规则明确

可以实际运行

可以实际验证

可以逐步扩展

的 Company Profile 数据基础层。

这将作为后续 Fundamental、Valuation、Trend、Investment Score 和 AI Research 模块的基础。