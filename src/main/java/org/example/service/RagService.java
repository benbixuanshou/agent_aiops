package org.example.service;

import com.alibaba.dashscope.aigc.generation.Generation;
import com.alibaba.dashscope.aigc.generation.GenerationParam;
import com.alibaba.dashscope.aigc.generation.GenerationResult;
import com.alibaba.dashscope.common.Message;
import com.alibaba.dashscope.common.Role;
import com.alibaba.dashscope.exception.ApiException;
import com.alibaba.dashscope.exception.InputRequiredException;
import com.alibaba.dashscope.exception.NoApiKeyException;
import com.alibaba.dashscope.utils.Constants;
import io.reactivex.Flowable;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * RAG (Retrieval-Augmented Generation) 服务
 * 结合向量检索和大语言模型生成答案
 */
@Service
public class RagService {

    private static final Logger logger = LoggerFactory.getLogger(RagService.class);

    @Autowired
    private VectorSearchService vectorSearchService;

    @Autowired
    private org.example.agent.RerankAgent rerankAgent;

    @Autowired
    private QueryOptimizer queryOptimizer;

    @Value("${dashscope.api.key}")
    private String apiKey;

    @Value("${rag.top-k:3}")
    private int topK;

    @Value("${rag.model:qwen3-30b-a3b-thinking-2507}")
    private String model;

    @Value("${rag.enable-multi-query:false}")
    private boolean enableMultiQuery;

    private Generation generation;

    @PostConstruct
    public void init() {
        // 设置 API Key 和 Base URL
        Constants.apiKey = apiKey;
        Constants.baseHttpApiUrl = "https://dashscope.aliyuncs.com/api/v1";
        
        // 创建 Generation 实例
        generation = new Generation();
        
        logger.info("RAG 服务初始化完成，model: {}, topK: {}", model, topK);
    }

    /**
     * 流式处理用户问题（不带历史消息）
     * 
     * @param question 用户问题
     * @param callback 流式回调接口
     */
    public void queryStream(String question, StreamCallback callback) {
        queryStream(question, new ArrayList<>(), callback);
    }

    /**
     * 流式处理用户问题（带历史消息）
     * 
     * @param question 用户问题
     * @param history 历史消息列表，格式：[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
     * @param callback 流式回调接口
     */
    public void queryStream(String question, List<Map<String, String>> history, StreamCallback callback) {
        try {
            logger.info("收到 RAG 流式查询: {}", question);

            // 1. 优化查询
            String optimizedQuery = queryOptimizer.optimize(question);

            // 2. 执行检索
            List<VectorSearchService.SearchResult> initialResults;
            if (enableMultiQuery) {
                // 多查询策略
                List<String> queryVariants = queryOptimizer.generateQueryVariants(question);
                initialResults = executeMultiQuerySearch(queryVariants);
            } else {
                // 单查询策略
                initialResults = vectorSearchService.searchSimilarDocuments(optimizedQuery, topK);
            }

            // 3. 使用重排Agent对结果进行重排
            List<VectorSearchService.SearchResult> searchResults = 
                rerankAgent.rerank(optimizedQuery, initialResults);

            // 发送检索结果
            callback.onSearchResults(searchResults);

            if (searchResults.isEmpty()) {
                logger.warn("未找到相关文档");
                callback.onComplete("抱歉，我在知识库中没有找到相关信息来回答您的问题。", "");
                return;
            }

            // 2. 构建上下文和提示词
            String context = buildContext(searchResults);
            String prompt = buildPrompt(question, context);

            // 3. 流式调用大语言模型（传入历史消息）
            generateAnswerStream(prompt, history, callback);

        } catch (Exception e) {
            logger.error("RAG 流式查询失败", e);
            callback.onError(e);
        }
    }

    /**
     * 构建上下文
     */
    private String buildContext(List<VectorSearchService.SearchResult> searchResults) {
        StringBuilder context = new StringBuilder();
        
        for (int i = 0; i < searchResults.size(); i++) {
            VectorSearchService.SearchResult result = searchResults.get(i);
            context.append("【参考资料 ").append(i + 1).append("】\n");
            context.append(result.getContent()).append("\n\n");
        }
        
        return context.toString();
    }

    /**
     * 构建提示词
     */
    private String buildPrompt(String question, String context) {
        return String.format(
            "你是一个专业的AI助手。请根据以下参考资料回答用户的问题。\n\n" +
            "参考资料：\n%s\n" +
            "用户问题：%s\n\n" +
            "请基于上述参考资料给出准确、详细的回答。如果参考资料中没有相关信息，请明确说明。",
            context, question
        );
    }

