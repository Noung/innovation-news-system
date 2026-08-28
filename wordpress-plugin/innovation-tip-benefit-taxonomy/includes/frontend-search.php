<?php
/**
 * Frontend search form for Innovation Tips.
 *
 * This module deliberately uses its own WP_Query and namespaced GET parameters
 * so it does not alter the PTB or theme main query.
 */

if (!defined('ABSPATH')) {
    exit;
}

const OAR_INNOVATION_SEARCH_SHORTCODE = 'innovation_tip_search';
const OAR_INNOVATION_SEARCH_STYLE_HANDLE = 'oar-innovation-tip-search';

/**
 * Register the frontend stylesheet. It is scoped to the search component and
 * loaded on singular pages so builder/meta-based shortcode placement is styled
 * before wp_head finishes.
 */
function oar_register_innovation_tip_search_assets() {
    wp_register_style(
        OAR_INNOVATION_SEARCH_STYLE_HANDLE,
        OAR_INNOVATION_BENEFIT_PLUGIN_URL . 'assets/innovation-tip-search.css',
        array(),
        OAR_INNOVATION_BENEFIT_PLUGIN_VERSION
    );

    if (is_singular()) {
        wp_enqueue_style(OAR_INNOVATION_SEARCH_STYLE_HANDLE);
    }
}
add_action('wp_enqueue_scripts', 'oar_register_innovation_tip_search_assets', 5);

/**
 * Return a scalar, sanitized GET value. Array input is rejected.
 */
function oar_innovation_tip_search_request_value($key) {
    if (!isset($_GET[$key]) || !is_scalar($_GET[$key])) {
        return '';
    }

    return sanitize_text_field(wp_unslash((string) $_GET[$key]));
}

/**
 * Limit text without splitting a UTF-8 character when mbstring is unavailable.
 */
function oar_innovation_tip_search_limit_text($value, $limit) {
    if (function_exists('mb_substr')) {
        return mb_substr($value, 0, $limit);
    }

    if (preg_match_all('/./us', $value, $characters)) {
        return implode('', array_slice($characters[0], 0, $limit));
    }

    return substr($value, 0, $limit);
}

/**
 * Validate and normalize an HTML date input.
 *
 * @return string|false Empty string for no filter, normalized Y-m-d for a
 *                      valid date, or false for invalid input.
 */
function oar_innovation_tip_search_normalize_date($value) {
    if ($value === '') {
        return '';
    }

    if (!preg_match('/\A(\d{4})-(\d{2})-(\d{2})\z/D', $value, $matches)) {
        return false;
    }

    $year = (int) $matches[1];
    $month = (int) $matches[2];
    $day = (int) $matches[3];
    if (!checkdate($month, $day, $year)) {
        return false;
    }

    return sprintf('%04d-%02d-%02d', $year, $month, $day);
}

/**
 * Convert a validated Y-m-d value to the array format expected by WP_Date_Query.
 */
function oar_innovation_tip_search_date_parts($value) {
    if (!$value) {
        return array();
    }

    $parts = array_map('intval', explode('-', $value));
    return array(
        'year' => $parts[0],
        'month' => $parts[1],
        'day' => $parts[2],
    );
}

/**
 * Normalize all search filters from the current request.
 */
