package com.spzx.common.rabbit.service;

import com.spzx.common.rabbit.constant.MqConst;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class RabbitService {

    @Autowired
    private RabbitTemplate rabbitTemplate;

    /**
     * 发送消息
     *
     * @param exchange   交换机
     * @param routingKey 路由键
     * @param message    消息
     */
    public boolean sendMessage(String exchange, String routingKey, Object message) {
        rabbitTemplate.convertAndSend(exchange, routingKey, message);
        return true;
    }

    /**
     * 发送延迟消息
     *
     * @param exchange
     * @param routingKey
     * @param message
     * @return
     */
    public boolean sendDelayedMessage(String exchange, String routingKey, Object message) {
        rabbitTemplate.convertAndSend(exchange, routingKey, message,msg->{
            msg.getMessageProperties().setDelay(MqConst.CANCEL_ORDER_DELAY_TIME);
            return msg;
        });
        return true;
    }


}