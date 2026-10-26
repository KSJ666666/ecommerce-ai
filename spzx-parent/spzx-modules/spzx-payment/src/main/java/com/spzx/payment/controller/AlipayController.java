package com.spzx.payment.controller;

import com.alipay.api.AlipayApiException;
import com.alipay.api.internal.util.AlipaySignature;
import com.spzx.common.core.web.controller.BaseController;
import com.spzx.common.core.web.domain.AjaxResult;
import com.spzx.common.security.annotation.RequiresLogin;
import com.spzx.payment.configure.AlipayConfig;
import com.spzx.payment.service.IAlipayService;
import com.spzx.payment.service.IPaymentInfoService;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.ModelAndView;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Controller
@RequestMapping("/alipay")
public class AlipayController extends BaseController {

    @Autowired
    private IAlipayService alipayService;

    @Autowired
    private IPaymentInfoService paymentInfoService;

    @Operation(summary = "获取支付宝返回的表单")
    @GetMapping("submitAlipay/{orderNo}")
    public AjaxResult submitAlipay(@PathVariable String orderNo) {
        String form = alipayService.submitAlipay(orderNo);
        return AjaxResult.success(form);
    }

    /**
     * 异步回调：支付宝服务器在用户付款成功后主动POST通知我们
     * 这是判断"到底有没有付款"的唯一可靠依据，同步回调不可信（用户自己就能访问）
     */
    @Operation(summary = "支付宝异步回调通知支付结果")
    @PostMapping("/callback/notify")
    public String notifyPay(HttpServletRequest request) {
        Map<String, String> params = convertParams(request);
        log.info("收到支付宝异步回调，参数：{}", params);
        try {
            //1.验签：确认这真是支付宝发来的，防止别人伪造请求把订单改成已支付
            boolean signVerified = AlipaySignature.rsaCheckV1(params, AlipayConfig.alipay_public_key,
                    AlipayConfig.charset, AlipayConfig.sign_type);
            if (!signVerified) {
                log.error("支付宝异步回调验签失败，参数：{}", params);
                return "failure";
            }
            //2.处理业务
            alipayService.paySuccess(params);
            //3.必须原样返回success这7个字符，否则支付宝认为我们没收到，会隔一段时间重发一次
            return "success";
        } catch (Exception e) {
            //返回failure，支付宝会重试，靠paySuccess里的幂等逻辑保证不会重复处理
            log.error("支付宝异步回调处理失败", e);
            return "failure";
        }
    }

    /**
     * 同步回调：用户付完款后支付宝把浏览器跳回我们自己的页面，只做展示用
     */
    @Operation(summary = "支付宝同步回调跳转回商城页面")
    @GetMapping("/callback/return")
    public ModelAndView returnPay(HttpServletRequest request) {
        log.info("收到支付宝同步回调，参数：{}", convertParams(request));
        //这里不能用return "redirect:xxx"，因为继承了BaseController上的@RestController，
        //字符串会被当成响应体直接写出去而不是跳转，必须用ModelAndView
        return new ModelAndView("redirect:" + AlipayConfig.return_payment_url);
    }

    /**
     * 把request里的参数转成Map<String,String>，支付宝回调参数是这种格式
     */
    private Map<String, String> convertParams(HttpServletRequest request) {
        Map<String, String> params = new HashMap<>();
        Map<String, String[]> requestParams = request.getParameterMap();
        for (Map.Entry<String, String[]> entry : requestParams.entrySet()) {
            String[] values = entry.getValue();
            params.put(entry.getKey(), values != null && values.length > 0 ? values[0] : "");
        }
        return params;
    }

}