package com.spzx.common.rabbit.config;

import com.alibaba.fastjson2.JSON;
import com.spzx.common.rabbit.entity.GuiguCorrelationData;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import java.util.concurrent.TimeUnit;

/**
 * 服务器启动时，执行rabbitTemplate初始化，设置确认函数和回退函数
 * ApplicationEvent      一些子事件的父类。
 * ApplicationReadyEvent 具体子事件。表示应用程序启动好，IOC容器初始化好，存在相关bean对象了。再进行相关的初始化。
 * 也可以使用相关的注解替代： @EventListener
 */
@Slf4j
@Component
public class RabbitInitConfigApplicationListener implements ApplicationListener<ApplicationReadyEvent> {

    @Autowired
    RabbitTemplate rabbitTemplate;

    @Autowired
    RedisTemplate redisTemplate;


    @Override
    public void onApplicationEvent(ApplicationReadyEvent event) {
        this.setUpInitRabbitTemplete();
    }


    private void setUpInitRabbitTemplete() {
        // 路由失败时回退：消息到了交换机但找不到队列，必须退回

        rabbitTemplate.setMandatory(true);

        // 确认模式回调：消息是否成功到达交换机（成功失败都回调）

        rabbitTemplate.setConfirmCallback((correlationData, ack, cause) -> {

            if(ack) {

                log.info("消息成功发送到交换机: {}", correlationData);

            } else {

                log.error("消息发送到交换机失败: {}", cause);

                this.retrySendMsg((GuiguCorrelationData) correlationData);

            }

        });

        // 退回模式回调：已到交换机，但路由到队列失败

        rabbitTemplate.setReturnsCallback(returned -> {

            log.error("消息路由到队列失败: {}", returned.getMessage());

            Message returnedMessage = returned.getMessage();

            // 从消息头取出发送时写入的 UUID（Redis 的 key）

            String redisKey = returnedMessage.getMessageProperties()

                    .getHeader("spring_returned_message_correlation");

            String json = (String) redisTemplate.opsForValue().get(redisKey);

            GuiguCorrelationData data = JSON.parseObject(json, GuiguCorrelationData.class);

            this.retrySendMsg(data);

        });

    }
    private void retrySendMsg(GuiguCorrelationData correlationData) {

        // 取出当前重试次数，未超过 3 次则继续重试

        Integer retryCount = correlationData.getRetryCount();

        if(retryCount >= 3) {

            // 生产者超过最大重试次数，消息可以落库，人工处理（发邮件/短信通知运维）

            log.error("生产者超过最大重试次数，消息请人工处理: {}", correlationData);

            return;

        }

        // 重试次数 +1

        retryCount++;

        correlationData.setRetryCount(retryCount);

        // 重新写回 Redis，相当于续期（又是 10 分钟）

        redisTemplate.opsForValue().set(correlationData.getId(),

                JSON.toJSONString(correlationData), 10, TimeUnit.MINUTES);

        // 区分普通消息 / 延迟消息，按原参数重发

        if(correlationData.isDelay()) {

            rabbitTemplate.convertAndSend(correlationData.getExchange(),

                    correlationData.getRoutingKey(), correlationData.getMessage(),

                    message -> { message.getMessageProperties().setDelay(correlationData.getDelayTime()); return message; },

                    correlationData);

        } else {

            rabbitTemplate.convertAndSend(correlationData.getExchange(),

                    correlationData.getRoutingKey(), correlationData.getMessage(), correlationData);

        }

    }




}



