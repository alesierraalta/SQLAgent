## Prompts avanzados para probar manualmente

### 1) Revenue total y promedio por país con filtro de ventas mínimas
**Comando CLI**
`python -m src.cli query "¿Cuál es el revenue total y el promedio por país excluyendo países con menos de 5 ventas?" --explain`
**SQL**
```sql
WITH ventas_por_pais AS (
    SELECT country, COUNT(*) AS n_ventas, SUM(revenue) AS total_revenue
    FROM sales
    GROUP BY country
)
SELECT country, total_revenue, ROUND(total_revenue / NULLIF(n_ventas, 0), 2) AS avg_revenue
FROM ventas_por_pais
WHERE n_ventas >= 5
ORDER BY total_revenue DESC;
```

### 2) Comparación de revenue entre junio y julio 2025
**Comando CLI**
`python -m src.cli query "Compara el revenue total de junio 2025 vs julio 2025 por categoría de producto" --explain`
**SQL**
```sql
WITH junio AS (
    SELECT p.category, SUM(s.revenue) AS total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE EXTRACT(YEAR FROM s.date) = 2025 AND EXTRACT(MONTH FROM s.date) = 6
    GROUP BY p.category
),
julio AS (
    SELECT p.category, SUM(s.revenue) AS total_revenue
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE EXTRACT(YEAR FROM s.date) = 2025 AND EXTRACT(MONTH FROM s.date) = 7
    GROUP BY p.category
)
SELECT COALESCE(j.categoria, jl.categoria) AS categoria,
       COALESCE(j.total_revenue, 0) AS revenue_junio,
       COALESCE(jl.total_revenue, 0) AS revenue_julio,
       (COALESCE(jl.total_revenue, 0) - COALESCE(j.total_revenue, 0)) AS delta,
       CASE WHEN COALESCE(j.total_revenue, 0) = 0 THEN NULL
            ELSE ROUND((jl.total_revenue - j.total_revenue) / j.total_revenue * 100, 2) END AS delta_pct
FROM junio j
FULL OUTER JOIN julio jl ON j.categoria = jl.categoria
ORDER BY COALESCE(jl.total_revenue, 0) DESC;
```

### 3) Promedio móvil 7 días de revenue por categoría (últimos 60 días)
**Comando CLI**
`python -m src.cli query "Calcula el promedio móvil de 7 días del revenue por categoría de producto para los últimos 60 días" --explain`
**SQL**
```sql
SELECT fecha, categoria,
       revenue_dia,
       ROUND(AVG(revenue_dia) OVER (PARTITION BY categoria ORDER BY fecha ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS avg_movil_7d
FROM (
    SELECT s.date::date AS fecha,
           p.category AS categoria,
           SUM(s.revenue) AS revenue_dia
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE s.date >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY s.date::date, p.category
) daily_revenue
ORDER BY categoria, fecha;
```

### 4) Revenue mensual por categoría de producto con crecimiento vs mes anterior
**Comando CLI**
`python -m src.cli query "Revenue mensual y crecimiento porcentual vs mes anterior por categoría de producto" --explain`
**SQL**
```sql
WITH mensuales AS (
    SELECT DATE_TRUNC('month', s.date) AS mes,
           p.category,
           SUM(s.revenue) AS revenue_mes
    FROM sales s
    JOIN products p ON s.product_id = p.id
    GROUP BY mes, p.category
)
SELECT mes,
       category,
       revenue_mes,
       LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes) AS revenue_prev_mes,
       (revenue_mes - LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes)) AS delta_absoluto,
       CASE WHEN LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes) = 0 THEN NULL
            ELSE ROUND((revenue_mes - LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes)) /
                       NULLIF(LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes), 0) * 100, 2)
        END AS crecimiento_pct
FROM mensuales
ORDER BY category, mes;
```

### 5) Estadísticas de revenue por país con percentiles
**Comando CLI**
`python -m src.cli query "Estadísticas de revenue por país incluyendo total, promedio, mediana y percentiles 25/75" --explain`
**SQL**
```sql
SELECT country,
       COUNT(*) AS num_transacciones,
       SUM(revenue) AS total_revenue,
       ROUND(AVG(revenue), 2) AS avg_revenue,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue), 2) AS mediana,
       ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue), 2) AS p25,
       ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue), 2) AS p75,
       ROUND(STDDEV(revenue), 2) AS desviacion_estandar
FROM sales
GROUP BY country
HAVING COUNT(*) >= 3
ORDER BY total_revenue DESC;
```

