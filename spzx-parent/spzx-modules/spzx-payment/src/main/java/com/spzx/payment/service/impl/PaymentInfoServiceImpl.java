package com.spzx.payment.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.spzx.common.rabbit.service.RabbitService;
import com.spzx.order.api.RemoteOrderInfoService;
import com.spzx.payment.domain.PaymentInfo;
import com.spzx.payment.mapper.PaymentInfoMapper;
import com.spzx.payment.service.IPaymentInfoService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

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

}