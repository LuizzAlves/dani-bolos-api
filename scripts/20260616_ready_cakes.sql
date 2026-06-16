-- Migration: Bolos Pronta Entrega
-- Adiciona tabela ready_cakes e novos valores de enum para o fluxo de pronta entrega.
-- Execute com: psql "$DATABASE_URL" -f scripts/20260616_ready_cakes.sql

BEGIN;

-- 1. Tabela de bolos prontos para entrega
CREATE TABLE IF NOT EXISTS ready_cakes (
    id SERIAL PRIMARY KEY,
    flavor VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10,2),
    available BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Novos valores de enum
ALTER TYPE alert_type_enum ADD VALUE IF NOT EXISTS 'READY_CAKE_INTEREST';
ALTER TYPE conversation_state ADD VALUE IF NOT EXISTS 'PRONTA_ENTREGA';
ALTER TYPE sm_trigger_enum ADD VALUE IF NOT EXISTS 'OPTION_5';
ALTER TYPE sm_action_enum ADD VALUE IF NOT EXISTS 'SHOW_READY_CAKES';
ALTER TYPE sm_action_enum ADD VALUE IF NOT EXISTS 'RESERVE_READY_CAKE_INTEREST';

COMMIT;
