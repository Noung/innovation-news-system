#!/bin/sh

# Install exactly one managed Innovation News scheduler entry while preserving
# every unrelated crontab line. Dry-run is the default; pass --apply to install.

set -eu
umask 077

MODE="dry-run"
case "${1:-}" in
    "") ;;
    --dry-run) MODE="dry-run" ;;
    --apply) MODE="apply" ;;
    *)
        echo "Usage: $0 [--dry-run|--apply]" >&2
        exit 64
        ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE_DIR=${INNOVATION_NEWS_WORKSPACE_DIR:-$(dirname -- "$SCRIPT_DIR")}
SCHEDULE=${INNOVATION_NEWS_CRON_SCHEDULE:-"0 9 * * *"}
WRAPPER="$WORKSPACE_DIR/scripts/run-fetch-innovation-news.sh"
DIRECT_FETCHER="$WORKSPACE_DIR/scripts/fetch-innovation-news-mysql.py"
BEGIN_MARKER="# BEGIN INNOVATION-NEWS MANAGED"
END_MARKER="# END INNOVATION-NEWS MANAGED"

schedule_line_count=$(printf '%s\n' "$SCHEDULE" | awk 'END { print NR }')
schedule_field_count=$(printf '%s\n' "$SCHEDULE" | awk 'NR == 1 { print NF }')
if [ "$schedule_line_count" -ne 1 ] || [ "$schedule_field_count" -ne 5 ]; then
    echo "ERROR: INNOVATION_NEWS_CRON_SCHEDULE must contain exactly five cron fields" >&2
    exit 64
fi

if ! command -v crontab >/dev/null 2>&1; then
    echo "ERROR: crontab command is not available" >&2
    exit 69
fi
if [ ! -x "$WRAPPER" ]; then
    echo "ERROR: fetch wrapper is missing or not executable: $WRAPPER" >&2
    exit 66
fi

CURRENT_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.current.XXXXXX")
FILTERED_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.filtered.XXXXXX")
CANDIDATE_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.candidate.XXXXXX")
RECHECK_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.recheck.XXXXXX")
VERIFY_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.verify.XXXXXX")
ERROR_FILE=$(mktemp "${TMPDIR:-/tmp}/innovation-news-cron.error.XXXXXX")
cleanup() {
    rm -f -- \
        "$CURRENT_FILE" "$FILTERED_FILE" "$CANDIDATE_FILE" \
        "$RECHECK_FILE" "$VERIFY_FILE" "$ERROR_FILE"
}
trap cleanup EXIT HUP INT TERM

read_crontab() {
    output_file=$1
    if crontab -l >"$output_file" 2>"$ERROR_FILE"; then
        return 0
    fi

    # Vixie cron/Cronie report an absent first crontab with this phrase. Any
    # other failure is treated as an access/read error and must fail closed.
    if grep -Eiq 'no crontab([[:space:]]+for)?' "$ERROR_FILE"; then
        : >"$output_file"
        return 0
    fi

    echo "ERROR: existing crontab could not be read; no changes were made" >&2
    return 1
}

read_crontab "$CURRENT_FILE"

# Reject malformed or multiple managed blocks. Silently consuming an unmatched
# BEGIN marker could otherwise remove every unrelated job below it.
if ! awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin {
        if (inside || blocks > 0) bad = 1
        inside = 1
        blocks++
        next
    }
    $0 == end {
        if (!inside) bad = 1
        inside = 0
        next
    }
    END {
        if (inside) bad = 1
        exit bad ? 1 : 0
    }
' "$CURRENT_FILE"; then
    echo "ERROR: malformed or duplicate Innovation News managed markers" >&2
    exit 65
fi

# Remove one validated managed block plus only exact legacy command shapes.
# Substring matches are deliberately avoided so unrelated jobs mentioning a
# path in an argument or log message remain untouched.
awk \
    -v begin="$BEGIN_MARKER" \
    -v end="$END_MARKER" \
    -v direct="$DIRECT_FETCHER" \
    -v wrapper="$WRAPPER" '
        $0 == begin { managed = 1; next }
        $0 == end { managed = 0; next }
        managed { next }
        /^[[:space:]]*#/ { print; next }
        $6 == wrapper { next }
        ($6 == "/usr/bin/python3" || $6 == "python3") && $7 == direct { next }
        { print }
    ' "$CURRENT_FILE" >"$FILTERED_FILE"

