# Remote Pay Guide OS AI Production Architecture Clarification

## Purpose

This document corrects the interpretation of AI Production architecture to avoid future development mistakes.

## Important Correction

Remote Pay Guide OS runs on the user's computer as the local control center.

It is NOT designed as a local video generation workstation.

The AI Production Line does NOT mean:

```
PC
↓
Local GPU
↓
Local AI Model
↓
Generate Video
```

That interpretation is incorrect.

## Correct Architecture

The intended architecture is:

```
Remote Pay Guide OS (running on user's computer)

↓

Production Center

↓

AI Production Provider

↓

AI Gateway / API Relay

↓

External AI Video Generation Service

↓

Video Result

↓

Video Asset Center

↓

Publish Center
```

## Role Of Local Computer

The local computer is responsible for:

- running Remote Pay Guide OS
- managing production tasks
- selecting providers
- calling AI services
- tracking status
- managing assets
- controlling publishing
- collecting feedback data

It is not required to perform AI video inference locally.

## Dual Production Lines

Remote Pay Guide OS maintains two execution paths:

### 1. Legacy GitHub Production Line

```
Production Task
↓
GitHub Provider
↓
GitHub Actions
↓
Existing Video Production Pipeline
↓
Production Result
```

This line must remain compatible.

### 2. AI Remote Production Line

```
Production Task
↓
AI Gateway Provider
↓
AI API Service
↓
Video Result
↓
Production Result
```

## Development Rules

Future development must follow:

- Do not replace GitHub Production
- Do not introduce unnecessary local model inference
- Do not bind to a single AI model
- Keep AI Provider abstraction
- Keep the computer as the OS control center
- Keep Video Asset and Publish layers unified

## Terminology Correction

Previous ambiguous term:

"Local AI Production Line"

Recommended term:

"AI Remote Production Line"

or

"AI Gateway Production Line"

This prevents misunderstanding that the system requires local GPU video generation.
