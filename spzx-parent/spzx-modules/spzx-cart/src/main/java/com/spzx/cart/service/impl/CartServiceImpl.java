package com.spzx.cart.service.impl;

import com.spzx.cart.service.ICartService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

@Service
@Slf4j
public class CartServiceImpl implements ICartService {

    @Autowired
    RedisTemplate redisTemplate;

}