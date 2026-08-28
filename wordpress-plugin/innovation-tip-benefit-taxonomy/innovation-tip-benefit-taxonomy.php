<?php
/**
 * Plugin Name: Innovation Tip Benefit Taxonomy
 * Description: Adds the controlled "ประโยชน์ต่อองค์กร" taxonomy to the innovation-tip post type.
 * Version: 1.2.0
 * Requires at least: 5.9
 * Requires PHP: 7.2
 * Author: สำนักวิทยบริการ มหาวิทยาลัยสงขลานครินทร์
 */

if (!defined('ABSPATH')) {
    exit;
}

const OAR_INNOVATION_BENEFIT_TAXONOMY = 'organization_benefit';
const OAR_INNOVATION_BENEFIT_REST_BASE = 'organization-benefits';
const OAR_INNOVATION_BENEFIT_TERMS_VERSION = '1';
const OAR_INNOVATION_TIP_POST_TYPE = 'innovation-tip';
const OAR_INNOVATION_BENEFIT_PLUGIN_VERSION = '1.2.0';
const OAR_INNOVATION_BENEFIT_BACKFILL_NAMESPACE = 'oar-innovation/v1';
const OAR_INNOVATION_BENEFIT_BACKFILL_CONTRACT_VERSION = '2';
define('OAR_INNOVATION_BENEFIT_PLUGIN_URL', plugin_dir_url(__FILE__));

function oar_innovation_benefit_terms() {
    return array(
        'competitiveness' => array('name' => 'ความสามารถในการแข่งขัน', 'emoji' => '🏆'),
        'cost-efficiency' => array('name' => 'การลดต้นทุนและเพิ่มประสิทธิภาพ', 'emoji' => '⚡'),
        'digital-transformation' => array('name' => 'การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน', 'emoji' => '💻'),
        'skills-learning' => array('name' => 'การพัฒนาทักษะและการเรียนรู้', 'emoji' => '🎓'),
        'ai-advanced-technology' => array('name' => 'การใช้งาน AI และเทคโนโลยีขั้นสูง', 'emoji' => '🤖'),
        'security-privacy' => array('name' => 'ความปลอดภัยและความเป็นส่วนตัว', 'emoji' => '🛡️'),
        'innovation-change' => array('name' => 'การสร้างนวัตกรรมและการเปลี่ยนแปลง', 'emoji' => '🚀'),
        'trends-market-adaptation' => array('name' => 'การปรับตัวต่อเทรนด์และตลาด', 'emoji' => '📊'),
        'data-management-analytics' => array('name' => 'การจัดการข้อมูลและวิเคราะห์ข้อมูล', 'emoji' => '🔍'),
        'customer-experience-service' => array('name' => 'การสร้างประสบการณ์ลูกค้าและบริการ', 'emoji' => '🤝'),
        'connectivity-collaboration' => array('name' => 'การเชื่อมต่อและการทำงานร่วมกัน', 'emoji' => '👥'),
        'technology-infrastructure' => array('name' => 'การพัฒนาเทคโนโลยีและโครงสร้าง', 'emoji' => '💼'),
        'innovation-startup-support' => array('name' => 'การสนับสนุนนวัตกรรมและสตาร์ทอัพ', 'emoji' => '🚀'),
        'blockchain-fintech' => array('name' => 'การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน', 'emoji' => '💰'),
        'green-technology-sustainability' => array('name' => 'การใช้เทคโนโลยีสีเขียวและยั่งยืน', 'emoji' => '🇪🇺'),
        'healthcare-hospital-care' => array('name' => 'การพัฒนาสุขภาพและการดูแลโรงพยาบาล', 'emoji' => '🏥'),
        'generative-ai' => array('name' => 'การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์', 'emoji' => '🤖'),
        'education-smart-city' => array('name' => 'การพัฒนาภาคศึกษาและเมืองอัจฉริยะ', 'emoji' => '🎯'),
        'digital-business' => array('name' => 'การทำธุรกิจในยุคดิจิทัล', 'emoji' => '📈'),
        'research-knowledge-development' => array('name' => 'การวิจัยและพัฒนาองค์ความรู้', 'emoji' => '🔬'),
    );
}

function oar_register_innovation_benefit_taxonomy() {
    $labels = array(
        'name' => 'ประโยชน์ต่อองค์กร',
        'singular_name' => 'ประโยชน์ต่อองค์กร',
        'menu_name' => 'ประโยชน์ต่อองค์กร',
        'all_items' => 'ประโยชน์ทั้งหมด',
        'edit_item' => 'แก้ไขประโยชน์',
        'view_item' => 'ดูประโยชน์',
        'update_item' => 'อัปเดตประโยชน์',
        'add_new_item' => 'เพิ่มประโยชน์',
        'new_item_name' => 'ชื่อประโยชน์ใหม่',
        'search_items' => 'ค้นหาประโยชน์',
        'parent_item' => 'ประโยชน์หลัก',
        'parent_item_colon' => 'ประโยชน์หลัก:',
        'not_found' => 'ไม่พบประโยชน์',
    );

    if (!taxonomy_exists(OAR_INNOVATION_BENEFIT_TAXONOMY)) {
        register_taxonomy(
            OAR_INNOVATION_BENEFIT_TAXONOMY,
            array(OAR_INNOVATION_TIP_POST_TYPE),
            array(
                'labels' => $labels,
                'public' => true,
                'publicly_queryable' => true,
                'hierarchical' => true,
                'show_ui' => true,
                'show_admin_column' => true,
                'show_in_nav_menus' => true,
                'show_tagcloud' => false,
                'show_in_quick_edit' => true,
                'show_in_rest' => true,
                'rest_base' => OAR_INNOVATION_BENEFIT_REST_BASE,
                'rest_namespace' => 'wp/v2',
                'rest_controller_class' => 'WP_REST_Terms_Controller',
                'query_var' => OAR_INNOVATION_BENEFIT_TAXONOMY,
                'rewrite' => array(
                    'slug' => 'organization-benefit',
                    'with_front' => false,
                    'hierarchical' => false,
                ),
            )
        );
    } else {
        $taxonomy = get_taxonomy(OAR_INNOVATION_BENEFIT_TAXONOMY);
        if (
            !$taxonomy
            || !$taxonomy->show_in_rest
            || $taxonomy->rest_base !== OAR_INNOVATION_BENEFIT_REST_BASE
        ) {
            error_log(
                'Innovation benefit taxonomy collision: existing taxonomy must use '
                . 'show_in_rest=true and rest_base=' . OAR_INNOVATION_BENEFIT_REST_BASE
            );
        }
    }

    register_taxonomy_for_object_type(
        OAR_INNOVATION_BENEFIT_TAXONOMY,
        OAR_INNOVATION_TIP_POST_TYPE
    );
}
add_action('init', 'oar_register_innovation_benefit_taxonomy', 100);

