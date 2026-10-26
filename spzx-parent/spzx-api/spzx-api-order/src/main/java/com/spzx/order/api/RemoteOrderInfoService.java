package com.spzx.order.api;

import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.constant.ServiceNameConstants;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.web.domain.AjaxResult;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.api.factory.RemoteOrderInfoFallbackFactory;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;

@FeignClient(contextId = "remoteOrderInfoService", value = ServiceNameConstants.ORDER_SERVICE,
        path = "/orderInfo", fallbackFactory = RemoteOrderInfoFallbackFactory.class)
public interface RemoteOrderInfoService {

    /**
     * 根据订单号查询订单信息（注意是orderNo订单号，不是订单主键id）
     * 注意：path已统一加了/orderInfo前缀，这里只需写controller里方法级的路径
     */
    @GetMapping("/inner/getOrderInfo/{orderNo}")
    R<OrderInfo> getOrderInfoByOrderNo(@PathVariable("orderNo") String orderNo,
                                       @RequestHeader(value = SecurityConstants.FROM_SOURCE) String fromSource);

    /**
     * 支付成功后修改订单状态，返回true表示修改成功
     */
    @GetMapping("/inner/updateOrderStatus/{orderNo}/{orderStatus}")
    R<Boolean> updateOrderStatus(@PathVariable("orderNo") String orderNo,
                                 @PathVariable("orderStatus") Integer orderStatus,
                                 @RequestHeader(value = SecurityConstants.FROM_SOURCE) String fromSource);

}