    /**
     * 生成答案（流式）
     * 
     * @param prompt 当前问题的提示词
     * @param history 历史消息列表
     * @param callback 流式回调接口
     */
    private void generateAnswerStream(String prompt, List<Map<String, String>> history, StreamCallback callback) 
            throws NoApiKeyException, ApiException, InputRequiredException {
        
        // 构建消息列表：历史消息 + 当前问题
        List<Message> messages = new ArrayList<>();
        
        // 添加历史消息
        for (Map<String, String> historyMsg : history) {
            String role = historyMsg.get("role");
            String content = historyMsg.get("content");
            
            if ("user".equals(role)) {
                messages.add(Message.builder()
                        .role(Role.USER.getValue())
                        .content(content)
                        .build());
            } else if ("assistant".equals(role)) {
                messages.add(Message.builder()
                        .role(Role.ASSISTANT.getValue())
                        .content(content)
                        .build());
            }
        }
        
        // 添加当前用户问题
        Message userMsg = Message.builder()
                .role(Role.USER.getValue())
                .content(prompt)
                .build();
        messages.add(userMsg);
        
        logger.debug("发送给AI模型的消息数量: {}（包含 {} 条历史消息）", 
            messages.size(), history.size());

        GenerationParam param = GenerationParam.builder()
                .apiKey(apiKey)
                .model(model)
                .incrementalOutput(true)
                .resultFormat("message")
                .messages(messages)
                .build();

        logger.info("开始调用AI模型流式接口...");
        
        Flowable<GenerationResult> result = generation.streamCall(param);
        
        StringBuilder reasoningContent = new StringBuilder();
        StringBuilder finalContent = new StringBuilder();
        
        logger.info("开始接收AI模型流式响应...");

        result.blockingForEach(message -> {
            if (message.getOutput() != null && 
                message.getOutput().getChoices() != null && 
                !message.getOutput().getChoices().isEmpty()) {
                
                // 获取消息内容
                // 注意：qwen3-30b-a3b-thinking-2507 模型会在 content 中返回完整内容
                // reasoning 部分可能需要通过特殊方式提取或者直接包含在 content 中
                String content = message.getOutput().getChoices().get(0).getMessage().getContent();

                if (content != null && !content.isEmpty()) {
                    logger.debug("收到AI模型内容块: {}", content);
                    
                    // 对于 thinking 模型，content 可能包含思考过程和最终答案
                    // 这里我们将所有内容都作为答案返回
                    finalContent.append(content);
                    callback.onContentChunk(content);
                    
                    logger.debug("已调用 onContentChunk 回调");
                } else {
                    logger.debug("收到空内容块，跳过");
                }
            }
        });
        
        logger.info("AI模型流式响应完成，总内容长度: {}", finalContent.length());

        callback.onComplete(finalContent.toString(), reasoningContent.toString());
        logger.info("已调用 onComplete 回调");
    }

    /**
     * 执行多查询搜索
     * 
     * @param queryVariants 查询变体列表
     * @return 融合后的搜索结果
     */
    private List<VectorSearchService.SearchResult> executeMultiQuerySearch(List<String> queryVariants) {
        logger.info("执行多查询搜索，查询变体数量: {}", queryVariants.size());

        // 存储所有查询的结果
        List<VectorSearchService.SearchResult> allResults = new ArrayList<>();

        // 对每个查询变体执行搜索
        for (String queryVariant : queryVariants) {
            List<VectorSearchService.SearchResult> variantResults = 
                vectorSearchService.searchSimilarDocuments(queryVariant, topK);
            allResults.addAll(variantResults);
        }

        // 融合结果（去重并重新排序）
        List<VectorSearchService.SearchResult> fusedResults = fuseResults(allResults);

        logger.info("多查询搜索完成，融合后结果数量: {}", fusedResults.size());
        return fusedResults;
    }

    /**
     * 融合多个查询的结果
     * 
     * @param allResults 所有查询的结果
     * @return 融合后的结果
     */
    private List<VectorSearchService.SearchResult> fuseResults(List<VectorSearchService.SearchResult> allResults) {
        // 去重：根据文档ID
        java.util.Map<String, VectorSearchService.SearchResult> uniqueResultsMap = new java.util.HashMap<>();
        for (VectorSearchService.SearchResult result : allResults) {
            String id = result.getId();
            if (!uniqueResultsMap.containsKey(id)) {
                uniqueResultsMap.put(id, result);
            } else {
                // 如果文档已存在，保留得分更高的版本
                VectorSearchService.SearchResult existingResult = uniqueResultsMap.get(id);
                if (result.getScore() > existingResult.getScore()) {
                    uniqueResultsMap.put(id, result);
                }
            }
        }

        // 转换为列表并按得分排序
        List<VectorSearchService.SearchResult> fusedResults = new ArrayList<>(uniqueResultsMap.values());
        fusedResults.sort((r1, r2) -> Float.compare(r2.getScore(), r1.getScore()));

        // 限制结果数量
        if (fusedResults.size() > topK) {
            fusedResults = fusedResults.subList(0, topK);
        }

        return fusedResults;
    }

    /**
     * 流式回调接口
     */
    public interface StreamCallback {
        void onSearchResults(List<VectorSearchService.SearchResult> results);
        void onReasoningChunk(String chunk);
        void onContentChunk(String chunk);
        void onComplete(String fullContent, String fullReasoning);
        void onError(Exception e);
    }
}