function oar_seed_innovation_benefit_terms() {
    if (!taxonomy_exists(OAR_INNOVATION_BENEFIT_TAXONOMY)) {
        return;
    }

    $previous_version = get_option('oar_innovation_benefit_terms_version', '');
    if ($previous_version === OAR_INNOVATION_BENEFIT_TERMS_VERSION) {
        return;
    }

    $all_terms_ready = true;
    foreach (oar_innovation_benefit_terms() as $slug => $term_data) {
        $existing_term = get_term_by('slug', $slug, OAR_INNOVATION_BENEFIT_TAXONOMY);
        if ($existing_term) {
            $result = wp_update_term(
                $existing_term->term_id,
                OAR_INNOVATION_BENEFIT_TAXONOMY,
                array(
                    'name' => $term_data['name'],
                    'slug' => $slug,
                    'description' => $term_data['emoji'] . ' ' . $term_data['name'],
                )
            );
        } else {
            $result = wp_insert_term(
                $term_data['name'],
                OAR_INNOVATION_BENEFIT_TAXONOMY,
                array(
                    'slug' => $slug,
                    'description' => $term_data['emoji'] . ' ' . $term_data['name'],
                )
            );
        }

        if (is_wp_error($result)) {
            $all_terms_ready = false;
            error_log(sprintf(
                'Innovation benefit taxonomy: failed to create term %s: %s',
                $slug,
                $result->get_error_message()
            ));
        }
    }

    if ($all_terms_ready) {
        update_option(
            'oar_innovation_benefit_terms_version',
            OAR_INNOVATION_BENEFIT_TERMS_VERSION,
            false
        );

        // Run only when the controlled vocabulary version changes.
        flush_rewrite_rules(false);
    }
}
add_action('init', 'oar_seed_innovation_benefit_terms', 101);

/**
 * Return the assigned organization-benefit term IDs in stable order.
 */
function oar_innovation_benefit_backfill_current_ids($post_id) {
    $term_ids = wp_get_object_terms(
        (int) $post_id,
        OAR_INNOVATION_BENEFIT_TAXONOMY,
        array('fields' => 'ids')
    );
    if (is_wp_error($term_ids)) {
        return $term_ids;
    }
    $term_ids = array_values(array_unique(array_map('intval', $term_ids)));
    sort($term_ids, SORT_NUMERIC);
    return $term_ids;
}

/**
 * Read the numeric post ID from the URL route, never from JSON/query input.
 */
function oar_innovation_benefit_backfill_route_post_id($request) {
    $url_params = $request->get_url_params();
    if (!is_array($url_params) || !isset($url_params['id'])) {
        return 0;
    }
    return absint($url_params['id']);
}

/**
 * Reject a conflicting body/query ID instead of silently ignoring it.
 */
function oar_innovation_benefit_backfill_validate_route_identity($request) {
    $route_post_id = oar_innovation_benefit_backfill_route_post_id($request);
    if (!$route_post_id) {
        return true;
    }
    $parameter_sets = array(
        $request->get_json_params(),
        $request->get_body_params(),
        $request->get_query_params(),
    );
    foreach ($parameter_sets as $parameters) {
        if (!is_array($parameters) || !array_key_exists('id', $parameters)) {
            continue;
        }
        $provided_id = $parameters['id'];
        $valid_provided_id = (
            is_int($provided_id)
            || (
                is_string($provided_id)
                && preg_match('/^\d+$/', $provided_id)
            )
        );
        if (
            !$valid_provided_id
            || (int) $provided_id !== $route_post_id
        ) {
            return new WP_Error(
                'oar_backfill_conflicting_post_id',
                'The request post ID conflicts with the URL.',
                array('status' => 400)
            );
        }
    }
    return true;
}

/**
 * Normalize a REST array of term IDs without silently accepting bad values.
 */
function oar_innovation_benefit_backfill_normalize_ids($values) {
    if (!is_array($values)) {
        return new WP_Error(
            'oar_backfill_invalid_term_ids',
            'Term IDs must be an array.',
            array('status' => 400)
        );
    }
    $normalized = array();
    foreach ($values as $value) {
        if (
            !is_int($value)
            && !(
                is_string($value)
                && preg_match('/^\d+$/', $value)
            )
        ) {
            return new WP_Error(
                'oar_backfill_invalid_term_ids',
                'Every term ID must be a positive integer.',
                array('status' => 400)
            );
        }
        $term_id = (int) $value;
        if ($term_id <= 0) {
            return new WP_Error(
                'oar_backfill_invalid_term_ids',
                'Every term ID must be a positive integer.',
                array('status' => 400)
            );
        }
        $normalized[] = $term_id;
    }
    if (count($normalized) !== count(array_unique($normalized))) {
        return new WP_Error(
            'oar_backfill_duplicate_term_ids',
            'Term IDs must be unique.',
            array('status' => 400)
        );
    }
    sort($normalized, SORT_NUMERIC);
    return $normalized;
}

/**
 * Validate that the target is exactly three pre-existing controlled terms.
 */