### 6) Top 5 productos por revenue en el último trimestre y participación por categoría
**Comando CLI**
`python -m src.cli query "Top 5 productos por revenue en el último trimestre y su participación porcentual dentro de su categoría" --explain`
**SQL**
```sql
WITH productos_trimestre AS (
    SELECT s.product_id,
           SUM(s.revenue) AS revenue_total,
           SUM(s.quantity) AS cantidad_total
    FROM sales s
    WHERE s.date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY s.product_id
),
categoria_trimestre AS (
    SELECT p.category,
           SUM(s.revenue) AS revenue_categoria_total
    FROM sales s
    JOIN products p ON p.id = s.product_id
    WHERE s.date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY p.category
)
SELECT p.name AS producto,
       p.category AS categoria,
       pt.revenue_total,
       pt.cantidad_total,
       ROUND(pt.revenue_total / NULLIF(ct.revenue_categoria_total, 0) * 100, 2) AS participacion_categoria_pct
FROM productos_trimestre pt
JOIN products p ON p.id = pt.product_id
JOIN categoria_trimestre ct ON ct.category = p.category
ORDER BY pt.revenue_total DESC
LIMIT 5;
```

### 7) Ranking de productos por revenue dentro de cada país (últimos 45 días)
**Comando CLI**
`python -m src.cli query "Ranking de productos por revenue dentro de cada país para los últimos 45 días, incluyendo posición y porcentaje del total por país" --explain`
**SQL**
```sql
WITH ventas_pais AS (
    SELECT s.country,
           s.product_id,
           p.name AS producto,
           SUM(s.revenue) AS revenue_total,
           SUM(s.quantity) AS cantidad_total
    FROM sales s
    JOIN products p ON s.product_id = p.id
    WHERE s.date >= CURRENT_DATE - INTERVAL '45 days'
    GROUP BY s.country, s.product_id, p.name
),
ranking_pais AS (
    SELECT country,
           producto,
           revenue_total,
           cantidad_total,
           DENSE_RANK() OVER (PARTITION BY country ORDER BY revenue_total DESC) AS ranking_pais,
           SUM(revenue_total) OVER (PARTITION BY country) AS revenue_pais_total
    FROM ventas_pais
)
SELECT country,
       producto,
       revenue_total,
       cantidad_total,
       ranking_pais,
       ROUND(revenue_total / NULLIF(revenue_pais_total, 0) * 100, 2) AS participacion_pais_pct
FROM ranking_pais
WHERE ranking_pais <= 3
ORDER BY country, ranking_pais;
```

### 8) Análisis de productos por frecuencia de venta en el último trimestre
**Comando CLI**
`python -m src.cli query "Productos ordenados por frecuencia de venta en el último trimestre, incluyendo días desde última venta" --explain`
**SQL**
```sql
WITH ultima_venta AS (
    SELECT product_id,
           MAX(date) AS fecha_ultima_venta,
           COUNT(*) AS num_ventas_trimestre,
           SUM(revenue) AS revenue_trimestre
    FROM sales
    WHERE date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY product_id
)
SELECT p.name AS producto,
       p.category AS categoria,
       p.price AS precio,
       COALESCE(uv.num_ventas_trimestre, 0) AS ventas_trimestre,
       COALESCE(uv.revenue_trimestre, 0) AS revenue_trimestre,
       CASE WHEN uv.fecha_ultima_venta IS NULL THEN NULL
            ELSE CURRENT_DATE - uv.fecha_ultima_venta END AS dias_desde_ultima_venta,
       CASE WHEN uv.num_ventas_trimestre IS NULL THEN 'SIN VENTAS'
            WHEN uv.num_ventas_trimestre <= 2 THEN 'BAJA FRECUENCIA'
            WHEN uv.num_ventas_trimestre <= 5 THEN 'MEDIA FRECUENCIA'
            ELSE 'ALTA FRECUENCIA' END AS categoria_frecuencia
FROM products p
LEFT JOIN ultima_venta uv ON uv.product_id = p.id
ORDER BY COALESCE(uv.num_ventas_trimestre, 0) ASC, p.category;
```

