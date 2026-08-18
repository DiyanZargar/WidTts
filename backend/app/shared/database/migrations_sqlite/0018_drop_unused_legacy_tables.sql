-- Migration 0018: Safely prune unused legacy tables
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS responses;
DROP TABLE IF EXISTS interruptions;
DROP TABLE IF EXISTS audit_logs;
