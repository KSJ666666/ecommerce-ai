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
import java.util.List;
import java.util.stream.Collectors;

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
             cartInfo = new CartInfo();
            //设置购物车中商品数量为1
            cartInfo.setSkuNum(1);
            //设置商品skuID
            cartInfo.setSkuId(skuId);
            //设置添加购物车的时间
            cartInfo.setCreateTime(new Date());
            //设置添加购物车的用户的名字
            cartInfo.setCreateBy(SecurityContextHolder.getUserName());
            //远程调用商品微服务，获取sku详情
            R<ProductSku> productSku = productService.getProductSku(skuId, SecurityConstants.INNER);
            if (productSku.getCode() == R.FAIL){//如果调用失败
                throw new ServiceException(productSku.getMsg());
            }
            //获取商品信息
            ProductSku productSku1 = productSku.getData();
            //设置商品信息
            cartInfo.setSkuName(productSku1.getSkuName());
            cartInfo.setThumbImg(productSku1.getThumbImg());
            //设置放入购物车时的价格
            cartInfo.setCartPrice(productSku1.getSalePrice());
            //设置商品Sku的实时价格
            cartInfo.setSkuPrice(productSku1.getSalePrice());

        }
        redisTemplate.opsForHash().put(cartKey,String.valueOf(skuId),cartInfo);

    }

    @Override
    public void deleteCart(Long skuId) {
        String cartKey = getCartKey();

        redisTemplate.opsForHash().delete(cartKey,String.valueOf(skuId));

    }

    @Override
    public void clearCart() {
        String cartKey = getCartKey();

        redisTemplate.delete(cartKey);

    }

    @Override
    public void allCheckCart(Integer status) {
        String cartKey = getCartKey();
        List<CartInfo>cartInfos = redisTemplate.opsForHash().values(cartKey);

        cartInfos.forEach(cartInfo -> {
            cartInfo.setIsChecked(status);
            redisTemplate.opsForHash().put(cartKey,String.valueOf(cartInfo.getSkuId()),cartInfo);
        });

    }

    @Override
    public List<CartInfo> getCheckedCartInfo() {

        String cartKey = getCartKey();
        List<CartInfo>cartInfoList = redisTemplate.opsForHash().values(cartKey);
        //获取checkedId = 1的
        List<CartInfo> cartInfoCheckeds = cartInfoList.stream().filter(cartInfo -> cartInfo.getIsChecked() == 1).collect(Collectors.toList());


        return cartInfoCheckeds;
    }

    @Override
    public void clearCheckedCartInfo() {
        String cartKey = getCartKey();
        getCheckedCartInfo().forEach(cartInfo -> {
            redisTemplate.opsForHash().delete(cartKey,String.valueOf(cartInfo.getSkuId()));
        });
    }

    @Override
    public void checkCart(Long skuId, Integer status) {
        String cartKey = getCartKey();

          CartInfo cartInfo =(CartInfo) redisTemplate.opsForHash().get(cartKey, String.valueOf(skuId));

          cartInfo.setIsChecked(status);

          redisTemplate.opsForHash().put(cartKey,String.valueOf(skuId),cartInfo);


    }

    @Override
    public List<CartInfo> cartList() {
        String cartKey = getCartKey();

        List<CartInfo>cartInfoList = redisTemplate.opsForHash().values(cartKey);
        //更新数据库中真实的商品价格
        cartInfoList.forEach(cartInfo -> {
            R<ProductSku> productSkuR = productService.getProductSku(cartInfo.getSkuId(), SecurityConstants.INNER);

            if (productSkuR.getCode() == R.FAIL){
                throw new RuntimeException(productSkuR.getMsg());

            }

            ProductSku productSku = productSkuR.getData();
            cartInfo.setSkuPrice(productSku.getSalePrice());

            redisTemplate.opsForHash().put(cartKey,String.valueOf(cartInfo.getSkuId()),cartInfo);
        });

        return cartInfoList;
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