-- ============================================================
-- TechFlow SaaS Analytics — SQL Queries
-- Database: techflow (PostgreSQL 14)
-- Tables: customers (7,043 rows), ab_test (294,478 rows)
--
-- Each query answers a real business question.
-- SQL concepts are introduced one at a time, building on each other.
-- ============================================================


-- ============================================================
-- Q1 — SELECT + basic aggregation
-- Business question: How many customers are on each plan type?
-- ============================================================
-- The most basic query pattern: count rows grouped by a category.
-- COUNT(*) = count every row in the group.
-- ORDER BY 2 DESC = sort by the second column (count) descending.

SELECT
    plan_type,
    COUNT(*) AS customer_count
FROM customers
GROUP BY plan_type
ORDER BY customer_count DESC;


-- ============================================================
-- Q2 — GROUP BY + numeric aggregation
-- Business question: What is our total and average MRR by plan?
-- ============================================================
-- SUM() and AVG() work on numeric columns.
-- ROUND(..., 2) trims to 2 decimal places.
-- This tells you which plan generates the most revenue.

SELECT
    plan_type,
    COUNT(*)                        AS customers,
    ROUND(SUM(monthly_mrr), 0)      AS total_mrr,
    ROUND(AVG(monthly_mrr), 2)      AS avg_mrr_per_customer
FROM customers
GROUP BY plan_type
ORDER BY total_mrr DESC;


-- ============================================================
-- Q3 — WHERE clause (filtering)
-- Business question: Who are our newest customers (first 6 months)?
-- ============================================================
-- WHERE filters rows BEFORE grouping.
-- These are your most at-risk customers — they haven't built loyalty yet.

SELECT
    customer_id,
    plan_type,
    subscription_months,
    monthly_mrr,
    churned
FROM customers
WHERE subscription_months <= 6
ORDER BY subscription_months ASC, monthly_mrr DESC
LIMIT 20;


-- ============================================================
-- Q4 — CASE WHEN (conditional logic — like IF in Excel)
-- Business question: Classify every customer into a lifecycle stage.
-- ============================================================
-- CASE WHEN is SQL's if/elseif/else.
-- We're creating a new column that doesn't exist in the raw data.
-- Result: new (0-6mo), growing (7-24mo), mature (25mo+)

SELECT
    customer_id,
    subscription_months,
    monthly_mrr,
    churned,
    CASE
        WHEN subscription_months <= 6  THEN 'new'
        WHEN subscription_months <= 24 THEN 'growing'
        ELSE                                'mature'
    END AS lifecycle_stage
FROM customers
ORDER BY subscription_months;


-- ============================================================
-- Q5 — GROUP BY on a derived column (combining Q2 + Q4)
-- Business question: What is churn rate by lifecycle stage?
-- ============================================================
-- We reuse the CASE WHEN logic inside GROUP BY.
-- AVG(churned = 'Yes') doesn't work directly in PostgreSQL —
-- so we use SUM + COUNT to calculate the rate manually.

SELECT
    CASE
        WHEN subscription_months <= 6  THEN 'new'
        WHEN subscription_months <= 24 THEN 'growing'
        ELSE                                'mature'
    END AS lifecycle_stage,
    COUNT(*)                                                  AS customers,
    SUM(CASE WHEN churned = 'Yes' THEN 1 ELSE 0 END)         AS churned_count,
    ROUND(
        SUM(CASE WHEN churned = 'Yes' THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*),
        1
    )                                                         AS churn_rate_pct
FROM customers
GROUP BY lifecycle_stage
ORDER BY churn_rate_pct DESC;


-- ============================================================
-- Q6 — CTE (Common Table Expression — named subquery)
-- Business question: What is average LTV by lifecycle stage,
--                    and how does it compare to overall avg?
-- ============================================================
-- A CTE (WITH clause) is a named subquery you can reference below.
-- Think of it as a temporary table that only lives for this query.
-- This is cleaner than nesting subqueries inside subqueries.

WITH lifecycle AS (
    SELECT
        customer_id,
        lifetime_value,
        CASE
            WHEN subscription_months <= 6  THEN 'new'
            WHEN subscription_months <= 24 THEN 'growing'
            ELSE                                'mature'
        END AS stage
    FROM customers
    WHERE lifetime_value IS NOT NULL   -- exclude the 11 brand-new customers with $0 LTV
),

overall_avg AS (
    SELECT AVG(lifetime_value) AS avg_ltv_all
    FROM customers
    WHERE lifetime_value IS NOT NULL
)

SELECT
    l.stage,
    COUNT(*)                                  AS customers,
    ROUND(AVG(l.lifetime_value), 2)           AS avg_ltv,
    ROUND(o.avg_ltv_all, 2)                   AS overall_avg_ltv,
    ROUND(AVG(l.lifetime_value) - o.avg_ltv_all, 2) AS delta_vs_overall
FROM lifecycle l
CROSS JOIN overall_avg o
GROUP BY l.stage, o.avg_ltv_all
ORDER BY avg_ltv DESC;


-- ============================================================
-- Q7 — Subquery
-- Business question: Which customers are paying above-average MRR
--                    but still churned? (Revenue leakage check)
-- ============================================================
-- A subquery inside WHERE lets you filter against an aggregated value
-- without needing a CTE. Read the inner SELECT first, then the outer.

SELECT
    customer_id,
    plan_type,
    subscription_months,
    monthly_mrr,
    lifetime_value
FROM customers
WHERE
    churned = 'Yes'
    AND monthly_mrr > (
        SELECT AVG(monthly_mrr) FROM customers
    )
ORDER BY monthly_mrr DESC
LIMIT 25;


-- ============================================================
-- Q8 — Window function RANK()
-- Business question: Within each plan type, who are the top-5
--                    highest-MRR customers that churned?
-- ============================================================
-- Window functions compute values ACROSS rows without collapsing them.
-- PARTITION BY = restart the ranking for each plan_type.
-- ORDER BY monthly_mrr DESC = highest MRR gets rank 1.
-- The outer WHERE filters to only the top 5 per plan.

WITH ranked AS (
    SELECT
        customer_id,
        plan_type,
        subscription_months,
        monthly_mrr,
        RANK() OVER (
            PARTITION BY plan_type
            ORDER BY monthly_mrr DESC
        ) AS mrr_rank_within_plan
    FROM customers
    WHERE churned = 'Yes'
)

SELECT *
FROM ranked
WHERE mrr_rank_within_plan <= 5
ORDER BY plan_type, mrr_rank_within_plan;


-- ============================================================
-- BONUS — A/B Test quick summary (ab_test table)
-- Business question: Did the new landing page improve conversion?
-- ============================================================

SELECT
    grp                                              AS test_group,
    landing_page,
    COUNT(*)                                         AS users,
    SUM(converted)                                   AS conversions,
    ROUND(SUM(converted) * 100.0 / COUNT(*), 2)     AS conversion_rate_pct
FROM ab_test
GROUP BY grp, landing_page
ORDER BY grp, landing_page;
