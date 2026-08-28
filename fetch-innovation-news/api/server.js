const crypto = require('crypto');
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

const APP_DIR = path.resolve(__dirname, '..');
const DEPLOY_WORKSPACE_DIR = path.resolve(APP_DIR, '..');
const SCRIPTS_DIR = path.join(DEPLOY_WORKSPACE_DIR, 'scripts');

function loadEnvFile(filePath) {
    if (!filePath || !fs.existsSync(filePath)) {
        return false;
    }

    const lines = fs.readFileSync(filePath, 'utf8').split(/\r?\n/);
    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#') || !line.includes('=')) {
            continue;
        }

        const [rawKey, ...valueParts] = line.split('=');
        const key = rawKey.trim();
        if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
            continue;
        }
        const value = valueParts.join('=').trim().replace(/^['"]|['"]$/g, '');
        if (key !== 'INNOVATION_NEWS_ENV_FILE') {
            process.env[key] = value;
        }
    }

    return true;
}

function readIntegerEnv(name, defaultValue, minimum, maximum) {
    const rawValue = process.env[name];
    if (rawValue === undefined || String(rawValue).trim() === '') {
        return defaultValue;
    }
    const normalized = String(rawValue).trim();
    if (!/^[0-9]+$/.test(normalized)) {
        throw new Error(`${name} must be an integer`);
    }
    const value = Number(normalized);
    if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
        throw new Error(`${name} must be between ${minimum} and ${maximum}`);
    }
    return value;
}

const explicitEnvFile = (process.env.INNOVATION_NEWS_ENV_FILE || '').trim();
const envCandidates = [
    path.join(DEPLOY_WORKSPACE_DIR, '.env'),
    path.join(SCRIPTS_DIR, '.env'),
].filter(Boolean);

if (explicitEnvFile) {
    if (!loadEnvFile(explicitEnvFile)) {
        throw new Error(`Explicit INNOVATION_NEWS_ENV_FILE does not exist: ${explicitEnvFile}`);
    }
} else {
    let loadedEnvFile = false;
    for (const envPath of envCandidates) {
        if (loadEnvFile(envPath)) {
            loadedEnvFile = true;
            break;
        }
    }
    if (!loadedEnvFile) {
        throw new Error(
            'No Innovation News environment file found; expected workspace-root .env or temporary scripts/.env fallback'
        );
    }
}

const port = readIntegerEnv('PORT', 3001, 1, 65535);
const bindHost = (process.env.ADMIN_BIND_HOST || '127.0.0.1').trim();
const allowedBindHosts = new Set(['127.0.0.1', '::1', 'localhost', '0.0.0.0']);
if (!allowedBindHosts.has(bindHost)) {
    throw new Error(
        'ADMIN_BIND_HOST must be 127.0.0.1, ::1, localhost, or 0.0.0.0 for the existing LAN deployment'
    );
}
const trustProxy = (process.env.ADMIN_TRUST_PROXY || 'loopback').trim();
const allowedTrustProxyValues = new Set(['loopback', 'linklocal', 'uniquelocal']);
if (!allowedTrustProxyValues.has(trustProxy)) {
    throw new Error(
        'ADMIN_TRUST_PROXY must be loopback, linklocal, or uniquelocal; arbitrary proxy trust is not allowed'
    );
}
const allowedCorsOrigins = new Set(
    (process.env.ADMIN_CORS_ORIGINS || '')
        .split(',')
        .map((origin) => origin.trim())
        .filter(Boolean)
);
const AUTH_COOKIE_NAME = 'innovation_news_admin_session';
const ADMIN_USERNAME = (process.env.ADMIN_USERNAME || 'admin').trim();
const ADMIN_PASSWORD = (process.env.ADMIN_PASSWORD || '').trim();
const ADMIN_USERNAME_2 = (process.env.ADMIN_USERNAME_2 || '').trim();
const ADMIN_PASSWORD_2 = (process.env.ADMIN_PASSWORD_2 || '').trim();
const ADMIN_SESSION_SECRET = (process.env.ADMIN_SESSION_SECRET || '').trim();
const configuredAdminCredentials = [
    { username: ADMIN_USERNAME, password: ADMIN_PASSWORD, label: 'primary' },
    { username: ADMIN_USERNAME_2, password: ADMIN_PASSWORD_2, label: 'secondary' },
];
function looksLikePlaceholderSecret(value) {
    return /(?:^|[_-])(your|change[-_]?me|changeme|example|placeholder|password)(?:$|[_-])/i.test(
        String(value || '')
    );
}
for (const credential of configuredAdminCredentials) {
    const partiallyConfigured = Boolean(credential.username) !== Boolean(credential.password);
    if (partiallyConfigured) {
        throw new Error(`The ${credential.label} admin credential requires both username and password`);
    }
    if (credential.password && credential.password.length < 16) {
        throw new Error(`The ${credential.label} admin password must contain at least 16 characters`);
    }
    if (credential.password && looksLikePlaceholderSecret(credential.password)) {
        throw new Error(`The ${credential.label} admin password must not be a placeholder value`);
    }
}
if (configuredAdminCredentials.some((credential) => credential.password) && ADMIN_SESSION_SECRET.length < 32) {
    throw new Error('ADMIN_SESSION_SECRET must contain at least 32 characters when admin login is configured');
}
if (ADMIN_SESSION_SECRET && looksLikePlaceholderSecret(ADMIN_SESSION_SECRET)) {
    throw new Error('ADMIN_SESSION_SECRET must not be a placeholder value');
}
const ADMIN_SESSION_TTL_SECONDS = readIntegerEnv('ADMIN_SESSION_TTL_SECONDS', 43200, 60, 604800);
const SESSION_STORE = new Map();
const LOGIN_RATE_WINDOW_MS = readIntegerEnv('ADMIN_LOGIN_RATE_WINDOW_MS', 900000, 1000, 86400000);
const LOGIN_RATE_MAX_ATTEMPTS = readIntegerEnv('ADMIN_LOGIN_RATE_MAX_ATTEMPTS', 10, 1, 100);
const LOGIN_ATTEMPTS = new Map();
const WORKSPACE_DIR = process.env.INNOVATION_NEWS_WORKSPACE_DIR || DEPLOY_WORKSPACE_DIR;
const FETCH_MAIN_SCRIPT = resolveFirstExistingPath(
    process.env.INNOVATION_NEWS_MAIN_SCRIPT,
    path.join(SCRIPTS_DIR, 'fetch-innovation-news-mysql.py'),
    path.join(WORKSPACE_DIR, 'scripts', 'fetch-innovation-news-mysql.py'),
    path.join(WORKSPACE_DIR, 'fetch-innovation-news-mysql.py'),
    path.join(APP_DIR, 'fetch-innovation-news-mysql.py')
);
const FETCH_WORKDIR = process.env.INNOVATION_NEWS_FETCH_WORKDIR
    || process.env.INNOVATION_NEWS_WORKSPACE_DIR
    || path.dirname(FETCH_MAIN_SCRIPT);