function oar_innovation_benefit_backfill_validate_target($target_ids) {
    if (count($target_ids) !== 3) {
        return new WP_Error(
            'oar_backfill_requires_three_terms',
            'Exactly three controlled benefit terms are required.',
            array('status' => 400)
        );
    }

    $controlled_ids = array();
    foreach (oar_innovation_benefit_terms() as $slug => $term_data) {
        $term = get_term_by(
            'slug',
            $slug,
            OAR_INNOVATION_BENEFIT_TAXONOMY
        );
        if (
            !$term
            || is_wp_error($term)
            || $term->name !== $term_data['name']
        ) {
            return new WP_Error(
                'oar_backfill_controlled_terms_changed',
                'The controlled benefit vocabulary is not ready.',
                array('status' => 409)
            );
        }
        $controlled_ids[] = (int) $term->term_id;
    }
    sort($controlled_ids, SORT_NUMERIC);
    if (count(array_intersect($target_ids, $controlled_ids)) !== 3) {
        return new WP_Error(
            'oar_backfill_uncontrolled_term',
            'Target contains a term outside the controlled vocabulary.',
            array('status' => 400)
        );
    }
    return true;
}

/**
 * Require InnoDB tables so the guarded update can use row locks.
 */
function oar_innovation_benefit_backfill_storage_ready() {
    global $wpdb;
    $required_tables = array(
        $wpdb->posts,
        $wpdb->postmeta,
        $wpdb->terms,
        $wpdb->term_taxonomy,
        $wpdb->term_relationships,
    );
    foreach ($required_tables as $table_name) {
        $table_status = $wpdb->get_row(
            $wpdb->prepare(
                'SHOW TABLE STATUS WHERE Name = %s',
                $table_name
            )
        );
        if (
            !$table_status
            || !isset($table_status->Engine)
            || strtolower((string) $table_status->Engine) !== 'innodb'
        ) {
            return false;
        }
    }
    return true;
}

/**
 * Confirm that wpdb stayed on the connection that owns the named lock.
 */
function oar_innovation_benefit_backfill_connection_guard(
    $lock_name,
    $expected_connection_id
) {
    global $wpdb;
    $current_connection_id = $wpdb->get_var('SELECT CONNECTION_ID()');
    if (
        $wpdb->last_error
        || (string) $current_connection_id !== (
            (string) $expected_connection_id
        )
    ) {
        return false;
    }
    $lock_owner = $wpdb->get_var(
        $wpdb->prepare('SELECT IS_USED_LOCK(%s)', $lock_name)
    );
    if (
        $wpdb->last_error
        || (string) $lock_owner !== (string) $expected_connection_id
    ) {
        return false;
    }
    // The mutation savepoint below is the portable proof that the
    // transaction boundary survived WordPress hooks. This guard deliberately
    // avoids MariaDB-only transaction-state variables.
    return true;
}

/**
 * Return the first PTB content-meta value from rows ordered like get_post_meta.
 */
function oar_innovation_benefit_backfill_ptb_meta_value($meta_rows) {
    if (!$meta_rows) {
        return '';
    }
    $first_row = reset($meta_rows);
    if (is_array($first_row) && array_key_exists('meta_value', $first_row)) {
        return maybe_unserialize($first_row['meta_value']);
    }
    if (is_object($first_row) && isset($first_row->meta_value)) {
        return maybe_unserialize($first_row->meta_value);
    }
    return '';
}

/**
 * Hash the exact raw fields used as the server-side source guard.
 *
 * Each UTF-8 value is length-prefixed in bytes. The APPLY client computes the
 * same framing from context=edit REST raw fields before sending a mutation.
 */
function oar_innovation_benefit_backfill_source_sha256(
    $post_row,
    $ptb_meta_value
) {
    $post_values = is_array($post_row) ? $post_row : (array) $post_row;
    $values = array(
        isset($post_values['post_title'])
            ? $post_values['post_title']
            : '',
        isset($post_values['post_content'])
            ? $post_values['post_content']
            : '',
        isset($post_values['post_excerpt'])
            ? $post_values['post_excerpt']
            : '',
        $ptb_meta_value,
    );
    $framed = '';
    foreach ($values as $value) {
        if (is_null($value)) {
            $value = '';
        }
        if (!is_scalar($value)) {
            return new WP_Error(
                'oar_backfill_source_not_scalar',
                'The guarded source fields must be scalar values.',
                array('status' => 409)
            );
        }
        $value = (string) $value;
        $framed .= strlen($value) . ':' . $value;
    }
    return hash('sha256', $framed);
}

/**
 * Query the source row and relevant meta directly, optionally with row locks.
 */
function oar_innovation_benefit_backfill_source_state($post_id, $for_update) {
    global $wpdb;
    $lock_clause = $for_update ? ' FOR UPDATE' : '';
    $post_row = $wpdb->get_row(
        $wpdb->prepare(
            "SELECT * FROM {$wpdb->posts} WHERE ID = %d{$lock_clause}",
            $post_id
        ),
        ARRAY_A
    );
    if ($wpdb->last_error) {
        return new WP_Error(
            'oar_backfill_source_query_failed',
            'The guarded post source could not be read.',
            array('status' => 500)
        );
    }
    if (!$post_row) {
        return new WP_Error(
            'oar_backfill_post_not_found',
            'The innovation-tip post was not found.',
            array('status' => 404)
        );
    }
    $meta_rows = $wpdb->get_results(
        $wpdb->prepare(
            "SELECT meta_id, meta_key, meta_value
            FROM {$wpdb->postmeta}
            WHERE post_id = %d
              AND meta_key = %s
            ORDER BY meta_id ASC{$lock_clause}",
            $post_id,
            'ptb_innovation_tip_content'
        ),
        ARRAY_A
    );
    if ($wpdb->last_error || !is_array($meta_rows)) {
        return new WP_Error(
            'oar_backfill_source_query_failed',
            'The guarded source state could not be read.',
            array('status' => 500)
        );
    }
    $source_sha256 = oar_innovation_benefit_backfill_source_sha256(
        $post_row,
        oar_innovation_benefit_backfill_ptb_meta_value($meta_rows)
    );
    if (is_wp_error($source_sha256)) {
        return $source_sha256;
    }
    return array(
        'post_row' => $post_row,
        'meta_rows' => $meta_rows,
        'source_sha256' => $source_sha256,
    );
}

