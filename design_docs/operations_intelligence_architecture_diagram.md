# Operations Intelligence - Architecture Diagram

A visual representation of the Operations Intelligence platform architecture for executive presentations.

---

## System Architecture Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#8B5CF6', 'secondaryColor': '#F8F5F0', 'tertiaryColor': '#E8F5F0', 'background': '#FFFFFF', 'mainBkg': '#FFFFFF', 'secondBkg': '#F8F5F0', 'border1': '#FF7B6B', 'border2': '#8B5CF6', 'note': '#FFF5F3', 'text': '#1a0d13', 'textColor': '#1a0d13'}}}%%
flowchart TB
    subgraph Sources["OPERATIONAL DATA SOURCES"]
        direction LR
        Jira["<b>Jira</b><br/><i>Engineering</i><br/>Sprints & Velocity<br/>Work Items"]
        HubSpot["<b>HubSpot</b><br/><i>Marketing</i><br/>Campaigns & Leads<br/>Pipeline Data"]
        Salesforce["<b>Salesforce</b><br/><i>Sales</i><br/>Opportunities<br/>Revenue & Accounts"]
        Analytics["<b>Google Analytics</b><br/><i>Product</i><br/>Traffic & Conversions<br/>User Behavior"]
    end

    subgraph MCP["MCP INTEGRATION LAYER"]
        direction LR
        JiraMCP["jira-mcp<br/>server"]
        HubSpotMCP["hubspot-mcp<br/>server"]
        SalesforceMCP["salesforce-mcp<br/>server"]
        AnalyticsMCP["analytics-mcp<br/>server"]
    end

    subgraph Platform["ELIZA INTELLIGENCE PLATFORM"]
        direction TB
        
        subgraph Ingestion["Data Ingestion"]
            MCPClient["<b>MCP Client Manager</b><br/>Real-time data orchestration"]
            EntityResolver["<b>Entity Resolver</b><br/>Cross-system mapping"]
        end
        
        subgraph Engine["Intelligence Engine"]
            MetricEngine["<b>Metric Calculation Engine</b><br/>25 metrics across 5 roles<br/>Redis caching & trending"]
        end
        
        subgraph Agents["AI SYNTHESIS AGENTS"]
            direction LR
            ExecAgent["<b>Executive</b><br/>Chief of Staff<br/>Analyst"]
            MktgAgent["<b>Marketing</b><br/>Demand Gen<br/>Analyst"]
            SalesAgent["<b>Sales</b><br/>RevOps<br/>Analyst"]
            ProductAgent["<b>Product</b><br/>Analytics<br/>Strategist"]
            CSAgent["<b>CS</b><br/>Customer Health<br/>Analyst"]
        end
    end

    subgraph Outputs["ROLE-SPECIFIC INSIGHTS"]
        direction LR
        ExecView["<b>EXECUTIVE</b><br/>NRR / Rule of 40<br/>LTV:CAC / Margins<br/>Revenue Risk"]
        MktgView["<b>MARKETING</b><br/>Pipeline/Dollar<br/>ICP Coverage<br/>Funnel Rates"]
        SalesView["<b>SALES</b><br/>Win Rates<br/>Deal Velocity<br/>Quota Attainment"]
        ProductView["<b>PRODUCT</b><br/>Activation<br/>Feature Adoption<br/>Time to Value"]
        CSView["<b>CS</b><br/>GRR / Expansion<br/>Health Scores<br/>Churn Signals"]
    end

    subgraph Delivery["DELIVERY CHANNELS"]
        direction LR
        Dashboard["<b>Interactive<br/>Dashboard</b><br/>Real-time metrics<br/>& visualizations"]
        Chat["<b>Conversational<br/>AI</b><br/>Natural language<br/>queries"]
        Reports["<b>Scheduled<br/>Reports</b><br/>Daily, Weekly<br/>Monthly"]
    end

    Jira --> JiraMCP
    HubSpot --> HubSpotMCP
    Salesforce --> SalesforceMCP
    Analytics --> AnalyticsMCP

    JiraMCP --> MCPClient
    HubSpotMCP --> MCPClient
    SalesforceMCP --> MCPClient
    AnalyticsMCP --> MCPClient

    MCPClient --> EntityResolver
    EntityResolver --> MetricEngine

    MetricEngine --> ExecAgent
    MetricEngine --> MktgAgent
    MetricEngine --> SalesAgent
    MetricEngine --> ProductAgent
    MetricEngine --> CSAgent

    ExecAgent --> ExecView
    MktgAgent --> MktgView
    SalesAgent --> SalesView
    ProductAgent --> ProductView
    CSAgent --> CSView

    ExecView --> Dashboard
    MktgView --> Dashboard
    SalesView --> Dashboard
    ProductView --> Dashboard
    CSView --> Dashboard

    ExecView --> Chat
    MktgView --> Chat
    SalesView --> Chat
    ProductView --> Chat
    CSView --> Chat

    ExecView --> Reports
    MktgView --> Reports
    SalesView --> Reports
    ProductView --> Reports
    CSView --> Reports
