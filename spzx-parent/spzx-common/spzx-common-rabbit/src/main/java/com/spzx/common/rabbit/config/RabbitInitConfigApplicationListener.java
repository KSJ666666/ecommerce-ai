package com.spzx.common.rabbit.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

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

    }


}
