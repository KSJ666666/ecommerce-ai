package com.spzx.payment.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.context.SecurityContextHolder;
import com.spzx.common.core.domain.R;
import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.api.RemoteOrderInfoService;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.api.domain.OrderItem;
import com.spzx.payment.domain.PaymentInfo;
import com.spzx.payment.mapper.PaymentInfoMapper;
import com.spzx.payment.service.IPaymentInfoService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 付款信息Service业务层处理
 */
@Service
public class PaymentInfoServiceImpl extends ServiceImpl<PaymentInfoMapper, PaymentInfo> implements IPaymentInfoService {
    @Autowired
    private PaymentInfoMapper paymentInfoMapper;

    @Autowired
    private RemoteOrderInfoService remoteOrderInfoService;

    @Autowired
    private RabbitService rabbitService;

    @Override
    public PaymentInfo addOrGetPaymentInfo(String orderNo) {
        PaymentInfo paymentInfo = baseMapper.selectOne(new LambdaQueryWrapper<PaymentInfo>().eq(PaymentInfo::getOrderNo, orderNo));
        if (paymentInfo != null) {
            return paymentInfo;
        }
        paymentInfo = new PaymentInfo();
        paymentInfo.setPayType(2);
        paymentInfo.setPaymentStatus("0");
        paymentInfo.setUserId(SecurityContextHolder.getUserId());

        //远程调用订单内部微服务
        R<OrderInfo> orderInfoByOrderNo = remoteOrderInfoService.getOrderInfoByOrderNo(orderNo, SecurityConstants.INNER);
        //先判错误码再判数据，错误时data必为null，直接看data会丢失真实失败原因
        if (R.FAIL == orderInfoByOrderNo.getCode()) {
            throw new RuntimeException("远程调用订单微服务失败，原因: " + orderInfoByOrderNo.getMsg());
        }
        OrderInfo data = orderInfoByOrderNo.getData();
        if (data == null) {
            throw new RuntimeException("远程调用订单微服务失败，原因: 订单不存在");
        }

        //交易内容拼的是商品名称，多个商品用逗号隔开
        StringBuilder sb = new StringBuilder();
        List<OrderItem> orderItemList = data.getOrderItemList();
        for (OrderItem orderItem : orderItemList) {
            if (!sb.isEmpty()) {
                sb.append(",");
            }
            sb.append(orderItem.getSkuName());
        }
        paymentInfo.setContent(sb.toString());
        paymentInfo.setAmount(data.getTotalAmount());
        //必须关联订单号，否则上面的查重永远查不到，每次支付都会重复插入支付记录
        paymentInfo.setOrderNo(orderNo);


        paymentInfoMapper.insert(paymentInfo);


        return paymentInfo;
    }
}