const PYTHON_BIN = (process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3')).trim();
const FETCH_TIMEOUT_MS = readIntegerEnv('MANUAL_FETCH_TIMEOUT_MS', 600000, 1000, 3600000);
const SOURCES_INDEX_FILE = process.env.INNOVATION_NEWS_SOURCES_INDEX_FILE || path.join(WORKSPACE_DIR, 'cache', 'innovation-sources-index.txt');
const VALID_FETCH_METHODS = new Set(['rss', 'html', 'api']);
const VALID_API_VARIANTS = new Set(['wordpress', 'generic_json']);
const SENSITIVE_QUERY_PARAMETER = /^(api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)$/i;
const SENSITIVE_DETAIL_KEY = /(password|secret|token|api[_-]?key|authorization)/i;
const SUPPORTED_FETCHERS = Object.freeze({
    nia: 'html',
    etda: 'rss',
    techsauce: 'rss',
    nstda: 'api',
    ryt9: 'rss',
    it24hrs: 'rss',
    techtalkthai: 'rss',
    nectec: 'html',
    nriis: 'rss',
    innomatter: 'rss',
    techmovement: 'html'
});
let manualFetchRun = null;
const SOURCE_TEST_TIMEOUT_MS = readIntegerEnv('SOURCE_TEST_TIMEOUT_MS', 120000, 1000, 1800000);

function resolveFirstExistingPath(...candidatePaths) {
    const normalizedCandidates = candidatePaths
        .filter(Boolean)
        .map((candidatePath) => path.resolve(candidatePath));

    return normalizedCandidates.find((candidatePath) => fs.existsSync(candidatePath))
        || normalizedCandidates[0]
        || '';
}

function hasCredentialQueryParameter(rawUrls) {
    return String(rawUrls || '')
        .split(',')
        .map((rawUrl) => rawUrl.trim())
        .filter(Boolean)
        .some((rawUrl) => {
            try {
                const parsed = new URL(rawUrl);
                return Boolean(parsed.username || parsed.password) || Array.from(parsed.searchParams.keys()).some(
                    (key) => SENSITIVE_QUERY_PARAMETER.test(key)
                );
            } catch (error) {
                return false;
            }
        });
}

function redactUrlCredentials(rawValue) {
    return String(rawValue || '')
        .split(',')
        .map((rawUrl) => {
            const trimmed = rawUrl.trim();
            try {
                const parsed = new URL(trimmed);
                let changed = false;
                if (parsed.username) {
                    parsed.username = '[REDACTED]';
                    changed = true;
                }
                if (parsed.password) {
                    parsed.password = '[REDACTED]';
                    changed = true;
                }
                for (const key of Array.from(parsed.searchParams.keys())) {
                    if (SENSITIVE_QUERY_PARAMETER.test(key)) {
                        parsed.searchParams.set(key, '[REDACTED]');
                        changed = true;
                    }
                }
                return changed ? parsed.toString() : trimmed;
            } catch (error) {
                return trimmed.replace(
                    /([?&](?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)=)[^&#\s"'\\},]*/gi,
                    '$1[REDACTED]'
                );
            }
        })
        .join(',');
}

function redactSensitiveText(rawValue) {
    return String(rawValue || '')
        .replace(
            /([?&](?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)=)[^&#\s"'\\},]*/gi,
            '$1[REDACTED]'
        )
        .replace(
            /(https?:\/\/)[^/@\s:]+:[^/@\s]+@/gi,
            '$1[REDACTED]@'
        )
        .replace(
            /\b(authorization\s*:\s*(?:bearer|basic)\s+)\S+/gi,
            '$1[REDACTED]'
        )
        .replace(
            /(["'](?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|auth)["']\s*:\s*["'])[^"']*/gi,
            '$1[REDACTED]'
        );
}

function sanitizeAuditDetails(value, keyName = '') {
    if (value === null || value === undefined) {
        return value;
    }
    if (SENSITIVE_DETAIL_KEY.test(keyName)) {
        return '[REDACTED]';
    }
    if (Array.isArray(value)) {
        return value.map((item) => sanitizeAuditDetails(item));
    }
    if (typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, sanitizeAuditDetails(item, key)])
        );
    }
    if (typeof value === 'string') {
        return redactSensitiveText(
            keyName === 'source_url' || /^https?:\/\//i.test(value)
                ? redactUrlCredentials(value)
                : value
        );
    }
    return value;
}

function sanitizeApiResponse(value, keyName = '') {
    if (value === null || value === undefined || value instanceof Date || Buffer.isBuffer(value)) {
        return value;
    }
    if (SENSITIVE_DETAIL_KEY.test(keyName)) {
        return '[REDACTED]';
    }
    if (Array.isArray(value)) {
        return value.map((item) => sanitizeApiResponse(item));
    }
    if (typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, sanitizeApiResponse(item, key)])
        );
    }
    if (typeof value === 'string') {
        return redactSensitiveText(
            keyName === 'source_url' || /^https?:\/\//i.test(value)
                ? redactUrlCredentials(value)
                : value
        );
    }
    return value;
}

if (process.argv.includes('--config-check')) {
    console.log(
        `Configuration OK: bind=${bindHost}, trusted_proxy=${trustProxy}, admin_users=${getConfiguredAdminUsers().length}`
    );
    process.exit(0);
}

const express = require('express');
const mysql = require('mysql2/promise');
const bodyParser = require('body-parser');
const app = express();
app.set('trust proxy', trustProxy);

// Database connection
const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || process.env.MYSQL_USER || '',
    password: process.env.DB_PASS || process.env.MYSQL_PASSWORD || '',
    database: process.env.DB_NAME || process.env.MYSQL_DATABASE || 'innovation_news',
    waitForConnections: true,
    connectionLimit: readIntegerEnv('DB_POOL_SIZE', 10, 1, 100),
    queueLimit: 0
};

// Middleware
app.use((req, res, next) => {
    const sendJson = res.json.bind(res);
    res.json = (payload) => sendJson(sanitizeApiResponse(payload));
    next();
});
app.use((req, res, next) => {
    const origin = req.get('Origin');
    if (!origin) {
        return next();
    }

    let sameHost = false;
    try {
        sameHost = new URL(origin).host === req.get('host');
    } catch (error) {
        return res.status(403).json({ success: false, error: 'Origin not allowed' });
    }

    if (!sameHost && !allowedCorsOrigins.has(origin)) {
        return res.status(403).json({ success: false, error: 'Origin not allowed' });
    }

    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Vary', 'Origin');
    if (req.method === 'OPTIONS') {
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
        return res.status(204).end();
    }
    return next();
});
app.disable('x-powered-by');
app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        + "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
        + "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    );
    next();
});
app.use(bodyParser.json({ limit: '100kb' }));
app.use(express.static(path.join(__dirname, '../public')));

// Root route - serve index.html explicitly
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../public/index.html'));
});

app.post('/api/auth/login', async (req, res) => {
    if (!isAuthConfigured()) {
        return res.status(503).json({ success: false, error: 'Admin authentication is not configured' });
    }

    const username = typeof req.body?.username === 'string' ? req.body.username.trim() : '';
    const password = typeof req.body?.password === 'string' ? req.body.password : '';
    const rateKey = req.ip || req.socket?.remoteAddress || 'unknown';
    const now = Date.now();
    const previousAttempt = LOGIN_ATTEMPTS.get(rateKey);
    const attempt = !previousAttempt || previousAttempt.resetAt <= now
        ? { count: 0, resetAt: now + LOGIN_RATE_WINDOW_MS }
        : previousAttempt;

    if (attempt.count >= LOGIN_RATE_MAX_ATTEMPTS) {
        res.setHeader('Retry-After', String(Math.max(1, Math.ceil((attempt.resetAt - now) / 1000))));
        return res.status(429).json({ success: false, error: 'Too many login attempts' });
    }

    const matchedUser = getAuthenticatedAdminCredentials(username, password);
    if (!matchedUser) {
        attempt.count += 1;
        LOGIN_ATTEMPTS.set(rateKey, attempt);
        return res.status(401).json({ success: false, error: 'Invalid username or password' });
    }

    LOGIN_ATTEMPTS.delete(rateKey);
    setSessionCookie(res, matchedUser.username);
    await writeAuditLogEntry({
        username: matchedUser.username,
        action: 'login',
        targetType: 'auth',
        targetName: 'admin-session',
        details: { success: true }
    });
    res.json({ success: true, data: { username: matchedUser.username } });
});

app.post('/api/auth/logout', async (req, res) => {
    const user = getAuthenticatedUser(req);
    if (user?.sessionId) {
        SESSION_STORE.delete(user.sessionId);
    }
    clearSessionCookie(res);
    await writeAuditLogEntry({
        username: user?.username || 'unknown',
        action: 'logout',
        targetType: 'auth',
        targetName: 'admin-session',
        details: { success: true }
    });
    res.json({ success: true });
});

app.get('/api/auth/me', (req, res) => {
    if (!isAuthConfigured()) {
        return res.status(503).json({ success: false, error: 'Admin authentication is not configured' });
    }

    const user = getAuthenticatedUser(req);
    if (!user) {
        return res.status(401).json({ success: false, error: 'Authentication required' });
    }

    res.json({ success: true, data: { username: user.username, expires_at: user.expiresAt } });
});

app.use((req, res, next) => {
    if (!req.path.startsWith('/api/')) {
        return next();
    }

    if (req.path === '/api/health' || req.path === '/api/auth/login') {
        return next();
    }

    if (!isAuthConfigured()) {
        return res.status(503).json({ success: false, error: 'Admin authentication is not configured' });
    }

    const user = getAuthenticatedUser(req);
    if (!user) {
        return res.status(401).json({ success: false, error: 'Authentication required' });
    }

    req.authenticatedUser = user;
    return next();
});

if (!dbConfig.user) {
    console.warn('DB_USER is not set. Configure database credentials via environment variables or .env.');
}

if (!isAuthConfigured()) {
    console.warn('Admin authentication is not fully configured. Set ADMIN_PASSWORD and ADMIN_SESSION_SECRET to protect the admin panel.');
}

// Database pool
const pool = mysql.createPool(dbConfig);