```

---

## Data Flow Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#8B5CF6', 'secondaryColor': '#F8F5F0', 'tertiaryColor': '#E8F5F0'}}}%%
flowchart LR
    subgraph Input["Data Sources"]
        Raw["Raw Operational<br/>Data"]
    end

    subgraph Transform["Transformation"]
        MCP["MCP Protocol<br/>Standardization"]
        Entity["Entity<br/>Resolution"]
        Metric["Metric<br/>Calculation"]
    end

    subgraph Intelligence["AI Processing"]
        Agent["Role-Specific<br/>Synthesis Agent"]
    end

    subgraph Output["Delivery"]
        Insight["Tailored<br/>Insights"]
    end

    Raw -->|"API Calls"| MCP
    MCP -->|"Normalized Data"| Entity
    Entity -->|"Unified Entities"| Metric
    Metric -->|"Calculated Metrics"| Agent
    Agent -->|"Synthesized Analysis"| Insight
```

---

## Role-Based Metric Distribution

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#8B5CF6'}}}%%
flowchart TB
    subgraph MetricEngine["METRIC CALCULATION ENGINE<br/><i>25 Core Metrics</i>"]
        direction TB
        Calc["Real-time Calculation<br/>Historical Trending<br/>Redis Caching"]
    end

    subgraph Executive["EXECUTIVE METRICS"]
        E1["Net Revenue Retention"]
        E2["Rule of 40"]
        E3["LTV/CAC by Segment"]
        E4["Gross Margin"]
        E5["Revenue Concentration"]
    end

    subgraph Marketing["MARKETING METRICS"]
        M1["Pipeline per Dollar"]
        M2["ICP Coverage Ratio"]
        M3["Funnel Conversion Rates"]
        M4["Cost per Pipeline"]
        M5["PQL % of Pipeline"]
    end

    subgraph Sales["SALES METRICS"]
        S1["Win Rate by Segment"]
        S2["Average Deal Size"]
        S3["Sales Cycle Length"]
        S4["Quota Distribution"]
        S5["CAC Payback Period"]
    end

    subgraph Product["PRODUCT METRICS"]
        P1["Activation Rate"]
        P2["Feature Adoption"]
        P3["Product-Led Expansion"]
        P4["Time to Value"]
        P5["Churn Attribution"]
    end

    subgraph CS["CS METRICS"]
        C1["Gross Revenue Retention"]
        C2["Expansion ARR/Customer"]
        C3["Health Score Accuracy"]
        C4["Time to First Expansion"]
        C5["ARR per CSM"]
    end

    MetricEngine --> Executive
    MetricEngine --> Marketing
    MetricEngine --> Sales
    MetricEngine --> Product
    MetricEngine --> CS
```

---

## MCP Server Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#14B8A6'}}}%%
flowchart TB
    subgraph MCPServers["MCP SERVER LAYER<br/><i>Model Context Protocol</i>"]
        direction TB
        
        subgraph JiraServer["jira-mcp"]
            JT1["get_sprint_velocity"]
            JT2["get_ticket_lifecycle"]
            JT3["get_engineering_metrics"]
            JR1["jira://issues"]
            JR2["jira://sprints"]
        end
        
        subgraph HubSpotServer["hubspot-mcp"]
            HT1["get_deals_by_stage"]
            HT2["get_pipeline_metrics"]
            HT3["get_campaign_attribution"]
            HR1["hubspot://deals"]
            HR2["hubspot://contacts"]
        end
        
        subgraph SalesforceServer["salesforce-mcp"]
            ST1["get_opportunities"]
            ST2["get_revenue_metrics"]
            ST3["get_account_health"]
            SR1["sf://opportunities"]
            SR2["sf://accounts"]
        end
        
        subgraph AnalyticsServer["analytics-mcp"]
            AT1["get_traffic_metrics"]
            AT2["get_conversion_funnel"]
            AT3["get_user_behavior"]
            AR1["ga://traffic"]
            AR2["ga://conversions"]
        end
    end

    subgraph Client["MCP CLIENT MANAGER"]
        Orchestrator["Connection Orchestrator<br/>Health Monitoring<br/>Retry Logic"]
    end

    JiraServer --> Client
    HubSpotServer --> Client
    SalesforceServer --> Client
    AnalyticsServer --> Client
```

