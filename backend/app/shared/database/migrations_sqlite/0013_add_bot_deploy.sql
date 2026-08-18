-- Add deploy slug and deployment status to bots table.
ALTER TABLE bots ADD COLUMN deploy_slug TEXT;
ALTER TABLE bots ADD COLUMN is_deployed INTEGER NOT NULL DEFAULT 0;

-- Index for fast slug lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_bots_deploy_slug ON bots (deploy_slug) WHERE deploy_slug IS NOT NULL;
