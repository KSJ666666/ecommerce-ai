package com.spzx.cart.service;

import com.spzx.cart.api.domain.CartInfo;

import java.util.List;

public interface ICartService {

    void add2Cart(Long skuId, Integer num);

    List<CartInfo> cartList();

    void checkCart(Long skuId, Integer status);

    void deleteCart(Long skuId);

    void clearCart();

    void allCheckCart(Integer status);

    List<CartInfo> getCheckedCartInfo();
}