---

## AI Agent Synthesis Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#8B5CF6', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#6D28D9', 'lineColor': '#FF9580'}}}%%
flowchart LR
    subgraph Input["INPUT"]
        Customer["Customer/Account<br/>Selection"]
        Role["Stakeholder<br/>Role"]
    end

    subgraph Processing["AGENT PROCESSING"]
        Filter["Role Metric<br/>Filter"]
        Context["Context<br/>Builder"]
        Agent["Synthesis<br/>Agent"]
    end

    subgraph Output["OUTPUT"]
        Headline["Headline<br/>Summary"]
        Metrics["Key Metrics<br/>with Trends"]
        Risks["Risk<br/>Signals"]
        Actions["Recommended<br/>Actions"]
    end

    Customer --> Filter
    Role --> Filter
    Filter --> Context
    Context --> Agent
    Agent --> Headline
    Agent --> Metrics
    Agent --> Risks
    Agent --> Actions
```

---

## Executive Summary View

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#19C37D', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#0D9668', 'lineColor': '#FF9580'}}}%%
flowchart TB
    subgraph Summary["OPERATIONS INTELLIGENCE - EXECUTIVE VIEW"]
        direction TB
        
        subgraph Value["VALUE DELIVERED"]
            V1["Unified View<br/>Single source of truth<br/>across all systems"]
            V2["Role-Tailored<br/>Each stakeholder sees<br/>relevant metrics"]
            V3["Real-Time<br/>Live data with<br/>< 5 min latency"]
            V4["AI-Synthesized<br/>Actionable insights<br/>not just data"]
        end
        
        subgraph Stack["TECHNOLOGY STACK"]
            S1["MCP Protocol<br/>Standardized integration"]
            S2["CrewAI Agents<br/>Specialized synthesis"]
            S3["Redis + PostgreSQL<br/>Caching & history"]
            S4["React Dashboard<br/>Interactive delivery"]
        end
        
        subgraph Outcome["BUSINESS OUTCOMES"]
            O1["Faster Decisions<br/>Minutes not hours"]
            O2["Better Alignment<br/>Shared metrics across teams"]
            O3["Proactive Action<br/>AI-detected risks & opportunities"]
        end
    end
```

---

