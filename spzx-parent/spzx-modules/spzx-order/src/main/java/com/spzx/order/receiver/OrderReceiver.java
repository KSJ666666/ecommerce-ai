package com.spzx.order.receiver;

import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.service.IOrderInfoService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class OrderReceiver {

    @Autowired
    private IOrderInfoService orderInfoService;

    @Autowired
    private RabbitService rabbitService;

}