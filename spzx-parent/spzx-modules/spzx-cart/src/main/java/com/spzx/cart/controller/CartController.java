package com.spzx.cart.controller;

import com.spzx.cart.service.ICartService;
import com.spzx.common.core.context.SecurityContextHolder;
import com.spzx.common.core.web.controller.BaseController;
import com.spzx.common.core.web.domain.AjaxResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "购物车接口")
@RestController
@RequestMapping
public class CartController extends BaseController {

    @Autowired
    private ICartService cartService;

    @Autowired
    private RedisTemplate redisTemplate;


    @Operation(description = "添加购物车操作")
    @GetMapping("addToCart/{skuId}/{num}")
    public AjaxResult add2cart(@PathVariable Long skuId,@PathVariable Integer num){
        cartService.add2Cart(skuId,num);
        return success();
    }

}