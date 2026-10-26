package com.spzx.order.domain.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 面向 AI 客服的订单视图。
 *
 * <p>为什么要单独建这么一个 VO，而不是让客服直接解析 OrderInfo：
 * 订单聚合根里有行政区划编码、优惠券、审计字段等一堆客服根本用不上的东西，
 * 一旦对方按实体字段名写死逻辑，后台改一个字段名就会把 AI 链路打挂。
 * 这里把「客服能用得上的那几项」固化成稳定契约，字段增减只影响本类。</p>
 */
@Data
@Schema(description = "AI 客服订单视图")
public class AiOrderView {

    @Schema(description = "订单号")
    private String orderNo;

    @Schema(description = "订单状态：0待付款 1待发货 2已发货 3已完成 -1已取消")
    private Integer orderStatus;

    @Schema(description = "可直接面向用户播报的状态说明")
    private String statusDesc;

    @Schema(description = "订单总额")
    private BigDecimal totalAmount;

    @Schema(description = "收货人")
    private String receiverName;

    @Schema(description = "收货人手机号（已脱敏）")
    private String receiverPhoneMasked;

    @Schema(description = "收货地址")
    private String receiverAddress;

    @Schema(description = "下单时间，格式 yyyy-MM-dd HH:mm")
    private String createTime;

    @Schema(description = "订单商品明细")
    private List<Item> items;

    @Data
    @Schema(description = "AI 客服订单商品明细")
    public static class Item {

        @Schema(description = "商品 skuId")
        private Long productId;

        @Schema(description = "商品名称（下单时的快照）")
        private String title;

        @Schema(description = "数量")
        private Integer quantity;

        @Schema(description = "成交单价")
        private BigDecimal price;
    }
}
