package com.spzx.order.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.mysql.cj.x.protobuf.MysqlxCrud;
import com.spzx.cart.api.RemoteCartService;
import com.spzx.cart.api.domain.CartInfo;
import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.exception.ServiceException;
import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.api.domain.OrderItem;
import com.spzx.order.domain.vo.TradeVo;
import com.spzx.order.mapper.OrderInfoMapper;
import com.spzx.order.mapper.OrderItemMapper;
import com.spzx.order.mapper.OrderLogMapper;
import com.spzx.order.service.IOrderInfoService;
import com.spzx.product.api.RemoteProductService;
import com.spzx.user.api.RemoteUserAddressService;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class OrderInfoServiceImpl extends ServiceImpl<OrderInfoMapper, OrderInfo> implements IOrderInfoService {
    @Autowired
    private OrderInfoMapper orderInfoMapper;

    @Autowired
    private OrderItemMapper orderItemMapper;

    @Autowired
    private OrderLogMapper orderLogMapper;

    @Autowired
    private RemoteCartService remoteCartService;

    @Autowired
    private RedisTemplate redisTemplate;

    @Autowired
    private RemoteProductService remoteProductService;

    @Autowired
    private RemoteUserAddressService remoteUserAddressService;

    @Autowired
    RabbitService rabbitService; //来自于公共模块：spzx-common-rabbit

    /**
     * 查询订单列表
     *
     * @param orderInfo 订单
     * @return 订单
     */
    @Override
    public List<OrderInfo> selectOrderInfoList(OrderInfo orderInfo) {
        return orderInfoMapper.selectOrderInfoList(orderInfo);
    }

    /**
     * 查询订单
     *
     * @param id 订单主键
     * @return 订单
     */
    @Override
    public OrderInfo selectOrderInfoById(Long id) {
        OrderInfo orderInfo = orderInfoMapper.selectById(id);
        List<OrderItem> orderItemList = orderItemMapper.selectList(new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, id));
        orderInfo.setOrderItemList(orderItemList);
        return orderInfo;
    }

    @Override
    public TradeVo trade() {
        TradeVo tradeVo = new TradeVo();
        //结算商品列表
        R<List<CartInfo>> checkedCartInfo = remoteCartService.getCheckedCartInfo(SecurityConstants.INNER);
        if (R.FAIL == checkedCartInfo.getCode()){
            throw new ServiceException(checkedCartInfo.getMsg());
        }
        List<OrderItem>orderItemList = new ArrayList<>();
        List<CartInfo> cartInfoList = checkedCartInfo.getData();
        if (!CollectionUtils.isEmpty(cartInfoList)){
            orderItemList = cartInfoList.stream().map(cartInfo -> {
                OrderItem orderItem = new OrderItem();
                BeanUtils.copyProperties(cartInfo, orderItem);
                return orderItem;
            }).collect(Collectors.toList());

            tradeVo.setOrderItemList(orderItemList);

            String tradeNo = UUID.randomUUID().toString().replace("-", "");
            tradeVo.setTradeNo(tradeNo);
            //计算总的需要支付的价钱
            BigDecimal bigDecimal = new BigDecimal(0);
            for (OrderItem orderItem : orderItemList) {
                BigDecimal skuPrice = orderItem.getSkuPrice();
                Integer skuNum = orderItem.getSkuNum();
                bigDecimal = bigDecimal.add(skuPrice.multiply(new BigDecimal(skuNum))) ;
            }
            tradeVo.setTotalAmount(bigDecimal);

        }

        return tradeVo;
    }

}