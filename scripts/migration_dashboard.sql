-- ============================================================
-- Dani Bolos — Migração: Dashboard Administrativo
-- Executar contra o banco PostgreSQL existente.
-- ============================================================

BEGIN;

-- 1. Enum para tipos de alerta
DO $$ BEGIN
    CREATE TYPE alert_type_enum AS ENUM (
        'HUMAN_REQUESTED',
        'STUCK_CLIENT',
        'CUSTOM_FILLING',
        'INTERPRETATION_ERROR',
        'FLOW_ERROR',
        'MAX_FALLBACK'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. Tabela de alertas
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    alert_type alert_type_enum NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    client_phone VARCHAR(20),
    client_name VARCHAR(255),
    last_message TEXT,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);

-- 3. Tabela de configurações administrativas
CREATE TABLE IF NOT EXISTS admin_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Valores iniciais das configurações
INSERT INTO admin_settings (key, value) VALUES
    ('bot_active', 'true'::jsonb),
    ('orders_paused', 'false'::jsonb),
    ('opening_time', '"08:00"'::jsonb),
    ('closing_time', '"18:00"'::jsonb),
    ('max_orders_default', '5'::jsonb),
    ('seasonal_message', '""'::jsonb),
    ('shop_name', '"Dani Bolos"'::jsonb),
    ('shop_phone', '""'::jsonb),
    ('timeout_minutes', '120'::jsonb),
    ('max_fallback_count', '3'::jsonb),
    ('limit_reached_message', '""'::jsonb),
    ('service_hours', '{"0": {"isOpen": true, "openTime": "06:00", "closeTime": "20:00"}, "1": {"isOpen": true, "openTime": "06:00", "closeTime": "20:00"}, "2": {"isOpen": true, "openTime": "06:00", "closeTime": "20:00"}, "3": {"isOpen": true, "openTime": "06:00", "closeTime": "20:00"}, "4": {"isOpen": true, "openTime": "06:00", "closeTime": "20:00"}, "5": {"isOpen": true, "openTime": "07:00", "closeTime": "18:00"}, "6": {"isOpen": true, "openTime": "09:00", "closeTime": "12:00"}}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- 5. Tornar conversation_id nullable em orders (para pedidos manuais)
ALTER TABLE orders ALTER COLUMN conversation_id DROP NOT NULL;

COMMIT;
