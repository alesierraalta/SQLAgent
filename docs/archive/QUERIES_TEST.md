# Queries de Prueba para el Sistema LLM-DW

Este documento contiene una colección completa de queries para testear el sistema de consultas LLM en diferentes niveles de complejidad.

## 📊 Nivel 1: Queries Simples (Agregaciones Básicas)

### 1.1 Conteos y Totales
```sql
-- Total de clientes
SELECT COUNT(*) as total_clientes FROM customers;

-- Total de órdenes
SELECT COUNT(*) as total_ordenes FROM orders;

-- Total de productos
SELECT COUNT(*) as total_productos FROM products;

-- Total de revenue de todas las órdenes
SELECT SUM(total_amount) as total_revenue FROM orders;

-- Promedio de valor de órdenes
SELECT AVG(total_amount) as promedio_orden FROM orders;
```

### 1.2 Agregaciones por Categoría
```sql
-- Total de revenue por país
SELECT country, SUM(total_amount) as total_revenue 
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY country
ORDER BY total_revenue DESC;

-- Total de revenue por segmento de cliente
SELECT customer_segment, SUM(total_amount) as total_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY customer_segment
ORDER BY total_revenue DESC;

-- Total de productos por categoría
SELECT category, COUNT(*) as total_productos
FROM products
GROUP BY category
ORDER BY total_productos DESC;
```

### 1.3 Top N Queries
```sql
-- Top 10 países por revenue
SELECT country, SUM(total_amount) as revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY country
ORDER BY revenue DESC
LIMIT 10;

-- Top 5 categorías de productos más vendidas
SELECT p.category, SUM(oi.quantity) as total_vendido
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.category
ORDER BY total_vendido DESC
LIMIT 5;
```

## 📈 Nivel 2: Queries Intermedias (JOINs y Filtros)

### 2.1 JOINs Básicos
```sql
-- Clientes con sus órdenes y totales
SELECT 
    c.name,
    c.country,
    COUNT(o.order_id) as total_ordenes,
    SUM(o.total_amount) as total_gastado
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.country
HAVING COUNT(o.order_id) > 0
ORDER BY total_gastado DESC
LIMIT 20;

-- Productos vendidos con detalles
SELECT 
    p.name,
    p.category,
    SUM(oi.quantity) as unidades_vendidas,
    SUM(oi.subtotal) as revenue_total
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category
ORDER BY revenue_total DESC
LIMIT 20;
```

### 2.2 Filtros por Fecha
```sql
-- Revenue por mes del último año
SELECT 
    DATE_TRUNC('month', order_date) as mes,
    COUNT(*) as ordenes,
    SUM(total_amount) as revenue
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY mes DESC;

-- Órdenes del último mes
SELECT 
    COUNT(*) as ordenes,
    SUM(total_amount) as revenue,
    AVG(total_amount) as promedio
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '1 month';

-- Revenue por día de la semana
SELECT 
    EXTRACT(DOW FROM order_date) as dia_semana,
    TO_CHAR(order_date, 'Day') as nombre_dia,
    COUNT(*) as ordenes,
    SUM(total_amount) as revenue
FROM orders
GROUP BY EXTRACT(DOW FROM order_date), TO_CHAR(order_date, 'Day')
ORDER BY dia_semana;
```

### 2.3 Filtros por Estado
```sql
-- Órdenes completadas vs pendientes
SELECT 
    status,
    COUNT(*) as cantidad,
    SUM(total_amount) as revenue_total,
    AVG(total_amount) as promedio
FROM orders
GROUP BY status
ORDER BY cantidad DESC;

-- Clientes con órdenes completadas
SELECT 
    c.customer_segment,
    COUNT(DISTINCT c.customer_id) as clientes,
    COUNT(o.order_id) as ordenes_completadas,
    SUM(o.total_amount) as revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status = 'completed'
GROUP BY c.customer_segment
ORDER BY revenue DESC;
```

## 🔄 Nivel 3: Queries Avanzadas (Múltiples JOINs)