/**
 * Lock every post-meta row so term hooks cannot silently mutate metadata.
 */
function oar_innovation_benefit_backfill_lock_all_meta($post_id) {
    global $wpdb;
    $rows = $wpdb->get_results(
        $wpdb->prepare(
            "SELECT meta_id, meta_key, meta_value
            FROM {$wpdb->postmeta}
            WHERE post_id = %d
            ORDER BY meta_id ASC FOR UPDATE",
            $post_id
        ),
        ARRAY_A
    );
    if ($wpdb->last_error || !is_array($rows)) {
        return new WP_Error(
            'oar_backfill_postmeta_query_failed',
            'Post metadata could not be locked.',
            array('status' => 500)
        );
    }
    return hash('sha256', serialize($rows));
}

/**
 * Read assigned IDs directly from locked relationship rows.
 */
function oar_innovation_benefit_backfill_db_current_ids(
    $post_id,
    $for_update
) {
    global $wpdb;
    $lock_clause = $for_update ? ' FOR UPDATE' : '';
    $rows = $wpdb->get_col(
        $wpdb->prepare(
            "SELECT t.term_id
            FROM {$wpdb->term_relationships} tr
            INNER JOIN {$wpdb->term_taxonomy} tt
                ON tt.term_taxonomy_id = tr.term_taxonomy_id
            INNER JOIN {$wpdb->terms} t
                ON t.term_id = tt.term_id
            WHERE tr.object_id = %d
              AND tt.taxonomy = %s
            ORDER BY t.term_id ASC{$lock_clause}",
            $post_id,
            OAR_INNOVATION_BENEFIT_TAXONOMY
        )
    );
    if ($wpdb->last_error || !is_array($rows)) {
        return new WP_Error(
            'oar_backfill_relationship_query_failed',
            'Benefit relationships could not be read.',
            array('status' => 500)
        );
    }
    $ids = array_values(array_unique(array_map('intval', $rows)));
    sort($ids, SORT_NUMERIC);
    return $ids;
}

/**
 * Hash every relationship outside organization_benefit for hook detection.
 */
function oar_innovation_benefit_backfill_other_relationships_hash($post_id) {
    global $wpdb;
    $rows = $wpdb->get_results(
        $wpdb->prepare(
            "SELECT tr.term_taxonomy_id, tr.term_order, tt.taxonomy
            FROM {$wpdb->term_relationships} tr
            INNER JOIN {$wpdb->term_taxonomy} tt
                ON tt.term_taxonomy_id = tr.term_taxonomy_id
            WHERE tr.object_id = %d
              AND tt.taxonomy <> %s
            ORDER BY tr.term_taxonomy_id ASC FOR UPDATE",
            $post_id,
            OAR_INNOVATION_BENEFIT_TAXONOMY
        ),
        ARRAY_A
    );
    if ($wpdb->last_error || !is_array($rows)) {
        return new WP_Error(
            'oar_backfill_other_relationship_query_failed',
            'Other taxonomy relationships could not be verified.',
            array('status' => 500)
        );
    }
    return hash('sha256', serialize($rows));
}

/**
 * Read and validate the exact controlled vocabulary, optionally locking it.
 */
function oar_innovation_benefit_backfill_controlled_terms_state(
    $target_ids = array(),
    $target_slugs = array(),
    $for_update = false
) {
    global $wpdb;
    $lock_clause = $for_update ? ' FOR UPDATE' : '';
    $rows = $wpdb->get_results(
        $wpdb->prepare(
            "SELECT t.term_id, t.slug, t.name, tt.term_taxonomy_id,
                tt.description, tt.parent
            FROM {$wpdb->terms} t
            INNER JOIN {$wpdb->term_taxonomy} tt
                ON tt.term_id = t.term_id
            WHERE tt.taxonomy = %s
            ORDER BY t.term_id ASC{$lock_clause}",
            OAR_INNOVATION_BENEFIT_TAXONOMY
        ),
        ARRAY_A
    );
    $expected = oar_innovation_benefit_terms();
    if (
        $wpdb->last_error
        || !is_array($rows)
        || count($rows) !== count($expected)
    ) {
        return new WP_Error(
            'oar_backfill_controlled_terms_changed',
            'The controlled benefit vocabulary is not exact.',
            array('status' => 409)
        );
    }
    $controlled_ids = array();
    $controlled_by_id = array();
    $seen_slugs = array();
    foreach ($rows as $row) {
        $slug = (string) $row['slug'];
        if (
            !isset($expected[$slug])
            || isset($seen_slugs[$slug])
            || (string) $row['name'] !== $expected[$slug]['name']
            || (int) $row['parent'] !== 0
            || (string) $row['description'] !== (
                $expected[$slug]['emoji']
                . ' '
                . $expected[$slug]['name']
            )
        ) {
            return new WP_Error(
                'oar_backfill_controlled_terms_changed',
                'The controlled benefit vocabulary changed after PLAN.',
                array('status' => 409)
            );
        }
        $seen_slugs[$slug] = true;
        $term_id = (int) $row['term_id'];
        $controlled_ids[] = $term_id;
        $controlled_by_id[$term_id] = $slug;
    }
    sort($controlled_ids, SORT_NUMERIC);
    if (
        $target_ids
        && count(array_intersect($target_ids, $controlled_ids)) !== 3
    ) {
        return new WP_Error(
            'oar_backfill_uncontrolled_term',
            'Target contains a term outside the controlled vocabulary.',
            array('status' => 400)
        );
    }
    foreach ((array) $target_ids as $index => $term_id) {
        if (
            !isset($target_slugs[$index])
            || !isset($controlled_by_id[$term_id])
            || $controlled_by_id[$term_id] !== $target_slugs[$index]
        ) {
            return new WP_Error(
                'oar_backfill_term_mapping_changed',
                'A controlled term ID no longer maps to its planned slug.',
                array('status' => 409)
            );
        }
    }
    return hash('sha256', serialize($rows));
}