### 9) Top 10 productos por crecimiento mensual de revenue (comparación mes actual vs anterior)
**Comando CLI**
`python -m src.cli query "Top 10 productos con mayor crecimiento porcentual de revenue comparando el mes actual vs el mes anterior" --explain`
**SQL**
```sql
WITH revenue_mensual AS (
    SELECT DATE_TRUNC('month', s.date) AS mes,
           s.product_id,
           SUM(s.revenue) AS revenue_mes,
           SUM(s.quantity) AS cantidad_mes
    FROM sales s
    GROUP BY mes, s.product_id
),
comparacion_meses AS (
    SELECT rm.product_id,
           rm.mes,
           rm.revenue_mes,
           rm.cantidad_mes,
           LAG(rm.revenue_mes) OVER (PARTITION BY rm.product_id ORDER BY rm.mes) AS revenue_mes_anterior,
           LAG(rm.cantidad_mes) OVER (PARTITION BY rm.product_id ORDER BY rm.mes) AS cantidad_mes_anterior
    FROM revenue_mensual rm
)
SELECT p.name AS producto,
       p.category AS categoria,
       cm.mes,
       cm.revenue_mes,
       cm.revenue_mes_anterior,
       (cm.revenue_mes - cm.revenue_mes_anterior) AS delta_revenue,
       CASE WHEN cm.revenue_mes_anterior = 0 THEN NULL
            ELSE ROUND((cm.revenue_mes - cm.revenue_mes_anterior) / cm.revenue_mes_anterior * 100, 2)
       END AS crecimiento_pct
FROM comparacion_meses cm
JOIN products p ON p.id = cm.product_id
WHERE cm.revenue_mes_anterior IS NOT NULL
  AND cm.revenue_mes_anterior > 0
ORDER BY crecimiento_pct DESC NULLS LAST
LIMIT 10;
```

### 10) Top 5 países por revenue en el último trimestre con participación global y crecimiento
**Comando CLI**
`python -m src.cli query "Top 5 países por revenue en el último trimestre, incluyendo participación global y comparación con el trimestre anterior" --explain`
**SQL**
```sql
WITH trimestre_actual AS (
    SELECT country,
           SUM(revenue) AS revenue_actual,
           COUNT(*) AS num_ventas_actual
    FROM sales
    WHERE date >= DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY country
),
trimestre_anterior AS (
    SELECT country,
           SUM(revenue) AS revenue_anterior,
           COUNT(*) AS num_ventas_anterior
    FROM sales
    WHERE date >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL '3 months')
      AND date < DATE_TRUNC('quarter', CURRENT_DATE)
    GROUP BY country
),
global_actual AS (
    SELECT SUM(revenue_actual) AS total_global_actual FROM trimestre_actual
)
SELECT ta.country,
       ta.revenue_actual,
       ta.num_ventas_actual,
       ROUND(ta.revenue_actual / NULLIF(ga.total_global_actual, 0) * 100, 2) AS participacion_global_pct,
       COALESCE(ta_anterior.revenue_anterior, 0) AS revenue_trimestre_anterior,
       (ta.revenue_actual - COALESCE(ta_anterior.revenue_anterior, 0)) AS delta_revenue,
       CASE WHEN COALESCE(ta_anterior.revenue_anterior, 0) = 0 THEN NULL
            ELSE ROUND((ta.revenue_actual - ta_anterior.revenue_anterior) /
                       NULLIF(ta_anterior.revenue_anterior, 0) * 100, 2)
       END AS crecimiento_trimestre_pct
FROM trimestre_actual ta
CROSS JOIN global_actual ga
LEFT JOIN trimestre_anterior ta_anterior ON ta.country = ta_anterior.country
ORDER BY ta.revenue_actual DESC
LIMIT 5;
```