## DETAILED VIEW: Executive / HoldCo Role

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#8B5CF6', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#6D28D9', 'lineColor': '#FF9580', 'secondaryColor': '#F8F5F0'}}}%%
flowchart TB
    subgraph Objective["EXECUTIVE OBJECTIVE"]
        Goal["<b>Maximize Enterprise Value</b><br/><i>Through capital allocation, portfolio focus, and durable growth</i>"]
    end

    subgraph DataSources["DATA SOURCES"]
        direction LR
        SF["<b>Salesforce</b><br/>Revenue Data<br/>Account ARR<br/>Churn Records"]
        HS["<b>HubSpot</b><br/>Pipeline Data<br/>CAC Components<br/>Marketing Spend"]
        Fin["<b>Financial Systems</b><br/>COGS Data<br/>Profit Margins<br/>Operating Costs"]
    end

    subgraph Metrics["EXECUTIVE METRICS"]
        direction TB
        
        subgraph NRR["<b>Net Revenue Retention</b><br/><i>Lagging / Shared</i>"]
            NRR_Q["Is the core business<br/>compounding without<br/>proportional new spend?"]
            NRR_F["(Starting MRR + Expansion<br/>- Contraction - Churn)<br/>/ Starting MRR"]
            NRR_D["Reinvest decisions<br/>Pricing validation<br/>M&A vs organic"]
        end

        subgraph R40["<b>Rule of 40</b><br/><i>Lagging / Shared</i>"]
            R40_Q["Are we balancing growth<br/>and profitability for<br/>our stage?"]
            R40_F["Revenue Growth Rate %<br/>+ Profit Margin %"]
            R40_D["Burn vs growth tradeoffs<br/>Margin expansion timing<br/>Board narrative"]
        end

        subgraph LTV["<b>LTV/CAC by Segment</b><br/><i>Lagging / Shared</i>"]
            LTV_Q["Where does incremental<br/>capital create the most<br/>long-term value?"]
            LTV_F["(ARPU x Gross Margin<br/>x Avg Lifetime) / CAC"]
            LTV_D["Segment prioritization<br/>Channel mix decisions<br/>GTM scaling pace"]
        end

        subgraph GM["<b>Gross Margin by Product</b><br/><i>Lagging / Shared</i>"]
            GM_Q["Which offerings<br/>scale economically?"]
            GM_F["(Revenue - COGS)<br/>/ Revenue"]
            GM_D["Product investment<br/>Services vs software mix<br/>Pricing floors"]
        end

        subgraph RC["<b>Revenue Concentration</b><br/><i>Lagging / Shared</i>"]
            RC_Q["How fragile is<br/>the revenue base?"]
            RC_F["Top N Customer Revenue<br/>/ Total Revenue"]
            RC_D["Vertical expansion<br/>Enterprise vs PLG<br/>Risk management"]
        end
    end

    subgraph Agent["EXECUTIVE SYNTHESIS AGENT"]
        AgentDef["<b>Chief of Staff Analyst</b><br/>━━━━━━━━━━━━━━━━━━━━<br/><i>Goal:</i> Synthesize operational data<br/>into board-ready insights focusing on<br/>enterprise value, capital efficiency,<br/>and strategic positioning<br/>━━━━━━━━━━━━━━━━━━━━<br/><i>Tools:</i> metric_tool, trend_tool,<br/>benchmark_tool, forecast_tool"]
    end

    subgraph Output["EXECUTIVE OUTPUT"]
        direction TB
        
        subgraph Headline["HEADLINE"]
            HL["<b>Acme Corp: NRR 112%</b><br/>Rule of 40 at 52, LTV:CAC 4.2x<br/>High-value expansion ready"]
        end

        subgraph Summary["EXECUTIVE SUMMARY"]
            ES["Core business compounding at 12%<br/>net expansion. Gross margins healthy<br/>at 78%. Top 3 customers represent<br/>18% of ARR - within tolerance."]
        end

        subgraph KeyMetrics["KEY METRICS WITH TRENDS"]
            KM1["NRR: 112% ↑3%"]
            KM2["Rule of 40: 52 ↑5"]
            KM3["LTV:CAC: 4.2x ↓0.3"]
            KM4["Gross Margin: 78% →"]
            KM5["Top 10 Concentration: 35% ↓2%"]
        end

        subgraph Risks["RISK SIGNALS"]
            R1["LTV:CAC declining - monitor<br/>CAC efficiency in Enterprise"]
            R2["Q4 churn forecast elevated<br/>in Mid-Market segment"]
        end

        subgraph Actions["RECOMMENDED ACTIONS"]
            A1["1. Reallocate $500K from<br/>SMB to Enterprise GTM"]
            A2["2. Accelerate Mid-Market<br/>retention program"]
            A3["3. Review pricing for<br/>Professional tier"]
        end
    end

    subgraph Decisions["DECISIONS INFLUENCED"]
        D1["Capital Allocation"]
        D2["M&A Strategy"]
        D3["Segment Investment"]
        D4["Board Narrative"]
        D5["Pricing Strategy"]
    end

    DataSources --> Metrics
    Metrics --> Agent
    Agent --> Output
    Output --> Decisions
