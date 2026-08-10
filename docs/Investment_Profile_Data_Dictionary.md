Investment Profile Data Dictionary
AI_investing V3.8.0

Version: V1.0

Purpose:

定义 AI_investing 长期投资研究系统中 Company Profile 数据结构、字段含义和填写规则。

1. ticker
Definition

股票代码。

Format
使用市场标准代码
大写
与 stock_loader 数据接口保持一致
Example
NVDA
MSFT
TSM
RKLB
2. company
Definition

公司名称。

Example
NVIDIA Corporation
Microsoft Corporation
Tesla Inc.
3. sector
Definition

行业大类。

Standard Categories
Technology
Semiconductor
Healthcare
Financial
Consumer
Industrial
Energy
Communication
Aerospace
Purpose

用于未来：

行业权重分析
行业轮动研究
组合风险控制
4. industry
Definition

细分行业。

Example

NVDA:

AI Semiconductor

TSM:

Foundry Semiconductor

RKLB:

Space Infrastructure
5. country
Definition

公司所属国家或主要经营区域。

Purpose

用于：

地域风险分析
全球资产配置
宏观环境分析
Format

使用国家标准英文名称。

Example
United States
Taiwan
China
Germany
6. business_model
Definition

公司商业模式描述。

用于说明：

公司如何赚钱
收入来源
客户类型
商业壁垒来源
Writing Principle

要求：

简洁
可解释
避免营销语言
Example
NVIDIA
GPU platform company providing AI computing hardware and software ecosystem.
Microsoft
Enterprise software, cloud computing and AI platform provider.
Costco
Membership-based retail model generating recurring revenue.
7. investment_thesis
Definition

投资逻辑。

说明为什么该公司值得长期研究或持有。

Purpose

建立长期投资判断基础。

Required Content

至少包含：

核心业务优势
长期成长驱动因素
竞争优势
投资周期逻辑
Example
AI infrastructure leader benefiting from long-term AI computing demand growth.
8. moat_score
Definition

公司护城河评分。

用于衡量企业长期竞争优势。

Score Range
0 - 10
Scoring Reference
9-10

极强护城河：

网络效应
平台优势
技术领先
品牌壁垒

Example:

MSFT
NVDA
GOOGL
6-8

较强竞争优势：

行业领先
稳定客户
规模优势

Example:

TSM
AVGO
COST
0-5

弱护城河：

周期公司
竞争激烈
产品容易替代
9. growth_driver
Definition

长期增长驱动力。

用于描述未来 3-10 年影响公司增长的核心因素。

Categories

可以包括：

AI Adoption

Cloud Computing

Semiconductor Cycle

Space Economy

Healthcare Innovation

Energy Transition

Consumer Growth

Automation
Example
RKLB
Space infrastructure growth driven by launch services and satellite systems.
AMD
AI accelerator demand and data center expansion.
10. valuation_type
Definition

估值分析类型。

不同企业采用不同估值方法。

Standard Values
Growth

Quality Growth

Value

Cyclical

Asset Based

Turnaround
Example
Ticker	Valuation Type
NVDA	Growth
MSFT	Quality Growth
JPM	Value
CAT	Cyclical
INTC	Turnaround
11. risk_factor
Definition

主要投资风险。

用于长期风险管理。

Required Content

包括：

行业风险
公司风险
估值风险
宏观风险
Example
NVDA
High valuation, semiconductor cycle risk, increasing competition.
TSM
Geopolitical risk and semiconductor cycle volatility.
12. investment_stage
Definition

投资阶段分类。

用于区分：

当前是否适合买入
是否观察
是否等待机会
Standard Values
Core Holding

Growth Candidate

Watchlist

Research

Avoid
Example
NVDA:
Core Holding

RKLB:
Growth Candidate

High valuation startup:
Research
13. last_update
Definition

最后更新时间。

用于追踪公司信息更新。

Format
YYYY-MM-DD
Example
2026-08-10
Company Profile 数据结构总结

当前基础字段：

字段	作用
ticker	股票代码
company	公司名称
sector	行业
industry	细分行业
country	国家
business_model	商业模式
investment_thesis	投资逻辑
moat_score	护城河评分
growth_driver	成长驱动
valuation_type	估值类型
risk_factor	风险因素
investment_stage	投资阶段
last_update	更新时间
AI_investing V3.8.0 长期投资模型定位

Company Profile 是未来长期投资研究系统的基础数据层。

未来系统将基于：

Company Profile
        |
        ↓
Investment Quality Analysis
        |
        ↓
Growth Analysis
        |
        ↓
Valuation Analysis
        |
        ↓
Technical Trend Analysis
        |
        ↓
Investment Decision

形成：

价值投资为底层
+
趋势分析寻找买点
+
风险控制决定仓位

的长期投资研究框架。