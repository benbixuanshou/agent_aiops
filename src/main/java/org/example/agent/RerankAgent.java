package org.example.agent;

import org.example.service.VectorSearchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * 召回重排Agent
 * 负责对检索到的文档进行重新排序，考虑remark信息
 */
@Component
public class RerankAgent {

    private static final Logger logger = LoggerFactory.getLogger(RerankAgent.class);

    /**
     * 对检索结果进行重排
     * 
     * @param query 用户查询
     * @param initialResults 初始检索结果
     * @return 重排后的结果
     */
    public List<VectorSearchService.SearchResult> rerank(String query, List<VectorSearchService.SearchResult> initialResults) {
        logger.info("开始重排检索结果，初始结果数量: {}", initialResults.size());

        // 复制结果列表以避免修改原始数据
        List<VectorSearchService.SearchResult> rerankedResults = new ArrayList<>(initialResults);

        // 执行重排逻辑
        rerankedResults.sort(new RerankComparator(query));

        logger.info("重排完成，返回重排后的结果");
        return rerankedResults;
    }

    /**
     * 重排比较器
     * 考虑多种因素进行排序
     */
    private static class RerankComparator implements Comparator<VectorSearchService.SearchResult> {
        private final String query;

        public RerankComparator(String query) {
            this.query = query;
        }

        @Override
        public int compare(VectorSearchService.SearchResult result1, VectorSearchService.SearchResult result2) {
            // 计算综合得分
            double score1 = calculateScore(result1, query);
            double score2 = calculateScore(result2, query);

            // 降序排列（得分高的排在前面）
            return Double.compare(score2, score1);
        }

        /**
         * 计算文档的综合得分
         * 
         * @param result 搜索结果
         * @param query 用户查询
         * @return 综合得分
         */
        private double calculateScore(VectorSearchService.SearchResult result, String query) {
            // 基础得分：向量相似度得分
            double baseScore = result.getScore();

            // 1. 考虑内容与查询的相关性（关键词匹配）
            double relevanceScore = calculateRelevanceScore(result.getContent(), query);

            // 2. 考虑metadata中的remark信息
            double remarkScore = calculateRemarkScore(result.getMetadata());

            // 3. 计算综合得分
            // 权重分配：向量相似度(0.6) + 内容相关性(0.3) + remark得分(0.1)
            return baseScore * 0.6 + relevanceScore * 0.3 + remarkScore * 0.1;
        }

        /**
         * 计算内容与查询的相关性得分
         * 
         * @param content 文档内容
         * @param query 用户查询
         * @return 相关性得分
         */
        private double calculateRelevanceScore(String content, String query) {
            if (content == null || query == null) {
                return 0.0;
            }

            // 简单的关键词匹配逻辑
            String[] queryWords = query.split("\\s+");
            int matchCount = 0;

            for (String word : queryWords) {
                if (content.toLowerCase().contains(word.toLowerCase())) {
                    matchCount++;
                }
            }

            // 计算匹配率
            return queryWords.length > 0 ? (double) matchCount / queryWords.length : 0.0;
        }

        /**
         * 计算remark得分
         * 
         * @param metadata 文档元数据
         * @return remark得分
         */
        private double calculateRemarkScore(String metadata) {
            if (metadata == null) {
                return 0.0;
            }

            // 检查metadata中是否包含remark相关信息
            // 这里可以根据实际的metadata格式进行调整
            double score = 0.0;

            // 示例：如果metadata中包含"重要"、"关键"等关键词，提高得分
            String lowerMetadata = metadata.toLowerCase();
            if (lowerMetadata.contains("重要") || lowerMetadata.contains("关键") || 
                lowerMetadata.contains("核心") || lowerMetadata.contains("remark")) {
                score = 1.0;
            }

            return score;
        }
    }
}