/**
 * Permission gate shared by capability and mutation endpoints.
 */
function oar_innovation_benefit_backfill_permission($request) {
    $identity_validation = (
        oar_innovation_benefit_backfill_validate_route_identity($request)
    );
    if (is_wp_error($identity_validation)) {
        return $identity_validation;
    }
    $taxonomy = get_taxonomy(OAR_INNOVATION_BENEFIT_TAXONOMY);
    if (!$taxonomy || !current_user_can($taxonomy->cap->assign_terms)) {
        return new WP_Error(
            'oar_backfill_forbidden',
            'You cannot assign organization-benefit terms.',
            array('status' => rest_authorization_required_code())
        );
    }

    $post_id = oar_innovation_benefit_backfill_route_post_id($request);
    if ($post_id && !current_user_can('edit_post', $post_id)) {
        return new WP_Error(
            'oar_backfill_forbidden',
            'You cannot edit this innovation-tip post.',
            array('status' => rest_authorization_required_code())
        );
    }
    $post_type = get_post_type_object(OAR_INNOVATION_TIP_POST_TYPE);
    $edit_posts_capability = (
        $post_type && isset($post_type->cap->edit_posts)
        ? $post_type->cap->edit_posts
        : 'edit_posts'
    );
    if (!$post_id && !current_user_can($edit_posts_capability)) {
        return new WP_Error(
            'oar_backfill_forbidden',
            'You cannot edit posts.',
            array('status' => rest_authorization_required_code())
        );
    }
    return true;
}

/**
 * Read-only contract probe used by APPLY preflight.
 */
function oar_innovation_benefit_backfill_capability() {
    $controlled_terms_state = (
        oar_innovation_benefit_backfill_controlled_terms_state()
    );
    return rest_ensure_response(array(
        'contract_version' => OAR_INNOVATION_BENEFIT_BACKFILL_CONTRACT_VERSION,
        'plugin_version' => OAR_INNOVATION_BENEFIT_PLUGIN_VERSION,
        'post_type' => OAR_INNOVATION_TIP_POST_TYPE,
        'taxonomy' => OAR_INNOVATION_BENEFIT_TAXONOMY,
        'taxonomy_rest_base' => OAR_INNOVATION_BENEFIT_REST_BASE,
        'storage_ready' => oar_innovation_benefit_backfill_storage_ready(),
        'controlled_terms_ready' => !is_wp_error($controlled_terms_state),
        'guard_strategy' => 'innodb-row-lock-and-expected-state',
        'transaction_isolation' => 'serializable',
        'source_guard' => 'sha256-length-prefixed-raw-post-and-ptb-meta',
    ));
}

/**
 * Read-only state probe used to prove that REST and guarded DB views agree.
 */
function oar_innovation_benefit_backfill_state($request) {
    $identity_validation = (
        oar_innovation_benefit_backfill_validate_route_identity($request)
    );
    if (is_wp_error($identity_validation)) {
        return $identity_validation;
    }
    $post_id = oar_innovation_benefit_backfill_route_post_id($request);
    $source_state = oar_innovation_benefit_backfill_source_state(
        $post_id,
        false
    );
    if (is_wp_error($source_state)) {
        return $source_state;
    }
    $post_row = $source_state['post_row'];
    $current_ids = oar_innovation_benefit_backfill_db_current_ids(
        $post_id,
        false
    );
    if (is_wp_error($current_ids)) {
        return $current_ids;
    }
    return rest_ensure_response(array(
        'id' => $post_id,
        'post_type' => (string) $post_row['post_type'],
        'status' => (string) $post_row['post_status'],
        'modified_gmt' => mysql_to_rfc3339(
            $post_row['post_modified_gmt']
        ),
        'current_term_ids' => $current_ids,
        'source_sha256' => $source_state['source_sha256'],
        'contract_version' => (
            OAR_INNOVATION_BENEFIT_BACKFILL_CONTRACT_VERSION
        ),
    ));
}

/**
 * Compare expected state and assign the three terms within one transaction.
 */