### 11) Segmentación de clientes por valor y frecuencia de compra
**Comando CLI**
`python -m src.cli query "Segmenta clientes por valor total de compras y frecuencia, incluyendo estadísticas por segmento" --explain`
**SQL**
```sql
WITH cliente_stats AS (
    SELECT o.customer_id,
           COUNT(DISTINCT o.order_id) AS num_pedidos,
           SUM(o.total_amount) AS valor_total_compras,
           AVG(o.total_amount) AS ticket_promedio,
           MAX(o.order_date) AS ultima_compra,
           MIN(o.order_date) AS primera_compra
    FROM orders o
    GROUP BY o.customer_id
),
segmentacion AS (
    SELECT customer_id,
           num_pedidos,
           valor_total_compras,
           ticket_promedio,
           CASE WHEN valor_total_compras >= 5000 AND num_pedidos >= 10 THEN 'VIP'
                WHEN valor_total_compras >= 2000 AND num_pedidos >= 5 THEN 'ALTO VALOR'
                WHEN valor_total_compras >= 500 OR num_pedidos >= 2 THEN 'MEDIO VALOR'
                ELSE 'BAJO VALOR' END AS segmento_cliente
    FROM cliente_stats
)
SELECT segmento_cliente,
       COUNT(*) AS num_clientes,
       ROUND(AVG(valor_total_compras), 2) AS valor_promedio,
       ROUND(AVG(num_pedidos), 1) AS pedidos_promedio,
       ROUND(AVG(ticket_promedio), 2) AS ticket_promedio,
       ROUND(SUM(valor_total_compras), 2) AS valor_total_segmento
FROM segmentacion
GROUP BY segmento_cliente
ORDER BY valor_total_segmento DESC;
```

### 12) Análisis de proveedores por rendimiento y productos suministrados
**Comando CLI**
`python -m src.cli query "Análisis de proveedores por rating, productos suministrados y revenue generado" --explain`
**SQL**
```sql
WITH proveedor_productos AS (
    SELECT s.supplier_id,
           COUNT(DISTINCT p.id) AS num_productos,
           COUNT(DISTINCT s.product_id) AS productos_con_ventas,
           SUM(sales.revenue) AS revenue_total_generado
    FROM suppliers s
    LEFT JOIN products p ON p.id = s.product_id
    LEFT JOIN sales ON sales.product_id = p.id
    GROUP BY s.supplier_id
)
SELECT sup.supplier_name AS proveedor,
       sup.country AS pais,
       sup.rating AS rating,
       pp.num_productos,
       pp.productos_con_ventas,
       ROUND(pp.revenue_total_generado, 2) AS revenue_generado,
       ROUND(pp.revenue_total_generado / NULLIF(pp.num_productos, 0), 2) AS revenue_por_producto,
       CASE WHEN sup.rating >= 4.5 THEN 'EXCELENTE'
            WHEN sup.rating >= 4.0 THEN 'BUENO'
            WHEN sup.rating >= 3.0 THEN 'REGULAR'
            ELSE 'BAJO' END AS categoria_rating
FROM suppliers sup
LEFT JOIN proveedor_productos pp ON pp.supplier_id = sup.supplier_id
ORDER BY pp.revenue_total_generado DESC NULLS LAST;
```

### 13) Análisis de categorías con jerarquía y rendimiento
**Comando CLI**
`python -m src.cli query "Análisis jerárquico de categorías de productos con revenue y participación" --explain`
**SQL**
```sql
WITH categoria_stats AS (
    SELECT COALESCE(c.parent_category_id, c.category_id) AS categoria_padre,
           c.category_id,
           c.category_name,
           c.parent_category_id,
           COALESCE(parent.category_name, 'SIN PADRE') AS categoria_padre_nombre,
           COUNT(DISTINCT p.id) AS num_productos,
           SUM(s.revenue) AS revenue_total,
           COUNT(DISTINCT s.id) AS num_ventas
    FROM categories c
    LEFT JOIN categories parent ON parent.category_id = c.parent_category_id
    LEFT JOIN products p ON p.category = c.category_name
    LEFT JOIN sales s ON s.product_id = p.id
    GROUP BY c.category_id, c.category_name, c.parent_category_id, parent.category_name
),
total_global AS (
    SELECT SUM(revenue_total) AS revenue_global FROM categoria_stats WHERE parent_category_id IS NULL
)
SELECT cs.categoria_padre,
       cs.categoria_padre_nombre,
       cs.category_name AS subcategoria,
       cs.num_productos,
       cs.num_ventas,
       ROUND(cs.revenue_total, 2) AS revenue_categoria,
       ROUND(cs.revenue_total / NULLIF(cs.num_productos, 0), 2) AS revenue_por_producto,
       ROUND(cs.revenue_total / NULLIF(tg.revenue_global, 0) * 100, 2) AS participacion_global_pct
FROM categoria_stats cs
CROSS JOIN total_global tg
ORDER BY cs.categoria_padre, cs.revenue_total DESC;
```
