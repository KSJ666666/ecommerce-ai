package com.spzx.product.domain.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.util.Map;

/**
 * 面向 AI 客服的 SKU 视图。
 *
 * <p>SKU 的库存并不在 product_sku 表里（在 sku_stock 表，且分 total/lock/available），
 * 客服问「还有货吗」需要的是可用库存，所以这里把两张表拼成一个可直接播报的视图，
 * 避免调用方自己算库存、自己拼状态文案。</p>
 */
@Data
@Schema(description = "AI 客服 SKU 视图")
public class AiSkuView {

    @Schema(description = "商品 skuId")
    private Long productId;

    @Schema(description = "SKU 名称")
    private String title;

    @Schema(description = "商品名称（SPU 级）")
    private String productName;

    @Schema(description = "售价")
    private BigDecimal price;

    @Schema(description = "市场价")
    private BigDecimal marketPrice;

    @Schema(description = "可用库存")
    private Integer stockNum;

    @Schema(description = "库存状态文案")
    private String stockStatus;

    @Schema(description = "规格描述")
    private String specs;

    @Schema(description = "主图")
    private String imageUrl;

    @Schema(description = "结构化规格（sku_spec 解析后的键值对，解析不了就为空）")
    private Map<String, Object> attributes;
}
