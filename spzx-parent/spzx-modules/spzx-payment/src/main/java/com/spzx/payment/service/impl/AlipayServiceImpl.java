package com.spzx.payment.service.impl;

import com.alipay.api.AlipayClient;
import com.spzx.payment.service.IAlipayService;
import com.spzx.payment.service.IPaymentInfoService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class AlipayServiceImpl implements IAlipayService {

    @Autowired
    AlipayClient alipayClient;

    @Autowired
    IPaymentInfoService paymentInfoService;

}