function oar_innovation_tip_search_filters() {
    $errors = array();
    $submitted = oar_innovation_tip_search_request_value('it_search') === '1';
    if (!$submitted) {
        return array(
            'keyword' => '',
            'benefit' => '',
            'from' => '',
            'to' => '',
            'page' => 1,
            'submitted' => false,
            'errors' => array(),
        );
    }

    foreach (array('it_q', 'it_benefit', 'it_from', 'it_to', 'it_page') as $key) {
        if (isset($_GET[$key]) && !is_scalar($_GET[$key])) {
            $errors[] = 'รูปแบบเงื่อนไขการค้นหาไม่ถูกต้อง';
            break;
        }
    }

    $keyword = oar_innovation_tip_search_request_value('it_q');
    $keyword = oar_innovation_tip_search_limit_text($keyword, 200);

    $raw_benefit = sanitize_title(
        oar_innovation_tip_search_request_value('it_benefit')
    );
    $allowed_benefits = oar_innovation_benefit_terms();
    $benefit = '';
    if ($raw_benefit !== '') {
        if (isset($allowed_benefits[$raw_benefit])) {
            $benefit = $raw_benefit;
        } else {
            $errors[] = 'หมวดประโยชน์ต่อองค์กรไม่ถูกต้อง';
        }
    }

    $raw_from = oar_innovation_tip_search_request_value('it_from');
    $raw_to = oar_innovation_tip_search_request_value('it_to');
    $from = oar_innovation_tip_search_normalize_date($raw_from);
    $to = oar_innovation_tip_search_normalize_date($raw_to);

    if ($from === false) {
        $errors[] = 'วันที่เริ่มต้นไม่ถูกต้อง';
        $from = '';
    }
    if ($to === false) {
        $errors[] = 'วันที่สิ้นสุดไม่ถูกต้อง';
        $to = '';
    }
    if ($from !== '' && $to !== '' && strcmp($from, $to) > 0) {
        $errors[] = 'วันที่เริ่มต้นต้องไม่อยู่หลังวันที่สิ้นสุด';
    }

    $raw_page = oar_innovation_tip_search_request_value('it_page');
    $page = 1;
    if ($raw_page !== '') {
        if (!preg_match('/\A\d+\z/D', $raw_page) || (int) $raw_page > 100) {
            $errors[] = 'หน้าผลการค้นหาไม่ถูกต้อง';
        } else {
            $page = max(1, (int) $raw_page);
        }
    }

    return array(
        'keyword' => $keyword,
        'benefit' => $benefit,
        'from' => $from,
        'to' => $to,
        'page' => $page,
        'submitted' => true,
        'errors' => $errors,
    );
}

/**
 * Build a private WP_Query for the shortcode results.
 */
function oar_innovation_tip_search_query_args($filters, $posts_per_page) {
    $posts_per_page = max(1, min(absint($posts_per_page), 24));
    $args = array(
        'post_type' => OAR_INNOVATION_TIP_POST_TYPE,
        'post_status' => 'publish',
        'posts_per_page' => $posts_per_page,
        'paged' => $filters['page'],
        'orderby' => array(
            'date' => 'DESC',
            'ID' => 'DESC',
        ),
        'ignore_sticky_posts' => true,
        'no_found_rows' => false,
        'oar_innovation_search' => true,
    );

    if (!empty($filters['errors'])) {
        // Invalid or contradictory input must not silently become "show all".
        $args['post__in'] = array(0);
        return $args;
    }

    if ($filters['keyword'] !== '') {
        $args['s'] = $filters['keyword'];
    }

    if ($filters['benefit'] !== '') {
        $args['tax_query'] = array(
            array(
                'taxonomy' => OAR_INNOVATION_BENEFIT_TAXONOMY,
                'field' => 'slug',
                'terms' => array($filters['benefit']),
                'operator' => 'IN',
                'include_children' => false,
            ),
        );
    }

    if ($filters['from'] !== '' || $filters['to'] !== '') {
        $date_clause = array(
            'column' => 'post_date',
            'inclusive' => true,
        );
        if ($filters['from'] !== '') {
            $date_clause['after'] = oar_innovation_tip_search_date_parts(
                $filters['from']
            );
        }
        if ($filters['to'] !== '') {
            $date_clause['before'] = oar_innovation_tip_search_date_parts(
                $filters['to']
            );
        }
        $args['date_query'] = array($date_clause);
    }

    return $args;
}

/**
 * Return controlled taxonomy terms in the same order as the vocabulary map.
 */
