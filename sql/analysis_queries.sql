-- Most extreme recent signals
SELECT ticker, metric, date, z_score, description
FROM fact_anomaly
WHERE flagged
ORDER BY ABS(z_score) DESC, date DESC
LIMIT 25;

-- Peer-pair divergence events
SELECT pair, date, z_score, divergence
FROM fact_pair_divergence
WHERE flagged
ORDER BY ABS(z_score) DESC;

-- Quarterly inventory-to-revenue ratio (when both facts are present)
WITH q AS (
  SELECT ticker, period_end,
         MAX(CASE WHEN tag = 'Revenue' THEN value END) AS revenue,
         MAX(CASE WHEN tag = 'InventoryNet' THEN value END) AS inventory
  FROM fact_financials
  GROUP BY 1, 2
)
SELECT ticker, period_end, inventory / NULLIF(revenue, 0) AS inventory_to_revenue
FROM q
WHERE revenue IS NOT NULL AND inventory IS NOT NULL
ORDER BY ticker, period_end;
