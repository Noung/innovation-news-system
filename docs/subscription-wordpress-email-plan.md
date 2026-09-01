# WordPress Subscription and Email Delivery Plan

## Objective

Develop two related capabilities without disrupting the existing news fetch and
publication workflow:

1. Send the published WordPress URL to LINE instead of the source article URL.
2. Let readers subscribe from a WordPress form and choose the organization
   benefits they want to follow. Innovation News owns subscriber data and sends
   email notifications.

WordPress remains the public form host only. The Innovation News Node API,
MySQL database, and email worker own all subscription state and delivery.

## Architecture decisions

- Use the existing controlled vocabulary of 20 benefits. Store stable benefit
  slugs, not translated display names, as the subscription selection.
- Use email as the initial subscriber delivery channel.
- Require double opt-in before a subscriber becomes active.
- Include a signed, expiring unsubscribe token in every notification email.
- Keep subscription endpoints separate from authenticated Admin endpoints.
- Do not store subscriber records, email provider credentials, or delivery
  secrets in WordPress.
- Preserve the default feature gates until production rollout is approved:
  `ENABLE_SUBSCRIPTION_API=0`, `ENABLE_EMAIL_WORKER=0`, and
  `EMAIL_SEND_MODE=disabled`.

## Phase 1: Publish WordPress URLs to LINE

1. Update `scripts/wordpress_integration.py` so both newly-created and
   duplicate WordPress posts return their post ID and canonical public URL.
2. Update `sync_wordpress_and_line()` in
   `scripts/fetch-innovation-news-mysql.py` to pass the WordPress URL to LINE.
3. Update `scripts/line_integration.py` to render that URL, not
   `article['link']`.
4. Enforce the delivery rule: do not send LINE when a canonical WordPress URL
   is unavailable. Do not fall back to the source URL.
5. Record WordPress and LINE outcomes in the existing article and fetch logs
   so delivery failures can be traced.

Acceptance criteria:

- Every LINE notification links to the published WordPress post.
- A failed or unavailable WordPress publication blocks LINE delivery.
- A duplicate WordPress post still supplies its canonical URL.

## Phase 2: Subscription schema and migration baseline

Production migrations require the schema-only baseline, review, checksum,
backup, and advisory-lock process defined in `sql/migrations/README.md`.
Create an append-only migration only after that preflight is complete.

Add these tables:

| Table | Responsibility |
|---|---|
| `subscribers` | Normalized email, lifecycle status (`pending`, `active`, `unsubscribed`), consent metadata, and confirmation timestamps |
| `subscriber_benefits` | Many-to-many association of an active subscriber and selected benefit slugs |
| `subscription_tokens` | Hashed confirmation and unsubscribe tokens, expiry, and use timestamps |
| `email_deliveries` | Per-article recipient delivery status, provider message ID, and sanitized error details |
| `email_delivery_attempts` | Retry attempts and their sanitized result |

The migration should include foreign keys, indexes for active
subscriber/benefit lookups and delivery processing, a unique normalized-email
constraint, and an explicit rollback or forward-fix procedure.

## Phase 3: Public subscription API and email worker

Add Node API endpoints that are not part of the authenticated Admin API:

- `POST /api/subscriptions` accepts an email address, selected benefit slugs,
  consent, and the WordPress form origin. It creates or refreshes a pending
  confirmation request without exposing whether the email already exists.
- `GET /api/subscriptions/confirm` validates a single-use, expiring token and
  activates the subscription.
- `GET /api/subscriptions/unsubscribe` validates its token and deactivates the
  subscription.

Protect the public surface with input validation, IP and email rate limits,
origin restrictions, generic anti-enumeration responses, and sanitized audit
logs.

Add a dedicated email worker rather than placing outbound email work in the
fetcher process. When a WordPress post has been published, the worker:

1. Reads its three controlled benefit slugs.
2. Finds active subscribers with at least one matching benefit.
3. Creates an idempotent delivery record.
4. Sends an email containing the canonical WordPress URL and unsubscribe link.
5. Records provider status and retries only transient failures.

Keep email-provider credentials in environment configuration outside Git. Use
an adapter so the local stack can use a mock provider and production can use
the approved provider.

## Phase 4: WordPress form compatible with PHP 5.6

Extend `wordpress-plugin/innovation-tip-benefit-taxonomy` with a shortcode,
for example `[innovation_news_subscribe]`.

The shortcode renders:

- An email address input.
- A multi-select list of the controlled benefit vocabulary.
- A required consent checkbox and privacy/unsubscribe notice.
- A status message that does not reveal whether an email was already
  registered.

The plugin must retain PHP 5.6 compatibility and use safe escaping,
sanitization, and a WordPress nonce. Its browser code sends requests only to
the approved HTTPS subscription API. Configure either a narrowly scoped CORS
allowlist or a server-side WordPress proxy; do not expose API credentials in
browser code.

## Phase 5: Local testing and production rollout

1. Extend the Docker-local MySQL fixture with subscription tables.
2. Add a mock email provider to the local-only integration environment.
3. Add tests for benefit normalization, subscription validation, repeated
   registrations, token expiry, confirmation, unsubscription, rate limiting,
   email anti-enumeration, recipient matching, idempotent delivery, retry
   behavior, error redaction, and the WordPress shortcode.
4. Verify the complete local flow with mock email while feature gates are
   explicitly enabled only in local configuration.
5. Before production: complete migration preflight, backup/checksum review,
   HTTPS and CORS/proxy review, email-domain/DNS/provider readiness, rollback
   plan, and explicit approval.
6. Deploy in this order: database migration, disabled API/worker release,
   WordPress plugin and shortcode, test subscription, enable subscription API,
   then enable the email worker after delivery verification.

## Implementation order

Implement Phase 1 first. Then complete Phases 2 through 5 in order. This
delivers WordPress links to LINE independently while keeping subscription and
outbound email changes gated until the required security and production
controls are ready.
