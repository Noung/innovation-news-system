# Subscription Runtime Setup

The subscription form is implemented but remains disabled by default. The
local MySQL baseline includes its tables; production use is blocked until a
reviewed schema-only baseline and append-only migration are approved under
`sql/migrations/README.md`.

## Components

- `wordpress-plugin/innovation-news-subscription-form/` is a PHP
  5.6-compatible shortcode plugin. Add `[innovation_news_subscribe]` to the
  public WordPress page.
- `POST /api/subscriptions` creates a pending request and sends a confirmation
  email. Confirmation and unsubscribe links are handled by the matching
  public API routes.
- `fetch-innovation-news/api/email-worker.js` selects active subscribers that
  match an article's benefit slugs and sends each article once.

## WordPress configuration

Set the public API URL in WordPress configuration, never in page content:

```php
define(
    'OAR_INNOVATION_SUBSCRIPTION_API_URL',
    'https://news.example.org/api/subscriptions'
);
```

The WordPress origin must appear exactly in
`SUBSCRIPTION_ALLOWED_ORIGINS`. The browser submits JSON, so a non-allowed
origin cannot make a permitted cross-origin request.

## Production configuration

Use the production environment file outside Git:

```text
ENABLE_SUBSCRIPTION_API=1
ENABLE_EMAIL_WORKER=1
EMAIL_SEND_MODE=smtp
SUBSCRIPTION_ALLOWED_ORIGINS=https://www.example.org
SUBSCRIPTION_CONFIRM_BASE_URL=https://news.example.org/
SUBSCRIPTION_TOKEN_SECRET=<generated-secret-with-at-least-32-characters>
EMAIL_FROM=Innovation News <news@example.org>
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_SECURE=0
SMTP_USERNAME=<smtp-user>
SMTP_PASSWORD=<smtp-password>
```

`SMTP_SECURE=0` requires STARTTLS. Set `SMTP_SECURE=1` only for an implicit
TLS SMTP endpoint. Do not enable either feature flag until TLS, the schema
migration, the sender domain, SMTP credentials, and rollback plan have been
reviewed.

Run the worker separately from the fetcher, for example using the existing
OS cron owner:

```bash
cd /path/to/innovation-news-system/fetch-innovation-news/api
node email-worker.js
```

The worker creates an idempotent `(article_id, subscriber_id)` delivery record
before it sends. It sends only articles with a canonical published WordPress
URL and only to subscribers whose selected benefits match the article.

## Local testing

`docker/local.env.example` keeps both feature flags off. For an isolated
manual test, create an ignored local environment override that sets both flags
to `1`. Its `EMAIL_SEND_MODE=json` transport creates no outbound SMTP
connection while exercising the confirmation and delivery paths.
