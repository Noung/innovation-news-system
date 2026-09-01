const crypto = require('crypto');
const mysql = require('mysql2/promise');
const nodemailer = require('nodemailer');

const enabled = process.env.ENABLE_EMAIL_WORKER === '1';
const mode = (process.env.EMAIL_SEND_MODE || 'disabled').trim().toLowerCase();
const tokenSecret = (process.env.SUBSCRIPTION_TOKEN_SECRET || '').trim();
const unsubscribeBaseUrl = (process.env.SUBSCRIPTION_CONFIRM_BASE_URL || '').trim();

function readInteger(name, fallback, minimum, maximum) {
    const value = Number(process.env[name] || fallback);
    if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
        throw new Error(`${name} must be an integer between ${minimum} and ${maximum}`);
    }
    return value;
}

function getTransport() {
    if (mode === 'json') {
        return nodemailer.createTransport({ jsonTransport: true });
    }
    if (mode !== 'smtp') {
        throw new Error('EMAIL_SEND_MODE must be json or smtp when the email worker is enabled');
    }
    const host = (process.env.SMTP_HOST || '').trim();
    const from = (process.env.EMAIL_FROM || '').trim();
    if (!host || !from) {
        throw new Error('SMTP_HOST and EMAIL_FROM are required');
    }
    const username = (process.env.SMTP_USERNAME || '').trim();
    const password = (process.env.SMTP_PASSWORD || '').trim();
    return nodemailer.createTransport({
        host,
        port: readInteger('SMTP_PORT', 587, 1, 65535),
        secure: process.env.SMTP_SECURE === '1',
        auth: username || password ? { user: username, pass: password } : undefined,
        requireTLS: process.env.SMTP_SECURE !== '1',
    });
}

function unsubscribeToken() {
    const token = crypto.randomBytes(32).toString('base64url');
    return {
        token,
        hash: crypto.createHmac('sha256', tokenSecret).update(token).digest('hex'),
    };
}

function unsubscribeUrl(token) {
    const url = new URL('/api/subscriptions/unsubscribe', unsubscribeBaseUrl);
    url.searchParams.set('token', token);
    return url.toString();
}

function sanitizedError(error) {
    return String(error && error.message ? error.message : error || 'Unknown delivery error')
        .replace(/(password|token|secret)=\S+/gi, '$1=[REDACTED]')
        .slice(0, 1000);
}

async function main() {
    if (!enabled) {
        console.log('Email worker is disabled');
        return;
    }
    if (tokenSecret.length < 32 || !unsubscribeBaseUrl.startsWith('https://')) {
        throw new Error('A token secret and HTTPS subscription base URL are required');
    }

    const pool = mysql.createPool({
        host: process.env.DB_HOST || 'localhost',
        user: process.env.DB_USER || '',
        password: process.env.DB_PASS || '',
        database: process.env.DB_NAME || 'innovation_news',
        connectionLimit: 2,
    });
    const transport = getTransport();
    const batchSize = readInteger('EMAIL_WORKER_BATCH_SIZE', 50, 1, 200);
    const [candidates] = await pool.execute(
        `SELECT DISTINCT n.id AS article_id, n.title, n.summary, n.wordpress_url,
                s.id AS subscriber_id, s.email_normalized
         FROM innovation_news n
         INNER JOIN article_benefits ab ON ab.article_id = n.id
         INNER JOIN subscriber_benefits sb ON sb.benefit_slug = ab.benefit_slug
         INNER JOIN subscribers s ON s.id = sb.subscriber_id AND s.status = 'active'
         LEFT JOIN email_deliveries d
           ON d.article_id = n.id AND d.subscriber_id = s.id
         WHERE n.wordpress_status IN ('created', 'duplicate')
           AND n.wordpress_url IS NOT NULL AND n.wordpress_url <> ''
           AND d.id IS NULL
         ORDER BY n.id ASC
         LIMIT ?`,
        [batchSize]
    );

    for (const candidate of candidates) {
        const connection = await pool.getConnection();
        try {
            await connection.beginTransaction();
            const [delivery] = await connection.execute(
                `INSERT IGNORE INTO email_deliveries (article_id, subscriber_id, status)
                 VALUES (?, ?, 'pending')`,
                [candidate.article_id, candidate.subscriber_id]
            );
            if (!delivery.affectedRows) {
                await connection.rollback();
                continue;
            }
            const deliveryId = delivery.insertId;
            const token = unsubscribeToken();
            await connection.execute(
                `INSERT INTO subscription_tokens (subscriber_id, token_type, token_hash, expires_at)
                 VALUES (?, 'unsubscribe', ?, DATE_ADD(NOW(), INTERVAL 365 DAY))`,
                [candidate.subscriber_id, token.hash]
            );
            await connection.commit();

            try {
                const result = await transport.sendMail({
                    from: process.env.EMAIL_FROM || 'Innovation News <no-reply@localhost>',
                    to: candidate.email_normalized,
                    subject: candidate.title,
                    text: `${candidate.summary}\n\nRead more: ${candidate.wordpress_url}\n\nUnsubscribe: ${unsubscribeUrl(token.token)}`,
                });
                await connection.execute(
                    `UPDATE email_deliveries
                     SET status = 'sent', provider_message_id = ?, sent_at = NOW()
                     WHERE id = ?`,
                    [String(result.messageId || '').slice(0, 255) || null, deliveryId]
                );
                await connection.execute(
                    `INSERT INTO email_delivery_attempts (email_delivery_id, status)
                     VALUES (?, 'sent')`,
                    [deliveryId]
                );
            } catch (error) {
                const message = sanitizedError(error);
                await connection.execute(
                    `UPDATE email_deliveries SET status = 'failed', error_message = ? WHERE id = ?`,
                    [message, deliveryId]
                );
                await connection.execute(
                    `INSERT INTO email_delivery_attempts (email_delivery_id, status, error_message)
                     VALUES (?, 'failed', ?)`,
                    [deliveryId, message]
                );
                console.error(`Email delivery ${deliveryId} failed: ${message}`);
            }
        } finally {
            connection.release();
        }
    }
    await pool.end();
}

main().catch((error) => {
    console.error(`Email worker failed: ${sanitizedError(error)}`);
    process.exitCode = 1;
});
