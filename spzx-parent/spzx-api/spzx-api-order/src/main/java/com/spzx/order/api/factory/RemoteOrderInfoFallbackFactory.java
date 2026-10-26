package com.spzx.order.api.factory;

import com.spzx.common.core.domain.R;
import com.spzx.common.core.web.domain.AjaxResult;
import com.spzx.order.api.RemoteOrderInfoService;
import com.spzx.order.api.domain.OrderInfo;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.openfeign.FallbackFactory;
import org.springframework.stereotype.Component;

@Component
public class RemoteOrderInfoFallbackFactory implements FallbackFactory<RemoteOrderInfoService> {
    private static final Logger log = LoggerFactory.getLogger(RemoteOrderInfoFallbackFactory.class);

    @Override
    public RemoteOrderInfoService create(Throwable throwable) {
        log.error("订单服务调用失败:{}", throwable.getMessage());
        return new RemoteOrderInfoService() {

            @Override
            public R<OrderInfo> getOrderInfoByOrderNo(String orderNo, String fromSource) {
                //带上入参和异常类型，否则线上只看到"远程调用失败"却不知道是哪个订单、什么原因
                log.error("远程调用订单微服务失败，orderNo={}, 异常类型={}, 原因={}",
                        orderNo, throwable.getClass().getSimpleName(), throwable.getMessage());
                return R.fail("远程调用订单微服务失败:" + throwable.getMessage());
            }

            @Override
            public R<Boolean> updateOrderStatus(String orderNo, Integer orderStatus, String fromSource) {
                log.error("远程调用订单微服务修改订单状态失败，orderNo={}, 异常类型={}, 原因={}",
                        orderNo, throwable.getClass().getSimpleName(), throwable.getMessage());
                return R.fail("远程调用订单微服务修改订单状态失败:" + throwable.getMessage());
            }
        };
    }
}