```

---

## DETAILED VIEW: Sales Role

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#3AA0FF', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#1E7FD9', 'lineColor': '#FF9580', 'secondaryColor': '#F8F5F0'}}}%%
flowchart TB
    subgraph Objective["SALES OBJECTIVE"]
        Goal["<b>Convert Demand into Durable Revenue</b><br/><i>At the right cost and velocity</i>"]
    end

    subgraph DataSources["DATA SOURCES"]
        direction LR
        SF["<b>Salesforce</b><br/>Opportunities<br/>Win/Loss Records<br/>Rep Quotas<br/>Account Data"]
        HS["<b>HubSpot</b><br/>Lead Source<br/>Marketing Attribution<br/>Contact History"]
        Comp["<b>Compensation System</b><br/>Quota Assignments<br/>Attainment Records<br/>Commission Data"]
    end

    subgraph Metrics["SALES METRICS"]
        direction TB
        
        subgraph WR["<b>Win Rate by Segment</b><br/><i>Lagging / Shared</i>"]
            WR_Q["Where do we win<br/>when we compete?"]
            WR_F["Won Deals /<br/>(Won + Lost Deals)"]
            WR_D["Segment focus<br/>Qualification rigor<br/>Competitive positioning"]
        end

        subgraph ADS["<b>Average Deal Size</b><br/><i>Lagging / Shared</i>"]
            ADS_Q["Are we moving upmarket<br/>or commoditizing?"]
            ADS_F["Total Bookings /<br/>Deal Count"]
            ADS_D["Rep specialization<br/>Packaging & bundling<br/>Motion selection"]
        end

        subgraph SCL["<b>Sales Cycle Length</b><br/><i>Lagging / Shared</i>"]
            SCL_Q["How fast can we convert<br/>growth into cash?"]
            SCL_F["Avg(Close Date -<br/>Create Date)"]
            SCL_D["Forecast accuracy<br/>Headcount planning<br/>Motion tradeoffs"]
        end

        subgraph QA["<b>Quota Attainment</b><br/><i>Lagging / Local</i>"]
            QA_Q["Is performance systemic<br/>or hero-driven?"]
            QA_F["Rep Bookings /<br/>Rep Quota (distribution)"]
            QA_D["Territory design<br/>Enablement vs hiring<br/>Comp plan redesign"]
        end

        subgraph CAC["<b>CAC Payback Period</b><br/><i>Lagging / Shared</i>"]
            CAC_Q["How long before growth<br/>investments self-fund?"]
            CAC_F["CAC / (ARPU x<br/>Gross Margin)"]
            CAC_D["Hiring pace<br/>Discounting discipline<br/>Market entry timing"]
        end
    end

    subgraph Agent["SALES SYNTHESIS AGENT"]
        AgentDef["<b>Revenue Operations Analyst</b><br/>━━━━━━━━━━━━━━━━━━━━<br/><i>Goal:</i> Provide sales leadership<br/>with actionable insights on pipeline<br/>health, rep performance, and deal<br/>optimization<br/>━━━━━━━━━━━━━━━━━━━━<br/><i>Tools:</i> metric_tool, pipeline_tool,<br/>forecast_tool, rep_performance_tool"]
    end

    subgraph Output["SALES OUTPUT"]
        direction TB
        
        subgraph Headline["HEADLINE"]
            HL["<b>Q4 Pipeline: $4.2M at Risk</b><br/>Enterprise win rate up 8%, SMB declining<br/>3 reps below 50% attainment"]
        end

        subgraph Summary["EXECUTIVE SUMMARY"]
            ES["Enterprise motion showing strong<br/>momentum with 42% win rate (up from 34%).<br/>SMB velocity deals taking 12 days longer<br/>than benchmark. Quota distribution skewed<br/>- top 20% of reps driving 55% of bookings."]
        end

        subgraph KeyMetrics["KEY METRICS WITH TRENDS"]
            KM1["Win Rate (Ent): 42% ↑8%"]
            KM2["Win Rate (SMB): 28% ↓4%"]
            KM3["Avg Deal (Ent): $85K ↑12%"]
            KM4["Cycle Length: 47 days ↑5"]
            KM5["CAC Payback: 14 mo ↑2"]
        end

        subgraph Pipeline["PIPELINE HEALTH"]
            P1["Stage 3+: $8.2M (68% coverage)"]
            P2["Commit: $3.1M"]
            P3["At Risk: $4.2M (aging deals)"]
            P4["Created This Month: $2.8M"]
        end

        subgraph Risks["RISK SIGNALS"]
            R1["12 deals in Stage 4 with<br/>no activity in 14+ days"]
            R2["SMB conversion dropping -<br/>possible ICP mismatch"]
            R3["3 Enterprise deals pushing<br/>to Q1 (budget freeze)"]
        end

        subgraph Actions["RECOMMENDED ACTIONS"]
            A1["1. Executive sponsor calls<br/>on 5 stalled Enterprise deals"]
            A2["2. SMB qualification criteria<br/>review - tighten ICP"]
            A3["3. Enablement blitz for<br/>bottom quartile reps"]
            A4["4. Discount approval for<br/>Q4 close acceleration"]
        end
    end

    subgraph Decisions["DECISIONS INFLUENCED"]
        D1["Pipeline Management"]
        D2["Territory Design"]
        D3["Rep Enablement"]
        D4["Hiring Priorities"]
        D5["Forecast Accuracy"]
        D6["Discount Strategy"]
    end

    DataSources --> Metrics
    Metrics --> Agent
    Agent --> Output
    Output --> Decisions
```