### 3.1 Análisis de Órdenes Completo
```sql
-- Análisis completo de órdenes con clientes y productos
SELECT 
    c.country,
    c.customer_segment,
    p.category,
    COUNT(DISTINCT o.order_id) as ordenes,
    SUM(oi.quantity) as items_vendidos,
    SUM(oi.subtotal) as revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE o.status = 'completed'
GROUP BY c.country, c.customer_segment, p.category
ORDER BY revenue DESC
LIMIT 30;

-- Clientes VIP con sus compras detalladas
SELECT 
    c.name,
    c.country,
    COUNT(DISTINCT o.order_id) as total_ordenes,
    SUM(o.total_amount) as total_gastado,
    AVG(o.total_amount) as promedio_orden,
    MAX(o.order_date) as ultima_compra
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE c.customer_segment = 'VIP'
GROUP BY c.customer_id, c.name, c.country
HAVING COUNT(DISTINCT o.order_id) >= 5
ORDER BY total_gastado DESC
LIMIT 20;
```

### 3.2 Análisis de Productos
```sql
-- Productos más vendidos con información de inventario
SELECT 
    p.name,
    p.category,
    SUM(oi.quantity) as unidades_vendidas,
    SUM(oi.subtotal) as revenue,
    AVG(i.stock_quantity) as stock_promedio,
    AVG(i.reorder_level) as nivel_reorden
FROM products p
JOIN order_items oi ON p.id = oi.product_id
LEFT JOIN inventory i ON p.id = i.product_id
GROUP BY p.id, p.name, p.category
ORDER BY revenue DESC
LIMIT 20;

-- Categorías con análisis de inventario
SELECT 
    p.category,
    COUNT(DISTINCT p.id) as productos,
    SUM(oi.quantity) as items_vendidos,
    SUM(oi.subtotal) as revenue,
    AVG(i.stock_quantity) as stock_promedio,
    SUM(CASE WHEN i.stock_quantity < i.reorder_level THEN 1 ELSE 0 END) as productos_bajo_stock
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
LEFT JOIN inventory i ON p.id = i.product_id
GROUP BY p.category
ORDER BY revenue DESC NULLS LAST;
```

### 3.3 Análisis Temporal Complejo
```sql
-- Revenue mensual por país y segmento
SELECT 
    DATE_TRUNC('month', o.order_date) as mes,
    c.country,
    c.customer_segment,
    COUNT(DISTINCT o.order_id) as ordenes,
    SUM(o.total_amount) as revenue,
    COUNT(DISTINCT c.customer_id) as clientes_unicos
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY DATE_TRUNC('month', o.order_date), c.country, c.customer_segment
ORDER BY mes DESC, revenue DESC;

-- Comparación año sobre año (últimos 2 años)
SELECT 
    EXTRACT(YEAR FROM order_date) as año,
    EXTRACT(MONTH FROM order_date) as mes,
    COUNT(*) as ordenes,
    SUM(total_amount) as revenue,
    AVG(total_amount) as promedio
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '24 months'
GROUP BY EXTRACT(YEAR FROM order_date), EXTRACT(MONTH FROM order_date)
ORDER BY año DESC, mes DESC;
```

## 🎯 Nivel 4: Queries Complejas (CTEs, Subqueries, Window Functions)

### 4.1 Common Table Expressions (CTEs)
```sql
-- Análisis de clientes con ranking
WITH customer_stats AS (
    SELECT 
        c.customer_id,
        c.name,
        c.country,
        c.customer_segment,
        COUNT(o.order_id) as total_ordenes,
        SUM(o.total_amount) as total_gastado,
        AVG(o.total_amount) as promedio_orden
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_id, c.name, c.country, c.customer_segment
)
SELECT 
    *,
    RANK() OVER (PARTITION BY customer_segment ORDER BY total_gastado DESC) as ranking_segmento,
    RANK() OVER (PARTITION BY country ORDER BY total_gastado DESC) as ranking_pais
FROM customer_stats
WHERE total_ordenes > 0
ORDER BY total_gastado DESC
LIMIT 30;

-- Análisis de productos con tendencias
WITH product_sales AS (
    SELECT 
        p.id,
        p.name,
        p.category,
        DATE_TRUNC('month', o.order_date) as mes,
        SUM(oi.quantity) as unidades_vendidas,
        SUM(oi.subtotal) as revenue
    FROM products p
    JOIN order_items oi ON p.id = oi.product_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY p.id, p.name, p.category, DATE_TRUNC('month', o.order_date)
)
SELECT 
    category,
    mes,
    SUM(unidades_vendidas) as total_unidades,
    SUM(revenue) as total_revenue,
    COUNT(DISTINCT id) as productos_activos
FROM product_sales
GROUP BY category, mes
ORDER BY mes DESC, total_revenue DESC;
```

