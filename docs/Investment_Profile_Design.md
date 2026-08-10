企业投资档案模块设计文档（正式版 V1.0）

文档定位：
AI_investing 从「技术分析系统」向「投资研究系统」升级的基础模块。

1. 文档目的
1.1 背景

AI_investing V3.7.0 已经完成：

市场数据更新
技术指标计算
股票筛选
回测分析
组合模拟
风险分析
股票研究卡片
Daily Research Terminal

当前系统主要关注：

股票价格行为（Price Behavior）

例如：

趋势是否向上？
动量是否增强？
是否突破？
风险是否可控？

但是长期投资决策还需要回答：

这家公司本身是否值得长期持有？

因此增加：

Investment Profile Module
2. 模块定位
2.1 系统层级

未来 AI_investing 架构：

                 AI_investing


                      │


        ┌─────────────┴─────────────┐


        │                           │


 Technical Engine             Research Engine


        │                           │


价格趋势                      企业质量


技术指标                      商业模式


交易信号                      竞争优势


风险控制                      成长逻辑



        └─────────────┬─────────────┘


                      │


             Investment Score Engine


                      │


             Stock Research Card


                      │


             Daily Research Terminal

3. 模块目标

Investment Profile 不负责：

实时价格
技术指标
财务计算

它负责：

企业长期研究信息管理

包括：

公司是谁
做什么业务
如何赚钱
为什么可能增长
是否具有竞争优势
最大风险在哪里
当前投资阶段
4. 数据文件设计
文件位置
data/

    company_profile.csv

5. 数据字段设计
5.1 基础信息字段
字段	类型	说明
ticker	string	股票代码
company	string	公司名称
sector	string	行业
industry	string	细分行业
country	string	国家

示例：

NVDA,NVIDIA,Technology,Semiconductor,USA
6. 商业模式字段

字段：

business_model

定义：

公司通过什么方式创造收入？

示例：

NVDA：

设计GPU和AI计算平台，
通过数据中心、游戏和专业计算业务销售硬件与软件生态。

TSLA：

新能源汽车、能源存储、
自动驾驶软件和机器人业务。
7. 投资逻辑字段

字段：

investment_thesis

定义：

为什么未来可能创造投资回报？

要求：

必须回答：

增长来源
核心逻辑
长期机会

示例：

NVDA：

AI基础设施建设推动GPU需求增长，
CUDA生态形成长期竞争壁垒。

RKLB：

商业航天产业增长，
发射服务和卫星平台业务具有长期扩张潜力。
8. 护城河评分

字段：

moat_score

类型：

整数

范围：

0-5

定义：

评分	含义
0	没有明显优势
1	弱优势
2	一般优势
3	明显优势
4	强竞争壁垒
5	极强护城河

评价因素：

技术壁垒
网络效应
品牌
成本优势
数据优势
生态系统
9. 增长驱动

字段：

growth_driver

定义：

未来3-10年的主要增长来源。

例如：

NVDA：

AI服务器
Blackwell架构
数据中心
CUDA生态

TSLA：

Robotaxi
FSD
Energy Storage
Optimus
10. 风险因素

字段：

risk_factor

定义：

记录投资失败可能原因。

例如：

NVDA：

AI资本开支下降
竞争加剧
估值压力

RKLB：

发射失败风险
盈利周期较长
商业航天竞争
11. 投资阶段

字段：

investment_stage

分类：

类别	说明
Mature	成熟企业
Growth	成长企业
Early Growth	早期成长
Speculative	高风险创新
Cyclical	周期企业

示例：

股票	阶段
MSFT	Mature Growth
NVDA	Growth
RKLB	Early Growth
ASTS	Speculative
12. 投资者评分

字段：

investor_rating

范围：

0-100

说明：

这是人工研究评分。

不是模型评分。

作用：

记录：

当前阶段投资者对公司的整体判断。

例如：

NVDA

90


RKLB

70
13. 更新时间

字段：

last_update

格式：

YYYY-MM-DD

用途：

跟踪研究有效期。

14. 完整 Schema

最终：

ticker

company

sector

industry

country

business_model

investment_thesis

moat_score

growth_driver

risk_factor

investment_stage

investor_rating

last_update

15. 数据维护规则
15.1 更新频率

不是每日更新。

建议：

季度更新

结合：

财报
管理层变化
行业变化
15.2 重大事件更新

以下情况立即更新：

CEO变化
商业模式变化
重大收购
技术路线变化
竞争格局变化
16. 与现有系统连接

V3.8.0之后：

Stock Card升级：

当前：

Technical Summary

Price

Trend

Risk

Signal


增加：

Company Profile


Business Model

Investment Thesis

Moat

Growth

Risk


形成完整研究卡片。

17. 与AI模块连接

未来：

增加：

AI Research Agent

自动生成：

投资摘要
多空观点
风险提示
财报解读

输入：

company_profile.csv

+

financial_data

+

news


输出：

AI Analyst Summary

18. 第一阶段范围控制

V3.8.0 Phase 1：

只完成：

✅ 数据结构
✅ CSV文件
✅ 读取模块
✅ 单元测试

暂不实现：

❌ 自动新闻抓取
❌ AI自动评分
❌ 财务模型
❌ 自动投资建议

原因：

先建立稳定基础。

19. Phase 1 文件规划

新增：

docs/

    Investment_Profile_Design.md


data/

    company_profile.csv


src/

    company_profile.py


tests/

    test_company_profile.py

20. 开发流程

严格按照 AI_investing 原流程：

设计文档

↓

建立CSV

↓

读取模块

↓

测试

↓

接入Stock Card

↓

Git Commit

↓

版本升级

文档结束

版本：

Investment_Profile_Design.md

Version: V1.0

For AI_investing V3.8.0
