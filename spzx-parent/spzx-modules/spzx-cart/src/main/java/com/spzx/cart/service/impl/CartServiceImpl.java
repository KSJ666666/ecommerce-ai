package com.spzx.cart.service.impl;

import com.spzx.cart.api.domain.CartInfo;
import com.spzx.cart.service.ICartService;
import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.context.SecurityContextHolder;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.exception.ServiceException;
import com.spzx.product.api.RemoteProductService;
import com.spzx.product.api.domain.ProductSku;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Date;

@Service
@Slf4j
public class CartServiceImpl implements ICartService {

    @Autowired
    RedisTemplate redisTemplate;

    @Autowired
    private RemoteProductService productService;

    @Override
    public void add2Cart(Long skuId, Integer num) {
        String cartKey = getCartKey();
        //从缓存中查询购物车详情
        CartInfo cartInfo =(CartInfo) redisTemplate.opsForHash().get(cartKey, String.valueOf(skuId));
        if (cartInfo != null){ //此商品已经加入购物车了,只需要改变数量即可
            log.info("商品已经加入购物车了");
            cartInfo.setSkuNum(Math.min(cartInfo.getSkuNum() + num,99));
        }
        else { //证明此商品是第一次加入购物车，需要给前端返回购物详情
            CartInfo cartInfo1 = new CartInfo();
            //设置购物车中商品数量为1
            cartInfo1.setSkuNum(1);
            //设置商品skuID
            cartInfo1.setSkuId(skuId);
            //设置添加购物车的时间
            cartInfo1.setCreateTime(new Date());
            //设置添加购物车的用户的名字
            cartInfo1.setCreateBy(SecurityContextHolder.getUserName());
            //远程调用商品微服务，获取sku详情
            R<ProductSku> productSku = productService.getProductSku(skuId, SecurityConstants.INNER);
            if (productSku.getCode() == R.FAIL){//如果调用失败
                throw new ServiceException(productSku.getMsg());
            }
            //获取商品信息
            ProductSku productSku1 = productSku.getData();
            //设置商品信息
            cartInfo1.setSkuName(productSku1.getSkuName());
            cartInfo1.setThumbImg(productSku1.getThumbImg());
            //设置放入购物车时的价格
            cartInfo1.setCartPrice(productSku1.getSalePrice());
            //设置商品Sku的实时价格
            cartInfo1.setSkuPrice(productSku1.getSalePrice());

        }
        redisTemplate.opsForHash().put(cartKey,String.valueOf(skuId),cartInfo);

    }
    /**
     * 设置购物车key
     * @return
     */
    public String getCartKey(){
        Long userId = SecurityContextHolder.getUserId();
        return "user:cart"+userId;
    }
}