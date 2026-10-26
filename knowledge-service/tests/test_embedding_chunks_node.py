"""
EmbeddingChunksNode 单元测试

覆盖点：
1. 正常流程：多批次嵌入、dense/sparse 向量正确写入 chunks
2. state 校验：chunks 缺失 / 非 list / 元素非 dict
3. 异常分支：模型创建失败、嵌入失败、嵌入结果为空
4. 稀疏向量提取的正确性

设计为全 mock 外部依赖（AIClients / BGE-M3），可离线运行。
"""
import sys
from pathlib import Path
from unittest import mock

# 将项目根加入 sys.path，保证 knowledge 包可导入
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 导入期 mock ──
# 1) pymilvus.model.hybrid 依赖 torch 等重库，测试不加载真实模型
# 2) knowledge.utils.client.ai_clients 导入链含 langchain_openai 等重依赖，
#    而测试中对 AIClients.get_bge_m3_client 全量 mock，故整体注入假模块
def _ensure_import_mocks():
    import types
    # (1) pymilvus.model.hybrid
    try:
        from pymilvus.model.hybrid import BGEM3EmbeddingFunction  # noqa: F401
    except (ImportError, AttributeError):
        pymilvus_pkg = sys.modules.get("pymilvus")
        model_pkg = types.ModuleType("pymilvus.model")
        hybrid_pkg = types.ModuleType("pymilvus.model.hybrid")
        hybrid_pkg.BGEM3EmbeddingFunction = type("BGEM3EmbeddingFunction", (), {})
        model_pkg.hybrid = hybrid_pkg
        if pymilvus_pkg is not None:
            pymilvus_pkg.model = model_pkg
        sys.modules["pymilvus.model"] = model_pkg
        sys.modules["pymilvus.model.hybrid"] = hybrid_pkg

    # (2) 确保父包可解析（即便真实包无法导入也不阻断）
    for parent in ("knowledge", "knowledge.utils", "knowledge.utils.client"):
        if parent not in sys.modules:
            try:
                __import__(parent)
            except Exception:
                sys.modules[parent] = types.ModuleType(parent)

    # (3) 注入假 ai_clients 模块
    if "knowledge.utils.client.ai_clients" not in sys.modules:
        fake_clients = types.ModuleType("knowledge.utils.client.ai_clients")

        class AIClients:
            @classmethod
            def get_bge_m3_client(cls):
                raise NotImplementedError("测试中必须 mock 本方法")

        fake_clients.AIClients = AIClients
        sys.modules["knowledge.utils.client.ai_clients"] = fake_clients


_ensure_import_mocks()

import pytest
import numpy as np
from scipy import sparse

from knowledge.processor.improt_processor.config import ImportConfig
from knowledge.processor.improt_processor.exceptions import (
    StateFieldError,
    ValidationError,
    EmbeddingError,
)
from knowledge.processor.improt_processor.nodes.embedding_chunks_node import (
    EmbeddingChunksNode,
)

# 需要 mock 的模块级引用位置
NODE_MODULE = "knowledge.processor.improt_processor.nodes.embedding_chunks_node"


# ---------------------------------------------------------------
# 工具函数：构造假 chunk 与假嵌入模型
# ---------------------------------------------------------------
def make_chunk(index: int) -> dict:
    return {
        "item_name": f"商品{index}",
        "content": f"这是第 {index} 个 chunk 的内容",
    }


def make_fake_embed_model(total: int, batch_size: int):
    """构造假的 BGE-M3 客户端：按批次返回 dense/sparse 结果。

    dense: 每行一个长度为 embedding_dim 的 list
    sparse: scipy CSR 矩阵，模拟 BGE-M3 输出
    """
    embedding_dim = 4

    class FakeEmbedModel:
        def encode_documents(self, documents):
            n = len(documents)
            # 真实 BGE-M3 返回的 dense 为 numpy 数组（源码对其调用 .tolist()）
            dense = np.array(
                [[float(i), 0.0, 0.0, 0.0] for i in range(n)], dtype=np.float32
            )
            data, indices, indptr = [], [], [0]
            for doc in documents:
                # 从 "商品{i}\n这是第 {i} 个 chunk 的内容" 解析出全局索引，
                # 使 token_id 与全局 chunk 序号对齐（模拟真实 tokenizer 的确定性输出）
                idx = int(doc.split("商品")[1].split("\n")[0])
                # 每个 chunk 的 (token_id, value) 对
                for token_id in (idx * 10, idx * 10 + 1):
                    indices.append(token_id)
                    data.append(float(idx + 1) if token_id % 2 == 0 else float(idx + 1) * 0.5)
                indptr.append(len(data))
            sparse_csr = sparse.csr_matrix((data, indices, indptr))
            return {"dense": dense, "sparse": sparse_csr}

    return FakeEmbedModel()


# ---------------------------------------------------------------
# Fixture：默认配置 + 节点实例
# ---------------------------------------------------------------
@pytest.fixture
def node():
    config = ImportConfig(embedding_batch_size=2)
    return EmbeddingChunksNode(config=config)


