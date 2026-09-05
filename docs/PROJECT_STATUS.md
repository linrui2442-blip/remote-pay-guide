# Remote Pay Guide — Project Status

## Goal

Remote Pay Guide is an overseas content acquisition MVP for people receiving USDT or USDC payments for the first time.

The goal is not to build a crypto media account. The goal is to validate whether stablecoin payment education content can generate user intent and referral conversions.

## Current Stage

MVP completed. The project has entered content scale testing and data feedback validation.

## Phase 11

### Dashboard Database Integration

Status:

- SQLite connected
- Dashboard reads exported database data

## Phase 12B

### Publish Sync Database Integration

Status:

- publish_status table created
- publish sync remains read-only

Data flow:

```
publish-state
    ↓
publish-sync
    ↓
publish_status table
```

## Implemented

### Website

Completed:

- Landing Page
- Binance referral flow
- User intent questionnaire
- GA4 tracking

### Content Factory

Production pipeline completed:

```
JSONL Tasks
    ↓
Video Production Pipeline
    ↓
MP4
```

## Distribution

Postiz publishing system completed.

Confirmed platforms:

- Facebook ✅
- Instagram ✅
- YouTube Shorts ✅

## Data Architecture

```
Content Registry
        ↓
SQLite Database
        ↓
Dashboard Export Layer
        ↓
Read-only Dashboard
        ↓
publish-sync read-only layer
```
