package com.spzx.payment.service;

import java.util.Map;

public interface IAlipayService {

    /**
     * 调用支付宝下单，返回支付宝收银台链接
     * @param orderNo 订单号（不是订单主键id）
     * @return 支付宝支付页面url
     */
    String submitAlipay(String orderNo);

    /**
     * 支付宝异步回调通知支付成功后的业务处理
     * @param params 支付宝回调带过来的全部参数
     */
    void paySuccess(Map<String, String> params);
}