function oar_innovation_benefit_backfill_apply($request) {
    global $wpdb;

    $identity_validation = (
        oar_innovation_benefit_backfill_validate_route_identity($request)
    );
    if (is_wp_error($identity_validation)) {
        return $identity_validation;
    }
    $post_id = oar_innovation_benefit_backfill_route_post_id($request);
    $expected_modified_gmt = sanitize_text_field(
        (string) $request->get_param('expected_modified_gmt')
    );
    $expected_source_sha256 = sanitize_text_field(
        (string) $request->get_param('expected_source_sha256')
    );
    $plan_run_id = sanitize_text_field(
        (string) $request->get_param('plan_run_id')
    );
    $expected_ids = oar_innovation_benefit_backfill_normalize_ids(
        $request->get_param('expected_term_ids')
    );
    $target_ids = oar_innovation_benefit_backfill_normalize_ids(
        $request->get_param('target_term_ids')
    );
    $target_slugs = $request->get_param('target_term_slugs');
    if (is_wp_error($expected_ids)) {
        return $expected_ids;
    }
    if (is_wp_error($target_ids)) {
        return $target_ids;
    }
    if (
        !is_array($target_slugs)
        || count($target_slugs) !== 3
        || count(array_unique($target_slugs)) !== 3
    ) {
        return new WP_Error(
            'oar_backfill_invalid_term_slugs',
            'Exactly three unique controlled term slugs are required.',
            array('status' => 400)
        );
    }
    foreach ($target_slugs as $index => $target_slug) {
        if (
            !is_string($target_slug)
            || !preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $target_slug)
            || !isset(oar_innovation_benefit_terms()[$target_slug])
        ) {
            return new WP_Error(
                'oar_backfill_invalid_term_slugs',
                'Target contains an invalid controlled term slug.',
                array('status' => 400)
            );
        }
        $target_slugs[$index] = $target_slug;
    }
    if ($expected_ids !== array()) {
        return new WP_Error(
            'oar_backfill_expected_terms_not_empty',
            'This endpoint only backfills posts whose taxonomy is empty.',
            array('status' => 400)
        );
    }
    if (
        !preg_match(
            '/^benefit-backfill-plan-\d{8}T\d{6}Z$/',
            $plan_run_id
        )
    ) {
        return new WP_Error(
            'oar_backfill_invalid_run_id',
            'The plan run ID is invalid.',
            array('status' => 400)
        );
    }
    if (!preg_match('/^[0-9a-f]{64}$/', $expected_source_sha256)) {
        return new WP_Error(
            'oar_backfill_invalid_source_sha256',
            'The expected source fingerprint is invalid.',
            array('status' => 400)
        );
    }
    $target_validation = oar_innovation_benefit_backfill_validate_target(
        $target_ids
    );
    if (is_wp_error($target_validation)) {
        return $target_validation;
    }
    if (!oar_innovation_benefit_backfill_storage_ready()) {
        return new WP_Error(
            'oar_backfill_storage_not_ready',
            'Backfill requires InnoDB post and term relationship tables.',
            array('status' => 503)
        );
    }

    $lock_name = 'oar_benefit_' . md5(
        $wpdb->prefix . '|' . get_current_blog_id() . '|' . $post_id
    );
    $lock_acquired = $wpdb->get_var(
        $wpdb->prepare('SELECT GET_LOCK(%s, 0)', $lock_name)
    );
    if ((string) $lock_acquired !== '1') {
        return new WP_Error(
            'oar_backfill_locked',
            'Another backfill request is handling this post.',
            array('status' => 423)
        );
    }
    $lock_connection_id = $wpdb->get_var('SELECT CONNECTION_ID()');
    if ($wpdb->last_error || !is_numeric($lock_connection_id)) {
        $wpdb->get_var(
            $wpdb->prepare('SELECT RELEASE_LOCK(%s)', $lock_name)
        );
        return new WP_Error(
            'oar_backfill_connection_guard_failed',
            'Could not establish the guarded database connection.',
            array('status' => 500)
        );
    }

    $transaction_started = false;
    $target_ids_for_cache = $target_ids;
    try {
        if (
            false === $wpdb->query(
                'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE'
            )
        ) {
            return new WP_Error(
                'oar_backfill_isolation_failed',
                'Could not require serializable transaction isolation.',
                array('status' => 500)
            );
        }
        if (false === $wpdb->query('START TRANSACTION')) {
            return new WP_Error(
                'oar_backfill_transaction_failed',
                'Could not start the guarded backfill transaction.',
                array('status' => 500)
            );
        }
        $transaction_started = true;
        if (
            !oar_innovation_benefit_backfill_connection_guard(
                $lock_name,
                $lock_connection_id
            )
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_connection_guard_failed',
                'The guarded database transaction is not active.',
                array('status' => 500)
            );
        }

        $source_state = oar_innovation_benefit_backfill_source_state(
            $post_id,
            true
        );
        if (is_wp_error($source_state)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return $source_state;
        }
        $locked_post = $source_state['post_row'];
        if (
            $locked_post['post_type'] !== OAR_INNOVATION_TIP_POST_TYPE
            || $locked_post['post_status'] !== 'publish'
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_post_state_changed',
                'The post type or status changed after PLAN.',
                array('status' => 409)
            );
        }
        $live_modified_gmt = mysql_to_rfc3339(
            $locked_post['post_modified_gmt']
        );
        if ($live_modified_gmt !== $expected_modified_gmt) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_post_stale',
                'The post modified timestamp changed after PLAN.',
                array('status' => 409)
            );
        }
        if ($source_state['source_sha256'] !== $expected_source_sha256) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_source_stale',
                'The guarded source fields changed before APPLY.',
                array('status' => 409)
            );
        }

        $post_row_hash = hash('sha256', serialize($locked_post));
        $postmeta_hash = oar_innovation_benefit_backfill_lock_all_meta(
            $post_id
        );
        if (is_wp_error($postmeta_hash)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return $postmeta_hash;
        }
        // Lock all existing term relationships for this object, including
        // its insertion range under SERIALIZABLE isolation, before comparing
        // the expected taxonomy.
        $relationship_lock_rows = $wpdb->get_col(
            $wpdb->prepare(
                "SELECT term_taxonomy_id
                FROM {$wpdb->term_relationships}
                WHERE object_id = %d FOR UPDATE",
                $post_id
            )
        );
        if ($wpdb->last_error || !is_array($relationship_lock_rows)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_relationship_lock_failed',
                'Benefit relationships could not be locked.',
                array('status' => 500)
            );
        }
        $other_relationships_hash = (
            oar_innovation_benefit_backfill_other_relationships_hash(
                $post_id
            )
        );
        if (is_wp_error($other_relationships_hash)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return $other_relationships_hash;
        }
        clean_object_term_cache(
            $post_id,
            OAR_INNOVATION_TIP_POST_TYPE
        );
        $current_ids = oar_innovation_benefit_backfill_db_current_ids(
            $post_id,
            true
        );
        if (is_wp_error($current_ids)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return $current_ids;
        }
        if ($current_ids !== $expected_ids) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_taxonomy_conflict',
                'The benefit taxonomy changed after PLAN.',
                array('status' => 409)
            );
        }
        $controlled_state_hash = (
            oar_innovation_benefit_backfill_controlled_terms_state(
                $target_ids,
                $target_slugs,
                true
            )
        );
        if (is_wp_error($controlled_state_hash)) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return $controlled_state_hash;
        }
        if (
            !oar_innovation_benefit_backfill_connection_guard(
                $lock_name,
                $lock_connection_id
            )
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_connection_guard_failed',
                'The guarded database transaction changed before mutation.',
                array('status' => 500)
            );
        }
        if (false === $wpdb->query('SAVEPOINT oar_backfill_mutation')) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_savepoint_failed',
                'Could not establish the guarded mutation savepoint.',
                array('status' => 500)
            );
        }

        $set_result = wp_set_post_terms(
            $post_id,
            $target_ids,
            OAR_INNOVATION_BENEFIT_TAXONOMY,
            false
        );
        if (is_wp_error($set_result) || false === $set_result) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_set_terms_failed',
                'WordPress could not assign the benefit terms.',
                array('status' => 500)
            );
        }
        if (
            false === $wpdb->query(
                'RELEASE SAVEPOINT oar_backfill_mutation'
            )
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_transaction_boundary_lost',
                'The guarded mutation lost its transaction boundary.',
                array('status' => 500)
            );
        }
        if (
            !oar_innovation_benefit_backfill_connection_guard(
                $lock_name,
                $lock_connection_id
            )
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_connection_guard_failed',
                'The guarded database transaction changed during mutation.',
                array('status' => 500)
            );
        }

        clean_object_term_cache(
            $post_id,
            OAR_INNOVATION_TIP_POST_TYPE
        );
        $verified_ids = oar_innovation_benefit_backfill_db_current_ids(
            $post_id,
            true
        );
        if (is_wp_error($verified_ids) || $verified_ids !== $target_ids) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_verification_failed',
                'The assigned benefit terms did not verify.',
                array('status' => 500)
            );
        }
        $post_after = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT * FROM {$wpdb->posts} WHERE ID = %d FOR UPDATE",
                $post_id
            ),
            ARRAY_A
        );
        $post_after_query_failed = (bool) $wpdb->last_error;
        $postmeta_after_hash = (
            oar_innovation_benefit_backfill_lock_all_meta($post_id)
        );
        $other_relationships_after_hash = (
            oar_innovation_benefit_backfill_other_relationships_hash(
                $post_id
            )
        );
        $controlled_after_hash = (
            oar_innovation_benefit_backfill_controlled_terms_state(
                $target_ids,
                $target_slugs,
                true
            )
        );
        if (
            $post_after_query_failed
            || !$post_after
            || is_wp_error($postmeta_after_hash)
            || is_wp_error($other_relationships_after_hash)
            || is_wp_error($controlled_after_hash)
            || hash('sha256', serialize($post_after)) !== $post_row_hash
            || $postmeta_after_hash !== $postmeta_hash
            || $other_relationships_after_hash !== (
                $other_relationships_hash
            )
            || $controlled_after_hash !== $controlled_state_hash
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_non_taxonomy_side_effect',
                'A term hook changed guarded post data.',
                array('status' => 500)
            );
        }
        if (
            !oar_innovation_benefit_backfill_connection_guard(
                $lock_name,
                $lock_connection_id
            )
        ) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_connection_guard_failed',
                'The guarded database transaction changed before commit.',
                array('status' => 500)
            );
        }
        if (false === $wpdb->query('COMMIT')) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
            return new WP_Error(
                'oar_backfill_commit_failed',
                'The backfill transaction could not be committed.',
                array('status' => 500)
            );
        }
        $transaction_started = false;
        $committed_ids = oar_innovation_benefit_backfill_db_current_ids(
            $post_id,
            false
        );
        $committed_source = oar_innovation_benefit_backfill_source_state(
            $post_id,
            false
        );
        if (
            is_wp_error($committed_ids)
            || $committed_ids !== $target_ids
            || is_wp_error($committed_source)
            || $committed_source['source_sha256'] !== (
                $expected_source_sha256
            )
        ) {
            return new WP_Error(
                'oar_backfill_commit_verification_failed',
                'The committed backfill state could not be verified.',
                array('status' => 500)
            );
        }
        clean_object_term_cache(
            $post_id,
            OAR_INNOVATION_TIP_POST_TYPE
        );

        return rest_ensure_response(array(
            'id' => $post_id,
            'status' => 'publish',
            'modified_gmt' => $live_modified_gmt,
            OAR_INNOVATION_BENEFIT_REST_BASE => $target_ids,
            'contract_version' => (
                OAR_INNOVATION_BENEFIT_BACKFILL_CONTRACT_VERSION
            ),
            'plan_run_id' => $plan_run_id,
            'source_sha256' => $expected_source_sha256,
            'target_term_slugs' => $target_slugs,
        ));
    } catch (Throwable $error) {
        if ($transaction_started) {
            $wpdb->query('ROLLBACK');
            $transaction_started = false;
        }
        error_log(
            'Innovation benefit guarded backfill failed: '
            . $error->getMessage()
        );
        return new WP_Error(
            'oar_backfill_unexpected_failure',
            'The guarded backfill request failed.',
            array('status' => 500)
        );
    } finally {
        clean_post_cache($post_id);
        clean_object_term_cache(
            $post_id,
            OAR_INNOVATION_TIP_POST_TYPE
        );
        if ($target_ids_for_cache) {
            clean_term_cache(
                $target_ids_for_cache,
                OAR_INNOVATION_BENEFIT_TAXONOMY
            );
        }
        if (function_exists('wp_cache_set_terms_last_changed')) {
            wp_cache_set_terms_last_changed();
        }
        $lock_released = $wpdb->get_var(
            $wpdb->prepare('SELECT RELEASE_LOCK(%s)', $lock_name)
        );
        if ((string) $lock_released !== '1') {
            error_log(
                'Innovation benefit guarded backfill could not confirm '
                . 'release of its advisory lock.'
            );
        }
    }
}

