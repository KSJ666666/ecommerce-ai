from knowledge.processor.query_processor.base import BaseNode, T
from knowledge.processor.query_processor.exceptions import StateFieldError
from knowledge.processor.query_processor.state import QueryGraphState
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.embedding_util import generate_bge_m3_hybrid_vectors
from knowledge.utils.milvus_util import create_hybrid_search_requests, _item_names_filter, execute_hybrid_search_query


class HybridVectorSearch(BaseNode):
    """
    混合向量搜索节点

    """
    name = 'hybrid_vector_search_node'

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """
        混合向量搜索节点处理

        :param state:
        :return:
        """
        #1.校验参数
        rewritten_query, item_names = self._validate_state(state)

        #2.获取bgem3模型
        try:
            bge_m3_client = AIClients.get_bge_m3_client()
        except ConnectionError as e:
            self.logger.error(f"获取bgem3模型失败,原因： {e}")
            return state

        #3.获取milvus客户端
        try:
            milvus_client = StorageClients.get_milvus_client()
        except ConnectionError as e:
            self.logger.error(f"获取milvus客户端失败,原因： {e}")
            return state

        #4.将问题向量化
        try:
            query_vector = generate_bge_m3_hybrid_vectors(bge_m3_client, [rewritten_query])


        #5.创建混合向量请求
        #5.1创建过滤条件
            expr,expr_params =  _item_names_filter(item_names)
            hybrid_search_req = create_hybrid_search_requests(dense_vector=query_vector['dense'][0],
                                          sparse_vector=query_vector['sparse'][0],
                                          expr=expr,
                                          expr_params=expr_params,
                                          limit=5
                                          )
            #5.2执行混合向量搜索
            hybrid_search_res = execute_hybrid_search_query(milvus_client = milvus_client,
                                                            collection_name=self.config.chunks_collection,
                                                            search_requests=hybrid_search_req,
                                                            ranker_weights=(0.5,0.5),
                                                            norm_score=True,
                                                            limit=5,
                                                            output_fields=["chunk_id", "content", "item_name", 'title'],

                                                            )
        #6检索校验
            if not hybrid_search_res or not hybrid_search_res[0]:
                return state
        #7.返回state
            return {"embedding_chunks": hybrid_search_res[0]}

        except Exception as e:
            self.logger.error(f"用户问题{rewritten_query}执行混合搜索查询失败 原因:{str(e)}")
        return state



        return state
    def _validate_state(self, state: QueryGraphState)->tuple[str, list[str]]:
        rewritten_query = state.get("rewritten_query")

        item_names = state.get("item_names")

        if not rewritten_query or not isinstance(rewritten_query, str):
            raise StateFieldError(node_name=self.name, field_name='rewritten_query', expected_type=str)

        if not item_names or not isinstance(item_names, list):
            raise StateFieldError(node_name=self.name, field_name='item_names', expected_type=list)

        return rewritten_query, item_names



if __name__ == '__main__':
    import json

    state = {
        "rewritten_query": "RS-13 数字万用表怎么测电阻",
        "item_names": ["RS-13 数字万用表"]  # 没用的
    }

    vector_search = HybridVectorSearch()
    result = vector_search.process(state)

    for r in result.get('embedding_chunks'):
        print(json.dumps(r, ensure_ascii=False, indent=2))