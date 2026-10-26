package com.spzx.order.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
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
import com.spzx.order.domain.vo.AiOrderView;
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
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
        if (orderInfo == null) {
            throw new ServiceException("订单不存在");
        }
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

            redisTemplate.opsForValue().set("user:trade:" + tradeNo, tradeNo, 5, TimeUnit.MINUTES);
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

        //skuId是引用商品sku的业务外键，不能置空，否则提交订单时远程查询商品sku会因路径变量为空而404
        orderItem.setSkuId(skuId);

        orderItem.setSkuNum(1);
        orderItem.setSkuPrice(productSku.getSalePrice());

        tradeVo.setOrderItemList(List.of(orderItem));

        tradeVo.setTotalAmount(productSku.getSalePrice());

        String tradeNo = UUID.randomUUID().toString().replace("-", "");

        tradeVo.setTradeNo(tradeNo);
        redisTemplate.opsForValue().set("user:trade:" + tradeNo, tradeNo, 5, TimeUnit.MINUTES);

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
            //订单项缺少sku信息时直接失败，避免把null拼进远程调用url导致404难以排查
            if (null == skuId || null == skuNum || null == skuPrice) {
                throw new ServiceException("订单信息不完整，请去结算页面重新下单");
            }

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

        //8.发送延迟消息，30分钟未支付自动取消订单
        //必须等事务提交成功后再发，否则订单回滚了但消息已经发出去，消费者会查到一个不存在的订单
        String orderIdStr = String.valueOf(orderId);
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                rabbitService.sendDelayedMessage(MqConst.EXCHANGE_CANCEL_ORDER, MqConst.ROUTING_CANCEL_ORDER, orderIdStr);
            }
        });

        return orderId;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancelOrder(Long orderId, Integer flag) {
        OrderInfo orderInfo = new OrderInfo();
        orderInfo.setOrderStatus(-1);
        orderInfo.setId(orderId);
        orderInfo.setCancelTime(new Date());

        LambdaUpdateWrapper<OrderInfo> updateWrapper = new LambdaUpdateWrapper<OrderInfo>()
                .eq(OrderInfo::getId, orderId)
                .eq(OrderInfo::getOrderStatus, 0);
        //flag=1是用户主动取消，需要校验订单归属，防止取消别人的订单；
        //flag=2是系统自动取消（消息队列调用），没有用户上下文，不能加userId条件
        if (flag != null && flag == 1) {
            updateWrapper.eq(OrderInfo::getUserId, SecurityContextHolder.getUserId());
        }
        int update = orderInfoMapper.update(orderInfo, updateWrapper);
        if (update == 0) {
            //订单不存在、已取消或不是待支付状态，直接返回即可。
            //这里必须是幂等的：延迟消息到期时会再次调用本方法，抛异常会导致消息反复重试
            return;
        }
        String cancelReason = flag == 1 ? "用户取消订单" : "系统取消订单";
        orderInfo.setCancelReason(cancelReason);
        baseMapper.updateById(orderInfo);

        //回流库存：下单时锁定的库存要解锁回去，否则库存会越来越少
        List<OrderItem> orderItemList = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderId));
        for (OrderItem orderItem : orderItemList) {
            R<String> unlockR = remoteProductService.unlockStock(
                    orderItem.getSkuId(), orderItem.getSkuNum(), SecurityConstants.INNER);
            if (R.FAIL == unlockR.getCode()) {
                throw new ServiceException(unlockR.getMsg());
            }
            if (unlockR.getData() != null && !unlockR.getData().isEmpty()) {
                throw new ServiceException(unlockR.getData());
            }
        }

        //插入订单日志
        OrderLog orderLog = new OrderLog();
        orderLog.setOrderId(orderId);
        orderLog.setOperateUser(flag == 1 ? "用户" : "系统");
        orderLog.setCreateBy(flag == 1 ? SecurityContextHolder.getUserName() : "系统");
        orderLog.setProcessStatus(-1);
        orderLog.setNote(flag == 1 ? "用户取消订单" : "系统取消订单");
        orderLog.setUpdateBy(flag == 1 ? SecurityContextHolder.getUserName() : "系统");
        orderLogMapper.insert(orderLog);
    }

    @Override
    public List<OrderInfo> getMyOrderInfoList(String orderStatus) {
        Long userId = SecurityContextHolder.getUserId();
        LambdaQueryWrapper<OrderInfo> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(OrderInfo::getUserId, userId)
                .eq(StringUtils.hasLength(orderStatus), OrderInfo::getOrderStatus, orderStatus);
        List<OrderInfo> orderInfoList = baseMapper.selectList(wrapper);
// 给每个订单塞订单项
        orderInfoList.forEach(orderInfo -> {
            List<OrderItem> items = orderItemMapper.selectList(
                    new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderInfo.getId()));
            orderInfo.setOrderItemList(items);
        });
        return orderInfoList;
    }


    @Override
    public OrderInfo getOrderInfoByOrderNo(String orderNo) {
        OrderInfo orderInfo = orderInfoMapper.selectOne(new LambdaQueryWrapper<OrderInfo>().eq(OrderInfo::getOrderNo, orderNo));
        //查不到要先拦住，否则下面orderInfo.getId()直接空指针，调用方只能看到一个含糊的500
        if (orderInfo == null) {
            throw new ServiceException("订单不存在，请确认传的是订单号orderNo而不是订单id");
        }

        List<OrderItem> orderItemList = orderItemMapper.selectList(new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderInfo.getId()));

        orderInfo.setOrderItemList(orderItemList);


        return orderInfo;
    }

    /**
     * 支付成功后由支付微服务远程调用，把订单状态改成"待发货"
     * @param orderNo 订单号
     * @param orderStatus 目标状态，1表示待发货
     * @return true=改成功了；false=订单不是待付款状态（已支付过或已被取消）
     */
    @Override
    public boolean updateOrderStatus(String orderNo, Integer orderStatus) {
        OrderInfo orderInfo = new OrderInfo();
        orderInfo.setOrderStatus(orderStatus);
        orderInfo.setPaymentTime(new Date());

        //只改"待付款(0)"的订单，支付宝回调可能重复发，这个条件保证了重复调用只更新0行
        LambdaUpdateWrapper<OrderInfo> updateWrapper = new LambdaUpdateWrapper<OrderInfo>()
                .eq(OrderInfo::getOrderNo, orderNo)
                .eq(OrderInfo::getOrderStatus, 0);
        return orderInfoMapper.update(orderInfo, updateWrapper) > 0;
    }

    /**
     * 物流状态按订单状态机推导：0待支付 1待发货 2待收货 3已完成 -1已取消。
     * 未接入真实承运商，tracking_number / logistics_company 恒为 null，由调用方展示为"未知"。
     */
    @Override
    public Map<String, Object> getLogisticsByOrderNo(String orderNo) {
        OrderInfo orderInfo = orderInfoMapper.selectOne(new LambdaQueryWrapper<OrderInfo>().eq(OrderInfo::getOrderNo, orderNo));
        Map<String, Object> logistics = new HashMap<>();
        logistics.put("tracking_number", null);
        logistics.put("logistics_company", null);
        if (orderInfo == null) {
            logistics.put("status", "NOT_FOUND");
            logistics.put("status_desc", "当前系统中没有查到该订单。");
            return logistics;
        }
        SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd HH:mm");
        Integer status = orderInfo.getOrderStatus() == null ? -2 : orderInfo.getOrderStatus();
        switch (status) {
            case 0 -> {
                logistics.put("status", "UNPAID");
                logistics.put("status_desc", "订单尚未支付，未生成物流信息。");
            }
            case 1 -> {
                logistics.put("status", "PENDING_SHIPMENT");
                logistics.put("status_desc", "订单已支付，商家尚未发货。");
            }
            case 2 -> {
                logistics.put("status", "IN_TRANSIT");
                logistics.put("status_desc", orderInfo.getDeliveryTime() == null
                        ? "包裹已发出，运输中。"
                        : "包裹已于 " + fmt.format(orderInfo.getDeliveryTime()) + " 发出，运输中。");
            }
            case 3 -> {
                logistics.put("status", "RECEIVED");
                logistics.put("status_desc", orderInfo.getReceiveTime() == null
                        ? "包裹已签收。"
                        : "包裹已于 " + fmt.format(orderInfo.getReceiveTime()) + " 签收。");
            }
            default -> {
                logistics.put("status", "CANCELLED");
                logistics.put("status_desc", "订单已取消，无物流信息。");
            }
        }
        return logistics;
    }

    /**
     * 面向 AI 客服的订单视图。
     *
     * <p>状态文案刻意写成"可直接播报"的短句，且不带句号——客服流程模板
     * （flow_config/user_flows.yml）会是「订单{{order_number}}当前状态是：{{order_status}}。」
     * 自带一个句号，这里再带一个就会渲染成"备货中。。"。</p>
     */
    @Override
    public AiOrderView getAiOrderView(String orderNo) {
        OrderInfo orderInfo;
        try {
            orderInfo = getOrderInfoByOrderNo(orderNo);
        } catch (ServiceException e) {
            //订单号不存在属于正常的业务分支（用户打错一位就会走到这里），返回 null 让调用方给友好提示，
            //不把 500 抛给客服，否则客服只能回一句"查询失败"。
            return null;
        }

        AiOrderView view = new AiOrderView();
        view.setOrderNo(orderInfo.getOrderNo());
        view.setOrderStatus(orderInfo.getOrderStatus());
        view.setStatusDesc(AI_STATUS_DESC.getOrDefault(orderInfo.getOrderStatus(), "状态未知"));
        view.setTotalAmount(orderInfo.getTotalAmount());
        view.setReceiverName(orderInfo.getReceiverName());
        view.setReceiverPhoneMasked(maskPhone(orderInfo.getReceiverPhone()));
        view.setReceiverAddress(orderInfo.getReceiverAddress());
        if (orderInfo.getCreateTime() != null) {
            view.setCreateTime(new SimpleDateFormat("yyyy-MM-dd HH:mm").format(orderInfo.getCreateTime()));
        }

        List<AiOrderView.Item> items = new ArrayList<>();
        if (orderInfo.getOrderItemList() != null) {
            for (OrderItem orderItem : orderInfo.getOrderItemList()) {
                AiOrderView.Item item = new AiOrderView.Item();
                item.setProductId(orderItem.getSkuId());
                item.setTitle(orderItem.getSkuName());
                item.setQuantity(orderItem.getSkuNum());
                item.setPrice(orderItem.getSkuPrice());
                items.add(item);
            }
        }
        view.setItems(items);
        return view;
    }

    /**
     * 订单状态文案，与前端 myOrder 页面保持一致的口径。
     */
    private static final Map<Integer, String> AI_STATUS_DESC = Map.of(
            0, "待付款，订单已提交但还没有完成支付",
            1, "商家正在备货，尚未发货",
            2, "包裹已发出，正在配送途中",
            3, "已签收，订单完成",
            -1, "订单已取消"
    );

    /**
     * 手机号脱敏，避免客服把完整号码播报出去。
     */
    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) {
            return phone;
        }
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }

}