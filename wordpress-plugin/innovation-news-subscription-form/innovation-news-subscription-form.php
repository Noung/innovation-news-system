<?php
/**
 * Plugin Name: Innovation News Subscription Form
 * Description: Renders a benefit-based Innovation News email subscription form.
 * Version: 1.0.0
 * Requires at least: 4.9
 * Requires PHP: 5.6
 * Author: สำนักวิทยบริการ มหาวิทยาลัยสงขลานครินทร์
 */

if (!defined('ABSPATH')) {
    exit;
}

function oar_innovation_subscription_benefits() {
    return array(
        'competitiveness' => 'ความสามารถในการแข่งขัน',
        'cost-efficiency' => 'การลดต้นทุนและเพิ่มประสิทธิภาพ',
        'digital-transformation' => 'การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน',
        'skills-learning' => 'การพัฒนาทักษะและการเรียนรู้',
        'ai-advanced-technology' => 'การใช้งาน AI และเทคโนโลยีขั้นสูง',
        'security-privacy' => 'ความปลอดภัยและความเป็นส่วนตัว',
        'innovation-change' => 'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
        'trends-market-adaptation' => 'การปรับตัวต่อเทรนด์และตลาด',
        'data-management-analytics' => 'การจัดการข้อมูลและวิเคราะห์ข้อมูล',
        'customer-experience-service' => 'การสร้างประสบการณ์ลูกค้าและบริการ',
        'connectivity-collaboration' => 'การเชื่อมต่อและการทำงานร่วมกัน',
        'technology-infrastructure' => 'การพัฒนาเทคโนโลยีและโครงสร้าง',
        'innovation-startup-support' => 'การสนับสนุนนวัตกรรมและสตาร์ทอัพ',
        'blockchain-fintech' => 'การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน',
        'green-technology-sustainability' => 'การใช้เทคโนโลยีสีเขียวและยั่งยืน',
        'healthcare-hospital-care' => 'การพัฒนาสุขภาพและการดูแลโรงพยาบาล',
        'generative-ai' => 'การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์',
        'education-smart-city' => 'การพัฒนาภาคศึกษาและเมืองอัจฉริยะ',
        'digital-business' => 'การทำธุรกิจในยุคดิจิทัล',
        'research-knowledge-development' => 'การวิจัยและพัฒนาองค์ความรู้',
    );
}

function oar_innovation_subscription_api_url() {
    $url = defined('OAR_INNOVATION_SUBSCRIPTION_API_URL')
        ? OAR_INNOVATION_SUBSCRIPTION_API_URL
        : '';
    $url = apply_filters('oar_innovation_subscription_api_url', $url);
    return esc_url_raw($url);
}

function oar_innovation_subscription_form_shortcode() {
    static $instance = 0;
    $instance++;
    $api_url = oar_innovation_subscription_api_url();
    $form_id = 'oar-innovation-subscription-' . $instance;
    $status_id = $form_id . '-status';

    if (!$api_url || strpos($api_url, 'https://') !== 0) {
        if (current_user_can('manage_options')) {
            return '<p>' . esc_html(
                'Innovation subscription form is not configured.'
            ) . '</p>';
        }
        return '';
    }

    ob_start();
    ?>
    <form
        id="<?php echo esc_attr($form_id); ?>"
        class="oar-innovation-subscription"
        data-api-url="<?php echo esc_url($api_url); ?>"
        novalidate
    >
        <p>
            <label>
                <?php echo esc_html('อีเมล'); ?>
                <input type="email" name="email" required maxlength="254">
            </label>
        </p>
        <fieldset>
            <legend><?php echo esc_html('เลือกหัวข้อประโยชน์ต่อองค์กรที่ต้องการติดตาม'); ?></legend>
            <?php foreach (oar_innovation_subscription_benefits() as $slug => $name) : ?>
                <label style="display:block">
                    <input type="checkbox" name="benefits[]" value="<?php echo esc_attr($slug); ?>">
                    <?php echo esc_html($name); ?>
                </label>
            <?php endforeach; ?>
        </fieldset>
        <p>
            <label>
                <input type="checkbox" name="consent" value="1" required>
                <?php echo esc_html('ฉันยินยอมรับข่าวสารด้านนวัตกรรมทางอีเมล และสามารถยกเลิกได้ทุกเมื่อ'); ?>
            </label>
        </p>
        <button type="submit"><?php echo esc_html('สมัครรับข่าวสาร'); ?></button>
        <p id="<?php echo esc_attr($status_id); ?>" role="status" aria-live="polite"></p>
    </form>
    <script>
    (function () {
        var form = document.getElementById('<?php echo esc_js($form_id); ?>');
        var status = document.getElementById('<?php echo esc_js($status_id); ?>');
        if (!form || !status) { return; }
        form.onsubmit = function (event) {
            event.preventDefault();
            var selected = form.querySelectorAll('input[name="benefits[]"]:checked');
            if (!form.email.value || !form.consent.checked || selected.length === 0) {
                status.textContent = '<?php echo esc_js('กรุณากรอกอีเมล เลือกหัวข้ออย่างน้อยหนึ่งหัวข้อ และยอมรับเงื่อนไข'); ?>';
                return;
            }
            var benefits = [];
            for (var index = 0; index < selected.length; index++) {
                benefits.push(selected[index].value);
            }
            var request = new XMLHttpRequest();
            request.open('POST', form.getAttribute('data-api-url'), true);
            request.setRequestHeader('Content-Type', 'application/json');
            request.onreadystatechange = function () {
                if (request.readyState !== 4) { return; }
                status.textContent = request.status >= 200 && request.status < 300
                    ? '<?php echo esc_js('หากอีเมลนี้รับข่าวสารได้ ระบบจะส่งลิงก์ยืนยันให้'); ?>'
                    : '<?php echo esc_js('ไม่สามารถส่งคำขอได้ โปรดลองอีกครั้งภายหลัง'); ?>';
            };
            request.send(JSON.stringify({
                email: form.email.value,
                benefits: benefits,
                consent: true,
                consent_version: 'v1'
            }));
        };
    }());
    </script>
    <?php
    return ob_get_clean();
}
add_shortcode('innovation_news_subscribe', 'oar_innovation_subscription_form_shortcode');
