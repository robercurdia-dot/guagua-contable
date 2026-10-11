-- Se ejecuta una sola vez al crear el volumen de Postgres.
--
-- El rol de la app NO puede ser superusuario: los superusuarios se saltan el
-- Row-Level Security aunque este forzado, y el aislamiento entre empresas
-- quedaria sin efecto (y sus tests fallarian).
CREATE ROLE guagua LOGIN PASSWORD 'guagua' CREATEDB;
CREATE DATABASE guagua OWNER guagua;
CREATE DATABASE guagua_test OWNER guagua;
