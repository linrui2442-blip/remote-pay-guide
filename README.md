# Remote Pay Guide

Beginner-friendly landing page for people receiving USDT or USDC payments for the first time.

## Goal

Test whether first-time stablecoin payment intent can generate attributable Binance referrals.

## Referral

Binance referral ID: `137553211`

The page discloses the referral relationship and reminds users to verify the exact asset and network before transferring funds.

## Traffic source tracking

Append `?src=` to the URL, for example:

- `?src=yt01`
- `?src=tt01`
- `?src=fb01`

The V0 page emits these browser events:

- `page_view`
- `payment_type_select`
- `payer_type_select`
- `exchange_status_select`
- `new_to_exchange_identified`
- `binance_referral_click`

V0 stores a local event log and also pushes events to `window.dataLayer`. A real analytics destination (GA4/Plausible/Umami) should be connected before paid traffic is sent.

## Deployment

This repository is designed to be published from the `main` branch root with GitHub Pages.
