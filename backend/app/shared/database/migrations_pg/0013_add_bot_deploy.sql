-- Add deploy slug and deployment status to bots table.
-- Each bot can be independently deployed with a unique URL slug.

ALTER TABLE bots
    ADD COLUMN deploy_slug TEXT UNIQUE,
    ADD COLUMN is_deployed BOOLEAN NOT NULL DEFAULT FALSE;

-- Index for fast slug lookups (public user access)
CREATE INDEX IF NOT EXISTS idx_bots_deploy_slug ON bots (deploy_slug) WHERE deploy_slug IS NOT NULL;
