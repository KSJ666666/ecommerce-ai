package com.spzx.product.service.impl;

import com.spzx.common.core.utils.StringUtils;
import com.spzx.product.service.TestService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Service
public class TestServiceImpl implements TestService {

    @Autowired
    StringRedisTemplate stringRedisTemplate; //SpringBoot自动化配置

    @Override
    public void testLock() {

        // 查询Redis中的num值
        String value = (String) this.stringRedisTemplate.opsForValue().get("num");
        // 没有该值return
        if (StringUtils.isBlank(value)) {
            return;
        }
        // 有值就转成成int
        int num = Integer.parseInt(value);
        // 把Redis中的num值+1
        this.stringRedisTemplate.opsForValue().set("num", String.valueOf(++num)); //  java 中  ++ 操作不是原子的。

    }

}
