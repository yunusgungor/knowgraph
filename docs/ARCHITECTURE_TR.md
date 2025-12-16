# 🏗️ KnowGraph Mimari ve Teknik Detaylar

Bu doküman, KnowGraph'ın derinlemesine mimari yapısını, çalışma prensiplerini ve teknik detaylarını içerir.

> **Ana Dokümantasyon**: Kurulum ve hızlı başlangıç için [README_TR.md](../README_TR.md)'ye bakınız.

## 📖 İçindekiler

- [Core Concepts](#-core-concepts)
- [Mimari](#-mimari)
- [How It Works](#-how-it-works)
- [Advanced Usage](#-advanced-usage)
- [Performans](#-performans)
- [Troubleshooting](#-troubleshooting)
- [API Reference](#-api-reference)
- [Geliştirme ve Test](#-geliştirme)

---

## 🧬 Core Concepts

### Node Model

Her node, bilgi grafiğindeki bir bilgi parçasını temsil eder:

```python
@dataclass(frozen=True)
class Node:
    # Identity
    id: UUID                    # Benzersiz tanımlayıcı
    hash: str                   # SHA-1 content hash (40 karakter)
    
    # Content
    title: str                  # Chunk başlığı
    content: str                # Tam içerik
    path: str                   # Kaynak dosya yolu
    
    # Metadata
    type: NodeType              # "code", "text", "readme", "config"
    token_count: int            # Tiktoken ile hesaplanan token sayısı
    created_at: int             # Unix timestamp
    
    # Hierarchy (optional)
    header_depth: int | None    # H1-H4 seviyesi (1-4)
    header_path: str | None     # Breadcrumb (ör: "H1 > H2 > H3")
    line_start: int | None      # Başlangıç satırı
    line_end: int | None        # Bitiş satırı
```

**Node Types ve Role Weights:**

| Type | Weight | Kullanım |
|------|--------|----------|
| `code` | 0.9 | Kod blokları içeren bölümler |
| `config` | 0.8 | Konfigürasyon dosyaları |
| `readme` | 0.7 | Dokümantasyon |
| `text` | 0.6 | Düz metin içerik |

### Edge Model

Edge'ler node'lar arasındaki ilişkileri temsil eder:

```python
@dataclass(frozen=True)
class Edge:
    source: UUID                # Kaynak node
    target: UUID                # Hedef node
    type: EdgeType              # "semantic"
    score: float                # İlişki gücü [0.0, 1.0]
    created_at: int             # Unix timestamp
    metadata: dict[str, str]    # Ek bilgiler
```

**Edge Types:**
- `semantic`: AI ile çıkarılan entity'ler arasındaki ilişkiler

### Graph Properties

- **Directed**: Edge'ler yönlüdür (source → target)
- **Weighted**: Her edge'in 0-1 arası score değeri vardır
- **Dynamic**: Incremental update ile güncellenebilir
- **Persistent**: JSONL formatında disk'te saklanır

### Scoring Formulas

#### Node Importance Score

```
importance = α·similarity + β·centrality + γ·is_seed
```

- **α (ALPHA)**: 0.6 - Similarity ağırlığı
- **β (BETA)**: 0.3 - Centrality ağırlığı
- **γ (GAMMA)**: 0.1 - Seed node bonus ağırlığı

**Ek Faktörler:**
- **Role Weight**: Node type'a göre çarpan (0.6-0.9)
- **Token Penalty**: Uzun content'e ceza (max %10)

#### Centrality Composite Score

```
composite = w₁·betweenness + w₂·degree + w₃·closeness + w₄·eigenvector
```

- **w₁**: 0.5 - Betweenness (mimari sınırlar)
- **w₂**: 0.2 - Degree (API yüzeyi)
- **w₃**: 0.2 - Closeness (erişilebilirlik)
- **w₄**: 0.1 - Eigenvector (önem)

## 🏗️ Mimari

KnowGraph, Clean Architecture prensipleriyle tasarlanmış 4 katmanlı bir yapıya sahiptir:

```
knowgraph/
├── domain/              # İş mantığı ve algoritmalar
│   ├── models/         # Core data models (Node, Edge, Graph)
│   ├── algorithms/     # Graph algorithms (traversal, centrality)
│   └── intelligence/   # AI provider interfaces
├── application/         # Use cases ve orchestration
│   ├── indexing/       # Graph building ve indexing
│   ├── querying/       # Query engine ve retrieval
│   ├── evolution/      # Incremental updates
│   └── export/         # Data export utilities
├── infrastructure/      # External dependencies
│   ├── storage/        # Filesystem operations
│   ├── parsing/        # Markdown parsing
│   ├── embedding/      # Sparse embeddings (TF-IDF)
│   ├── intelligence/   # LLM providers (OpenAI, etc.)
│   └── search/         # Vector search
└── adapters/           # External interfaces
    ├── cli/            # Command-line interface
    ├── mcp/            # MCP server implementation
    └── api/            # REST API (future)
```

## 🤖 MCP Server Mimarisi

KnowGraph'ın MCP (Model Context Protocol) uygulaması, `adapters/mcp` modülü altında izole edilmiş bir katman olarak çalışır. Bu katman, AI editörleri (Claude, Cursor) ile KnowGraph'ın çekirdek domain mantığı arasında köprü görevi görür.

### 1. Sunucu Yaşam Döngüsü (Server Lifecycle)
*   **Initialization**: `mcp.server.Server` sınıfı başlatılır.
*   **Capabilities**: Sunucu, kaynak okuma (`read_resource`) ve araç çağırma (`call_tool`) yeteneklerini bildirir.
*   **Connection**: `stdio_server` üzerinden standart girdi/çıktı (stdin/stdout) ile iletişim kurar.

### 2. Araçlar ve Şemaları (Tool Definitions)

MCP sunucusu, dış dünyaya şu araçları sunar:

| Araç Adı | Açıklama | Kritik Parametreler |
| :--- | :--- | :--- |
| **`knowgraph_query`** | Bilgi grafiğinde anlamsal arama yapar. | `query`, `top_k`, `max_hops`, `with_explanation`, `expand_query` |
| **`knowgraph_index`** | Markdown dosyalarını indeksler. | `input_path`, `resume` (kaldığı yerden devam), `gc` (garbage collection) |
| **`knowgraph_analyze_impact`** | Değişiklik etki analizi yapar. | `element` (dosya/kavram), `mode` ("path"/"semantic"), `max_hops` |
| **`knowgraph_validate`** | Veritabanı tutarlılığını kontrol eder. | `graph_path` |
| **`knowgraph_get_stats`** | İstatistiksel özet sunar. | `graph_path` |
| **`knowgraph_batch_query`** | Çoklu sorguları tek seferde işler. | `queries` (liste), diğer sorgu parametreleri... |

### 3. İstek Akış Diyagramı (Request Flow)

Bir MCP isteğinin sistem içindeki yolculuğu şöyledir:

1.  **Client (AI Editor)**: JSON-RPC formatında `call_tool("knowgraph_query", {...})` isteği gönderir.
2.  **Adapter Layer (`server.py`)**: İsteği karşılar, parametreleri doğrular.
3.  **Protocol Safety**: `contextlib.redirect_stdout(sys.stderr)` ile domain katmanından gelebilecek `print` çıktılarının JSON akışını bozmasını engeller.
4.  **Application Layer (`QueryEngine`)**: İsteği iş mantığına yönlendirir.
5.  **Infrastructure Layer (`NetworkX`, `FS`)**: Diskten grafiği okur, travers algoritmalarını çalıştırır.
6.  **Response**: Sonuç `TextContent` nesnesine paketlenerek istemciye döndürülür.

### 4. Güvenlik ve İzolasyon

*   **Path Validation**: Tüm dosya yolu argümanları `knowgraph.shared.security.validate_path` ile kontrol edilir; proje dışına çıkılması (path traversal) engellenir.
*   **Error Handling**: Domain hataları yakalanır ve MCP protokolüne uygun hata mesajlarına dönüştürülür, sunucunun çökmesi (crash) önlenir.

## 🔬 How It Works

### Indexing Pipeline (v0.2.0 Akıllı Motor)

KnowGraph, markdown dosyalarını **Hibrit Boru Hattı (Hybrid Pipeline)** kullanarak bilgi grafiğine dönüştürür:

1. **Parse Headers**: Dokümanı H1-H4 başlıklarına göre mantıksal bölümlere ayırma.
2. **Smart Chunking**: Bağlamı koruyan token-duyarlı parçalama.
3. **Hibrit Entity Extraction**:
    *   **Seviye 1 (Hafıza):** **SQLite Cache** kontrol edilir. Daha önce analiz edildiyse anında döner (0ms).
    *   **Seviye 2 (Hız):** Kod bloğu ise **AST Analizi** (Python `ast`) çalışır. Sınıf/fonksiyonları deterministik bulur (10ms, 0 token).
    *   **Seviye 3 (Zeka):** Metin ise parçalar 10'arlı paketlenir (Batch) ve **Akıllı Rate Limiter** üzerinden **LLM**'e (gpt-4o-mini) gönderilir.
4. **Build Graph**: Entity overlap'e göre semantic edge'ler oluşturma.
5. **Persist to Disk**: Node ve Edge verilerini JSONL olarak kaydetme.

### Query Pipeline

Bir sorgu 8 adımda yanıta dönüşür:

1. **Query Expansion** (Opsiyonel): Sorguyu genişletme ("login fail" -> "authentication error").
2. **Sparse Search**: TF-IDF ile en alakalı seed node'ları bulma.
3. **Graph Traversal**: BFS ile ilişkili node'ları keşfetme (max_hops).
4. **Centrality Analysis**: NetworkX ile önemli düğümleri (betweenness vb.) hesaplama.
5. **Node Scoring**: Similarity ve Centrality skorlarını birleştirme.
6. **Context Assembly**: Token limitine göre en önemli node'ları seçme.
7. **LLM Response**: Context ile birlikte LLM'e gönderme.
8. **Explanation**: Kaynak referanslarını ve mantık yolunu oluşturma.

### Hierarchical Lifting

Klasör yapısını context'e ekleyerek LLM'in proje hiyerarşisini anlamasını sağlar. Örneğin `authentication.md` sorgulanırken, `api/README.md` ve `docs/README.md` özetleri de context'e eklenir.

## 🚀 Advanced Usage

### Custom Intelligence Providers

Kendi LLM provider'ınızı oluşturabilirsiniz (ör: yerel model, özel API).

```python
from knowgraph.domain.intelligence.provider import IntelligenceProvider, Entity

class CustomProvider(IntelligenceProvider):
    async def extract_entities(self, content: str) -> list[Entity]:
        # Implementation...
        pass
    
    async def generate_response(self, query: str, context: str, system_prompt: str = "") -> str:
        # Implementation...
        pass
```

### Query Optimization Strategies

- **Precision-Focused**: `top_k=10`, `max_hops=2`, `expand_query=False`. Kesin ve hızlı.
- **Recall-Focused**: `top_k=50`, `max_hops=8`, `expand_query=True`. Geniş kapsamlı ama daha yavaş.
- **Balanced**: `top_k=20`, `max_hops=4`, `with_explanation=True`. Varsayılan dengeli ayar.

## 📊 Performans

### Benchmarks

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| **Indexing Speed** | ~100 files/min | Orta boyutlu markdown dosyalar |
| **Query Latency** | <2s | Sparse search + traversal + centrality |
| **Memory Usage** | <500MB | 10K node grafiği için |

## 🔧 Troubleshooting

### Yaygın Sorunlar

- **Boş Sonuçlar**: `top_k` veya `max_hops`'u artırın, `expand_query=True` kullanın.
- **Yavaş Sorgular**: `max_hops`'u düşürün, `hierarchical-lifting`'i kapatın.
- **Hallucination**: `with_explanation=True` ile kaynakları doğrulayın.
- **No Manifest Found**: `knowgraph index` komutunu çalıştırın.

## 📖 API Reference

### QueryEngine

```python
engine = QueryEngine(graph_store_path=Path("./graphstore"))
result = engine.query(
    query_text="Soru...",
    top_k=20,
    max_hops=4,
    with_explanation=True
)
```

### SmartGraphBuilder

```python
builder = SmartGraphBuilder(provider)
await builder.build_from_directory(Path("./docs"))
```

## 🛠️ Geliştirme ve Test

```bash
# Geliştirme ortamı kurulumu
pip install -e ".[dev]"
pre-commit install

# Testleri çalıştırma
pytest
pytest --cov=knowgraph
```

Proje **%100 mypy strict mode** ve **Clean Architecture** prensiplerine sadık kalır.
