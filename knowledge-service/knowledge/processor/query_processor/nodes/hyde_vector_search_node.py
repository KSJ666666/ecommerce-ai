from typing import Optional, Dict, Any, Tuple, List

from langchain_core.messages import SystemMessage, HumanMessage

from knowledge.processor.query_processor.base import BaseNode, T
from knowledge.processor.query_processor.exceptions import StateFieldError
from knowledge.processor.query_processor.state import QueryGraphState
from knowledge.prompt.query_prompt import HYDE_USER_PROMPT_TEMPLATE
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors
from knowledge.utils.milvus_util import create_hybrid_search_requests, _item_names_filter, execute_hybrid_search_query


class HydeVectorSearch(BaseNode):
    name = "hyde_vector_search_node"
    def process(self, state: QueryGraphState) -> Dict[str,Any] | QueryGraphState:
        """

        :param state:
        :return:
        """
        #1.检验参数
        rewritten_query, item_names = self._validate_state(state)

        #2.# 2. 利用LLM生成原始问题对应的假设性答案（解决跨域不对称）
        hy_document = self._generate_hy_document(rewritten_query, item_names)

        #3.获取milvus客户端
        try:
            milvus_client = StorageClients.get_milvus_client()
        except ConnectionError as e:
            self.logger.error(f"获取milvus客户端失败，原因：{e}")
            return None
        #4.获取嵌入模型
        try:
            embedding_model = AIClients.get_bge_m3_client()
        except ConnectionError as e:
            self.logger.error(f"获取嵌入模型失败，原因：{e}")
            return None

        #5.生成查询向量
        try:
            query_vector = generate_bge_m3_hybrid_vectors(embedding_model,[f"{rewritten_query}\n{hy_document}"])
        except ConnectionError as e:
            self.logger.error(f"假设性文档{hy_document}嵌入获取失败 原因:{str(e)}")
            return state

        #6，创建混合搜索请求
        #6.1创建过滤条件
        expr, expr_params = _item_names_filter(item_names)

        hybrid_search_req = create_hybrid_search_requests(dense_vector=query_vector['dense'][0],
                                      sparse_vector=query_vector['sparse'][0],
                                      dense_params=None,
                                      expr=expr,
                                      expr_params=expr_params
                                      )

        #7.执行混合搜索
        hybrid_search_res = execute_hybrid_search_query(milvus_client,
                                    self.config.chunks_collection,
                                    hybrid_search_req,
                                    ranker_weights=(0.5,0.5),
                                    norm_score=True,
                                    limit=5,
                                    output_fields=["chunk_id", "content", "item_name", 'title']
                                    )
        if not hybrid_search_res or not hybrid_search_res[0]:
            return state

        return {
            "hybrid_embedding_chunks": hybrid_search_res[0]
        }

    def _validate_state(self, state:QueryGraphState)->Tuple[str,List[str]]:
        """
        参数检验
        :param state:
        :return:
        """
        #1.获取参数
        rewritten_query = state.get("rewritten_query")
        if not rewritten_query:
            raise StateFieldError(node_name=self.name, field_name="rewritten_query", message="rewritten_query is required")

        item_names = state.get("item_names")

        if not item_names:
            raise StateFieldError(node_name=self.name, field_name="item_names", message="item_names is required")

        return rewritten_query, item_names

    def _generate_hy_document(self, rewritten_query, item_names):
        #1.获取llm客户端
        #1.1。这里不需要大模型输出json,而是普通字符串
        try:
            llm_cilent = AIClients.get_openai_llm_client(response_format=False)
        except ConnectionError as e:
            self.logger.error(f"获取llm客户端失败，原因：{e}")
            return None



        #2.构建提示词
        # 2.1 获取系统提示词
        system_prompt = f"您是一位{item_names}方面的技术文档领域的专家，主要擅长编写技术文档、操作手册、文档规格说明"
        # 2.2 获取用户提示词
        user_prompt = HYDE_USER_PROMPT_TEMPLATE.format(item_names=item_names, rewritten_query=rewritten_query)

        #3.调用大模型
        try:
            response = llm_cilent.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
                ]
            )
        except ConnectionError as e:
            self.logger.error(f"调用大模型失败，原因：{e}")
            return None
        #4.判断结果
        if not response.content.strip():
            return None
        #5.返回结果
        return response.content.strip()
if __name__ == "__main__":

    mock_state = {
        "rewritten_query": "RS-13 数字万用表如何测量直流电压？",
        "item_names": ["RS-13 数字万用表"],
    }

    node = HydeVectorSearch()
    result = node.process(mock_state)

    chunks = result.get("hybrid_embedding_chunks", [])
    print(f"\n【HyDE 检索结果】: {len(chunks)} 条")
    for i, chunk in enumerate(chunks, 1):
        entity = chunk.get("entity", {})
        print(f"  [{i}] chunk_id={entity.get('chunk_id')} "
              f"item_name={entity.get('item_name')} "
              f"distance={chunk.get('distance', 'N/A')}")
        content = entity.get("content", "")
        print(f"      内容: {content[:80]}...")





