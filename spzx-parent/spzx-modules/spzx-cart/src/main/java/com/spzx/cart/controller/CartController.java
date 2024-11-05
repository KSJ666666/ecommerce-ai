package com.spzx.cart.controller;

import com.spzx.cart.service.ICartService;
import com.spzx.common.core.web.controller.BaseController;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "购物车接口")
@RestController
@RequestMapping
public class CartController extends BaseController {

    @Autowired
    private ICartService cartService;

}