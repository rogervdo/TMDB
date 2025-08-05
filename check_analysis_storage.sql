-- Consulta para verificar el almacenamiento de análisis
-- Ejecutar en la base de datos de Odoo

-- 1. Verificar si existe la tabla del wizard
SELECT table_name 
FROM information_schema.tables 
WHERE table_name = 'tmdb_collection_analysis_wizard';

-- 2. Verificar la estructura de la tabla
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'tmdb_collection_analysis_wizard'
ORDER BY ordinal_position;

-- 3. Ver análisis almacenados (últimos 10)
SELECT 
    id,
    create_date,
    write_date,
    analysis_type,
    total_movies,
    avg_rating,
    avg_popularity,
    is_analysis_complete
FROM tmdb_collection_analysis_wizard 
ORDER BY create_date DESC 
LIMIT 10;

-- 4. Ver contenido de un análisis específico
SELECT 
    id,
    decade_analysis,
    genre_analysis,
    rating_popularity_analysis,
    gaps_analysis
FROM tmdb_collection_analysis_wizard 
WHERE id = [ID_DEL_ANALISIS];

-- 5. Verificar datos de gráficos
SELECT 
    id,
    decade_chart_data,
    genre_chart_data,
    rating_popularity_chart_data
FROM tmdb_collection_analysis_wizard 
WHERE id = [ID_DEL_ANALISIS]; 