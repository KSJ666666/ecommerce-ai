package com.spzx.order.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.domain.vo.AiOrderView;
import com.spzx.order.domain.vo.OrderForm;
import com.spzx.order.domain.vo.TradeVo;
import io.swagger.v3.oas.models.security.SecurityScheme;

import java.util.List;
import java.util.Map;

public interface IOrderInfoService extends IService<OrderInfo> {
    /**
     * 查询订单列表
     *
     * @param orderInfo 订单
     * @return 订单集合
     */
    public List<OrderInfo> selectOrderInfoList(OrderInfo orderInfo);

    /**
     * 查询订单
     *
     * @param id 订单主键
     * @return 订单
     */
    public OrderInfo selectOrderInfoById(Long id);

    TradeVo trade();

    TradeVo buy(Long skuId);

    Long submit(OrderForm orderForm);

    void cancelOrder(Long orderId,Integer flag);

    List<OrderInfo> getMyOrderInfoList(String orderStatus);

    OrderInfo getOrderInfoByOrderNo(String orderNo);

    /**
     * 根据订单号获取物流状态（供客服中枢等内部服务远程调用）
     * 商城未接入真实承运商，库里没有运单号，物流状态按订单状态与发货/签收时间推导
     */
    Map<String, Object> getLogisticsByOrderNo(String orderNo);

    /**
     * 根据订单号组装面向 AI 客服的订单视图（供客服中枢远程调用）
     *
     * @param orderNo 订单号
     * @return 订单视图；订单不存在时返回 null
     */
    AiOrderView getAiOrderView(String orderNo);

    /**
     * 支付成功后修改订单状态（供支付微服务远程调用）
     * @return true=修改成功；false=订单不是待付款状态
     */
    boolean updateOrderStatus(String orderNo, Integer orderStatus);
}