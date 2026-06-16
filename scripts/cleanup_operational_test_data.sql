-- Dani Bolos - limpeza de dados operacionais/testes
-- Use no pgAdmin conectado ao banco correto.
--
-- Este script APAGA:
-- - pedidos e adicionais dos pedidos
-- - clientes/telefones
-- - conversas do robo
-- - eventos/logs de atendimento
-- - alertas do painel
--
-- Este script PRESERVA:
-- - catalogo: tamanhos, recheios, adicionais, finalizacoes, docinhos
-- - horarios: time_slots e service_hours em admin_settings
-- - configuracoes do painel/admin_settings
-- - midias do catalogo
-- - transicoes do robo/state_transitions
-- - datas/capacidades da agenda em availability

BEGIN;

-- Conferencia antes da limpeza.
SELECT 'antes' AS etapa, 'clients' AS tabela, COUNT(*) AS total FROM clients
UNION ALL SELECT 'antes', 'conversations', COUNT(*) FROM conversations
UNION ALL SELECT 'antes', 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'antes', 'order_extras', COUNT(*) FROM order_extras
UNION ALL SELECT 'antes', 'events', COUNT(*) FROM events
UNION ALL SELECT 'antes', 'alerts', COUNT(*) FROM alerts
ORDER BY tabela;

-- Trunca somente dados operacionais.
TRUNCATE TABLE
    alerts,
    events,
    order_extras,
    orders,
    conversations,
    clients
RESTART IDENTITY CASCADE;

-- Zera a ocupacao da agenda, preservando capacidade, bloqueios e mensagens.
UPDATE availability
SET confirmed_orders = 0,
    updated_at = NOW();

-- Conferencia depois da limpeza.
SELECT 'depois' AS etapa, 'clients' AS tabela, COUNT(*) AS total FROM clients
UNION ALL SELECT 'depois', 'conversations', COUNT(*) FROM conversations
UNION ALL SELECT 'depois', 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'depois', 'order_extras', COUNT(*) FROM order_extras
UNION ALL SELECT 'depois', 'events', COUNT(*) FROM events
UNION ALL SELECT 'depois', 'alerts', COUNT(*) FROM alerts
ORDER BY tabela;

COMMIT;

-- Opcional: se voce quiser tambem desbloquear todos os dias da agenda,
-- rode separadamente depois, somente se tiver certeza:
--
-- UPDATE availability
-- SET blocked = FALSE,
--     block_reason = NULL,
--     confirmed_orders = 0,
--     updated_at = NOW();
