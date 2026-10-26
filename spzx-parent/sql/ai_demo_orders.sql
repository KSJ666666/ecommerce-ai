-- =============================================================
-- AI 客服联调用的演示订单（可选）
--
-- 为什么需要这份脚本：
--   1. spzx 里真实下单产生的 order_no 是 32 位 UUID，让用户在对话框里手打不现实；
--      这里造几个可读的订单号（SP202610260001），演示时直接说订单号就能查。
--   2. 库里的历史订单基本都被取消了（order_status = -1），客服答出来全是"已取消"，
--      四种状态各来一单，才能看出状态文案/物流话术的区别。
--
-- 幂等：先按前缀删掉旧演示单再插入，可以反复执行。
-- 用法：mysql -uroot -p --default-character-set=utf8mb4 < sql/ai_demo_orders.sql
-- =============================================================

USE `spzx-order`;

-- 1. 清理旧的演示数据（只动 SP2026 开头的单，不碰真实订单）
DELETE FROM order_item
WHERE order_id IN (SELECT id FROM order_info WHERE order_no LIKE 'SP2026%');
DELETE FROM order_info WHERE order_no LIKE 'SP2026%';

-- 2. 待发货：已支付，商家备货中
INSERT INTO order_info (user_id, nick_name, order_no, total_amount, coupon_amount, original_total_amount,
                        feight_fee, order_status, receiver_name, receiver_phone, receiver_tag_name,
                        receiver_province, receiver_city, receiver_district, receiver_address,
                        payment_time, create_time, create_by)
VALUES (1, '晴天', 'SP202610260001', 1999.00, 0.00, 1999.00,
        0.00, 1, '孔少杰', '13700032456', '家',
        '410000', '410700', '410711', '河南省新乡市牧野区建设东路46号',
        DATE_SUB(NOW(), INTERVAL 6 HOUR), DATE_SUB(NOW(), INTERVAL 6 HOUR), '13700032456');
SET @o1 = (SELECT id FROM order_info WHERE order_no = 'SP202610260001' LIMIT 1);
INSERT INTO order_item (order_id, sku_id, sku_name, thumb_img, sku_price, sku_num)
VALUES (@o1, 3, '小米 红米Note10 5G手机 红色 + 8G',
        'http://139.198.127.41:9000/spzx/20230525/665832167-4_u_1.jpg', 1999.00, 1);

-- 3. 已发货：有发货时间，物流话术才带得上时间
INSERT INTO order_info (user_id, nick_name, order_no, total_amount, coupon_amount, original_total_amount,
                        feight_fee, order_status, receiver_name, receiver_phone, receiver_tag_name,
                        receiver_province, receiver_city, receiver_district, receiver_address,
                        payment_time, delivery_time, create_time, create_by)
VALUES (1, '晴天', 'SP202610260002', 3999.00, 0.00, 3999.00,
        0.00, 2, '孔少杰', '13700032456', '公司',
        '410000', '410700', '410711', '河南省新乡市牧野区建设东路46号',
        DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_SUB(NOW(), INTERVAL 3 DAY), '13700032456');
SET @o2 = (SELECT id FROM order_info WHERE order_no = 'SP202610260002' LIMIT 1);
INSERT INTO order_item (order_id, sku_id, sku_name, thumb_img, sku_price, sku_num)
VALUES (@o2, 7, '华为笔记本 8G',
        'http://139.198.127.41:9000/spzx/20230525/665832167-4_u_1.jpg', 3999.00, 1);

-- 4. 已完成：签收时间齐全
INSERT INTO order_info (user_id, nick_name, order_no, total_amount, coupon_amount, original_total_amount,
                        feight_fee, order_status, receiver_name, receiver_phone, receiver_tag_name,
                        receiver_province, receiver_city, receiver_district, receiver_address,
                        payment_time, delivery_time, receive_time, create_time, create_by)
VALUES (1, '晴天', 'SP202610260003', 4999.00, 0.00, 4999.00,
        0.00, 3, '孔少杰', '13700032456', '家',
        '410000', '410700', '410711', '河南省新乡市牧野区建设东路46号',
        DATE_SUB(NOW(), INTERVAL 10 DAY), DATE_SUB(NOW(), INTERVAL 8 DAY), DATE_SUB(NOW(), INTERVAL 5 DAY),
        DATE_SUB(NOW(), INTERVAL 10 DAY), '13700032456');
SET @o3 = (SELECT id FROM order_info WHERE order_no = 'SP202610260003' LIMIT 1);
INSERT INTO order_item (order_id, sku_id, sku_name, thumb_img, sku_price, sku_num)
VALUES (@o3, 8, '华为笔记本 16G',
        'http://139.198.127.41:9000/spzx/20230525/665832167-4_u_1.jpg', 4999.00, 1);

-- 5. 待付款：还没支付，物流话术应该提示"未生成物流信息"
INSERT INTO order_info (user_id, nick_name, order_no, total_amount, coupon_amount, original_total_amount,
                        feight_fee, order_status, receiver_name, receiver_phone, receiver_tag_name,
                        receiver_province, receiver_city, receiver_district, receiver_address,
                        create_time, create_by)
VALUES (1, '晴天', 'SP202610260004', 96.00, 0.00, 96.00,
        0.00, 0, '孔少杰', '13700032456', '家',
        '410000', '410700', '410711', '河南省新乡市牧野区建设东路46号',
        DATE_SUB(NOW(), INTERVAL 30 MINUTE), '13700032456');
SET @o4 = (SELECT id FROM order_info WHERE order_no = 'SP202610260004' LIMIT 1);
INSERT INTO order_item (order_id, sku_id, sku_name, thumb_img, sku_price, sku_num)
VALUES (@o4, 1, '小米 红米Note10 5G手机 白色 + 8G',
        'http://139.198.127.41:9000/spzx/20230525/665832167-5_u_1.jpg', 96.00, 1);

SELECT order_no, order_status, total_amount, receiver_address FROM order_info WHERE order_no LIKE 'SP2026%' ORDER BY order_no;
