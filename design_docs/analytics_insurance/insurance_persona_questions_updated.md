# Insurance Analytics Demo – Questions by Persona

This document lists example analytics questions that can be answered with the demo auto + property insurance schemas
(`core`, `auto_insurance`, `property_insurance`, `analytics.customer_360`). Questions are grouped by persona.

---

## 1. Executive Leadership (CEO / COO / CFO / Chief Underwriting Officer)

1. **Loss ratio by LOB and state over time**  
   Over the last 24 months, what is our loss ratio (total incurred claims / earned premium) by line of business and by state, and which combinations are above our target threshold?

2. **Customer segment profitability**  
   For each customer segment (e.g., HNW, personal standard, SMB), what are written premium, loss ratio, and average claim severity over the last 3 years?

3. **Growth vs profitability by agent region**  
   How has our policy count and written premium grown by agent region and line of business, and did the loss ratio worsen or improve in those growth areas?

4. **Tenure vs loss ratio**  
   Do long-tenured customers (tenure > 5 years) have materially better loss ratios than new customers in their first policy term, by line of business?

5. **Hot-spot territories**  
   Identify the top 10 ZIP or territory clusters where we have high written premium, loss ratio > 70%, and claim frequency above the portfolio average, and show which agents and product codes dominate those clusters.

---

## 2. Underwriting & Product Management

1. **Underwriting tier performance**  
   For each underwriting tier (PREFERRED, STANDARD, NON_STANDARD) and line of business, what are claim frequency, average severity, and loss ratio?

2. **Auto risk score adequacy**  
   Within personal auto, how does loss ratio vary by risk score deciles (e.g., 0.2–0.3, 0.3–0.4, …), and do we see any deciles where pricing looks inadequate?

3. **Auto severity by vehicle characteristics**  
   For auto collision and comprehensive claims, how does average incurred loss vary by vehicle model year and vehicle make?

4. **Property risk factors**  
   In homeowners and small commercial property, how do claim frequency and severity vary by construction type and year built, controlling for state?

5. **Multi-factor segment profitability**  
   For personal auto policies written in the last 3 years, segment customers by risk score decile, prior claims count (0, 1, 2+), and distribution type (INDEPENDENT vs CAPTIVE vs BROKER), and for each segment show earned premium, claim frequency, average severity, and loss ratio so we can identify where we are under-pricing or over-pricing.

---

## 3. Claims Management

1. **Cycle time by claim type and channel**  
   What is the average time to close (from report date to close date) by claim type and reported channel, and where are we significantly slower than average?

2. **Litigated vs non-litigated performance**  
   How do average incurred amounts (paid + reserves) and time to close differ between litigated and non-litigated claims, by line of business?

3. **Single-payment vs multi-payment claims**  
   For claims with multiple financial transactions versus those with a single transaction, how does ultimate incurred amount differ by claim type and cause of loss?

4. **Payee concentration**  
   By payee type (insured, third party, law firm, vendor) and line of business, what portion of total claim payments are we making, and how concentrated are payments in a small set of payees?

5. **Claims portfolio health by segment**  
   For the last 2 accident years, by state × line of business × cause of loss, show claim frequency per 1,000 exposures, average severity (total incurred), average claim cycle time, litigation rate, and attorney representation rate, and highlight segments where both cycle time and severity are above the 75th percentile.

---

## 4. Distribution / Sales / Agency Management

1. **Agent productivity and profitability**  
   Which agents have the highest written premium, and what are their loss ratios by line of business over the last 3 years?

2. **Regional mix and risk**  
   By agent region, how is premium split across AUTO vs HOME vs SMALL_COMMERCIAL, and which regions are over-indexed in higher-risk tiers or higher loss ratios?

3. **New business vs renewal quality**  
   For each agent, compare new business (first-term policies) vs renewal-tenure customers (tenure > 3 years) in terms of loss ratios and claim frequency.

4. **HNW property focus**  
   Which agents are most effective in writing HNW homeowners in specific high-value ZIP codes, and what are their corresponding loss ratios?

5. **Agent portfolio segmentation**  
   For each agent and line of business, show 3-year written premium, policy count, average risk score, loss ratio, and share of HNW/SMB customers, and identify agents who are high-growth with deteriorating loss ratios versus those with strong growth and improving loss ratios.

---

## 5. Customer Service / Operations / Contact Center

1. **Time-to-resolution by segment and geography**  
   For each customer segment and state, what is the average time from loss date to report date and from report date to close date?

2. **Aging open claims and impacted customers**  
   Which open claims have been in status OPEN for more than 90 days, and which customers have more than one such claim?

3. **Channel performance comparison**  
   Comparing claims reported via AGENT vs INSURED vs THIRD_PARTY, which channel has shorter or longer report-to-close time, higher claim frequency, and higher litigation or attorney representation rates?

4. **High-risk and complex claim customers**  
   Which customers have multiple claims in the last 24 months and at least one claim with severe injury severity or high incurred amounts, and are their claims resolving slower than average?

5. **Customer experience indicators by segment**  
   For each customer segment × line of business × state, show claim frequency per 1,000 policies, average time to first payment (from report date to first LOSS payment transaction), average claim cycle time, and share of claims with attorney representation, and flag segments where time to first payment and cycle time are both in the worst quartile.
