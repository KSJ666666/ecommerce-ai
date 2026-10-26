package com.spzx.order.controller;


import com.github.pagehelper.PageHelper;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.domain.R;
import com.spzx.common.core.utils.poi.ExcelUtil;
import com.spzx.common.core.web.controller.BaseController;
import com.spzx.common.core.web.domain.AjaxResult;
import com.spzx.common.core.web.page.TableDataInfo;
import com.spzx.common.log.annotation.Log;
import com.spzx.common.log.enums.BusinessType;
import com.spzx.common.security.annotation.InnerAuth;
import com.spzx.common.security.annotation.RequiresLogin;
import com.spzx.common.security.annotation.RequiresPermissions;
import com.spzx.order.api.domain.OrderInfo;
import com.spzx.order.domain.vo.AiOrderView;
import com.spzx.order.domain.vo.OrderForm;
import com.spzx.order.domain.vo.TradeVo;
import com.spzx.order.service.IOrderInfoService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Tag(name = "订单接口管理")
@RestController
@RequestMapping("/orderInfo")
public class OrderInfoController extends BaseController {
    @Autowired
    private IOrderInfoService orderInfoService;


    /**
     * 查询订单列表
     */
    @Operation(summary = "查询订单列表")
    @RequiresPermissions("user:orderInfo:list")
    @GetMapping("/list")
    public TableDataInfo list(OrderInfo orderInfo) {
        startPage();
        List<OrderInfo> list = orderInfoService.selectOrderInfoList(orderInfo);
        return getDataTable(list);
    }

    /**
     * 导出订单列表
     */
    @Operation(summary = "导出订单列表")
    @RequiresPermissions("user:orderInfo:export")
    @Log(title = "订单", businessType = BusinessType.EXPORT)
    @PostMapping("/export")
    public void export(HttpServletResponse response, OrderInfo orderInfo) {
        List<OrderInfo> list = orderInfoService.selectOrderInfoList(orderInfo);
        ExcelUtil<OrderInfo> util = new ExcelUtil<OrderInfo>(OrderInfo.class);
        util.exportExcel(response, list, "订单数据");
    }

    /**
     * 获取订单详细信息
     */
    @Operation(summary = "获取订单详细信息")
    @RequiresPermissions("user:orderInfo:query")
    @GetMapping(value = "/{id}")
    public AjaxResult getInfo(@PathVariable("id") Long id) {
        return success(orderInfoService.selectOrderInfoById(id));
    }

    @Operation(summary = "获取去结算详情页")
    @GetMapping("/trade")
    public AjaxResult trade() {
        TradeVo tradeVo = orderInfoService.trade();
        return success(tradeVo);
    }

    @Operation(summary = "立即购买按钮")
    @GetMapping("/buy/{skuId}")
    public AjaxResult buy(@PathVariable Long skuId) {
        TradeVo tradeVo = orderInfoService.buy(skuId);
        return success(tradeVo);
    }

    @Operation(summary = "提交订单")
    @PostMapping("/submitOrder")
    public AjaxResult submit(@RequestBody OrderForm orderForm) {
        Long orderId = orderInfoService.submit(orderForm);
        return success(orderId);
    }

    @Operation(summary = "根据订单id获取订单信息")
    @GetMapping("/getOrderInfo/{orderId}")
    public AjaxResult getOrderInfo(@PathVariable Long orderId) {

        return success(orderInfoService.selectOrderInfoById(orderId));
    }

    @Operation(summary = "供微服务内部远程调用：根据订单号获取订单信息")
    @InnerAuth
    @GetMapping("/inner/getOrderInfo/{orderNo}")
    public R<OrderInfo> getOrderInfoInner(@PathVariable String orderNo) {
        //内部接口统一返回R，和Feign客户端声明的R<OrderInfo>保持一致，避免依赖AjaxResult的巧合结构
        return R.ok(orderInfoService.getOrderInfoByOrderNo(orderNo));
    }

    @Operation(summary = "供微服务内部远程调用：根据订单号获取物流状态（按订单状态推导，未接入承运商）")
    @InnerAuth
    @GetMapping("/inner/logistics/{orderNo}")
    public R<Map<String, Object>> getLogisticsInner(@PathVariable String orderNo) {
        return R.ok(orderInfoService.getLogisticsByOrderNo(orderNo));
    }

    @Operation(summary = "供 AI 客服远程调用：订单聚合视图（状态文案/金额/收货信息/明细）")
    @InnerAuth
    @GetMapping("/inner/ai/{orderNo}")
    public R<AiOrderView> getAiOrderView(@PathVariable String orderNo) {
        return R.ok(orderInfoService.getAiOrderView(orderNo));
    }

    @Operation(summary = "供微服务内部远程调用：支付成功后修改订单状态")
    @InnerAuth
    @GetMapping("/inner/updateOrderStatus/{orderNo}/{orderStatus}")
    public R<Boolean> updateOrderStatus(@PathVariable String orderNo, @PathVariable Integer orderStatus) {
        return R.ok(orderInfoService.updateOrderStatus(orderNo, orderStatus));
    }

    @Operation(summary = "取消订单")
    @GetMapping("/cancelOrder/{orderId}")
    public AjaxResult cancelOrder(@PathVariable Long orderId){
        orderInfoService.cancelOrder(orderId,1);
        return success();
    }
    @Operation(summary = "查询订单列表")
    @GetMapping("/userOrderInfoList/{pageNum}/{pageSize}")
    public TableDataInfo userOrderInfoList(@PathVariable Integer pageNum, @PathVariable Integer pageSize,String orderStatus) {
        PageHelper.startPage(pageNum, pageSize);
        List<OrderInfo> list = orderInfoService.getMyOrderInfoList(orderStatus);
        return getDataTable(list);
    }
}