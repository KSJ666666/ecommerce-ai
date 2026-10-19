package com.spzx.order.receiver;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.spzx.common.rabbit.constant.MqConst;
import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.service.IOrderInfoService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import com.rabbitmq.client.Channel;
import org.springframework.amqp.rabbit.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Slf4j
@Component
public class OrderReceiver {

    @Autowired
    private IOrderInfoService orderInfoService;

    @Autowired
    private RabbitService rabbitService;

    @RabbitListener(bindings = @QueueBinding(
            value = @Queue(MqConst.QUEUE_CANCEL_ORDER),
            exchange = @Exchange(
                    value = MqConst.EXCHANGE_CANCEL_ORDER,
                    type = "x-delayed-message",
                    arguments = @Argument(name = "x-delayed-type",value = "direct")
            ),
            key = MqConst.ROUTING_CANCEL_ORDER

    ))
    /**
     * version1.0
     * 接收订单取消消息,消息队列中存放orderId，表示订单ID
     */
    public void receiverMessage(Message message,Channel channel) {
        Long deliveryTag = message.getMessageProperties().getDeliveryTag();
        try {
            String orderId = new String(message.getBody());

            orderInfoService.update(new LambdaUpdateWrapper<OrderInfo>()
                            .eq(OrderInfo::getId, orderId)
                            .eq(OrderInfo::getOrderStatus, 0)
                            .set(OrderInfo::getOrderStatus, -1)
            );
            channel.basicAck(deliveryTag, false);
        } catch (IOException e) {
            e.printStackTrace();

            //签收失败：requeue=true 重新放回队列（会再次投递）

            try {
                channel.basicNack(deliveryTag, false, true);
            } catch (IOException ex) {
                throw new RuntimeException(ex);
            }
        }

    }

}