/**
 * Register the authenticated guarded backfill REST contract.
 */
function oar_register_innovation_benefit_backfill_routes() {
    register_rest_route(
        OAR_INNOVATION_BENEFIT_BACKFILL_NAMESPACE,
        '/benefit-backfill-capability',
        array(
            'methods' => WP_REST_Server::READABLE,
            'callback' => 'oar_innovation_benefit_backfill_capability',
            'permission_callback' => (
                'oar_innovation_benefit_backfill_permission'
            ),
        )
    );
    register_rest_route(
        OAR_INNOVATION_BENEFIT_BACKFILL_NAMESPACE,
        '/benefit-backfill-state/(?P<id>\d+)',
        array(
            'methods' => WP_REST_Server::READABLE,
            'callback' => 'oar_innovation_benefit_backfill_state',
            'permission_callback' => (
                'oar_innovation_benefit_backfill_permission'
            ),
            'args' => array(
                'id' => array(
                    'type' => 'integer',
                    'required' => true,
                    'minimum' => 1,
                ),
            ),
        )
    );
    register_rest_route(
        OAR_INNOVATION_BENEFIT_BACKFILL_NAMESPACE,
        '/benefit-backfill/(?P<id>\d+)',
        array(
            'methods' => WP_REST_Server::CREATABLE,
            'callback' => 'oar_innovation_benefit_backfill_apply',
            'permission_callback' => (
                'oar_innovation_benefit_backfill_permission'
            ),
            'args' => array(
                'id' => array(
                    'type' => 'integer',
                    'required' => true,
                    'minimum' => 1,
                ),
                'expected_modified_gmt' => array(
                    'type' => 'string',
                    'required' => true,
                ),
                'expected_term_ids' => array(
                    'type' => 'array',
                    'required' => true,
                    'items' => array('type' => 'integer'),
                ),
                'expected_source_sha256' => array(
                    'type' => 'string',
                    'required' => true,
                    'pattern' => '^[0-9a-f]{64}$',
                ),
                'target_term_ids' => array(
                    'type' => 'array',
                    'required' => true,
                    'items' => array('type' => 'integer'),
                ),
                'target_term_slugs' => array(
                    'type' => 'array',
                    'required' => true,
                    'items' => array(
                        'type' => 'string',
                        'pattern' => '^[a-z0-9]+(?:-[a-z0-9]+)*$',
                    ),
                ),
                'plan_run_id' => array(
                    'type' => 'string',
                    'required' => true,
                ),
            ),
        )
    );
}
add_action(
    'rest_api_init',
    'oar_register_innovation_benefit_backfill_routes'
);

