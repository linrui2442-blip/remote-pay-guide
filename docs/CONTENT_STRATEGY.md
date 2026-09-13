# Remote Pay Guide — Content Strategy

## Positioning

Remote Pay Guide is not:

- crypto news
- trading content
- price prediction content

It is stablecoin payment education.

## Target Users

Primary users:

- freelancer
- remote worker
- digital nomad
- overseas service providers
- people receiving USDT / USDC payments for the first time

## Core Problem

A typical user situation:

```
Client:
"I can pay you in USDT"

User:
"How do I receive it safely?"
```

The content helps users understand:

- USDT / USDC payments
- network selection
- wallet and exchange differences
- first-time receiving process

## Current Content System

Content is managed through predefined JSONL tasks:

- tasks-launch01.jsonl
- tasks-launch02.jsonl

Each task defines:

- video_subject
- video_script
- video_terms
- metadata

## Content Direction

Content focuses on real payment questions:

Examples:

- What does a USDT network mean?
- Should I use USDT or USDC?
- How do I receive my first stablecoin payment?
- What should freelancers check before receiving payment?

## Measurement Goal

Content success is not measured only by views.

The goal is:

```
Content
    ↓
Traffic
    ↓
User Intent
    ↓
Conversion
    ↓
Revenue Feedback
```

The key question:

Which content creates users with real stablecoin payment intent?

## Content Novelty Gate

Before a candidate is materialized into a ProductionTask, the local deterministic
novelty checker compares it with repository task sources and prioritizes content
confirmed by runtime, asset, or publish evidence.

The rule is:

```text
same user question + same instructional path = duplicate
title rewrite alone != new content
```

short11 and short12 exposed the first real duplicate-topic risk: both teach the
same network/address matching workflow despite different titles. New candidates
must receive `PASS`, `WARN`, or `BLOCK` before production integration is added.

## Visual Novelty Gates

Visual plans are checked before render for scene-term overlap and within-video
diversity. After selection/render, provenance records provider, source ID, URL,
local filename, and SHA256 when available. Exact provider/source ID, normalized
URL, or clip fingerprint reuse in the latest 10 contents is blocked. A title or
query rewrite is not new visual material.

P2-C2 established this contract. Historical exact Pexels reuse for short11 and
short12 remains UNKNOWN because their source provenance is unavailable. Future
renders record true source clips when MoneyPrinterTurbo exposes them; otherwise
provenance is explicitly marked unavailable and the final-output fingerprint is
kept separate.
