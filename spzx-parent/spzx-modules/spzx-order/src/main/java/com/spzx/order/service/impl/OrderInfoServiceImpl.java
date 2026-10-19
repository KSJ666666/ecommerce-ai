package com.spzx.order.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.spzx.cart.api.RemoteCartService;
import com.spzx.cart.api.domain.CartInfo;
import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.context.SecurityContextHolder;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.exception.ServiceException;
import com.spzx.common.rabbit.constant.MqConst;
import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.api.domain.OrderItem;
import com.spzx.order.domain.OrderLog;
import com.spzx.order.domain.vo.OrderForm;
import com.spzx.order.domain.vo.TradeVo;
import com.spzx.order.mapper.OrderInfoMapper;
import com.spzx.order.mapper.OrderItemMapper;
import com.spzx.order.mapper.OrderLogMapper;
import com.spzx.order.service.IOrderInfoService;
import com.spzx.order.service.OrderItemService;
import com.spzx.product.api.RemoteProductService;
import com.spzx.product.api.domain.ProductDetails;
import com.spzx.product.api.domain.ProductSku;
import com.spzx.user.api.RemoteUserAddressService;
import com.spzx.user.domain.UserAddress;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
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

    @Autowired
    private OrderItemService orderItemService;

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
        if (R.FAIL == checkedCartInfo.getCode()) {
            throw new ServiceException(checkedCartInfo.getMsg());
        }
        List<OrderItem> orderItemList = new ArrayList<>();
        List<CartInfo> cartInfoList = checkedCartInfo.getData();
        if (!CollectionUtils.isEmpty(cartInfoList)) {
            orderItemList = cartInfoList.stream().map(cartInfo -> {
                OrderItem orderItem = new OrderItem();
                BeanUtils.copyProperties(cartInfo, orderItem);
                orderItem.setId(null);
                //清空购物车带来的时间，否则订单项的创建时间会显示成加入购物车的时间
                orderItem.setCreateTime(null);
                orderItem.setUpdateTime(null);
                return orderItem;
            }).collect(Collectors.toList());

            tradeVo.setOrderItemList(orderItemList);

            String tradeNo = UUID.randomUUID().toString().replace("-", "");
            tradeVo.setTradeNo(tradeNo);

            redisTemplate.opsForValue().set("user:trade:" + tradeNo, tradeNo,5, TimeUnit.MINUTES);
            //计算总的需要支付的价钱
            BigDecimal bigDecimal = new BigDecimal(0);
            for (OrderItem orderItem : orderItemList) {
                BigDecimal skuPrice = orderItem.getSkuPrice();
                Integer skuNum = orderItem.getSkuNum();
                bigDecimal = bigDecimal.add(skuPrice.multiply(new BigDecimal(skuNum)));
            }
            tradeVo.setTotalAmount(bigDecimal);

        }

        return tradeVo;
    }

    @Override
    public TradeVo buy(Long skuId) {
        TradeVo tradeVo = new TradeVo();
        R<ProductSku> productSkuR = remoteProductService.getProductSku(skuId, SecurityConstants.INNER);
        if (R.FAIL == productSkuR.getCode()) {
            throw new ServiceException(productSkuR.getMsg());
        }
        ProductSku productSku = productSkuR.getData();

        OrderItem orderItem = new OrderItem();
        BeanUtils.copyProperties(productSku, orderItem);
        orderItem.setId(null); // Set the ID to null to generate a new one
        //清空从商品sku复制过来的时间，否则入库时会沿用sku的创建时间
        orderItem.setCreateTime(null);
        orderItem.setUpdateTime(null);


        orderItem.setSkuNum(1);
        orderItem.setSkuPrice(productSku.getSalePrice());

        tradeVo.setOrderItemList(List.of(orderItem));

        tradeVo.setTotalAmount(productSku.getSalePrice());

        String tradeNo = UUID.randomUUID().toString().replace("-", "");

        tradeVo.setTradeNo(tradeNo);
        redisTemplate.opsForValue().set("user:trade:" + tradeNo, tradeNo,5, TimeUnit.MINUTES);

        return tradeVo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long submit(OrderForm orderForm) {
        //1.防止订单重复提交
        String tradeNo = orderForm.getTradeNo();
        String tradeNoStr = (String) redisTemplate.opsForValue().get("user:trade:" + tradeNo);
        if (!tradeNo.equals(tradeNoStr)) {
            throw new ServiceException("订单重复提交或订单超时");
        }
        redisTemplate.delete("user:trade:" + tradeNo);
        String remark = orderForm.getRemark();
        BigDecimal feightFee = orderForm.getFeightFee();
        Long userAddressId = orderForm.getUserAddressId();
        //3.组装订单基本信息
        OrderInfo orderInfo = new OrderInfo();
        List<OrderItem> orderItemList = orderForm.getOrderItemList();
        orderInfo.setOrderItemList(orderItemList);

        orderInfo.setOrderNo(UUID.randomUUID().toString().replace("-", ""));

        orderInfo.setOrderStatus(0);

        orderInfo.setUserId(SecurityContextHolder.getUserId());
        orderInfo.setNickName(SecurityContextHolder.getUserName());
        orderInfo.setCreateBy(SecurityContextHolder.getUserName());

        orderInfo.setCouponAmount(new BigDecimal(0));

        orderInfo.setFeightFee(feightFee);

        orderInfo.setRemark(remark);
        //2.校验订单项：查询商品实时价格、校验库存，并计算订单总金额
        StringBuffer sb = new StringBuffer();
        BigDecimal totalAmount = new BigDecimal(0);
        for (OrderItem orderItem : orderItemList) {
            Long skuId = orderItem.getSkuId();
            Integer skuNum = orderItem.getSkuNum();
            BigDecimal skuPrice = orderItem.getSkuPrice();

            //2.1查询商品实时价格，前端传来的价格不可信，必须以后端查到的实时价为准
            R<ProductSku> productSkuR = remoteProductService.getProductSku(skuId, SecurityConstants.INNER);
            if (R.FAIL == productSkuR.getCode()) {
                throw new ServiceException(productSkuR.getMsg());
            }
            BigDecimal salePrice = productSkuR.getData().getSalePrice();
            //实时价与结算页展示的价格不一致时，提示用户回到结算页重新下单，避免看到的价和实际扣款不一致
            BigDecimal diff = salePrice.subtract(skuPrice);
            if (diff.compareTo(BigDecimal.ZERO) > 0) {
                sb.append(orderItem.getSkuName()).append("涨价").append(diff).append("元，请去结算页面重新下单；");
            } else if (diff.compareTo(BigDecimal.ZERO) < 0) {
                sb.append(orderItem.getSkuName()).append("降价").append(diff.abs()).append("元，请去结算页面重新下单；");
            }

            //2.2校验库存并锁定库存，返回非空说明库存不足
            R<String> stockR = remoteProductService.checkStockAndSubStock(skuId, skuNum, SecurityConstants.INNER);
            if (R.FAIL == stockR.getCode()) {
                throw new ServiceException(stockR.getMsg());
            }
            if (stockR.getData() != null && !stockR.getData().isEmpty()) {
                throw new ServiceException(stockR.getData());
            }

            //2.3累加金额小计
            totalAmount = totalAmount.add(skuPrice.multiply(new BigDecimal(skuNum)));
        }
        //价格发生变动，中断下单
        if (sb.length() > 0) {
            throw new ServiceException(sb.toString());
        }
        orderInfo.setTotalAmount(totalAmount);
        orderInfo.setOriginalTotalAmount(totalAmount);
        //远程调用用户微服务获取用户地址
        R<UserAddress> userAddress = remoteUserAddressService.getUserAddress(userAddressId, SecurityConstants.INNER);
        if (R.FAIL == userAddress.getCode())
            throw new ServiceException(userAddress.getMsg());

        UserAddress address = userAddress.getData();

        orderInfo.setReceiverName(address.getName());
        orderInfo.setReceiverPhone(address.getPhone());
        orderInfo.setReceiverTagName(address.getTagName());
        orderInfo.setReceiverProvince(address.getProvinceCode());
        orderInfo.setReceiverCity(address.getCityCode());
        orderInfo.setReceiverDistrict(address.getDistrictCode());
        orderInfo.setReceiverAddress(address.getFullAddress());

        //4.插入订单
        orderInfoMapper.insert(orderInfo);

        //获取订单id
        Long orderId = orderInfo.getId();
        //5.为订单项设置订单id后批量插入订单项
        for (OrderItem orderItem : orderItemList) {
            orderItem.setOrderId(orderId);
            orderItem.setRemark(remark);
        }
        orderItemService.saveBatch(orderItemList);
        //6.插入订单日志
        OrderLog orderLog = new OrderLog();
        orderLog.setOrderId(orderId);
        orderLog.setOperateUser("用户");
        orderLog.setCreateBy(SecurityContextHolder.getUserName());
        orderLog.setProcessStatus(orderInfo.getOrderStatus());
        orderLog.setNote("创建订单");
        orderLog.setRemark(remark);
        orderLogMapper.insert(orderLog);

        //7.清空购物车中已选中的购物项，避免下单后还能重复购买
        remoteCartService.clearCheckedCartInfo(SecurityConstants.INNER);

        //TODO 发送一条延迟消息，30分钟未支付取消订单
        rabbitService.sendDelayedMessage(MqConst.EXCHANGE_CANCEL_ORDER,MqConst.ROUTING_CANCEL_ORDER,String.valueOf(orderId));

        return orderId;
    }

    @Override
    public void cancelOrder(Long orderId) {
         OrderInfo orderInfo = new OrderInfo();
         orderInfo.setOrderStatus(-1);
         orderInfo.setId(orderId);
         baseMapper.updateById(orderInfo);

    }

}