---

## Executive vs Sales: Metric Overlap

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#8B5CF6'}}}%%
flowchart LR
    subgraph Shared["SHARED METRICS<br/><i>Both roles care about</i>"]
        S1["LTV/CAC Ratio"]
        S2["CAC Payback Period"]
        S3["Revenue by Segment"]
        S4["Win Rate Trends"]
    end

    subgraph ExecOnly["EXECUTIVE ONLY<br/><i>Board-level view</i>"]
        E1["Net Revenue Retention"]
        E2["Rule of 40"]
        E3["Gross Margin by Product"]
        E4["Revenue Concentration"]
    end

    subgraph SalesOnly["SALES ONLY<br/><i>Operational view</i>"]
        SA1["Quota Attainment Distribution"]
        SA2["Sales Cycle Length"]
        SA3["Pipeline Coverage Ratio"]
        SA4["Deal Velocity by Stage"]
    end

    ExecOnly --> Shared
    Shared --> SalesOnly
```

---

## Decision Flow: How Metrics Drive Action

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#19C37D', 'primaryTextColor': '#1a0d13', 'primaryBorderColor': '#0D9668', 'lineColor': '#8B5CF6'}}}%%
flowchart TB
    subgraph Trigger["METRIC SIGNAL"]
        Signal["NRR drops below 100%<br/>or Win Rate declines 10%+"]
    end

    subgraph Analysis["AI ANALYSIS"]
        direction TB
        ExecView["<b>Executive Agent</b><br/>Identifies: Churn concentrated<br/>in Mid-Market segment"]
        SalesView["<b>Sales Agent</b><br/>Identifies: Win rate down<br/>due to longer cycles"]
    end

    subgraph Synthesis["CROSS-ROLE SYNTHESIS"]
        Combined["<b>Combined Insight</b><br/>Mid-Market customers churning<br/>because sales cycle too long -<br/>competitors winning on speed"]
    end

    subgraph Action["RECOMMENDED ACTIONS"]
        direction TB
        ExecAction["<b>Executive Action</b><br/>Reallocate budget from<br/>SMB to Mid-Market<br/>retention program"]
        SalesAction["<b>Sales Action</b><br/>Implement deal desk<br/>fast-track for Mid-Market<br/>competitive deals"]
    end

    subgraph Outcome["MEASURED OUTCOME"]
        Result["Track: Mid-Market win rate<br/>and cycle length over 90 days"]
    end

    Trigger --> Analysis
    ExecView --> Synthesis
    SalesView --> Synthesis
    Synthesis --> Action
    ExecAction --> Outcome
    SalesAction --> Outcome
```

---

## Color Reference (Eliza Platform)

| Element | Color | Hex |
|---------|-------|-----|
| Brand Primary | Coral Pink | `#FF9580` |
| Brand Strong | Salmon | `#FF7B6B` |
| AI Purple | Purple | `#8B5CF6` |
| AI Teal | Teal | `#14B8A6` |
| AI Success | Green | `#19C37D` |
| AI Info | Blue | `#3AA0FF` |
| AI Warning | Yellow | `#F4C542` |
| AI Danger | Red | `#EF4444` |
| Background | Cream | `#F8F5F0` |
| Text | Dark | `#1a0d13` |

---

## Usage Notes

These diagrams are designed for:
- Executive presentations
- Technical architecture reviews
- Stakeholder alignment meetings
- Product documentation

To render these diagrams:
1. **GitHub/GitLab**: Renders automatically in markdown files
2. **Mermaid Live Editor**: https://mermaid.live
3. **Confluence**: Use Mermaid plugin
4. **Slides**: Export as SVG from Mermaid Live Editor


