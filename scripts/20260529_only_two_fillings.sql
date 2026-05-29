-- Dani Bolos: manter apenas bolos com 2 recheios no catalogo.
-- Execute no banco de producao/homologacao apos subir a API atualizada.
--
-- Efeito:
-- 1. Desativa tamanhos antigos de 1 recheio.
-- 2. Desativa a midia visual antiga CARDAPIO_1R.
-- 3. Cancela rascunhos incompletos que ainda estejam em tamanho de 1 recheio.
-- 4. Preserva pedidos ja enviados/finalizados para auditoria.

BEGIN;

UPDATE sizes
SET active = FALSE,
    updated_at = NOW()
WHERE filling_layers <> 2
  AND active = TRUE;

UPDATE catalog_media
SET active = FALSE,
    updated_at = NOW()
WHERE reference_type = 'CARDAPIO_1R'
  AND active = TRUE;

UPDATE orders o
SET status = 'CANCELADO',
    updated_at = NOW()
FROM sizes s
WHERE o.size_id = s.id
  AND s.filling_layers <> 2
  AND o.status = 'RASCUNHO';

COMMIT;

-- Verificacao esperada:
-- active_sizes_1_recheio = 0
-- active_cardapio_1r = 0
SELECT
  (SELECT COUNT(*) FROM sizes WHERE active = TRUE AND filling_layers <> 2) AS active_sizes_1_recheio,
  (SELECT COUNT(*) FROM catalog_media WHERE active = TRUE AND reference_type = 'CARDAPIO_1R') AS active_cardapio_1r,
  (SELECT COUNT(*) FROM sizes WHERE active = TRUE AND filling_layers = 2) AS active_sizes_2_recheios;