function oar_innovation_tip_search_terms($hide_empty, $selected_slug = '') {
    $controlled_terms = oar_innovation_benefit_terms();
    $terms = get_terms(array(
        'taxonomy' => OAR_INNOVATION_BENEFIT_TAXONOMY,
        'hide_empty' => false,
        'slug' => array_keys($controlled_terms),
    ));
    if (!$terms || is_wp_error($terms)) {
        return array();
    }

    $terms_by_slug = array();
    foreach ($terms as $term) {
        $terms_by_slug[$term->slug] = $term;
    }

    $ordered_terms = array();
    foreach ($controlled_terms as $slug => $term_data) {
        if (!isset($terms_by_slug[$slug])) {
            continue;
        }
        $term = $terms_by_slug[$slug];
        if ($hide_empty && !$term->count && $slug !== $selected_slug) {
            continue;
        }
        $ordered_terms[] = $term;
    }

    return $ordered_terms;
}

/**
 * Build a permalink for the page that owns the shortcode.
 */
function oar_innovation_tip_search_action_url() {
    $queried_object = get_queried_object();
    if (!($queried_object instanceof WP_Post)) {
        return '';
    }

    return get_permalink($queried_object);
}

/**
 * Preserve permalink query arguments (for example page_id with plain
 * permalinks) when the browser submits the GET form.
 */
function oar_innovation_tip_search_form_action($action_url) {
    $query = wp_parse_url($action_url, PHP_URL_QUERY);
    if (!$query) {
        return array(
            'url' => $action_url,
            'hidden' => array(),
        );
    }

    wp_parse_str($query, $query_args);
    $hidden_args = array();
    foreach ($query_args as $key => $value) {
        if (
            !is_scalar($value)
            || strpos((string) $key, 'it_') === 0
        ) {
            continue;
        }
        $hidden_args[(string) $key] = (string) $value;
    }

    return array(
        'url' => remove_query_arg(array_keys($query_args), $action_url),
        'hidden' => $hidden_args,
    );
}

/**
 * Keep only validated filters in pagination links.
 */
function oar_innovation_tip_search_pagination_url($action_url, $filters) {
    $query_args = array('it_search' => '1');
    if ($filters['keyword'] !== '') {
        $query_args['it_q'] = $filters['keyword'];
    }
    if ($filters['benefit'] !== '') {
        $query_args['it_benefit'] = $filters['benefit'];
    }
    if ($filters['from'] !== '') {
        $query_args['it_from'] = $filters['from'];
    }
    if ($filters['to'] !== '') {
        $query_args['it_to'] = $filters['to'];
    }

    $url = add_query_arg($query_args, $action_url);
    $url = add_query_arg('it_page', 999999999, $url);
    return preg_replace(
        '/([?&]it_page=)999999999(?=&|$)/',
        '$1%#%',
        $url,
        1
    );
}

/**
 * Render benefit badges which keep visitors inside the combined search page.
 */
function oar_innovation_tip_search_benefits($post_id, $action_url, $results_id) {
    $terms = get_the_terms($post_id, OAR_INNOVATION_BENEFIT_TAXONOMY);
    if (!$terms || is_wp_error($terms)) {
        return '';
    }

    $allowed_slugs = array_keys(oar_innovation_benefit_terms());
    $links = array();
    foreach ($terms as $term) {
        if (!in_array($term->slug, $allowed_slugs, true)) {
            continue;
        }
        $url = add_query_arg(
            array(
                'it_search' => '1',
                'it_benefit' => $term->slug,
            ),
            $action_url
        );
        $links[] = sprintf(
            '<a class="oar-innovation-search__benefit" href="%s">%s</a>',
            esc_url($url . '#' . $results_id),
            esc_html($term->name)
        );
    }

    if (!$links) {
        return '';
    }

    return sprintf(
        '<div class="oar-innovation-search__benefits" aria-label="%s">%s</div>',
        esc_attr('ประโยชน์ต่อองค์กร'),
        implode('', $links)
    );
}

/**
 * Render the combined search form and its same-page results.
 *
 * Usage: [innovation_tip_search]
 * Options:
 *   posts_per_page="12"  Maximum 24.
 *   hide_empty="1"       Use 0 to show all 20 controlled benefit terms.
 *   show_excerpt="1"     Use 0 to hide result excerpts.
 */
