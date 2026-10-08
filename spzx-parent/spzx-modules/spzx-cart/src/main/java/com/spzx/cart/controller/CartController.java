package com.spzx.cart.controller;

import com.spzx.cart.api.domain.CartInfo;
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

import java.util.List;

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
    @Operation(description = "查询购物车列表")
    @GetMapping("cartList")
    public AjaxResult cartList(){
        List<CartInfo>cartInfoList = cartService.cartList();
        return success(cartInfoList);
    }
    @Operation(description = "购物车复选框选择")
    @GetMapping("checkCart/{skuId}/{status}")
    public AjaxResult checkCart(@PathVariable Long skuId,@PathVariable Integer status){
        cartService.checkCart(skuId,status);
        return success();
    }



}