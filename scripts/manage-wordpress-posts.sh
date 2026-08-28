#!/bin/bash
#
# WordPress Post Management - Check, Delete, Fix
# Usage: ./manage-wordpress-posts.sh [action]
#

WORDPRESS_PATH="/home/httpd/vhost/innovation.oas.psu.ac.th"
POST_ID=5944

case "$1" in
    check)
        echo "Checking post $POST_ID..."
        cd "$WORDPRESS_PATH"
        wp post get $POST_ID --format=table --fields=ID,post_title,post_status,post_type,post_date
        echo ""
        echo "=== Post Metadata ==="
        wp post meta list $POST_ID --format=table
        echo ""
        echo "=== Post Permalink ==="
        wp post get $POST_ID --field=link
        ;;

    delete)
        echo "Deleting post $POST_ID..."
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            cd "$WORDPRESS_PATH"
            wp post delete $POST_ID --force
            echo "Post $POST_ID deleted."
        else
            echo "Cancelled."
        fi
        ;;

    publish)
        echo "Publishing post $POST_ID..."
        cd "$WORDPRESS_PATH"
        wp post update $POST_ID --post_status=publish
        echo "Post $POST_ID published."
        ;;

    search)
        echo "Searching for test posts..."
        cd "$WORDPRESS_PATH"
        wp post list --post_type=innovation-tip --post_title__like="%TEST%" --format=table
        ;;

    *)
        echo "WordPress Post Management"
        echo ""
        echo "Usage: $0 {check|delete|publish|search}"
        echo ""
        echo "Commands:"
        echo "  check    - Check post details (ID: $POST_ID)"
        echo "  delete   - Delete post (ID: $POST_ID)"
        echo "  publish  - Publish post (ID: $POST_ID)"
        echo "  search   - Search for test posts"
        echo ""
        echo "WordPress Path: $WORDPRESS_PATH"
        ;;
esac
