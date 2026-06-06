-- The Global Ocean Freight Stress Index is a 0-100 scalar by construction
-- (a convex blend of two [0,1] components, scaled by 100). Any day whose index,
-- breadth, or depth falls outside [0,100] signals a bug in the re-expression
-- (a bad weight normalisation, a percentile NULL, a runaway smoothing window).
-- Belt-and-suspenders beyond the dbt_utils.accepted_range schema test, and the
-- closest warehouse-side analogue of the bounded-output checks the Python carries.

select date, index_value, breadth, depth, n_chokepoints
from {{ ref('mart_freight_stress_index') }}
where index_value < 0 or index_value > 100
   or breadth     < 0 or breadth     > 100
   or depth       < 0 or depth       > 100
   or n_chokepoints <= 0