### 4.2 Subqueries
```sql
-- Clientes que han gastado más que el promedio
SELECT 
    c.name,
    c.country,
    c.customer_segment,
    COUNT(o.order_id) as ordenes,
    SUM(o.total_amount) as total_gastado
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.country, c.customer_segment
HAVING SUM(o.total_amount) > (
    SELECT AVG(total_gastado)
    FROM (
        SELECT SUM(total_amount) as total_gastado
        FROM orders
        GROUP BY customer_id
    ) sub
)
ORDER BY total_gastado DESC
LIMIT 20;

-- Productos que están por debajo del stock de reorden
SELECT 
    p.name,
    p.category,
    i.warehouse_location,
    i.stock_quantity,
    i.reorder_level,
    (i.reorder_level - i.stock_quantity) as diferencia
FROM products p
JOIN inventory i ON p.id = i.product_id
WHERE i.stock_quantity < i.reorder_level
ORDER BY diferencia DESC;
```

### 4.3 Window Functions
```sql
-- Revenue acumulado por mes
SELECT 
    DATE_TRUNC('month', order_date) as mes,
    SUM(total_amount) as revenue_mes,
    SUM(SUM(total_amount)) OVER (ORDER BY DATE_TRUNC('month', order_date)) as revenue_acumulado,
    AVG(SUM(total_amount)) OVER (ORDER BY DATE_TRUNC('month', order_date) ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as promedio_movil_3meses
FROM orders
WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY mes;

-- Top productos por categoría con ranking
SELECT 
    category,
    name,
    revenue,
    ranking
FROM (
    SELECT 
        p.category,
        p.name,
        SUM(oi.subtotal) as revenue,
        ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(oi.subtotal) DESC) as ranking
    FROM products p
    JOIN order_items oi ON p.id = oi.product_id
    GROUP BY p.id, p.category, p.name
) ranked
WHERE ranking <= 5
ORDER BY category, ranking;
```

## 🌍 Nivel 5: Queries Geográficas y Segmentación

### 5.1 Análisis Geográfico
```sql
-- Revenue por país con porcentajes
SELECT 
    c.country,
    COUNT(DISTINCT c.customer_id) as clientes,
    COUNT(o.order_id) as ordenes,
    SUM(o.total_amount) as revenue,
    ROUND(100.0 * SUM(o.total_amount) / SUM(SUM(o.total_amount)) OVER (), 2) as porcentaje_revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.country
ORDER BY revenue DESC;

-- Comparación de países por segmento
SELECT 
    country,
    customer_segment,
    COUNT(DISTINCT customer_id) as clientes,
    COUNT(order_id) as ordenes,
    SUM(total_amount) as revenue,
    AVG(total_amount) as promedio_orden
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY country, customer_segment
ORDER BY country, revenue DESC;
```

### 5.2 Análisis de Segmentación
```sql
-- Comparación de segmentos de clientes
SELECT 
    customer_segment,
    COUNT(DISTINCT customer_id) as total_clientes,
    COUNT(order_id) as total_ordenes,
    SUM(total_amount) as revenue_total,
    AVG(total_amount) as promedio_orden,
    MAX(total_amount) as orden_maxima,
    MIN(total_amount) as orden_minima
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
GROUP BY customer_segment
ORDER BY revenue_total DESC;

-- Clientes por segmento con distribución geográfica
SELECT 
    customer_segment,
    country,
    COUNT(*) as clientes,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY customer_segment), 2) as porcentaje_segmento
FROM customers
GROUP BY customer_segment, country
ORDER BY customer_segment, clientes DESC;
```

