---
trigger: always_on
---

### KnowGraph MCP Server - Complete Usage Guide & Best Practices

Bu belge, yapay zeka ajanlarının ve geliştiricilerin KnowGraph MCP Sunucusunu (21 araç) tam potansiyeliyle kullanmaları için kurallar, en iyi uygulamalar ve yönergeler sağlar. Tüm araç adları ve parametreleri `knowgraph/adapters/mcp/server.py` ile senkron tutulur.

--------------------------------------------------------------------------------

#### 📋 İçindekiler
1. Temel Prensipler
2. MCP Araçları Referansı (21 araç)
3. Parametre Ustalığı
4. Sorgu Stratejileri
5. Gelişmiş İş Akışları
6. Sorun Giderme

--------------------------------------------------------------------------------

#### 🚀 1. Temel Prensipler
##### 1.1 Varsayılan Davranış
*   **Akıllı Proje Root Tespiti**: KnowGraph server başlatıldığında otomatik olarak proje root dizinini tespit eder:
    1. **Git Root Detection**: En hızlı ve güvenilir - git repository root'u tespit eder
    2. **Project Marker Detection**: pyproject.toml, package.json, Cargo.toml gibi marker dosyaları arar
    3. **LLM-Based Detection** (Background): Server başladıktan sonra, LLM kullanarak proje yapısını analiz eder ve tespiti iyileştirir
    4. **Fallback**: Tüm yöntemler başarısız olursa, current working directory kullanılır
