-- Sincroniza o catalogo de tamanhos do banco com a imagem visual atual.
-- A imagem usa 8 opcoes numeradas:
-- 1=1,100 kg, 2=1,600 kg, 3=2,300 kg, 4=3 kg,
-- 5=4 kg, 6=5 kg, 7=6 kg, 8=8 kg.
--
-- Este script e idempotente: atualiza tamanhos existentes pelo peso e
-- insere somente os pesos que ainda nao existem. Tamanhos ativos de
-- 2 recheios que nao aparecem na imagem sao desativados.

BEGIN;

WITH desired_sizes AS (
    SELECT *
    FROM (
        VALUES
            (1, '1,100 kg - Aro 15 cm', 1.100::numeric, 12, 'REDONDA'::cake_shape, 2,  65.00::numeric,  70.00::numeric),
            (2, '1,600 kg',             1.600::numeric, 18, 'RETANGULAR'::cake_shape, 2, 100.00::numeric, 105.00::numeric),
            (3, '2,300 kg',             2.300::numeric, 26, 'RETANGULAR'::cake_shape, 2, 145.00::numeric, 150.00::numeric),
            (4, '3 kg',                 3.000::numeric, 34, 'RETANGULAR'::cake_shape, 2, 180.00::numeric, 185.00::numeric),
            (5, '4 kg',                 4.000::numeric, 45, 'RETANGULAR'::cake_shape, 2, 240.00::numeric, 245.00::numeric),
            (6, '5 kg',                 5.000::numeric, 55, 'RETANGULAR'::cake_shape, 2, 300.00::numeric, 310.00::numeric),
            (7, '6 kg',                 6.000::numeric, 65, 'RETANGULAR'::cake_shape, 2, 350.00::numeric, 360.00::numeric),
            (8, '8 kg',                 8.000::numeric, 86, 'RETANGULAR'::cake_shape, 2, 430.00::numeric, 440.00::numeric)
    ) AS v(sort_order, description, weight_kg, servings, shape, filling_layers, price_white, price_chocolate)
),
existing_choice AS (
    SELECT DISTINCT ON (d.weight_kg)
        d.*,
        s.id AS existing_id
    FROM desired_sizes d
    LEFT JOIN sizes s
      ON s.filling_layers = 2
     AND s.weight_kg = d.weight_kg
    ORDER BY d.weight_kg, s.active DESC NULLS LAST, s.id ASC NULLS LAST
),
updated AS (
    UPDATE sizes s
    SET
        description = e.description,
        servings = e.servings,
        shape = e.shape,
        filling_layers = e.filling_layers,
        price_white = e.price_white,
        price_chocolate = e.price_chocolate,
        sort_order = e.sort_order,
        active = TRUE,
        updated_at = NOW()
    FROM existing_choice e
    WHERE e.existing_id IS NOT NULL
      AND s.id = e.existing_id
    RETURNING s.id
),
inserted AS (
    INSERT INTO sizes (
        description,
        weight_kg,
        servings,
        shape,
        filling_layers,
        price_white,
        price_chocolate,
        sort_order,
        active
    )
    SELECT
        d.description,
        d.weight_kg,
        d.servings,
        d.shape,
        d.filling_layers,
        d.price_white,
        d.price_chocolate,
        d.sort_order,
        TRUE
    FROM existing_choice d
    WHERE d.existing_id IS NULL
    RETURNING id
),
kept AS (
    SELECT id FROM updated
    UNION ALL
    SELECT id FROM inserted
)
UPDATE sizes
SET
    active = FALSE,
    updated_at = NOW()
WHERE filling_layers = 2
  AND id NOT IN (SELECT id FROM kept);

COMMIT;

SELECT
    sort_order AS numero_na_imagem,
    description,
    servings AS fatias,
    shape,
    price_white AS preco_branca,
    price_chocolate AS preco_chocolate,
    active
FROM sizes
WHERE filling_layers = 2
  AND active = TRUE
ORDER BY sort_order;
