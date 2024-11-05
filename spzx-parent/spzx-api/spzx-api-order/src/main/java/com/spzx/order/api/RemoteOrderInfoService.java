package com.spzx.order.api;

import com.spzx.common.core.constant.ServiceNameConstants;
import com.spzx.order.api.factory.RemoteOrderInfoFallbackFactory;
import org.springframework.cloud.openfeign.FeignClient;

@FeignClient(contextId = "remoteUserInfoService", value = ServiceNameConstants.ORDER_SERVICE, fallbackFactory = RemoteOrderInfoFallbackFactory.class)
public interface RemoteOrderInfoService {

}