function oar_innovation_tip_search_shortcode($attributes) {
    if (
        !post_type_exists(OAR_INNOVATION_TIP_POST_TYPE)
        || !taxonomy_exists(OAR_INNOVATION_BENEFIT_TAXONOMY)
    ) {
        return '';
    }

    $attributes = shortcode_atts(
        array(
            'posts_per_page' => 12,
            'hide_empty' => '1',
            'show_excerpt' => '1',
        ),
        $attributes,
        OAR_INNOVATION_SEARCH_SHORTCODE
    );
    $posts_per_page = max(1, min(absint($attributes['posts_per_page']), 24));
    $hide_empty = !in_array(
        strtolower((string) $attributes['hide_empty']),
        array('0', 'false', 'no'),
        true
    );
    $show_excerpt = !in_array(
        strtolower((string) $attributes['show_excerpt']),
        array('0', 'false', 'no'),
        true
    );

    static $instance = 0;
    ++$instance;
    $form_id = 'oar-innovation-search-form-' . $instance;
    $results_id = 'innovation-search-results-' . $instance;
    $keyword_id = $form_id . '-keyword';
    $benefit_id = $form_id . '-benefit';
    $from_id = $form_id . '-from';
    $to_id = $form_id . '-to';

    wp_enqueue_style(OAR_INNOVATION_SEARCH_STYLE_HANDLE);

    $filters = oar_innovation_tip_search_filters();
    $action_url = oar_innovation_tip_search_action_url();
    if (!$action_url) {
        return sprintf(
            '<p class="oar-innovation-search__errors">%s</p>',
            esc_html('แบบฟอร์มค้นหานี้ต้องวางบน Page หรือเนื้อหาแบบ singular')
        );
    }
    $form_action = oar_innovation_tip_search_form_action($action_url);
    $terms = oar_innovation_tip_search_terms(
        $hide_empty,
        $filters['benefit']
    );
    $query_args = oar_innovation_tip_search_query_args(
        $filters,
        $posts_per_page
    );
    $query_args = apply_filters(
        'oar_innovation_tip_search_query_args',
        $query_args,
        $filters,
        $attributes
    );
    $results = new WP_Query($query_args);

    if (
        !$filters['errors']
        && $filters['page'] > 1
        && $results->max_num_pages > 0
        && $filters['page'] > $results->max_num_pages
    ) {
        $filters['page'] = (int) $results->max_num_pages;
        $query_args['paged'] = $filters['page'];
        $results = new WP_Query($query_args);
    }

    ob_start();
    ?>
    <section class="oar-innovation-search" aria-labelledby="<?php echo esc_attr($form_id . '-heading'); ?>">
        <h2 id="<?php echo esc_attr($form_id . '-heading'); ?>" class="oar-innovation-search__sr-only">
            <?php echo esc_html('ค้นหา Innovation Tips'); ?>
        </h2>

        <form
            id="<?php echo esc_attr($form_id); ?>"
            class="oar-innovation-search__form"
            method="get"
            action="<?php echo esc_url($form_action['url']); ?>"
        >
            <?php foreach ($form_action['hidden'] as $key => $value) : ?>
                <input
                    type="hidden"
                    name="<?php echo esc_attr($key); ?>"
                    value="<?php echo esc_attr($value); ?>"
                >
            <?php endforeach; ?>
            <input type="hidden" name="it_search" value="1">

            <div class="oar-innovation-search__field oar-innovation-search__field--keyword">
                <label for="<?php echo esc_attr($keyword_id); ?>">
                    <?php echo esc_html('คำค้น'); ?>
                </label>
                <input
                    id="<?php echo esc_attr($keyword_id); ?>"
                    type="search"
                    name="it_q"
                    maxlength="200"
                    value="<?php echo esc_attr($filters['keyword']); ?>"
                    placeholder="<?php echo esc_attr('ค้นจากชื่อเรื่องและเนื้อหา'); ?>"
                >
            </div>

            <div class="oar-innovation-search__field oar-innovation-search__field--benefit">
                <label for="<?php echo esc_attr($benefit_id); ?>">
                    <?php echo esc_html('ประโยชน์ต่อองค์กร'); ?>
                </label>
                <select id="<?php echo esc_attr($benefit_id); ?>" name="it_benefit">
                    <option value=""><?php echo esc_html('ทั้งหมด'); ?></option>
                    <?php foreach ($terms as $term) : ?>
                        <option
                            value="<?php echo esc_attr($term->slug); ?>"
                            <?php selected($filters['benefit'], $term->slug); ?>
                        >
                            <?php
                            echo esc_html(sprintf(
                                '%s (%s)',
                                $term->name,
                                number_format_i18n($term->count)
                            ));
                            ?>
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>

            <fieldset class="oar-innovation-search__dates">
                <legend><?php echo esc_html('วันที่เผยแพร่'); ?></legend>
                <div class="oar-innovation-search__field">
                    <label
                        class="oar-innovation-search__sr-only"
                        for="<?php echo esc_attr($from_id); ?>"
                    >
                        <?php echo esc_html('ตั้งแต่'); ?>
                    </label>
                    <input
                        id="<?php echo esc_attr($from_id); ?>"
                        type="date"
                        name="it_from"
                        value="<?php echo esc_attr($filters['from']); ?>"
                        aria-label="<?php echo esc_attr('เผยแพร่ตั้งแต่วันที่'); ?>"
                    >
                </div>
                <div class="oar-innovation-search__field">
                    <label
                        class="oar-innovation-search__sr-only"
                        for="<?php echo esc_attr($to_id); ?>"
                    >
                        <?php echo esc_html('ถึง'); ?>
                    </label>
                    <input
                        id="<?php echo esc_attr($to_id); ?>"
                        type="date"
                        name="it_to"
                        value="<?php echo esc_attr($filters['to']); ?>"
                        aria-label="<?php echo esc_attr('เผยแพร่ถึงวันที่'); ?>"
                    >
                </div>
            </fieldset>

            <div class="oar-innovation-search__actions">
                <button type="submit" class="oar-innovation-search__submit">
                    <?php echo esc_html('ค้นหา'); ?>
                </button>
                <a class="oar-innovation-search__reset" href="<?php echo esc_url($action_url); ?>">
                    <?php echo esc_html('ล้างตัวกรอง'); ?>
                </a>
            </div>
        </form>

        <?php if ($filters['errors']) : ?>
            <div class="oar-innovation-search__errors" role="alert">
                <p><?php echo esc_html('โปรดตรวจสอบเงื่อนไขการค้นหา'); ?></p>
                <ul>
                    <?php foreach ($filters['errors'] as $error) : ?>
                        <li><?php echo esc_html($error); ?></li>
                    <?php endforeach; ?>
                </ul>
            </div>
        <?php endif; ?>

        <div
            id="<?php echo esc_attr($results_id); ?>"
            class="oar-innovation-search__results"
            aria-live="polite"
        >
            <p class="oar-innovation-search__count">
                <?php
                echo esc_html(sprintf(
                    'พบข่าว %s รายการ',
                    number_format_i18n($results->found_posts)
                ));
                ?>
            </p>

            <?php if ($results->have_posts()) : ?>
                <div class="oar-innovation-search__list">
                    <?php foreach ($results->posts as $result_post) : ?>
                        <?php
                        $post_id = $result_post->ID;
                        $title = get_the_title($post_id);
                        $permalink = get_permalink($post_id);
                        $author_id = (int) $result_post->post_author;
                        $author_name = get_the_author_meta(
                            'display_name',
                            $author_id
                        );
                        $excerpt = wp_trim_words(
                            wp_strip_all_tags(get_the_excerpt($post_id)),
                            40,
                            '…'
                        );
                        ?>
                        <article class="oar-innovation-search__item">
                            <h3 class="oar-innovation-search__title">
                                <a href="<?php echo esc_url($permalink); ?>">
                                    <?php echo esc_html($title); ?>
                                </a>
                            </h3>
                            <p class="oar-innovation-search__meta">
                                <span class="oar-innovation-search__meta-label">
                                    <?php echo esc_html('เผยแพร่เมื่อ'); ?>
                                </span>
                                <time datetime="<?php echo esc_attr(get_the_date('c', $post_id)); ?>">
                                    <?php echo esc_html(get_the_date(get_option('date_format'), $post_id)); ?>
                                </time>
                                <?php if ($author_name) : ?>
                                    <span class="oar-innovation-search__meta-label">
                                        <?php echo esc_html('โดย'); ?>
                                    </span>
                                    <span class="oar-innovation-search__author">
                                        <span><?php echo esc_html($author_name); ?></span>
                                    </span>
                                <?php endif; ?>
                            </p>
                            <?php
                            echo wp_kses_post(
                                oar_innovation_tip_search_benefits(
                                    $post_id,
                                    $action_url,
                                    $results_id
                                )
                            );
                            ?>
                            <?php if ($show_excerpt && $excerpt !== '') : ?>
                                <p class="oar-innovation-search__excerpt">
                                    <?php echo esc_html($excerpt); ?>
                                </p>
                            <?php endif; ?>
                        </article>
                    <?php endforeach; ?>
                </div>
            <?php else : ?>
                <p class="oar-innovation-search__empty">
                    <?php echo esc_html('ไม่พบข้อมูลที่ตรงกับเงื่อนไข'); ?>
                </p>
            <?php endif; ?>

            <?php
            $pagination = paginate_links(array(
                'base' => oar_innovation_tip_search_pagination_url(
                    $action_url,
                    $filters
                ),
                'format' => '',
                'current' => $filters['page'],
                'total' => max(1, (int) $results->max_num_pages),
                'type' => 'list',
                'prev_text' => '« ก่อนหน้า',
                'next_text' => 'ถัดไป »',
                'add_fragment' => '#' . $results_id,
            ));
            if ($pagination) :
                ?>
                <nav
                    class="oar-innovation-search__pagination"
                    aria-label="<?php echo esc_attr('หน้าผลการค้นหา'); ?>"
                >
                    <?php echo wp_kses_post($pagination); ?>
                </nav>
            <?php endif; ?>
        </div>
    </section>
    <?php

    return ob_get_clean();
}
add_shortcode(
    OAR_INNOVATION_SEARCH_SHORTCODE,
    'oar_innovation_tip_search_shortcode'
);