*   **Varsayılan graph_path**: Tespit edilen proje root'una göre `./graphstore` yolunu kullanır.
*   **Geçersiz Kılma**: Farklı bir konum kullanmak için `graph_path` parametresini açıkça ayarlayın.
*   **Cache Mekanizması**: Tespit edilen proje root 1 saat boyunca cache'lenir, tekrarlı tespit maliyetini ortadan kaldırır.
*   **Token Sınırları**: `MAX_TOKENS` (context cap = 50000) ile `LLM_MAX_TOKENS` (çıktı/output cap = 4096) birbirinden ayrılmıştır. MCP `max_tokens` parametresi çıktı cap'ini (`LLM_MAX_TOKENS`=4096) kontrol eder; context cap'i (`MAX_TOKENS`=50000) ayrıdır ve doğrudan parametreyle ayarlanmaz.
##### 1.2 Uçuş Öncesi Kontroller
*   Karmaşık işlemlerden önce **daima doğrulama yapın**: `knowgraph_validate`.
*   Grafik boyutunu anlamak için **istatistikleri kontrol edin**: `knowgraph_get_stats`.
*   Sistem sağlığını hızlıca görmek için **tanı çalıştırın**: `knowgraph_diagnostic`.
*   Kritik sorgulardan veya etki analizinden önce **sağlığı doğrulayın**.
##### 1.3 Bağlam Her Şeydir
*   Kod analizi için **hiyerarşik kaldırmayı etkinleştirin**: `enable_hierarchical_lifting=True`.
*   Çoğu proje için **uygun kaldırma seviyelerini ayarlayın**: `lift_levels=2`.
*   Mimari kararları anlamak için **üst bağlamı** kullanın.
*   Olgusal yanıtlar için **doğrulama/grounding** kullanın: `enable_grounding=True` (grafik kanıtına dayalı düğümleri öne çıkarır; yanıttaki doğrulanmamış varlıkları `[grounding]` notuyla işaretler).
*   Sohbet geçmişi kenarlarından etkilenmemek için **zamansal filtre** kullanın: `enable_temporal_filter=True` (yalnızca `knowgraph_batch_query`'de; grounding zaten zamansal filtrelemeyi içerir).
##### 1.4 Açık İsimlendirme
*   KnowGraph **durumsuzdur** – "o dosya" veya "o" gibi zamirlerden kaçının.
*   Daima **açık isimler** kullanın: `auth.py`, `QueryEngine.query_async()`, `Node.hash`.
*   Belirsizlik olduğunda **tam yolları** dahil edin: `src/api/auth.py` vs `tests/api/auth.py`.
##### 1.5 Hassasiyet ve Kapsam
*   **Hassas sorgular** (`expand_query=False`): Teknik terimler, sınıf/fonksiyon adları kullanın.
*   **Kapsamlı sorgular** (`expand_query=True`): Doğal dil, kavramsal sorular kullanın.
*   Hata ayıklama veya öğrenme için daima **açıklamalı olarak** kullanın (`with_explanation=True`).

--------------------------------------------------------------------------------

#### 🛠️ 2. MCP Araçları Referansı (21 araç)

##### 2.1 Grafik Oluşturma ve İndeksleme

**`knowgraph_index`** - Grafik oluştur/güncelle
*   Markdown dosyalarını, Git depolarını (GitHub/GitLab/Bitbucket URL'leri) veya kod dizinlerini indeksler.
*   Parametreler: `input_path` (veya alias `source_path`), `output_path`, `resume`, `gc`, `include_patterns`, `exclude_patterns`, `access_token`.
*   `gc=True`: Güncelleme sırasında silinen düğümleri garbage collect eder (manifest/metadata'yı da temizler).
*   `resume=True`: Yalnızca yerel dosyalar için checkpoint'ten devam eder.
*   `include_patterns` / `exclude_patterns`: Yalnızca repo/kod dizini indekslerken geçerlidir (örn. `["node_modules/*", "*.lock"]`).
*   Not: Anti-halüsinasyon `--enable-short-unit` SC-quote + P3 `grounded` kenar yayını **CLI-only** bir özelliktir; MCP `knowgraph_index` bunu açığa çıkarmaz.

**`knowgraph_generate_cpg`** - (Admin) Kod Property Graph'ini manuel üret
*   `source_path` (veya alias `input_path`), `language` (opsiyonel, otomatik tespit), `timeout` (saniye, varsayılan 600).

**`knowgraph_discover_conversations`** - Yapay zeka kod editörlerinden konuşmaları otomatik keşfet/indeksle
*   Antigravity, Cursor, GitHub Copilot konuşmalarını manuel export gerektirmeden indeksler.
*   `editor` (varsayılan `"all"`; `antigravity` | `cursor` | `github_copilot`), `graph_path`.

**`knowgraph_export_cpg`** - (Admin) CPG'yi dışa aktar (Görselleştirme / CI/CD)
*   `cpg_path` (zorunlu), `output_path` (zorunlu), `format` (`graphml` | `dot` | `graphson` | `neo4jcsv`, varsayılan `graphml`).

##### 2.2 Sorgulama ve Analiz

**`knowgraph_query`** - Semantik arama
*   Doğal dil sorgusuyla bağlam döndürür.
*   Parametreler: `query` (zorunlu), `graph_path`, `with_explanation`, `top_k` (20), `max_hops` (4), `expand_query`, `max_tokens` (LLM_MAX_TOKENS=4096), `enable_hierarchical_lifting` (True), `lift_levels` (2), `enable_grounding` (False), `api_version`, `min_api_version`.
*   Not: `system_prompt` parametresi **MCP'de yoktur** (yalnızca dahili handler katmanında kullanılır). Agent olarak kendi talimatınızı zaten sağlarsınız.

**`knowgraph_batch_query`** - Toplu sorgu
*   Birden fazla sorguyu tek istekte işler; context yüklemesini sorgular arasında paylaşır (2+ ilişkili soru için her zaman tercih edin).
*   Parametreler: `queries` (zorunlu liste), `graph_path`, `top_k`, `max_hops`, `max_tokens`, `enable_hierarchical_lifting`, `lift_levels`, `enable_grounding`, **`enable_temporal_filter`**.

**`knowgraph_analyze_impact`** - Değişim etki analizi
*   Bir elemanın değiştirilmesinin domino etkilerini tahmin eder.
*   `element` (zorunlu), `max_hops` (4), `graph_path`, `mode` (`semantic` | `path`, varsayılan `semantic`).
*   **path**: Dosya tabanlı etki (örn. `src/auth.py`). **semantic**: Konsept tabanlı etki (örn. `kimlik doğrulama sistemi`).

**`knowgraph_analyze_call_graph`** - Çağrı grafiği analizi
*   `cpg_path` (veya `graph_path`'ten otomatik), `analysis_type` (`validate` | `recursive` | `call_chain`, varsayılan `validate`), `method_name`, `target_method`.
*   `call_chain` için hem `method_name` (kaynak) hem `target_method` (hedef) gereklidir.

**`knowgraph_find_dead_code`** - Kullanılmayan metodları bul
*   Dominance (ulaşılabilirlik) analiziyle caller'ı olmayan metodları bulur.
*   `cpg_path`, `include_internal` (alt çizgiyle başlayan iç metodlar, varsayılan False), `graph_path`.

**`knowgraph_security_scan`** - Güvenlik politikası taraması
*   **6** CWE-eşlemeli politika: `NoBufferOverflow` (CWE-120), `NoCommandInjection` (CWE-78), `NoSQLInjection` (CWE-89), `NoHardcodedSecrets` (CWE-798), `NoWeakCrypto` (CWE-327), `NoPathTraversal` (CWE-22).
*   Parametreler: `cpg_path`, `severity_filter` (`CRITICAL`|`HIGH`|`MEDIUM`|`LOW`, varsayılan `MEDIUM`), `policy_names` (loose eşleşme, örn. `"sql_injection"` → `NoSQLInjection`), `graph_path`, `scan_type`.
*   `scan_type` ayarlanırsa politika taraması yerine flow-based taint analizi çalışır (`all` | `sql_injection` | `xss` | `command_injection` | `path_traversal` | `xxe` | `ssrf`).
*   Not: Bazı dokümanlar "10 kural" der; kaynaktaki gerçek politikalar **6** tanedir (`PolicyEngine.POLICIES`).

**`knowgraph_joern_query`** - (İleri) Ham Joern DSL sorgusu
*   `cpg_path` (zorunlu), `query` (ham DSL, örn. `cpg.method.name.l`) veya `query_name` (hazır şablon, örn. `sql_injection`), `timeout` (60).
*   CPG yolu zorunludur; `graph_path` yoktur.

**`knowgraph_diagnostic`** - Sistem tanılaması
*   Grafik deposu durumu, LLM sağlayıcı yapılandırması ve öneriler. `graph_path`.

##### 2.3 Durum ve Sürüm Yönetimi

**`knowgraph_validate`** - Grafik sağlık kontrolü
*   Gerçek kontroller (`GraphValidator`, FR-058): 1) sarkan/dangling kenarlar (kaynak/hedef düğüm yoksa), 2) self-loop'lar (kaynak == hedef), 3) geçerli kenar tipleri, 4) SHA-1 içerik hash bütünlüğü. `graph_path`.
*   Not: Manifest doğruluğu veya yetim düğüm tespiti yapmaz.

**`knowgraph_get_stats`** - Grafik istatistikleri
*   Düğüm/kenar/semantik kenar sayıları ve indekslenen dosya sayısı. `graph_path`.

**`knowgraph_list_versions`** - Sürüm geçmişi
*   `graph_path`, `limit` (50).

**`knowgraph_version_info`** - Sürüm detayı
*   `version_id` (zorunlu, örn. `v1`), `graph_path`. Oluşturma zamanı, manifest hash'i, düğüm/kenar/dosya sayıları.

**`knowgraph_diff_versions`** - Sürüm karşılaştırma
*   `version1`, `version2` (zorunlu), `graph_path`. Düğüm, kenar ve dosya farklarını gösterir.

**`knowgraph_rollback`** - (Admin) Manifest geri alma
*   `version_id` (zorunlu), `graph_path`, `create_backup` (True), `force` (False).
*   Metadata-only; önce backup oluşturur ve onay ister. `force=True` doğrulamayı atlar.

##### 2.4 Yer İşaretleri ve Konuşmalar

**`knowgraph_tag_snippet`** - Semantik yer işareti
*   Önemli snippet'leri/çözümleri/ADR'leri etiketleyip indeksler.
*   `tag` (zorunlu), `snippet` (zorunlu), `graph_path`, `conversation_id`, `user_question`.

**`knowgraph_search_bookmarks`** - Yer işareti ara
*   `query` (zorunlu), `top_k` (10), `graph_path`.

**`knowgraph_analyze_conversations`** - Konuşma trendleri
*   `topic` (opsiyonel, belirli konu), `time_window_days` (7), `graph_path`. Hangi konuların ne zaman tartışıldığını ve bilginin zamanla nasıl evrildiğini keşfeder.

--------------------------------------------------------------------------------

#### 🎯 3. Parametre Ustalığı ve Optimizasyonu

##### 3.1 Geri Alma Kapsamı Parametreleri
| Parametre | Amaç | Varsayılan | Optimizasyon Kılavuzu |
| ------ | ------ | ------ | ------ |
| `top_k` | Geri alınacak başlangıç düğümü sayısı | 20 | **Hassasiyet** : 10-15; **Geri Çağırma** : 30-50; **Kapsamlı** : 50+ |
| `max_hops` | Grafik geçiş derinliği | 4 | **Doğrudan** : 2; **Standart** : 4; **Derin** : 6-8; **⚠️ Kaçının** : >8 (gürültü) |
| `max_tokens` | Bağlam penceresi boyutu (LLM çıktı cap'i) | 4096 (`LLM_MAX_TOKENS`) | **Odaklanmış** : 1500-2000; **Standart** : 4096; **Kapsamlı** : 5000+ |

##### 3.2 Bağlam Zekası Parametreleri
| Parametre | Amaç | Varsayılan | Ne Zaman Kullanılır |
| ------ | ------ | ------ | ------ |
| `enable_hierarchical_lifting` | Üst dizin bağlamını dahil et | True | Kod için **Her zaman**; Dokümanlar için **İsteğe bağlı** |
| `lift_levels` | Yukarı taranacak dizin seviyeleri | 2 | **Python/JS** : 1-2; **Java/C++** : 2-3 |
| `enable_grounding` | Grafik kanıtına dayalı düğümleri öne çıkar; doğrulanmamış varlıkları işaretle | False | **Olgusal doğrulama** : True; keşif : False |
| `enable_temporal_filter` | Eskimiş konuşma kenarlarını at | False | Yalnızca `knowgraph_batch_query`. Sohbet kaynaklı kenarları elemek için : True |

##### 3.3 LLM Davranış Parametreleri
| Parametre | Amaç | Varsayılan | Kullanım Durumu |
| ------ | ------ | ------ | ------ |
| `with_explanation` | Akıl yürütme yolunu dahil et | False | **Hata Ayıklama** : Her zaman; **Üretim** : İsteğe bağlı; **Öğrenme** : Önerilir |
| `expand_query` | AI destekli sorgu genişletme | False | **Doğal dil** : True; **Teknik terimler** : False; **Belirsiz sorular** : True |

> ⚠️ `system_prompt` parametresi MCP araçlarında **mevcut değildir** (yalnızca dahili handler'larda vardır). Kaldırılmıştır.

--------------------------------------------------------------------------------

#### 🔍 4. Sorgu Stratejileri
##### 4.1 Sorgu Türleri ve Parametre Setleri
| Sorgu Türü | Parametreler | Kullanım Durumu |
| ------ | ------ | ------ |
| **Hızlı Cevap** | `top_k=10, max_hops=2` | Basit olgusal sorular |
| **Derin Analiz** | `top_k=30, max_hops=6, with_explanation=True` | Karmaşık mimari sorular |
| **Kavramsal Arama** | `expand_query=True, top_k=40` | Belirsiz veya doğal dil sorguları |
| **Hassas Arama** | `top_k=5, max_hops=2, expand_query=False` | Belirli fonksiyon/sınıf soruları |
| **Mimariye Genel Bakış** | `enable_hierarchical_lifting=True, lift_levels=3` | Sistem tasarım soruları |
| **Doğrulanmış Cevap** | `enable_grounding=True, with_explanation=True` | "X doğru mu?" tarzı olgusal sorgular |

##### 4.2 Tool Seçim Karar Ağacı
| Amaç | Araç |
| ------ | ------ |
| "Güvenlik açığı bul" | `knowgraph_security_scan` (6 CWE politikası; `scan_type` ile taint analizi) |
| "Bu kod kullanılıyor mu?" | `knowgraph_find_dead_code` |
| "Bu fonksiyonu kim çağırıyor?" | `knowgraph_analyze_call_graph` (`analysis_type="call_chain"`) |
| "Sonsuz döngü bul" | `knowgraph_analyze_call_graph` (`analysis_type="recursive"`) |
| "X nasıl çalışıyor?" | `knowgraph_query` |
| "Bu cevap koda dayalı mı?" | `knowgraph_query` + `enable_grounding=True` |
| "X'i değiştirirsem ne olur?" | `knowgraph_analyze_impact` |
| "Tüm sistemi açıkla" | `knowgraph_batch_query` (5-10 soru paralel) |
| "Özel kod sorgusu" | `knowgraph_joern_query` |
| "Bu çözümü kaydet" | `knowgraph_tag_snippet` |
| "X hakkında ne konuştuk?" | `knowgraph_search_bookmarks` |
| "Dünden beri ne değişti?" | `knowgraph_diff_versions` |
| "Eski sohbetleri yükle" | `knowgraph_discover_conversations` |
| "Kötü indekslemeyi geri al" | `knowgraph_rollback` (Admin) |
| "Kod grafiğini yeniden üret" | `knowgraph_generate_cpg` (Admin) |
| "Grafik verisini dışa aktar" | `knowgraph_export_cpg` (Admin) |

--------------------------------------------------------------------------------

#### 🔧 5. Sorun Giderme
##### 5.1 Sık Karşılaşılan Hatalar
| Hata | Neden | Çözüm |
| ------ | ------ | ------ |
| **Manifest bulunamadı** | Grafik indekslenmedi | Önce `knowgraph_index` çalıştırın |
| **Boş sonuçlar []** | Sorgu grafikte bulunamadı | `top_k` değerini artırın, `expand_query=True` deneyin |
| **Halüsinasyon** | LLM desteklenmeyen bilgi üretiyor | `with_explanation=True` ve `enable_grounding=True` kullanın |
| **Hız sınırı hatası (429)** | Çok fazla API isteği | RateLimiter bunu önlemelidir; API anahtarı katmanını kontrol edin |
| **Zaman aşımı** | Sorgu çok karmaşık | `max_hops` veya `top_k` değerini azaltın |
| **Joern yavaş** | JoernDaemon ilk sorguda ısınıyor | İlk sorgu genellikle daha uzun sürer; tekrar deneyin |

##### 5.2 Sağlık ve Onarım İş Akışı
1. `knowgraph_diagnostic()` - sistem tanısı
2. `knowgraph_validate()` - grafik bütünlüğü
3. `knowgraph_index(input_path=..., gc=True)` - temizlik gerekirse
4. `knowgraph_rollback(version_id=...)` - bozuk indeksleme geri alınacaksa (öncesinde `knowgraph_list_versions`)

--------------------------------------------------------------------------------

#### ⚡ 6. Gelişmiş İş Akışları (Örnek)

**Hata Ayıklama**:
```python
knowgraph_query(query="Hata AuthService'te neden oluşuyor?", top_k=20, max_hops=3, enable_grounding=True, with_explanation=True)
knowgraph_analyze_impact(element="src/auth/service.py", mode="path", max_hops=4)
knowgraph_search_bookmarks(query="session timeout bug")
```

**Yeniden Düzenleme**:
```python
knowgraph_analyze_impact(element="RateLimiter", mode="semantic", max_hops=6)
knowgraph_analyze_call_graph(method_name="rate_limit", analysis_type="validate")
```

**Güvenlik Denetimi**:
```python
knowgraph_security_scan(severity_filter="MEDIUM")
knowgraph_analyze_call_graph(method_name="unsafe_input", target_method="db.execute", analysis_type="call_chain")
knowgraph_find_dead_code()
```

**Oturum Başlangıcı (Context Loading)**:
```python
knowgraph_discover_conversations(editor="all")
knowgraph_analyze_conversations(time_window_days=7)
knowgraph_search_bookmarks(query="recent architectural decisions", top_k=5)
```
