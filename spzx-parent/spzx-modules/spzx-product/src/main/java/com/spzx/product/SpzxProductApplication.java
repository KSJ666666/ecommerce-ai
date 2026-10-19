package com.spzx.product;

import com.spzx.common.security.annotation.EnableCustomConfig;
import com.spzx.common.security.annotation.EnableRyFeignClients;
import com.spzx.product.api.domain.ProductSku;
import com.spzx.product.mapper.ProductSkuMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.redis.core.RedisTemplate;

import java.util.List;
import java.util.stream.Collectors;


@EnableCustomConfig
@EnableRyFeignClients
@SpringBootApplication
public class SpzxProductApplication implements CommandLineRunner {
    @Autowired
    private RedisTemplate redisTemplate;
    @Autowired
    private ProductSkuMapper productSkuMapper;
    public static void main(String[] args) {
        SpringApplication.run(SpzxProductApplication.class, args);
        System.out.println("(♥◠‿◠)ﾉﾞ  系统模块启动成功   ლ(´ڡ`ლ)ﾞ  \n" +
                " .-------.       ____     __        \n" +
                " |  _ _   \\      \\   \\   /  /    \n" +
                " | ( ' )  |       \\  _. /  '       \n" +
                " |(_ o _) /        _( )_ .'         \n" +
                " | (_,_).' __  ___(_ o _)'          \n" +
                " |  |\\ \\  |  ||   |(_,_)'         \n" +
                " |  | \\ `'   /|   `-'  /           \n" +
                " |  |  \\    /  \\      /           \n" +
                " ''-'   `'-'    `-..-'              ");
    }

    @Override
    public void run(String... args) throws Exception {
        //获取商品sku列表
        List<ProductSku> productSkuList = productSkuMapper.selectList(null);
        //获取商品skuid
        List<Long> productSkuIds = productSkuList.stream().map(ProductSku::getId).collect(Collectors.toList());
        productSkuIds.forEach(skuId->{
            //将sku注入redis位图中
            redisTemplate.opsForValue().setBit("product:productSku:data",skuId,true);
        });


    }
}
