# Investment Profile Data Dictionary
AI_investing V3.8.0

Version: V1.0

## Purpose:

定义 AI_investing 长期投资研究系统中 Company Profile 数据结构、字段含义和填写规则。

## 1. ticker
### Definition

股票代码。

### Format
使用市场标准代码
要求：
大写
与 stock_loader 数据接口保持一致
### Example
NVDA
MSFT
TSM
RKLB
## 2. company
### Definition

公司名称。

### Example
NVIDIA Corporation
Microsoft Corporation
Tesla Inc.
## 3. sector
### Definition

行业大类。

### Standard Categories
Technology
Semiconductor
Healthcare
Financial
Consumer
Industrial
Energy
Communication
Aerospace
### Purpose

用于未来：

行业权重分析
行业轮动研究
组合风险控制
## 4. industry
### Definition

细分行业。

### Example

NVDA:

AI Semiconductor

TSM:

Foundry Semiconductor

RKLB:

Space Infrastructure
## 5. country
### Definition

公司所属国家或主要经营区域。

### Purpose

用于：

地域风险分析
全球资产配置
宏观环境分析
### Format

使用国家标准英文名称。

### Example
United States
Taiwan
China
Germany
## 6. business_model
### Definition

公司商业模式描述。

用于说明：

公司如何赚钱
收入来源
客户类型
商业壁垒来源
### Writing Principle

要求：

简洁
可解释
避免营销语言
### Example
NVIDIA
GPU platform company providing AI computing hardware and software ecosystem.
Microsoft
Enterprise software, cloud computing and AI platform provider.
Costco
Membership-based retail model generating recurring revenue.
## 7. investment_thesis
### Definition

投资逻辑。

说明为什么该公司值得长期研究或持有。

### Purpose

建立长期投资判断基础。

### Required Content

至少包含：

核心业务优势
长期成长驱动因素
竞争优势
投资周期逻辑
### Example
AI infrastructure leader benefiting from long-term AI computing demand growth.

## 8. moat_score
### Definition
公司护城河评分。
用于衡量企业长期竞争优势的强弱。
### Score Range
0 – 5
### Scoring Reference
5
极强护城河。
企业具有非常强且可持续的长期竞争优势，例如强大的网络效应、平台优势、技术领先、品牌壁垒、规模优势或高转换成本。
4
强护城河。
企业具有明显且较稳定的竞争优势，竞争对手较难在短期内复制或替代。
3
明显竞争优势。
企业具有一定的长期竞争优势，但护城河强度或持续性仍需要持续观察。
2
一般竞争优势。
企业存在部分竞争优势，但行业竞争较强，优势的长期持续性存在不确定性。
1
弱护城河。
企业只有有限的竞争优势，产品、技术、品牌或商业模式较容易被竞争对手替代。
0
无明显护城河。
目前没有发现足够证据证明企业具有可持续的长期竞争优势。
### Example
MSFT
5
Reason
Microsoft 具有企业软件生态、云计算平台、客户转换成本、品牌和规模等多重长期竞争优势。

## 9. valuation_type

### Definition

公司当前适用的估值方法类型。

### Standard Values

Growth

Value

Cyclical

Asset-Based

Not Applicable


### Example

NVDA

Growth


BRK.B

Value


MU

Cyclical

## 10. growth_driver
### Definition

长期增长驱动力。

用于描述未来 3-10 年影响公司增长的核心因素。

### Categories

可以包括：

AI Adoption

Cloud Computing

Semiconductor Cycle

Space Economy

Healthcare Innovation

Energy Transition

Consumer Growth

Automation
### Example
RKLB
Space infrastructure growth driven by launch services and satellite systems.
AMD
AI accelerator demand and data center expansion.

## 11. risk_factor
### Definition

主要投资风险。

用于长期风险管理。

### Required Content

包括：

行业风险
公司风险
估值风险
宏观风险
### Example
NVDA
High valuation, semiconductor cycle risk, increasing competition.
TSM
Geopolitical risk and semiconductor cycle volatility.
## 12. investment_stage

### Definition

公司当前所处的长期投资生命周期或企业发展阶段。

该字段描述企业属性，不表示买入、卖出或持有建议。

### Standard Values

MATURE

GROWTH

EARLY_GROWTH

SPECULATIVE

CYCLICAL

### Examples

MSFT:
MATURE

NVDA:
GROWTH

RKLB:
EARLY_GROWTH

ASTS:
SPECULATIVE

MU:
CYCLICAL

## 13. investor_rating

### Definition

投资者长期研究评分。

该字段记录投资者基于当前研究，对公司长期投资质量所做的人工综合判断。

它不是系统自动评分，也不是 BUY、SELL 或 HOLD 信号。

### Score Range

0–100

### Interpretation

90–100：极高质量长期研究对象

80–89：优秀长期研究对象

70–79：具备较强投资研究价值

60–69：需要进一步研究或存在明显风险

0–59：当前长期投资吸引力较低

### Important Rule

investor_rating 属于人工研究判断。

未来 Fundamental Score、Valuation Score、Trend Score 和 Investment Score 将由独立模型计算。

不得使用 investor_rating 替代系统模型评分。

## 14. last_update
### Definition

最后更新时间。

用于追踪公司信息更新。

### Format
YYYY-MM-DD
### Example
2026-08-10
## Company Profile 数据结构总结

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
investor_rating    人工长期研究评分
last_update	更新时间
## AI_investing V3.8.0 长期投资模型定位

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