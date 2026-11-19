SELECT 'CREATE DATABASE controlmap_test'
WHERE NOT EXISTS (
    SELECT FROM pg_database
    WHERE datname = 'controlmap_test'
)
\gexec