function sanitizeSourcePayload(body = {}) {
    const fetchMethod = typeof body.fetch_method === 'string' ? body.fetch_method.trim().toLowerCase() : '';
    const rawApiVariant = typeof body.api_variant === 'string' ? body.api_variant.trim().toLowerCase() : '';
    const apiVariant = fetchMethod === 'api' ? (rawApiVariant || 'wordpress') : null;

    return {
        name: typeof body.name === 'string' ? body.name.trim() : '',
        slug: typeof body.slug === 'string' ? body.slug.trim().toLowerCase() : '',
        source_url: typeof body.source_url === 'string' ? body.source_url.trim() : '',
        fetch_method: fetchMethod,
        api_variant: apiVariant,
        json_items_path: typeof body.json_items_path === 'string' ? body.json_items_path.trim() : '',
        json_title_field: typeof body.json_title_field === 'string' ? body.json_title_field.trim() : '',
        json_link_field: typeof body.json_link_field === 'string' ? body.json_link_field.trim() : '',
        json_date_field: typeof body.json_date_field === 'string' ? body.json_date_field.trim() : '',
        json_summary_field: typeof body.json_summary_field === 'string' ? body.json_summary_field.trim() : '',
        is_active: body.is_active === undefined ? undefined : Number(Boolean(body.is_active))
    };
}

function normalizeSourceApiConfig(row = {}) {
    const fetchMethod = typeof row.fetch_method === 'string' ? row.fetch_method.trim().toLowerCase() : '';
    const apiVariant = fetchMethod === 'api'
        ? ((typeof row.api_variant === 'string' && row.api_variant.trim()) ? row.api_variant.trim().toLowerCase() : 'wordpress')
        : null;

    return {
        ...row,
        source_url: redactUrlCredentials(row.source_url || ''),
        fetch_method: fetchMethod,
        api_variant: apiVariant,
        json_items_path: typeof row.json_items_path === 'string' ? row.json_items_path.trim() : '',
        json_title_field: typeof row.json_title_field === 'string' ? row.json_title_field.trim() : '',
        json_link_field: typeof row.json_link_field === 'string' ? row.json_link_field.trim() : '',
        json_date_field: typeof row.json_date_field === 'string' ? row.json_date_field.trim() : '',
        json_summary_field: typeof row.json_summary_field === 'string' ? row.json_summary_field.trim() : '',
    };
}

function buildGenericJsonMapping(row = {}) {
    const normalized = normalizeSourceApiConfig(row);
    return {
        items_path: normalized.json_items_path,
        title_field: normalized.json_title_field,
        link_field: normalized.json_link_field,
        date_field: normalized.json_date_field,
        summary_field: normalized.json_summary_field || null,
    };
}

