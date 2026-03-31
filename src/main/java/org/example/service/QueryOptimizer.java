package org.example.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 查询优化器
 * 负责对用户查询进行预处理、扩展和重写，提升检索质量
 */
@Component
public class QueryOptimizer {

    private static final Logger logger = LoggerFactory.getLogger(QueryOptimizer.class);

    // 常见停用词列表
    private static final List<String> STOP_WORDS = Arrays.asList(
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"
    );

    // 同义词映射表
    private static final List<List<String>> SYNONYMS = Arrays.asList(
        Arrays.asList("使用", "应用", "利用"),
        Arrays.asList("如何", "怎样", "怎么"),
        Arrays.asList("配置", "设置", "部署"),
        Arrays.asList("问题", "疑问", "难题"),
        Arrays.asList("方法", "方式", "途径")
    );

    /**
     * 优化查询
     * 
     * @param query 原始查询
     * @return 优化后的查询
     */
    public String optimize(String query) {
        logger.info("开始优化查询: {}", query);

        // 1. 预处理
        String processedQuery = preprocess(query);
        
        // 2. 扩展
        String expandedQuery = expand(processedQuery);
        
        // 3. 重写
        String rewrittenQuery = rewrite(expandedQuery);

        logger.info("优化完成，原始查询: {}, 优化后: {}", query, rewrittenQuery);
        return rewrittenQuery;
    }

    /**
     * 生成多个查询变体
     * 
     * @param query 原始查询
     * @return 查询变体列表
     */
    public List<String> generateQueryVariants(String query) {
        List<String> variants = new ArrayList<>();
        variants.add(optimize(query));
        
        // 生成同义词变体
        for (List<String> synonymGroup : SYNONYMS) {
            for (String synonym : synonymGroup) {
                if (query.contains(synonym)) {
                    for (String otherSynonym : synonymGroup) {
                        if (!otherSynonym.equals(synonym)) {
                            String variant = query.replace(synonym, otherSynonym);
                            variants.add(optimize(variant));
                        }
                    }
                    break;
                }
            }
        }
        
        // 去重
        List<String> uniqueVariants = new ArrayList<>();
        for (String variant : variants) {
            if (!uniqueVariants.contains(variant)) {
                uniqueVariants.add(variant);
            }
        }
        
        logger.info("生成查询变体数量: {}", uniqueVariants.size());
        return uniqueVariants;
    }

    /**
     * 预处理查询
     * 
     * @param query 原始查询
     * @return 预处理后的查询
     */
    private String preprocess(String query) {
        if (query == null || query.trim().isEmpty()) {
            return query;
        }

        // 1. 去除首尾空格
        query = query.trim();
        
        // 2. 统一大小写（转为小写）
        query = query.toLowerCase();
        
        // 3. 去除多余的标点符号
        query = query.replaceAll("[\\p{Punct}]+$", "");
        
        // 4. 移除停用词
        String[] words = query.split("\\s+");
        StringBuilder sb = new StringBuilder();
        for (String word : words) {
            if (!STOP_WORDS.contains(word)) {
                sb.append(word).append(" ");
            }
        }
        
        return sb.toString().trim();
    }

    /**
     * 扩展查询
     * 
     * @param query 预处理后的查询
     * @return 扩展后的查询
     */
    private String expand(String query) {
        if (query == null || query.trim().isEmpty()) {
            return query;
        }

        // 使用同义词扩展
        String expandedQuery = query;
        for (List<String> synonymGroup : SYNONYMS) {
            for (String synonym : synonymGroup) {
                if (expandedQuery.contains(synonym)) {
                    // 添加其他同义词到查询中
                    for (String otherSynonym : synonymGroup) {
                        if (!otherSynonym.equals(synonym) && !expandedQuery.contains(otherSynonym)) {
                            expandedQuery += " " + otherSynonym;
                        }
                    }
                    break;
                }
            }
        }
        
        return expandedQuery;
    }

    /**
     * 重写查询
     * 
     * @param query 扩展后的查询
     * @return 重写后的查询
     */
    private String rewrite(String query) {
        if (query == null || query.trim().isEmpty()) {
            return query;
        }

        // 1. 句式转换：将疑问句转换为陈述句
        if (query.contains("如何") || query.contains("怎样") || query.contains("怎么")) {
            query = query.replace("如何", "")
                        .replace("怎样", "")
                        .replace("怎么", "")
                        .replace("？", "")
                        .replace("?", "");
            query = "如何" + query;
        }
        
        // 2. 去除冗余词汇
        query = query.replaceAll("\\s+如何\\s+", "如何");
        query = query.replaceAll("\\s+的\\s+", "的");
        
        return query.trim();
    }
}