# Normalize trailing blank lines only. This makes repeated dry-run/apply calls
# byte-for-byte idempotent while preserving internal layout and all other jobs.
awk '
    { lines[NR] = $0 }
    END {
        last = NR
        while (last > 0 && lines[last] ~ /^[[:space:]]*$/) last--
        for (line = 1; line <= last; line++) print lines[line]
    }
' "$FILTERED_FILE" >"$CANDIDATE_FILE"

if [ -s "$CANDIDATE_FILE" ]; then
    printf '\n' >>"$CANDIDATE_FILE"
fi
printf '%s\n%s %s\n%s\n' \
    "$BEGIN_MARKER" \
    "$SCHEDULE" \
    "$WRAPPER" \
    "$END_MARKER" >>"$CANDIDATE_FILE"

# Unknown command shapes are not deleted automatically. Abort and require an
# operator to review them, otherwise a second scheduler could remain active.
if ! awk -v direct="$DIRECT_FETCHER" -v wrapper="$WRAPPER" '
    /^[[:space:]]*#/ { next }
    index($0, direct) { exit 1 }
    index($0, wrapper) && $6 != wrapper { exit 1 }
    END { if (NR == 0) exit 0 }
' "$CANDIDATE_FILE"; then
    echo "ERROR: an unrecognized active cron line still references the Innovation News fetcher" >&2
    exit 65
fi

active_count=$(awk -v wrapper="$WRAPPER" '
    /^[[:space:]]*#/ { next }
    $6 == wrapper { count++ }
    END { print count + 0 }
' "$CANDIDATE_FILE")
if [ "$active_count" -ne 1 ]; then
    echo "ERROR: candidate crontab does not contain exactly one managed fetch entry" >&2
    exit 65
fi

if cmp -s "$CURRENT_FILE" "$CANDIDATE_FILE"; then
    echo "Innovation News cron is already canonical (one OS-cron owner)."
    exit 0
fi

if [ "$MODE" = "dry-run" ]; then
    current_active_count=$(awk '/^[[:space:]]*#/ { next } NF { count++ } END { print count + 0 }' "$CURRENT_FILE")
    candidate_active_count=$(awk '/^[[:space:]]*#/ { next } NF { count++ } END { print count + 0 }' "$CANDIDATE_FILE")
    echo "DRY RUN: no crontab changes were made."
    echo "Current active entries: $current_active_count"
    echo "Proposed active entries: $candidate_active_count"
    echo "Managed Innovation News schedule: $SCHEDULE"
    echo "Current checksum: $(cksum <"$CURRENT_FILE" | awk '{ print $1 ":" $2 }')"
    echo "Proposed checksum: $(cksum <"$CANDIDATE_FILE" | awk '{ print $1 ":" $2 }')"
    echo "Existing command lines are intentionally not printed because they can contain credentials."
    echo "Run again with --apply only after reviewing this summary and the scheduler ownership policy."
    exit 0
fi

# Re-read immediately before install and abort if another operator/process has
# changed the crontab since this plan was built.
read_crontab "$RECHECK_FILE"
if ! cmp -s "$CURRENT_FILE" "$RECHECK_FILE"; then
    echo "ERROR: crontab changed during planning; rerun --dry-run" >&2
    exit 75
fi

BACKUP_DIR="$WORKSPACE_DIR/backups/crontab"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/crontab-before-innovation-news-$(date +%Y%m%d-%H%M%S)-$$.txt"
cp "$CURRENT_FILE" "$BACKUP_FILE"
crontab "$CANDIDATE_FILE"

read_crontab "$VERIFY_FILE"
if ! cmp -s "$CANDIDATE_FILE" "$VERIFY_FILE"; then
    echo "ERROR: installed crontab did not verify byte-for-byte" >&2
    exit 74
fi

echo "Installed one managed Innovation News cron entry."
echo "Previous crontab backup: $BACKUP_FILE"