function validateSourcePayload(payload, { requireAllFields = true } = {}) {
    const normalizedPayload = normalizeSourceApiConfig(payload);

    if (requireAllFields && (!normalizedPayload.name || !normalizedPayload.slug || !normalizedPayload.source_url || !normalizedPayload.fetch_method)) {
        return 'Missing required fields';
    }

    if (normalizedPayload.slug && !/^[a-z0-9-]+$/.test(normalizedPayload.slug)) {
        return 'Slug must contain only lowercase letters, numbers, and hyphens';
    }

    if (normalizedPayload.fetch_method && !VALID_FETCH_METHODS.has(normalizedPayload.fetch_method)) {
        return 'Invalid fetch_method. Expected one of: rss, html, api';
    }

    if (normalizedPayload.source_url) {
        const urls = normalizedPayload.source_url
            .split(',')
            .map((url) => url.trim())
            .filter(Boolean);
        try {
            if (!urls.length || urls.some((url) => new URL(url).protocol !== 'https:')) {
                return 'source_url must contain HTTPS URLs only';
            }
        } catch (error) {
            return 'Invalid source_url';
        }
        if (hasCredentialQueryParameter(normalizedPayload.source_url)) {
            return 'Credential-like query parameters are not allowed in source_url';
        }
    }

    if (normalizedPayload.fetch_method === 'api') {
        if (!VALID_API_VARIANTS.has(normalizedPayload.api_variant)) {
            return 'Invalid api_variant. Expected one of: wordpress, generic_json';
        }

        if (normalizedPayload.api_variant === 'wordpress') {
            const urls = normalizedPayload.source_url
                .split(',')
                .map((url) => url.trim())
                .filter(Boolean);
            const isWordPressApi = urls.length > 0 && urls.every((url) => /\/wp-json\/wp\/v2\//i.test(url));
            const hasCustomApiFetcher = SUPPORTED_FETCHERS[normalizedPayload.slug] === 'api';

            if (!isWordPressApi && !hasCustomApiFetcher) {
                return 'WordPress API mode requires a /wp-json/wp/v2/... endpoint';
            }
        }

        if (normalizedPayload.api_variant === 'generic_json') {
            if (normalizedPayload.source_url.includes(',')) {
                return 'Generic JSON API currently supports exactly one endpoint URL';
            }

            if (
                !normalizedPayload.json_items_path
                || !normalizedPayload.json_title_field
                || !normalizedPayload.json_link_field
                || !normalizedPayload.json_date_field
            ) {
                return 'Generic JSON API requires items_path, title_field, link_field, and date_field';
            }
        }
    }

    const expectedMethod = SUPPORTED_FETCHERS[normalizedPayload.slug];
    if (expectedMethod && normalizedPayload.fetch_method && normalizedPayload.fetch_method !== expectedMethod) {
        return `Slug '${normalizedPayload.slug}' must use fetch_method '${expectedMethod}' to match the runtime fetcher`;
    }

    if (
        normalizedPayload.is_active === 1 &&
        !getRuntimeFetchMetadata({
            slug: normalizedPayload.slug,
            fetch_method: normalizedPayload.fetch_method,
            source_url: normalizedPayload.source_url,
            api_variant: normalizedPayload.api_variant,
            json_items_path: normalizedPayload.json_items_path,
            json_title_field: normalizedPayload.json_title_field,
            json_link_field: normalizedPayload.json_link_field,
            json_date_field: normalizedPayload.json_date_field,
            json_summary_field: normalizedPayload.json_summary_field,
        }).runtime_supported
    ) {
        return 'This source cannot be activated yet because the runtime does not support its slug/fetch_method combination';
    }

    return null;
}

function isSourceTestPassed(row = {}) {
    return row.last_test_status === 'passed' && Number(row.last_test_articles_found || 0) > 0;
}

function getRuntimeFetchMetadata(row = {}) {
    const normalizedRow = normalizeSourceApiConfig(row);
    const explicitExpectedFetchMethod = SUPPORTED_FETCHERS[normalizedRow.slug] || null;
    const urls = String(normalizedRow.source_url || '')
        .split(',')
        .map((url) => url.trim())
        .filter(Boolean);
    const genericRssSupported = normalizedRow.fetch_method === 'rss' && urls.length > 0;
    const genericWordPressApiSupported = normalizedRow.fetch_method === 'api'
        && normalizedRow.api_variant === 'wordpress'
        && urls.length > 0
        && urls.every((url) => /\/wp-json\/wp\/v2\//i.test(url));
    const genericJsonApiSupported = normalizedRow.fetch_method === 'api'
        && normalizedRow.api_variant === 'generic_json'
        && urls.length === 1
        && normalizedRow.json_items_path
        && normalizedRow.json_title_field
        && normalizedRow.json_link_field
        && normalizedRow.json_date_field;
    const runtimeSupported = Boolean(explicitExpectedFetchMethod)
        || genericRssSupported
        || genericWordPressApiSupported
        || genericJsonApiSupported;

    let runtimeWarning = null;
    let runtimeType = 'unsupported';
    if (explicitExpectedFetchMethod && normalizedRow.fetch_method && explicitExpectedFetchMethod !== normalizedRow.fetch_method) {
        runtimeWarning = `Runtime expects fetch_method '${explicitExpectedFetchMethod}'`;
    }

    if (genericJsonApiSupported) {
        runtimeType = 'generic_json_api';
    } else if (genericWordPressApiSupported) {
        runtimeType = 'generic_wp_api';
    } else if (genericRssSupported) {
        runtimeType = 'generic_rss';
    } else if (explicitExpectedFetchMethod) {
        runtimeType = `custom_${explicitExpectedFetchMethod}`;
    } else if (normalizedRow.fetch_method === 'api' && normalizedRow.api_variant === 'wordpress' && !genericWordPressApiSupported) {
        runtimeWarning = 'WordPress API mode requires a /wp-json/wp/v2/... endpoint';
    } else if (normalizedRow.fetch_method === 'api' && normalizedRow.api_variant === 'generic_json' && !genericJsonApiSupported) {
        runtimeWarning = 'Generic JSON API requires endpoint URL plus items_path, title_field, link_field, and date_field';
    } else if (!genericRssSupported) {
        runtimeWarning = 'Runtime has no fetcher implementation for this slug';
    }

    return {
        runtime_supported: runtimeSupported,
        runtime_expected_fetch_method:
            explicitExpectedFetchMethod
            || (genericRssSupported ? 'rss' : null)
            || (genericWordPressApiSupported ? 'api' : null)
            || (genericJsonApiSupported ? 'api' : null),
        runtime_type: runtimeType,
        runtime_warning: runtimeWarning,
    };
}

function enrichSourceRuntimeMetadata(row) {
    return {
        ...normalizeSourceApiConfig(row),
        ...getRuntimeFetchMetadata(row),
        test_ready: isSourceTestPassed(row),
        json_mapping: buildGenericJsonMapping(row),
    };
}

function getConfiguredAdminUsers() {
    return [
        { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
        { username: ADMIN_USERNAME_2, password: ADMIN_PASSWORD_2 },
    ].filter((user) => user.username && user.password);
}

function getAuthenticatedAdminCredentials(username, password) {
    return getConfiguredAdminUsers().find((user) =>
        safeEqual(username, user.username) && safeEqual(password, user.password)
    ) || null;
}

function isAuthConfigured() {
    return Boolean(getConfiguredAdminUsers().length > 0 && ADMIN_SESSION_SECRET);
}

function parseCookies(req) {
    const cookieHeader = req.headers.cookie || '';
    return cookieHeader
        .split(';')
        .map((part) => part.trim())
        .filter(Boolean)
        .reduce((accumulator, cookiePart) => {
            const separatorIndex = cookiePart.indexOf('=');
            if (separatorIndex === -1) {
                return accumulator;
            }

            const key = cookiePart.slice(0, separatorIndex).trim();
            const value = cookiePart.slice(separatorIndex + 1).trim();
            accumulator[key] = decodeURIComponent(value);
            return accumulator;
        }, {});
}

function safeEqual(left, right) {
    const leftBuffer = Buffer.from(String(left));
    const rightBuffer = Buffer.from(String(right));
    if (leftBuffer.length !== rightBuffer.length) {
        return false;
    }
    return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function cleanupExpiredSessions() {
    const now = Date.now();
    for (const [sessionId, session] of SESSION_STORE.entries()) {
        if (!session || !Number.isFinite(session.expiresAt) || session.expiresAt <= now) {
            SESSION_STORE.delete(sessionId);
        }
    }
}

function createSessionToken(username) {
    cleanupExpiredSessions();

    const sessionId = crypto.randomBytes(32).toString('hex');
    const expiresAt = Date.now() + ADMIN_SESSION_TTL_SECONDS * 1000;
    SESSION_STORE.set(sessionId, { username, expiresAt });
    return sessionId;
}

function verifySessionToken(token) {
    if (!token || !isAuthConfigured()) {
        return null;
    }

    cleanupExpiredSessions();
    const session = SESSION_STORE.get(token);
    if (!session) {
        return null;
    }

    if (!Number.isFinite(session.expiresAt) || session.expiresAt <= Date.now()) {
        SESSION_STORE.delete(token);
        return null;
    }

    return { username: session.username, expiresAt: session.expiresAt, sessionId: token };
}

function setSessionCookie(res, username) {
    const token = createSessionToken(username);
    const cookieParts = [
        `${AUTH_COOKIE_NAME}=${encodeURIComponent(token)}`,
        'Path=/',
        'HttpOnly',
        'SameSite=Lax',
        `Max-Age=${ADMIN_SESSION_TTL_SECONDS}`
    ];

    if (process.env.NODE_ENV === 'production') {
        cookieParts.push('Secure');
    }

    res.setHeader('Set-Cookie', cookieParts.join('; '));
}

function clearSessionCookie(res) {
    const cookieParts = [
        `${AUTH_COOKIE_NAME}=`,
        'Path=/',
        'HttpOnly',
        'SameSite=Lax',
        'Max-Age=0'
    ];

    if (process.env.NODE_ENV === 'production') {
        cookieParts.push('Secure');
    }

    res.setHeader('Set-Cookie', cookieParts.join('; '));
}

function getAuthenticatedUser(req) {
    const cookies = parseCookies(req);
    const token = cookies[AUTH_COOKIE_NAME];
    return verifySessionToken(token);
}

async function writeAuditLogEntry({
    username,
    action,
    targetType,
    targetId = null,
    targetName = null,
    details = null,
}) {
    try {
        const serializedDetails = details === null || details === undefined
            ? null
            : JSON.stringify(sanitizeAuditDetails(details));

        await pool.query(
            `INSERT INTO admin_audit_logs (
                username, action, target_type, target_id, target_name, details_json
            ) VALUES (?, ?, ?, ?, ?, ?)`,
            [
                username || 'unknown',
                action,
                targetType,
                targetId,
                targetName,
                serializedDetails,
            ]
        );
    } catch (error) {
        console.warn('Failed to write audit log:', error.message);
    }
}

async function writeAuditLog(req, action, targetType, options = {}) {
    return writeAuditLogEntry({
        username: req?.authenticatedUser?.username || options.username || 'unknown',
        action,
        targetType,
        targetId: options.targetId ?? null,
        targetName: options.targetName ?? null,
        details: options.details ?? null,
    });
}

function readSourceIndex() {
    try {
        const raw = fs.readFileSync(SOURCES_INDEX_FILE, 'utf8').trim();
        const parsed = Number.parseInt(raw, 10);
        return Number.isFinite(parsed) ? parsed : 0;
    } catch (error) {
        return 0;
    }
}

function tailOutput(output, lineLimit = 20) {
    return String(output || '')
        .split(/\r?\n/)
        .map((line) => line.trimEnd())
        .filter(Boolean)
        .slice(-lineLimit);
}

function runFetchNow() {
    return new Promise((resolve, reject) => {
        const startedAt = Date.now();
        const sourceIndexBefore = readSourceIndex();

        execFile(
            PYTHON_BIN,
            [FETCH_MAIN_SCRIPT],
            {
                cwd: FETCH_WORKDIR,
                env: { ...process.env },
                timeout: FETCH_TIMEOUT_MS,
                maxBuffer: 4 * 1024 * 1024,
            },
            (error, stdout, stderr) => {
                const sourceIndexAfter = readSourceIndex();
                const payload = {
                    duration_ms: Date.now() - startedAt,
                    source_index_before: sourceIndexBefore,
                    source_index_after: sourceIndexAfter,
                    output_tail: tailOutput(`${stdout || ''}\n${stderr || ''}`),
                };

                if (error) {
                    return reject({
                        ...payload,
                        error: error.message,
                        code: error.code ?? null,
                        timed_out: Boolean(error.killed),
                    });
                }

                return resolve(payload);
            }
        );
    });
}

function runSourceTest({ slug, name, fetch_method }) {
    if (!FETCH_MAIN_SCRIPT || !fs.existsSync(FETCH_MAIN_SCRIPT)) {
        return Promise.reject({
            error: `Fetcher script not found: ${FETCH_MAIN_SCRIPT || '(empty)'}`,
            script_path: FETCH_MAIN_SCRIPT,
            cwd: FETCH_WORKDIR,
            python_bin: PYTHON_BIN,
            output_tail: [],
        });
    }

    const sourceTestScript = `
import importlib.util, json, sys
script_path, slug, name, fetch_method = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("innovation_news_runtime", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fallback_fetcher = module.FETCHER_MAP.get(slug)
fetcher = module.build_runtime_fetcher(slug, name, fetch_method, fallback_fetcher)
payload = {
    "slug": slug,
    "fetch_method": fetch_method,
    "runtime_supported": bool(fetcher),
    "used_generic_rss": fetch_method == "rss",
}
if not fetcher:
    payload.update({"success": False, "error": "Runtime has no fetcher implementation for this source"})
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)
articles, fetch_error = module.safe_fetch_articles(name, fetcher)
payload.update({
    "success": fetch_error is None,
    "error": fetch_error,
    "articles_found": len(articles),
    "sample_titles": [str(article.get("title", ""))[:200] for article in articles[:5]],
})
print(json.dumps(payload, ensure_ascii=False))
`;

    return new Promise((resolve, reject) => {
        execFile(
            PYTHON_BIN,
            ['-c', sourceTestScript, FETCH_MAIN_SCRIPT, slug, name, fetch_method],
            {
                cwd: FETCH_WORKDIR,
                env: { ...process.env, DRY_RUN: '1', INNOVATION_NEWS_ALLOW_INACTIVE_SOURCE_URLS: '1' },
                timeout: SOURCE_TEST_TIMEOUT_MS,
                maxBuffer: 4 * 1024 * 1024,
            },
            (error, stdout, stderr) => {
                const outputTail = tailOutput(`${stdout || ''}\n${stderr || ''}`, 30);
                const jsonLine = [...outputTail].reverse().find((line) => line.startsWith('{') && line.endsWith('}'));

                if (!jsonLine) {
                    return reject({
                        error: 'Source test did not return structured output',
                        script_path: FETCH_MAIN_SCRIPT,
                        cwd: FETCH_WORKDIR,
                        python_bin: PYTHON_BIN,
                        output_tail: outputTail,
                        code: error?.code ?? null,
                        timed_out: Boolean(error?.killed),
                    });
                }

                try {
                    const parsed = JSON.parse(jsonLine);
                    parsed.output_tail = outputTail;
                    if (error && !parsed.success) {
                        parsed.code = error.code ?? null;
                        parsed.timed_out = Boolean(error.killed);
                    }
                    return resolve(parsed);
                } catch (parseError) {
                    return reject({
                        error: `Failed to parse source test output: ${parseError.message}`,
                        script_path: FETCH_MAIN_SCRIPT,
                        cwd: FETCH_WORKDIR,
                        python_bin: PYTHON_BIN,
                        output_tail: outputTail,
                        code: error?.code ?? null,
                        timed_out: Boolean(error?.killed),
                    });
                }
            }
        );
    });
}

// CRUD Operations

// GET all sources
app.get('/api/sources', async (req, res) => {
    try {
        const [rows] = await pool.query(
            `SELECT id, name, slug, source_url, fetch_method, api_variant,
                    json_items_path, json_title_field, json_link_field, json_date_field, json_summary_field,
                    is_active, last_fetched_at, fetch_count, success_count, error_count,
                    last_test_status, last_test_articles_found, last_test_at, last_test_error,
                    created_at, updated_at
             FROM news_sources
             ORDER BY id`
        );
        res.json({ success: true, data: rows.map(enrichSourceRuntimeMetadata) });
    } catch (error) {
        console.error('Error fetching sources:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// GET single source
app.get('/api/sources/:id', async (req, res) => {
    try {
        const [rows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [req.params.id]
        );
        if (rows.length === 0) {
            return res.status(404).json({ success: false, error: 'Source not found' });
        }
        res.json({ success: true, data: enrichSourceRuntimeMetadata(rows[0]) });
    } catch (error) {
        console.error('Error fetching source:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// CREATE new source
app.post('/api/sources', async (req, res) => {
    try {
        const payload = sanitizeSourcePayload(req.body);
        const {
            name,
            slug,
            source_url,
            fetch_method,
            api_variant,
            json_items_path,
            json_title_field,
            json_link_field,
            json_date_field,
            json_summary_field,
        } = payload;
        const storedApiVariant = fetch_method === 'api' ? api_variant : 'wordpress';
        const validationError = validateSourcePayload({ ...payload, is_active: 0 });

        if (validationError) {
            return res.status(400).json({ success: false, error: validationError });
        }

        const [result] = await pool.query(
            `INSERT INTO news_sources (
                name, slug, source_url, fetch_method, api_variant,
                json_items_path, json_title_field, json_link_field, json_date_field, json_summary_field,
                is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
            [
                name,
                slug,
                source_url,
                fetch_method,
                storedApiVariant,
                json_items_path || null,
                json_title_field || null,
                json_link_field || null,
                json_date_field || null,
                json_summary_field || null,
            ]
        );

        const [newRow] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [result.insertId]
        );

        await writeAuditLog(req, 'create', 'source', {
            targetId: result.insertId,
            targetName: name,
            details: {
                slug,
                source_url,
                fetch_method,
                api_variant,
                json_mapping: buildGenericJsonMapping(payload),
                is_active: 0,
                activation_required: true,
            }
        });
        res.json({ success: true, data: enrichSourceRuntimeMetadata(newRow[0]) });
    } catch (error) {
        console.error('Error creating source:', error);
        if (error && error.code === 'ER_DUP_ENTRY') {
            return res.status(409).json({ success: false, error: 'Source name or slug already exists' });
        }
        res.status(500).json({ success: false, error: error.message });
    }
});

// UPDATE source
app.put('/api/sources/:id', async (req, res) => {
    try {
        const payload = sanitizeSourcePayload(req.body);
        const {
            name,
            slug,
            source_url,
            fetch_method,
            api_variant,
            json_items_path,
            json_title_field,
            json_link_field,
            json_date_field,
            json_summary_field,
        } = payload;
        const storedApiVariant = fetch_method === 'api' ? api_variant : 'wordpress';
        const id = req.params.id;
        const [existingRows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );
        if (existingRows.length === 0) {
            return res.status(404).json({ success: false, error: 'Source not found' });
        }

        const existingSource = normalizeSourceApiConfig(existingRows[0]);
        const configChanged =
            existingSource.slug !== slug
            || existingSource.source_url !== source_url
            || existingSource.fetch_method !== fetch_method
            || existingSource.api_variant !== api_variant
            || existingSource.json_items_path !== json_items_path
            || existingSource.json_title_field !== json_title_field
            || existingSource.json_link_field !== json_link_field
            || existingSource.json_date_field !== json_date_field
            || existingSource.json_summary_field !== json_summary_field;
        const effectiveIsActive = configChanged ? 0 : (payload.is_active ?? 0);
        const validationError = validateSourcePayload({
            ...payload,
            is_active: effectiveIsActive,
        });

        if (validationError) {
            return res.status(400).json({ success: false, error: validationError });
        }

        if (!configChanged && effectiveIsActive === 1 && !isSourceTestPassed(existingSource)) {
            return res.status(400).json({
                success: false,
                error: 'This source cannot be activated yet because it has not passed the latest source test'
            });
        }

        const [result] = await pool.query(
            `UPDATE news_sources
             SET name = ?,
                 slug = ?,
                 source_url = ?,
                 fetch_method = ?,
                 api_variant = ?,
                 json_items_path = ?,
                 json_title_field = ?,
                 json_link_field = ?,
                 json_date_field = ?,
                 json_summary_field = ?,
                 is_active = ?,
                 last_test_status = ?,
                 last_test_articles_found = ?,
                 last_test_at = ?,
                 last_test_error = ?,
                 updated_at = CURRENT_TIMESTAMP
             WHERE id = ?`,
            [
                name,
                slug,
                source_url,
                fetch_method,
                storedApiVariant,
                json_items_path || null,
                json_title_field || null,
                json_link_field || null,
                json_date_field || null,
                json_summary_field || null,
                effectiveIsActive,
                configChanged ? 'pending' : existingSource.last_test_status,
                configChanged ? null : existingSource.last_test_articles_found,
                configChanged ? null : existingSource.last_test_at,
                configChanged ? null : existingSource.last_test_error,
                id,
            ]
        );

        const [updatedRow] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );

        await writeAuditLog(req, 'update', 'source', {
            targetId: Number(id),
            targetName: name,
            details: {
                before: {
                    name: existingSource.name,
                    slug: existingSource.slug,
                    source_url: existingSource.source_url,
                    fetch_method: existingSource.fetch_method,
                    api_variant: existingSource.api_variant,
                    json_mapping: buildGenericJsonMapping(existingSource),
                    is_active: existingSource.is_active,
                },
                after: {
                    name,
                    slug,
                    source_url,
                    fetch_method,
                    api_variant,
                    json_mapping: buildGenericJsonMapping(payload),
                    is_active: effectiveIsActive,
                    config_changed: configChanged,
                }
            }
        });
        res.json({
            success: true,
            data: enrichSourceRuntimeMetadata(updatedRow[0]),
            message: configChanged
                ? 'Source configuration changed and was set to Inactive until it passes a new test'
                : null,
        });
    } catch (error) {
        console.error('Error updating source:', error);
        if (error && error.code === 'ER_DUP_ENTRY') {
            return res.status(409).json({ success: false, error: 'Source name or slug already exists' });
        }
        res.status(500).json({ success: false, error: error.message });
    }
});

// DELETE source
app.delete('/api/sources/:id', async (req, res) => {
    try {
        const sourceId = req.params.id;
        const [existingRows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [sourceId]
        );
        if (existingRows.length === 0) {
            return res.status(404).json({ success: false, error: 'Source not found' });
        }

        const existingSource = existingRows[0];
        const [[articleUsage]] = await pool.query(
            'SELECT COUNT(*) AS total FROM innovation_news WHERE source_id = ?',
            [sourceId]
        );
        const [[logUsage]] = await pool.query(
            'SELECT COUNT(*) AS total FROM fetch_logs WHERE source_id = ?',
            [sourceId]
        );

        if (articleUsage.total > 0 || logUsage.total > 0) {
            return res.status(409).json({
                success: false,
                error: 'Source cannot be deleted because related articles or fetch logs still exist'
            });
        }

        const [result] = await pool.query(
            'DELETE FROM news_sources WHERE id = ?',
            [sourceId]
        );

        await writeAuditLog(req, 'delete', 'source', {
            targetId: Number(sourceId),
            targetName: existingSource.name,
            details: {
                slug: existingSource.slug,
                source_url: existingSource.source_url,
                fetch_method: existingSource.fetch_method,
                api_variant: existingSource.api_variant,
                json_mapping: buildGenericJsonMapping(existingSource),
                is_active: existingSource.is_active,
            }
        });
        res.json({ success: true, message: 'Source deleted successfully' });
    } catch (error) {
        console.error('Error deleting source:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Toggle active status
app.patch('/api/sources/:id/toggle', async (req, res) => {
    try {
        const id = req.params.id;
        const [existingRows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );
        if (existingRows.length === 0) {
            return res.status(404).json({ success: false, error: 'Source not found' });
        }

        const existingSource = existingRows[0];
        const turningActive = !Boolean(existingSource.is_active);
        const runtimeMetadata = getRuntimeFetchMetadata(existingSource);

        if (turningActive && !runtimeMetadata.runtime_supported) {
            return res.status(400).json({
                success: false,
                error: 'This source cannot be activated yet because the runtime does not support its slug/fetch_method combination'
            });
        }

        if (turningActive && !isSourceTestPassed(existingSource)) {
            return res.status(400).json({
                success: false,
                error: 'This source cannot be activated yet because it has not passed the latest source test'
            });
        }

        const [result] = await pool.query(
            'UPDATE news_sources SET is_active = NOT is_active, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            [id]
        );

        const [updatedRow] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );

        await writeAuditLog(req, 'toggle', 'source', {
            targetId: Number(id),
            targetName: existingSource.name,
            details: {
                before_is_active: existingSource.is_active,
                after_is_active: updatedRow[0]?.is_active ?? existingSource.is_active,
            }
        });
        res.json({ success: true, data: enrichSourceRuntimeMetadata(updatedRow[0]) });
    } catch (error) {
        console.error('Error toggling source:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/api/sources/:id/test', async (req, res) => {
    try {
        const id = req.params.id;
        const [rows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );

        if (rows.length === 0) {
            return res.status(404).json({ success: false, error: 'Source not found' });
        }

        const source = rows[0];
        const startedAt = Date.now();
        const testResult = await runSourceTest(source);
        const durationMs = Date.now() - startedAt;
        const articlesFound = Number(testResult.articles_found || 0);
        const passed = Boolean(testResult.success) && articlesFound > 0;
        const effectiveError = passed
            ? null
            : (testResult.error || (articlesFound === 0 ? 'No eligible articles found during source test' : 'Source test failed'));

        await pool.query(
            `UPDATE news_sources
             SET last_test_status = ?,
                 last_test_articles_found = ?,
                 last_test_at = NOW(),
                 last_test_error = ?
             WHERE id = ?`,
            [passed ? 'passed' : 'failed', articlesFound, effectiveError, id]
        );

        await writeAuditLog(req, passed ? 'test' : 'test_failed', 'source', {
            targetId: Number(id),
            targetName: source.name,
            details: {
                slug: source.slug,
                fetch_method: source.fetch_method,
                api_variant: normalizeSourceApiConfig(source).api_variant,
                json_mapping: buildGenericJsonMapping(source),
                articles_found: articlesFound,
                success: passed,
                error: effectiveError,
                duration_ms: durationMs,
            }
        });

        const [updatedRows] = await pool.query(
            'SELECT * FROM news_sources WHERE id = ?',
            [id]
        );

        res.json({
            success: true,
            data: {
                ...testResult,
                passed,
                error: effectiveError,
                duration_ms: durationMs,
                source: enrichSourceRuntimeMetadata(updatedRows[0] || source),
            }
        });
    } catch (error) {
        console.error('Error testing source:', error);
        await writeAuditLog(req, 'test_failed', 'source', {
            targetId: Number(req.params.id),
            targetName: null,
            details: {
                success: false,
                error: error.error || error.message || 'Unknown source test error',
                output_tail: error.output_tail || [],
                script_path: error.script_path || FETCH_MAIN_SCRIPT,
                cwd: error.cwd || FETCH_WORKDIR,
                python_bin: error.python_bin || PYTHON_BIN,
                code: error.code ?? null,
                timed_out: Boolean(error.timed_out),
            }
        });
        res.status(500).json({
            success: false,
            error: error.error || error.message || 'Source test failed',
            data: {
                output_tail: error.output_tail || [],
                script_path: error.script_path || FETCH_MAIN_SCRIPT,
                cwd: error.cwd || FETCH_WORKDIR,
                python_bin: error.python_bin || PYTHON_BIN,
                code: error.code ?? null,
                timed_out: Boolean(error.timed_out),
            }
        });
    }
});

// Health check
app.get('/api/health', async (req, res) => {
    try {
        await pool.query('SELECT 1');
        res.json({ status: 'ok', database: 'ok', timestamp: new Date().toISOString() });
    } catch (error) {
        console.error('Health check failed:', error);
        res.status(500).json({
            status: 'error',
            database: 'unreachable',
            timestamp: new Date().toISOString(),
        });
    }
});

app.post('/api/fetch/run-now', async (req, res) => {
    if (manualFetchRun) {
        return res.status(409).json({
            success: false,
            code: 'FETCH_ALREADY_RUNNING',
            error: 'A manual fetch run is already in progress'
        });
    }

    // Reserve the in-process slot before the first await. The database query
    // must succeed before spawning Python, otherwise no untracked child remains.
    manualFetchRun = (async () => {
        const [sourceRows] = await pool.query(
            'SELECT COUNT(*) AS total FROM news_sources WHERE is_active = 1'
        );
        const result = await runFetchNow();
        return {
            ...result,
            active_source_count: sourceRows[0]?.total || 0,
        };
    })();

    try {
        const result = await manualFetchRun;
        await writeAuditLog(req, 'run_now', 'fetch', {
            targetName: 'manual-fetch',
            details: {
                duration_ms: result.duration_ms,
                source_index_before: result.source_index_before,
                source_index_after: result.source_index_after,
                active_source_count: result.active_source_count,
                output_tail: result.output_tail,
            }
        });

        res.json({
            success: true,
            data: {
                ...result,
                active_source_count: result.active_source_count,
                dry_run: String(process.env.DRY_RUN || '').trim().toLowerCase() === '1',
            }
        });
    } catch (error) {
        const fetchAlreadyRunning = Number(error.code) === 75;
        console.error('Manual fetch failed:', error);
        await writeAuditLog(req, fetchAlreadyRunning ? 'run_now_skipped' : 'run_now_failed', 'fetch', {
            targetName: 'manual-fetch',
            details: {
                duration_ms: error.duration_ms || null,
                source_index_before: error.source_index_before ?? null,
                source_index_after: error.source_index_after ?? null,
                output_tail: error.output_tail || [],
                code: error.code ?? null,
                timed_out: Boolean(error.timed_out),
                error: error.error || 'Manual fetch failed',
            }
        });
        res.status(fetchAlreadyRunning ? 409 : 500).json({
            success: false,
            code: fetchAlreadyRunning ? 'FETCH_ALREADY_RUNNING' : 'FETCH_FAILED',
            error: fetchAlreadyRunning
                ? 'Another fetch run is already in progress'
                : (error.error || 'Manual fetch failed'),
            data: {
                duration_ms: error.duration_ms || null,
                source_index_before: error.source_index_before ?? null,
                source_index_after: error.source_index_after ?? null,
                output_tail: error.output_tail || [],
                code: error.code ?? null,
                timed_out: Boolean(error.timed_out),
            }
        });
    } finally {
        manualFetchRun = null;
    }
});

app.get('/api/audit-logs', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit || '100', 10), 500);
        const [rows] = await pool.query(
            `SELECT id, username, action, target_type, target_id, target_name, details_json, created_at
             FROM admin_audit_logs
             ORDER BY created_at DESC
             LIMIT ?`,
            [limit]
        );

        res.json({
            success: true,
            data: rows.map((row) => ({
                ...row,
                details: row.details_json ? JSON.parse(row.details_json) : null,
            })),
        });
    } catch (error) {
        console.error('Error fetching audit logs:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Fetch Logs CRUD

// GET all fetch logs
app.get('/api/logs', async (req, res) => {
    try {
        const [rows] = await pool.query(`
            SELECT 
                fl.id,
                fl.source_id,
                ns.name as source_name,
                ns.slug as source_slug,
                fl.articles_found,
                fl.mysql_status,
                fl.new_articles,
                fl.articles_sent,
                fl.telegram_status,
                fl.wordpress_status,
                fl.line_status,
                fl.status,
                fl.error_message,
                fl.duration_ms,
                fl.created_at
            FROM fetch_logs fl
            LEFT JOIN news_sources ns ON fl.source_id = ns.id
            ORDER BY fl.created_at DESC
            LIMIT 100
        `);
        res.json({ success: true, data: rows });
    } catch (error) {
        console.error('Error fetching logs:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// GET logs by source_id
app.get('/api/logs/source/:source_id', async (req, res) => {
    try {
        const sourceId = req.params.source_id;
        const [rows] = await pool.query(`
            SELECT 
                fl.id,
                fl.source_id,
                ns.name as source_name,
                ns.slug as source_slug,
                fl.articles_found,
                fl.mysql_status,
                fl.new_articles,
                fl.articles_sent,
                fl.telegram_status,
                fl.wordpress_status,
                fl.line_status,
                fl.status,
                fl.error_message,
                fl.duration_ms,
                fl.created_at
            FROM fetch_logs fl
            LEFT JOIN news_sources ns ON fl.source_id = ns.id
            WHERE fl.source_id = ?
            ORDER BY fl.created_at DESC
            LIMIT 50
        `, [sourceId]);
        res.json({ success: true, data: rows });
    } catch (error) {
        console.error('Error fetching logs by source:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// GET all articles with pagination
app.get('/api/articles', async (req, res) => {
    try {
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 20;
        const search = req.query.search || '';
        const source_id = req.query.source_id || '';
        const line_status = req.query.line_status || '';

        const offset = (page - 1) * limit;

        // Build WHERE clause
        let whereConditions = [];
        let queryParams = [];

        if (search) {
            whereConditions.push('(a.title LIKE ? OR a.summary LIKE ?)');
            queryParams.push(`%${search}%`, `%${search}%`);
        }

        if (source_id) {
            whereConditions.push('a.source_id = ?');
            queryParams.push(parseInt(source_id));
        }

        if (line_status === 'sent') {
            whereConditions.push("a.line_status = 'sent'");
        } else if (line_status === 'not_sent') {
            whereConditions.push("a.line_status <> 'sent'");
        } else if (line_status) {
            whereConditions.push('a.line_status = ?');
            queryParams.push(line_status);
        }

        const whereClause = whereConditions.length > 0
            ? 'WHERE ' + whereConditions.join(' AND ')
            : '';

        // Get total count
        const [countResult] = await pool.query(`
            SELECT COUNT(*) as total
            FROM innovation_news a
            LEFT JOIN news_sources ns ON a.source_id = ns.id
            ${whereClause}
        `, queryParams);

        const total = countResult[0].total;
        const totalPages = Math.ceil(total / limit);

        // Get paginated data
        const [rows] = await pool.query(`
            SELECT
                a.id,
                a.source_id,
                ns.name as source_name,
                ns.slug as source_slug,
                a.title,
                a.summary,
                a.link,
                a.date_published,
                a.content_hash,
                a.telegram_status,
                a.wordpress_status,
                a.line_status,
                a.date_sent,
                a.created_at
            FROM innovation_news a
            LEFT JOIN news_sources ns ON a.source_id = ns.id
            ${whereClause}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
        `, [...queryParams, limit, offset]);

        res.json({
            success: true,
            data: rows,
            pagination: {
                total,
                page,
                limit,
                totalPages,
                hasPrevPage: page > 1,
                hasNextPage: page < totalPages
            }
        });
    } catch (error) {
        console.error('Error fetching articles:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

function getSourceHealthStatus(source) {
    if (!source.is_active) {
        return 'inactive';
    }

    if (source.last_test_status && source.last_test_status !== 'passed') {
        return 'needs_test';
    }

    if (source.last_fetch_status === 'failed' || source.last_fetch_status === 'error') {
        return 'error';
    }

    if (source.last_fetch_status === 'partial') {
        return 'warning';
    }

    if (!source.last_fetched_at && !source.last_log_at) {
        return 'no_fetch_yet';
    }

    return 'ok';
}

// GET dashboard overview (read-only)
app.get('/api/dashboard/overview', async (req, res) => {
    try {
        const [articleRows] = await pool.query(`
            SELECT
                COUNT(*) AS total_articles,
                SUM(CASE WHEN DATE(created_at) = CURDATE() THEN 1 ELSE 0 END) AS articles_today,
                SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS articles_last_7_days,
                SUM(CASE WHEN line_status = 'sent' THEN 1 ELSE 0 END) AS line_sent_total,
                SUM(CASE WHEN telegram_status = 'sent' THEN 1 ELSE 0 END) AS telegram_sent_total,
                SUM(CASE WHEN wordpress_status IN ('created', 'duplicate') THEN 1 ELSE 0 END) AS wordpress_success_total
            FROM innovation_news
        `);

        const [sourceRows] = await pool.query(`
            SELECT
                COUNT(*) AS total_sources,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_sources,
                SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_sources
            FROM news_sources
        `);

        const [fetchRows] = await pool.query(`
            SELECT
                COUNT(*) AS total_fetches_24h,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_fetches_24h,
                SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) AS partial_fetches_24h,
                SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) AS failed_fetches_24h,
                AVG(duration_ms) AS avg_duration_ms_24h
            FROM fetch_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        `);

        const [healthRows] = await pool.query(`
            SELECT
                ns.id,
                ns.name,
                ns.slug,
                ns.fetch_method,
                ns.api_variant,
                ns.is_active,
                ns.fetch_count,
                ns.success_count,
                ns.error_count,
                ns.last_fetched_at,
                ns.last_test_status,
                ns.last_test_articles_found,
                ns.last_test_at,
                COALESCE(article_stats.total_articles, 0) AS total_articles,
                COALESCE(article_stats.articles_last_7_days, 0) AS articles_last_7_days,
                article_stats.last_article_at,
                COALESCE(log_stats.fetches_last_7_days, 0) AS fetches_last_7_days,
                COALESCE(log_stats.success_fetches_last_7_days, 0) AS success_fetches_last_7_days,
                log_stats.last_log_at,
                latest_log.status AS last_fetch_status,
                latest_log.error_message AS last_error_message
            FROM news_sources ns
            LEFT JOIN (
                SELECT
                    source_id,
                    COUNT(*) AS total_articles,
                    SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS articles_last_7_days,
                    MAX(created_at) AS last_article_at
                FROM innovation_news
                GROUP BY source_id
            ) article_stats ON article_stats.source_id = ns.id
            LEFT JOIN (
                SELECT
                    source_id,
                    COUNT(*) AS fetches_last_7_days,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_fetches_last_7_days,
                    MAX(created_at) AS last_log_at
                FROM fetch_logs
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY source_id
            ) log_stats ON log_stats.source_id = ns.id
            LEFT JOIN (
                SELECT
                    fl.source_id,
                    fl.status,
                    fl.error_message
                FROM fetch_logs fl
                INNER JOIN (
                    SELECT source_id, MAX(id) AS latest_log_id
                    FROM fetch_logs
                    WHERE source_id IS NOT NULL
                    GROUP BY source_id
                ) latest ON latest.latest_log_id = fl.id
            ) latest_log ON latest_log.source_id = ns.id
            ORDER BY ns.id ASC
        `);

        const sourceHealth = healthRows.map((source) => {
            const fetches7d = Number(source.fetches_last_7_days) || 0;
            const success7d = Number(source.success_fetches_last_7_days) || 0;
            const successRate7d = fetches7d > 0 ? Math.round((success7d * 10000) / fetches7d) / 100 : null;

            return {
                ...source,
                health_status: getSourceHealthStatus(source),
                success_rate_all_time: Number(source.fetch_count) > 0
                    ? Math.round((Number(source.success_count) * 10000) / Number(source.fetch_count)) / 100
                    : null,
                success_rate_last_7_days: successRate7d,
            };
        });

        const [issueRows] = await pool.query(`
            SELECT
                fl.id,
                fl.source_id,
                ns.name AS source_name,
                ns.slug AS source_slug,
                fl.status,
                fl.mysql_status,
                fl.telegram_status,
                fl.wordpress_status,
                fl.line_status,
                fl.error_message,
                fl.duration_ms,
                fl.created_at
            FROM fetch_logs fl
            LEFT JOIN news_sources ns ON fl.source_id = ns.id
            WHERE fl.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                AND (
                    fl.status <> 'success'
                    OR fl.mysql_status = 'failed'
                    OR fl.telegram_status = 'failed'
                    OR fl.wordpress_status = 'failed'
                    OR fl.line_status = 'failed'
                )
            ORDER BY fl.created_at DESC
            LIMIT 10
        `);

        const [articleTrendRows] = await pool.query(`
            SELECT
                DATE(created_at) AS metric_date,
                COUNT(*) AS total_articles,
                SUM(CASE WHEN line_status = 'sent' THEN 1 ELSE 0 END) AS line_sent
            FROM innovation_news
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(created_at)
            ORDER BY metric_date ASC
        `);

        const [fetchTrendRows] = await pool.query(`
            SELECT
                DATE(created_at) AS metric_date,
                COUNT(*) AS total_fetches,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_fetches,
                SUM(CASE WHEN status IN ('partial', 'failed', 'error') THEN 1 ELSE 0 END) AS attention_fetches
            FROM fetch_logs
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
            GROUP BY DATE(created_at)
            ORDER BY metric_date ASC
        `);

        const articles = articleRows[0] || {};
        const sources = sourceRows[0] || {};
        const fetches = fetchRows[0] || {};
        const totalFetches24h = Number(fetches.total_fetches_24h) || 0;
        const successFetches24h = Number(fetches.success_fetches_24h) || 0;
        const actionableAlerts = [];

        sourceHealth
            .filter((source) => source.is_active && ['needs_test', 'error', 'warning', 'no_fetch_yet'].includes(source.health_status))
            .slice(0, 6)
            .forEach((source) => {
                actionableAlerts.push({
                    severity: source.health_status === 'error' ? 'error' : 'warning',
                    title: `${source.name || source.slug || 'Source'} ควรตรวจสอบ`,
                    detail: source.last_error_message || `สถานะ health ล่าสุดคือ ${source.health_status}`,
                    source_id: source.id,
                    source_slug: source.slug,
                    created_at: source.last_log_at || source.last_test_at || source.last_fetched_at,
                });
            });

        sourceHealth
            .filter((source) => source.is_active && !source.last_article_at && source.health_status === 'ok')
            .slice(0, 3)
            .forEach((source) => {
                actionableAlerts.push({
                    severity: 'info',
                    title: `${source.name || source.slug || 'Source'} ยังไม่มีบทความ`,
                    detail: 'source active แล้ว แต่ยังไม่พบบทความที่ถูกบันทึกในระบบ',
                    source_id: source.id,
                    source_slug: source.slug,
                    created_at: source.last_log_at || source.last_fetched_at,
                });
            });

        issueRows.slice(0, 3).forEach((issue) => {
            actionableAlerts.push({
                severity: issue.status === 'failed' || issue.status === 'error' ? 'error' : 'warning',
                title: `${issue.source_name || 'System'} มี issue ล่าสุด`,
                detail: issue.error_message || `fetch status: ${issue.status || '-'}`,
                source_id: issue.source_id,
                source_slug: issue.source_slug,
                created_at: issue.created_at,
            });
        });

        const sortedActionableAlerts = actionableAlerts
            .sort((a, b) => {
                const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
                const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
                return timeB - timeA;
            })
            .slice(0, 8);

        res.json({
            success: true,
            data: {
                generated_at: new Date().toISOString(),
                kpis: {
                    total_articles: Number(articles.total_articles) || 0,
                    articles_today: Number(articles.articles_today) || 0,
                    articles_last_7_days: Number(articles.articles_last_7_days) || 0,
                    line_sent_total: Number(articles.line_sent_total) || 0,
                    telegram_sent_total: Number(articles.telegram_sent_total) || 0,
                    wordpress_success_total: Number(articles.wordpress_success_total) || 0,
                    total_sources: Number(sources.total_sources) || 0,
                    active_sources: Number(sources.active_sources) || 0,
                    inactive_sources: Number(sources.inactive_sources) || 0,
                    sources_need_attention: sourceHealth.filter((source) =>
                        ['needs_test', 'error', 'warning', 'no_fetch_yet'].includes(source.health_status)
                    ).length,
                    total_fetches_24h: totalFetches24h,
                    success_rate_24h: totalFetches24h > 0
                        ? Math.round((successFetches24h * 10000) / totalFetches24h) / 100
                        : null,
                    avg_duration_ms_24h: fetches.avg_duration_ms_24h ? Math.round(Number(fetches.avg_duration_ms_24h)) : null,
                },
                fetch_24h: {
                    total: totalFetches24h,
                    success: successFetches24h,
                    partial: Number(fetches.partial_fetches_24h) || 0,
                    failed: Number(fetches.failed_fetches_24h) || 0,
                },
                source_health: sourceHealth,
                recent_issues: issueRows,
                trends: {
                    articles_daily: articleTrendRows,
                    fetch_daily: fetchTrendRows,
                },
                actionable_alerts: sortedActionableAlerts,
            },
        });
    } catch (error) {
        console.error('Error fetching dashboard overview:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

async function handleDashboardStats(req, res) {
    try {
        // Overall stats
        const [overallStats] = await pool.query(`
            SELECT 
                COUNT(*) as total_articles,
                SUM(CASE WHEN line_status = 'sent' THEN 1 ELSE 0 END) as total_sent,
                SUM(CASE WHEN created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as articles_last_7_days,
                SUM(CASE WHEN created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as articles_last_30_days
            FROM innovation_news
        `);

        // Stats by source
        const [sourceStats] = await pool.query(`
            SELECT 
                ns.id as source_id,
                ns.name as source_name,
                ns.slug as source_slug,
                COUNT(a.id) as article_count,
                SUM(CASE WHEN a.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as articles_last_7_days,
                SUM(CASE WHEN a.line_status = 'sent' THEN 1 ELSE 0 END) as sent_count,
                MAX(a.created_at) as last_article_at
            FROM news_sources ns
            LEFT JOIN innovation_news a ON ns.id = a.source_id
            WHERE ns.is_active = 1
            GROUP BY ns.id, ns.name, ns.slug
            ORDER BY article_count DESC
        `);

        // Fetch logs stats
        const [fetchStats] = await pool.query(`
            SELECT 
                COUNT(*) as total_fetches,
                SUM(CASE WHEN created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as fetches_last_7_days,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END) as partial_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
                AVG(CASE WHEN status IN ('success', 'partial') THEN duration_ms ELSE NULL END) as avg_duration_ms
            FROM fetch_logs
        `);

        // Latest logs (last 10)
        const [recentLogs] = await pool.query(`
            SELECT 
                fl.id,
                fl.source_id,
                ns.name as source_name,
                fl.articles_found,
                fl.mysql_status,
                fl.new_articles,
                fl.articles_sent,
                fl.telegram_status,
                fl.wordpress_status,
                fl.line_status,
                fl.status,
                fl.duration_ms,
                fl.created_at
            FROM fetch_logs fl
            LEFT JOIN news_sources ns ON fl.source_id = ns.id
            ORDER BY fl.created_at DESC
            LIMIT 10
        `);

        res.json({
            success: true,
            data: {
                overall: overallStats[0],
                by_source: sourceStats,
                fetch_stats: fetchStats[0],
                recent_logs: recentLogs
            }
        });
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
        res.status(500).json({ success: false, error: error.message });
    }
}

// GET statistics dashboard
app.get('/api/stats/dashboard', handleDashboardStats);
app.get('/api/dashboard/stats', handleDashboardStats);

// GET single log
app.get('/api/logs/:id', async (req, res) => {
    try {
        const [rows] = await pool.query(`
            SELECT 
                fl.id,
                fl.source_id,
                ns.name as source_name,
                ns.slug as source_slug,
                fl.articles_found,
                fl.mysql_status,
                fl.new_articles,
                fl.articles_sent,
                fl.telegram_status,
                fl.wordpress_status,
                fl.line_status,
                fl.status,
                fl.error_message,
                fl.duration_ms,
                fl.created_at
            FROM fetch_logs fl
            LEFT JOIN news_sources ns ON fl.source_id = ns.id
            WHERE fl.id = ?
        `, [req.params.id]);
        if (rows.length === 0) {
            return res.status(404).json({ success: false, error: 'Log not found' });
        }
        res.json({ success: true, data: rows[0] });
    } catch (error) {
        console.error('Error fetching log:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.listen(port, bindHost, () => {
    console.log(`========================================`);
    console.log(`🚀 Innovation News Admin Server`);
    console.log(`========================================`);
    console.log(`Server listening on: ${bindHost}:${port}`);
    if (bindHost === '0.0.0.0' || bindHost === '::') {
        console.warn('Admin API is listening on all interfaces; use a firewall and HTTPS reverse proxy.');
    }
    console.log(`========================================`);
});