## 📦 Nivel 6: Queries de Inventario y Logística

### 6.1 Análisis de Inventario
```sql
-- Estado de inventario por ubicación
SELECT 
    warehouse_location,
    COUNT(DISTINCT product_id) as productos,
    SUM(stock_quantity) as stock_total,
    AVG(stock_quantity) as stock_promedio,
    COUNT(CASE WHEN stock_quantity < reorder_level THEN 1 END) as productos_bajo_stock
FROM inventory
GROUP BY warehouse_location
ORDER BY stock_total DESC;

-- Productos que necesitan reorden
SELECT 
    p.name,
    p.category,
    i.warehouse_location,
    i.stock_quantity,
    i.reorder_level,
    (i.reorder_level - i.stock_quantity) as unidades_necesarias,
    i.last_restocked,
    CURRENT_DATE - i.last_restocked as dias_sin_reponer
FROM products p
JOIN inventory i ON p.id = i.product_id
WHERE i.stock_quantity < i.reorder_level
ORDER BY unidades_necesarias DESC;
```

### 6.2 Análisis de Proveedores
```sql
-- Proveedores por país con ratings
SELECT 
    country,
    COUNT(*) as total_proveedores,
    AVG(rating) as rating_promedio,
    MIN(rating) as rating_minimo,
    MAX(rating) as rating_maximo
FROM suppliers
GROUP BY country
ORDER BY rating_promedio DESC;

-- Top proveedores por rating
SELECT 
    supplier_name,
    country,
    rating,
    contact_email
FROM suppliers
WHERE rating >= 4.0
ORDER BY rating DESC, supplier_name
LIMIT 20;
```

## 🔍 Nivel 7: Queries de Búsqueda y Filtrado Avanzado

### 7.1 Búsquedas con LIKE y Patrones
```sql
-- Buscar productos por nombre
SELECT name, category, price
FROM products
WHERE name ILIKE '%laptop%' OR name ILIKE '%phone%'
ORDER BY price DESC;

-- Buscar clientes por país o ciudad
SELECT name, email, country, city, customer_segment
FROM customers
WHERE country IN ('España', 'Colombia', 'México')
ORDER BY country, name;
```

### 7.2 Filtros Complejos
```sql
-- Órdenes con descuentos significativos
SELECT 
    o.order_id,
    c.name as cliente,
    o.order_date,
    o.total_amount,
    o.discount_percentage,
    (o.total_amount * o.discount_percentage / 100) as descuento_aplicado
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.discount_percentage IS NOT NULL 
    AND o.discount_percentage > 10
ORDER BY o.discount_percentage DESC
LIMIT 20;

-- Clientes con múltiples órdenes en el mismo mes
SELECT 
    c.name,
    c.country,
    DATE_TRUNC('month', o.order_date) as mes,
    COUNT(o.order_id) as ordenes_mes,
    SUM(o.total_amount) as total_mes
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.country, DATE_TRUNC('month', o.order_date)
HAVING COUNT(o.order_id) >= 3
ORDER BY mes DESC, ordenes_mes DESC;
```

## 📊 Nivel 8: Queries de Análisis Estadístico

### 8.1 Estadísticas Descriptivas
```sql
-- Estadísticas completas de órdenes
SELECT 
    COUNT(*) as total_ordenes,
    SUM(total_amount) as revenue_total,
    AVG(total_amount) as promedio,
    STDDEV(total_amount) as desviacion_estandar,
    MIN(total_amount) as minimo,
    MAX(total_amount) as maximo,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_amount) as mediana
FROM orders
WHERE status = 'completed';

-- Distribución de revenue por rangos
SELECT 
    CASE 
        WHEN total_amount < 100 THEN '0-100'
        WHEN total_amount < 500 THEN '100-500'
        WHEN total_amount < 1000 THEN '500-1000'
        WHEN total_amount < 2000 THEN '1000-2000'
        ELSE '2000+'
    END as rango_revenue,
    COUNT(*) as cantidad_ordenes,
    SUM(total_amount) as revenue_total
FROM orders
GROUP BY 
    CASE 
        WHEN total_amount < 100 THEN '0-100'
        WHEN total_amount < 500 THEN '100-500'
        WHEN total_amount < 1000 THEN '500-1000'
        WHEN total_amount < 2000 THEN '1000-2000'
        ELSE '2000+'
    END
ORDER BY MIN(total_amount);
```

