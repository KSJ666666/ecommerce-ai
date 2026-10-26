package com.spzx.payment.service.impl;

import com.alipay.api.AlipayApiException;
import com.alipay.api.AlipayClient;
import com.alipay.api.domain.AlipayTradeWapPayModel;
import com.alipay.api.request.AlipayTradeWapPayRequest;
import com.alipay.api.response.AlipayTradeWapPayResponse;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.spzx.common.core.constant.SecurityConstants;
import com.spzx.common.core.domain.R;
import com.spzx.order.api.RemoteOrderInfoService;
import com.spzx.payment.configure.AlipayConfig;
import com.spzx.payment.domain.PaymentInfo;
import com.spzx.payment.service.IAlipayService;
import com.spzx.payment.service.IPaymentInfoService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.Map;

@Slf4j
@Service
public class AlipayServiceImpl implements IAlipayService {

    @Autowired
    AlipayClient alipayClient;

    @Autowired
    IPaymentInfoService paymentInfoService;

    @Autowired
    RemoteOrderInfoService remoteOrderInfoService;


    /**
     * 调用支付宝下单：返回一个可以直接跳转的支付宝收银台链接
     * @param orderNo 订单号（不是订单主键id）
     * @return 支付宝支付页面url
     */
    @Override
    public String submitAlipay(String orderNo) {
        //1.保存/获取支付记录：同一个订单反复点"去支付"不会重复插入payment_info
        PaymentInfo paymentInfo = paymentInfoService.addOrGetPaymentInfo(orderNo);

        //2.创建请求对象：教程用的是【手机网站支付】AlipayTradeWapPayRequest，不是电脑网站支付
        AlipayTradeWapPayRequest request = new AlipayTradeWapPayRequest();
        AlipayTradeWapPayModel model = new AlipayTradeWapPayModel();

        //商户订单号，支付宝靠它和我们的payment_info.order_no对应
        model.setOutTradeNo(paymentInfo.getOrderNo());
        //订单总金额，必须和订单真实金额一致，否则回调校验金额对不上
        model.setTotalAmount(paymentInfo.getAmount().toString());
        //订单标题，这里放的是交易内容（商品名称拼接）
        model.setSubject(paymentInfo.getContent());
        //产品码，手机网站支付固定为QUICK_WAP_WAY
        model.setProductCode("QUICK_WAP_WAY");

        //同步回调地址：用户付完款，支付宝把浏览器跳回我们自己的页面（只做展示，不能当支付凭证）
        request.setReturnUrl(AlipayConfig.return_payment_url);
        //异步回调地址：支付宝服务器主动POST通知支付结果（真正改支付状态的依据）
        request.setNotifyUrl(AlipayConfig.notify_payment_url);

        request.setBizModel(model);

        try {
            //第二个参数传"GET"：支付宝直接返回一个可跳转的支付链接
            //如果传"POST"（或不传），返回的是一段会自动提交的表单html，前端得渲染表单才行
            AlipayTradeWapPayResponse response = alipayClient.pageExecute(request, "GET");
            if (response.isSuccess()) {
                log.info("调用支付宝下单成功，orderNo={}", orderNo);
                return response.getBody();
            }
            log.error("调用支付宝下单失败，orderNo={}，subCode={}，subMsg={}",
                    orderNo, response.getSubCode(), response.getSubMsg());
            throw new RuntimeException("调用支付宝下单失败：" + response.getSubMsg());
        } catch (AlipayApiException e) {
            log.error("调用支付宝下单异常，orderNo={}", orderNo, e);
            throw new RuntimeException("调用支付宝下单异常", e);
        }
    }

    /**
     * 支付宝异步回调的业务处理：改支付记录 + 改订单状态
     * 这个方法会被支付宝重复调用（我们没返回success它就会一直重发），所以必须做成幂等的
     */
    @Override
    public void paySuccess(Map<String, String> params) {
        //1.只处理"支付成功"的通知，退款、关闭交易等通知直接忽略
        String tradeStatus = params.get("trade_status");
        if (!"TRADE_SUCCESS".equals(tradeStatus) && !"TRADE_FINISHED".equals(tradeStatus)) {
            log.info("支付宝回调交易状态不是支付成功，trade_status={}，忽略本次通知", tradeStatus);
            return;
        }

        //2.找到我们自己的支付记录
        String orderNo = params.get("out_trade_no");
        PaymentInfo paymentInfo = paymentInfoService.getOne(
                new LambdaQueryWrapper<PaymentInfo>().eq(PaymentInfo::getOrderNo, orderNo));
        if (paymentInfo == null) {
            throw new RuntimeException("支付记录不存在，orderNo=" + orderNo);
        }

        //3.改支付记录：幂等判断放这里，已经处理过的直接跳过，避免重复回调把回调时间反复覆盖
        if (!"1".equals(paymentInfo.getPaymentStatus())) {
            paymentInfo.setPaymentStatus("1");                 //1-已支付
            paymentInfo.setTradeNo(params.get("trade_no"));    //支付宝那边的交易号
            paymentInfo.setCallbackTime(new Date());
            paymentInfo.setCallbackContent(params.toString());
            paymentInfoService.updateById(paymentInfo);
        }

        //4.远程调用订单微服务，把订单状态改成"待发货(1)"
        //update的where里带order_status=0，重复调用只会更新0行，本身也是幂等的
        R<Boolean> r = remoteOrderInfoService.updateOrderStatus(orderNo, 1, SecurityConstants.INNER);
        if (R.FAIL == r.getCode()) {
            //远程调用本身失败（超时、降级），抛异常让支付宝重发，下次进来还能补上
            throw new RuntimeException("支付成功后修改订单状态失败：" + r.getMsg());
        }
        if (!Boolean.TRUE.equals(r.getData())) {
            //返回false说明订单不是"待付款"状态了，可能已经被自动取消，或者之前已经改过了
            log.warn("订单状态未变更为待发货，可能已支付或已取消，orderNo={}", orderNo);
        }

        log.info("支付回调处理完成，orderNo={}", orderNo);
    }
}