/**
 * Render the assigned benefit terms for the current innovation-tip post.
 * Usage: [innovation_tip_benefits]
 */
function oar_innovation_tip_benefits_shortcode($attributes) {
    $attributes = shortcode_atts(
        array('post_id' => 0),
        $attributes,
        'innovation_tip_benefits'
    );
    $post_id = absint($attributes['post_id']);
    if (!$post_id) {
        $post_id = get_the_ID();
    }
    if (!$post_id) {
        return '';
    }

    $terms = get_the_terms($post_id, OAR_INNOVATION_BENEFIT_TAXONOMY);
    if (!$terms || is_wp_error($terms)) {
        return '';
    }

    $links = array();
    foreach ($terms as $term) {
        $term_link = get_term_link($term, OAR_INNOVATION_BENEFIT_TAXONOMY);
        if (is_wp_error($term_link)) {
            continue;
        }
        $links[] = sprintf(
            '<a class="innovation-benefit" href="%s">%s</a>',
            esc_url($term_link),
            esc_html($term->name)
        );
    }

    if (!$links) {
        return '';
    }

    return sprintf(
        '<div class="innovation-benefits" aria-label="%s">%s</div>',
        esc_attr('ประโยชน์ต่อองค์กร'),
        implode(' · ', $links)
    );
}
add_shortcode('innovation_tip_benefits', 'oar_innovation_tip_benefits_shortcode');

/**
 * Render links to benefit archives for use on an innovation-tip index page.
 * Usage: [innovation_benefit_filter]
 */
function oar_innovation_benefit_filter_shortcode() {
    $terms = get_terms(array(
        'taxonomy' => OAR_INNOVATION_BENEFIT_TAXONOMY,
        'hide_empty' => true,
    ));
    if (!$terms || is_wp_error($terms)) {
        return '';
    }

    $items = array();
    foreach ($terms as $term) {
        $term_link = get_term_link($term, OAR_INNOVATION_BENEFIT_TAXONOMY);
        if (is_wp_error($term_link)) {
            continue;
        }
        $items[] = sprintf(
            '<li><a href="%s">%s <span class="innovation-benefit-count">(%d)</span></a></li>',
            esc_url($term_link),
            esc_html($term->name),
            absint($term->count)
        );
    }

    if (!$items) {
        return '';
    }

    return sprintf(
        '<nav class="innovation-benefit-filter" aria-label="%s"><ul>%s</ul></nav>',
        esc_attr('ดูข่าวตามประโยชน์ต่อองค์กร'),
        implode('', $items)
    );
}
add_shortcode('innovation_benefit_filter', 'oar_innovation_benefit_filter_shortcode');

$oar_innovation_search_module = plugin_dir_path(__FILE__) . 'includes/frontend-search.php';
if (is_readable($oar_innovation_search_module)) {
    require_once $oar_innovation_search_module;
} else {
    error_log('Innovation Tip Benefit Taxonomy: frontend search module is missing.');
}
unset($oar_innovation_search_module);

function oar_activate_innovation_benefit_taxonomy() {
    oar_register_innovation_benefit_taxonomy();
    oar_seed_innovation_benefit_terms();
    flush_rewrite_rules(false);
}
register_activation_hook(__FILE__, 'oar_activate_innovation_benefit_taxonomy');

function oar_deactivate_innovation_benefit_taxonomy() {
    flush_rewrite_rules(false);
}
register_deactivation_hook(__FILE__, 'oar_deactivate_innovation_benefit_taxonomy');