## 🎨 Queries para Testing del LLM (Lenguaje Natural)

### Preguntas Simples que el LLM debe resolver:

1. **"¿Cuál es el total de revenue por país?"**
2. **"¿Cuántos clientes tenemos en cada segmento?"**
3. **"Muéstrame los top 10 productos más vendidos"**
4. **"¿Cuál es el promedio de valor de órdenes por mes?"**
5. **"¿Qué países tienen más clientes VIP?"**

### Preguntas Intermedias:

6. **"Muéstrame el revenue mensual de los últimos 6 meses"**
7. **"¿Cuáles son los clientes que han gastado más de $5000?"**
8. **"¿Qué categorías de productos tienen más unidades vendidas?"**
9. **"Muéstrame las órdenes completadas del último mes agrupadas por país"**
10. **"¿Cuál es el producto más vendido en cada categoría?"**

### Preguntas Avanzadas:

11. **"Muéstrame el análisis de clientes VIP con sus compras detalladas por país"**
12. **"¿Qué productos están por debajo del nivel de reorden en cada almacén?"**
13. **"Compara el revenue de este mes con el mes anterior por país"**
14. **"Muéstrame los clientes que han hecho más de 5 órdenes con su total gastado"**
15. **"¿Cuál es la tendencia de ventas por categoría en los últimos 6 meses?"**

### Preguntas Complejas:

16. **"Análisis completo de revenue por país, segmento de cliente y categoría de producto"**
17. **"Muéstrame los productos más vendidos con su información de inventario y proveedores"**
18. **"Compara el comportamiento de compra entre segmentos Premium y VIP por país"**
19. **"¿Qué clientes han comprado productos de todas las categorías disponibles?"**
20. **"Análisis de revenue acumulado mensual con promedio móvil de 3 meses"**

## 🧪 Queries de Validación

### Verificar Integridad de Datos
```sql
-- Verificar foreign keys
SELECT 
    'order_items sin order_id válido' as error,
    COUNT(*) as cantidad
FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL

UNION ALL

SELECT 
    'order_items sin product_id válido',
    COUNT(*)
FROM order_items oi
LEFT JOIN products p ON oi.product_id = p.id
WHERE p.id IS NULL;

-- Verificar consistencia de datos
SELECT 
    'Órdenes sin items' as tipo,
    COUNT(*) as cantidad
FROM orders o
LEFT JOIN order_items oi ON o.order_id = oi.order_id
WHERE oi.order_id IS NULL;
```

## 📝 Notas para Testing

1. **Prueba queries simples primero** para verificar que el sistema funciona básicamente
2. **Incrementa complejidad gradualmente** para identificar límites
3. **Prueba con diferentes formulaciones** de la misma pregunta
4. **Verifica que el LLM use las tablas correctas** según el schema
5. **Comprueba que los JOINs sean correctos** en queries complejas
6. **Valida que los filtros de fecha funcionen** correctamente
7. **Prueba queries con errores intencionales** para ver la recuperación de errores

## 🎯 Métricas de Éxito

- ✅ **Precisión**: El SQL generado debe ser correcto
- ✅ **Velocidad**: Queries simples < 5s, complejas < 15s
- ✅ **Cache Hit Rate**: Debe mejorar con queries repetidas
- ✅ **Model Selection**: Queries simples deben usar gpt-4o-mini
- ✅ **Error Recovery**: Debe recuperarse de errores SQL automáticamente