# ---------------------------------------------------------------
# 1. 正常流程
# ---------------------------------------------------------------
class TestNormalFlow:
    def test_multi_batch_embedding(self, node):
        """超过一个批次时，所有 chunks 都应被嵌入（当前实现存在 return 缩进 bug，会失败）"""
        chunks = [make_chunk(i) for i in range(5)]  # batch_size=2 → 3 批

        fake_model = make_fake_embed_model(total=5, batch_size=2)

        with mock.patch(f"{NODE_MODULE}.AIClients.get_bge_m3_client", return_value=fake_model):
            state = {"chunks": chunks}
            result = node.process(state)

        # 关键断言：所有 5 个 chunk 都必须被处理
        assert len(result["chunks"]) == 5, (
            f"期望处理全部 5 个 chunks，实际仅 {len(result['chunks'])} 个。"
            "疑似 process() 中 return state 位于 for 循环内，只处理了第一批。"
        )

        for i, chunk in enumerate(result["chunks"]):
            assert "dense_vector" in chunk, f"chunk[{i}] 缺少 dense_vector"
            assert "sparse_vector" in chunk, f"chunk[{i}] 缺少 sparse_vector"
            assert len(chunk["dense_vector"]) == 4
            assert isinstance(chunk["sparse_vector"], dict)
            assert set(chunk["sparse_vector"].keys()) == {i * 10, i * 10 + 1}

    def test_single_batch_embedding(self, node):
        """单个批次（chunk 数 <= batch_size）应正常嵌入"""
        chunks = [make_chunk(i) for i in range(2)]
        fake_model = make_fake_embed_model(total=2, batch_size=2)

        with mock.patch(f"{NODE_MODULE}.AIClients.get_bge_m3_client", return_value=fake_model):
            result = node.process({"chunks": chunks})

        assert len(result["chunks"]) == 2
        for chunk in result["chunks"]:
            assert "dense_vector" in chunk
            assert "sparse_vector" in chunk

    def test_sparse_vector_content(self, node):
        """稀疏向量应为 {token_id: weight} 字典"""
        chunks = [make_chunk(0)]
        fake_model = make_fake_embed_model(total=1, batch_size=2)

        with mock.patch(f"{NODE_MODULE}.AIClients.get_bge_m3_client", return_value=fake_model):
            result = node.process({"chunks": chunks})

        sparse_vec = result["chunks"][0]["sparse_vector"]
        # 偶数 token 权重为 1.0，奇数 token 权重为 0.5
        assert sparse_vec == {0: 1.0, 1: 0.5}


# ---------------------------------------------------------------
# 2. state 校验
# ---------------------------------------------------------------
class TestStateValidation:
    def test_missing_chunks(self, node):
        with pytest.raises(StateFieldError):
            node.process({})

    def test_empty_chunks(self, node):
        with pytest.raises(StateFieldError):
            node.process({"chunks": []})

    def test_chunks_not_list(self, node):
        with pytest.raises(StateFieldError):
            node.process({"chunks": "not-a-list"})

    def test_chunk_not_dict(self, node):
        with pytest.raises(ValidationError):
            node.process({"chunks": [make_chunk(0), "bad-chunk"]})


# ---------------------------------------------------------------
# 3. 异常分支
# ---------------------------------------------------------------
class TestErrorBranches:
    def test_model_creation_connection_error(self, node):
        """模型创建抛出 ConnectionError → EmbeddingError"""
        with mock.patch(
            f"{NODE_MODULE}.AIClients.get_bge_m3_client",
            side_effect=ConnectionError("模型加载失败"),
        ):
            with pytest.raises(EmbeddingError):
                node.process({"chunks": [make_chunk(0)]})

    def test_embed_failure(self, node):
        """encode_documents 抛异常 → EmbeddingError"""
        class BrokenModel:
            def encode_documents(self, documents):
                raise RuntimeError("GPU 内存不足")

        with mock.patch(f"{NODE_MODULE}.AIClients.get_bge_m3_client", return_value=BrokenModel()):
            with pytest.raises(EmbeddingError):
                node.process({"chunks": [make_chunk(0)]})

    def test_embed_result_empty(self, node):
        """encode_documents 返回空 → EmbeddingError"""
        class EmptyModel:
            def encode_documents(self, documents):
                return {}

        with mock.patch(f"{NODE_MODULE}.AIClients.get_bge_m3_client", return_value=EmptyModel()):
            with pytest.raises(EmbeddingError):
                node.process({"chunks": [make_chunk(0)]})


# ---------------------------------------------------------------
# 4. 稀疏向量提取单元测试
# ---------------------------------------------------------------
class TestExtractSparseVector:
    def test_extract(self, node):
        """从 CSR 矩阵中正确提取第 index 行的稀疏向量"""
        # 3 行 CSR：row0={(0:1.0),(1:0.5)} row1={(10:2.0),(11:1.0)} row2={(20:3.0)}
        data = [1.0, 0.5, 2.0, 1.0, 3.0]
        indices = [0, 1, 10, 11, 20]
        indptr = [0, 2, 4, 5]
        csr = sparse.csr_matrix((data, indices, indptr))

        assert node._extract_sparse_vector(csr, 0) == {0: 1.0, 1: 0.5}
        assert node._extract_sparse_vector(csr, 1) == {10: 2.0, 11: 1.0}
        assert node._extract_sparse_vector(csr, 2) == {20: 3.0}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