/**
 * Prevent search/filter URL combinations from becoming duplicate indexed pages.
 */
function oar_innovation_tip_search_is_current_page() {
    $queried_object = get_queried_object();
    if (!($queried_object instanceof WP_Post)) {
        return false;
    }

    $contains_shortcode = has_shortcode(
        $queried_object->post_content,
        OAR_INNOVATION_SEARCH_SHORTCODE
    );

    // PTB and other builders may store shortcode modules in post meta.
    if (!$contains_shortcode) {
        $shortcode_marker = '[' . OAR_INNOVATION_SEARCH_SHORTCODE;
        $metadata = get_post_meta($queried_object->ID);
        foreach ($metadata as $values) {
            foreach ((array) $values as $value) {
                if (
                    is_string($value)
                    && strpos($value, $shortcode_marker) !== false
                ) {
                    $contains_shortcode = true;
                    break 2;
                }
            }
        }
    }

    return (bool) apply_filters(
        'oar_innovation_tip_search_is_current_page',
        $contains_shortcode,
        $queried_object
    );
}

function oar_innovation_tip_search_robots($robots) {
    if (oar_innovation_tip_search_request_value('it_search') !== '1') {
        return $robots;
    }

    if (!oar_innovation_tip_search_is_current_page()) {
        return $robots;
    }

    $robots['noindex'] = true;
    return $robots;
}
add_filter('wp_robots', 'oar_innovation_tip_search_robots');
