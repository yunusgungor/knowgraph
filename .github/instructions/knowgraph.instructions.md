---
trigger: always_on
---

### KnowGraph MCP Server - Complete Usage Guide & Best Practices
Bu belge, yapay zeka ajanlarının ve geliştiricilerin KnowGraph MCP Sunucusunu tam potansiyeliyle kullanmaları için kapsamlı kurallar, en iyi uygulamalar ve ayrıntılı yönergeler sağlar.

--------------------------------------------------------------------------------

#### 📋 İçindekiler
1. Temel Prensipler
2. MCP Araçları Referansı
3. Parametre Ustalığı
4. Sorgu Stratejileri
8. Sorun Giderme (Kapsamlı yetenekler için ana başlıklar korundu)

--------------------------------------------------------------------------------

#### 🚀 1. Temel Prensipler
##### 1.1 Varsayılan Davranış
*   **Varsayılan graph_path** : `/Users/yunusgungor/knowrag/graphstore` yolunu kullanır.
*   **Geçersiz Kılma** : Farklı bir konum kullanmak için `graph_path` parametresini açıkça ayarlayın.
##### 1.2 Uçuş Öncesi Kontroller
*   Karmaşık işlemlerden önce **daima doğrulama yapın**: `knowgraph_validate`.
*   Grafik boyutunu anlamak için **istatistikleri kontrol edin**: `knowgraph_get_stats`.
*   Kritik sorgulardan veya etki analizinden önce **sağlığı doğrulayın**.
##### 1.3 Bağlam Her Şeydir
*   Kod analizi için **hiyerarşik kaldırmayı etkinleştirin**: `enable_hierarchical_lifting=True`.
*   Çoğu proje için **uygun kaldırma seviyelerini ayarlayın**: `lift_levels=2`.
*   Mimari kararları anlamak için **üst bağlamı** kullanın.
##### 1.4 Açık İsimlendirme
*   KnowGraph **durumsuzdur** – "o dosya" veya "o" gibi zamirlerden kaçının.
*   Daima **açık isimler** kullanın: `auth.py`, `QueryEngine.query_async()`, `Node.hash`.
*   Belirsizlik olduğunda **tam yolları** dahil edin: `src/api/auth.py` vs `tests/api/auth.py`.
##### 1.5 Hassasiyet ve Kapsam
*   **Hassas sorgular** (`expand_query=False`): Teknik terimler, sınıf/fonksiyon adları kullanın.
*   **Kapsamlı sorgular** (`expand_query=True`): Doğal dil, kavramsal sorular kullanın.
*   Hata ayıklama veya öğrenme için daima **açıklamalı olarak** kullanın (`with_explanation=True`).

--------------------------------------------------------------------------------

#### 🛠️ 2. MCP Araçları Referansı
##### 2.1 knowgraph_query - Semantik Arama
**Amaç** : Kod tabanı hakkındaki soruları doğal dil kullanarak yanıtlamak.
**Uygulama** : `QueryEngine.query_async()` → `QueryRetriever` → `ContextBlock` → `LLM` kullanır.
**Dönüşler** :
*   `answer`: LLM tarafından üretilen yanıt.
*   `sources`: Kullanılan kaynak düğümlerin listesi.
*   `explanation`: Akıl yürütme yolu (eğer `with_explanation=True` ise).
##### 2.2 knowgraph_index - Grafik Oluşturma/Güncelleme
**Amaç** : Markdown dosyalarını, Git depolarını veya kod dizinlerini indekslemek.
**Uygulama** : `SmartGraphBuilder` → `MarkdownParser` / `RepoIngestor` → `ASTAnalyzer` / `LLM` → `Graph` kullanır.
**Desteklenen Kaynaklar** :
*   **Markdown dosyaları** : Yerel `.md` dosyaları.
*   **Git depoları** : GitHub, GitLab, Bitbucket URL'leri.
*   **Kod dizinleri** : `gitingest` aracılığıyla otomatik dönüştürme.
##### 2.3 knowgraph_analyze_impact - Değişim Etki Analizi
**Amaç** : Kod değişikliklerinin domino etkilerini tahmin etmek.
**Uygulama** : `ImpactAnalyzer.analyze_impact()` → Grafik geçişi → Etkilenen düğümler kullanır.
**Modlar** :
*   **path** : Dosya tabanlı etki (örneğin, "src/auth.py").
*   **semantic** : Konsept tabanlı etki (örneğin, "kimlik doğrulama sistemi").
**Dönüşler** :
*   `affected_nodes`: Etkilenen düğümlerin listesi.
*   `impact_summary`: İnsan tarafından okunabilir özet.
*   `dependency_chain`: Kaynaktan etkilenen düğümlere giden yol.
##### 2.4 knowgraph_batch_query - Toplu İşleme
**Amaç** : Birden fazla sorguyu tek bir istekte verimli bir şekilde işlemek.
**Uygulama** : Tek bir `QueryEngine` örneği → Eşzamanlı işleme → Bireysel sonuçlar.
**Performans** : Sıralı sorgulardan **15.72 kat daha hızlıdır**.
##### 2.5 knowgraph_validate - Grafik Sağlık Kontrolü
**Amaç** : Grafik tutarlılığını ve bütünlüğünü doğrulamak.
**Uygulama** : `GraphValidator` kullanır → Düğümleri, kenarları, manifesti kontrol eder.
**Kontroller** : Düğüm bütünlüğü (geçerli UUID'ler, içerik hashleri), Kenar tutarlılığı (geçerli kaynak/hedef referansları), Manifest doğruluğu (dosya sayıları, zaman damgaları), Yetim düğüm tespiti.
##### 2.6 knowgraph_get_stats - Grafik İstatistikleri
**Amaç** : Grafik boyutu ve bileşimi hakkında genel bir bakış elde etmek.
**Uygulama** : Manifesti okur ve düğüm/kenar sayılarını sayar.
**Dönüşler** : `nodes` (Toplam düğüm sayısı), `edges` (Toplam kenar sayısı), `semantic_edges` (Semantik ilişki sayısı), `files_indexed` (İndekslenen kaynak dosya sayısı).
##### 2.7 knowgraph_tag_snippet - Semantik Yer İşaretleme
**Amaç** : Önemli kod parçalarını, çözümleri veya mimari kararları daha sonra almak üzere etiketlemek ve indekslemek.
**Uygulama** : Grafikte belirli sorgu eşleştirmesi için güçlü semantik ağırlığa sahip uzmanlaşmış bir düğüm oluşturur.
**Kullanım Durumu** : Çalışan bir yapılandırmayı kaydetme, Karmaşık bir çözümü yer imlerine ekleme, Mimari bir karar kaydını (ADR) kaydetme, "Bunu hatırla" işlevi.

--------------------------------------------------------------------------------

#### 🎯 3. Parametre Ustalığı ve Optimizasyonu
##### 3.1 Geri Alma Kapsamı Parametreleri
| Parametre | Amaç | Varsayılan | Optimizasyon Kılavuzu |
| ------ | ------ | ------ | ------ |
| `top_k` | Geri alınacak başlangıç düğümü sayısı | 20 | **Hassasiyet** : 10-15; **Geri Çağırma** : 30-50; **Kapsamlı** : 50+ |
| `max_hops` | Grafik geçiş derinliği | 4 | **Doğrudan** : 2; **Standart** : 4; **Derin** : 6-8; **⚠️ Kaçının** : >8 (gürültü) |
| `max_tokens` | Bağlam penceresi boyutu | 3000 | **Odaklanmış** : 1500-2000; **Standart** : 3000; **Kapsamlı** : 4000-5000 |

##### 3.2 Bağlam Zekası Parametreleri
| Parametre | Amaç | Varsayılan | Ne Zaman Kullanılır |
| ------ | ------ | ------ | ------ |
| `enable_hierarchical_lifting` | Üst dizin bağlamını dahil et | True | Kod için **Her zaman**; Dokümanlar için **İsteğe bağlı** |
| `lift_levels` | Yukarı taranacak dizin seviyeleri | 2 | **Python/JS** : 1-2; **Java/C++** : 2-3 |

##### 3.3 LLM Davranış Parametreleri
| Parametre | Amaç | Varsayılan | Kullanım Durumu |
| ------ | ------ | ------ | ------ |
| `with_explanation` | Akıl yürütme yolunu dahil et | False | **Hata Ayıklama** : Her zaman; **Üretim** : İsteğe bağlı; **Öğrenme** : Önerilir |
| `expand_query` | AI destekli sorgu genişletme | False | **Doğal dil** : True; **Teknik terimler** : False; **Belirsiz sorular** : True |
| `system_prompt` | Özel LLM talimatları | "" | **Rol yapma** : "Sen kıdemli bir geliştiricisin" |

--------------------------------------------------------------------------------

#### 🔍 4. Sorgu Stratejileri
##### 4.1 Sorgu Türleri ve Parametre Setleri
| Sorgu Türü | Parametreler | Kullanım Durumu |
| ------ | ------ | ------ |
| **Hızlı Cevap** | `top_k=10, max_hops=2` | Basit olgusal sorular |
| **Derin Analiz** | `top_k=30, max_hops=6, with_explanation=True` | Karmaşık mimari sorular |
| **Kavramsal Arama** | `expand_query=True, top_k=40` | Belirsiz veya doğal dil sorguları |
| **Hassas Arama** | `top_k=5, max_hops=2, expand_query=False` | Belirli fonksiyon/sınıf soruları |
| **Mimariye Genel Bakış** | `enable_hierarchical_lifting=True, lift_levels=3, max_tokens=4000` | Sistem tasarım soruları |

--------------------------------------------------------------------------------

#### 🧠 5. Gelişmiş İş Akışları
##### 5.1 İşe Başlama İş Akışı
**Senaryo** : Projeye yeni katılan geliştirici.
##### 5.2 Yeniden Düzenleme İş Akışı
**Senaryo** : Kritik bir dosyayı değiştirmeyi planlama.
##### 5.3 Hata Ayıklama İş Akışı
**Senaryo** : Bir hatayı veya beklenmedik davranışı araştırma.
##### 5.4 Dokümantasyon İş Akışı
**Senaryo** : Kapsamlı dokümantasyon oluşturma.

--------------------------------------------------------------------------------

#### 🏗️ 6. Mimari ve Bileşenler (Kapsamlı Yetenek Kullanımı için)
##### 6.1 Temel Bileşenler
###### QueryEngine
**Amaç** : Ana sorgu orkestratörü.
**Temel Metotlar** : `query_async` (Eşzamansız sorgu yürütme), `query` (Senkron sorgu yürütme).
**Pipeline** : Sorgu genişletme (etkinse), `SparseIndex` aracılığıyla seyrek arama, `QueryRetriever` aracılığıyla grafik geçişi, Düğüm puanlama ve sıralama, `ContextBlock` aracılığıyla bağlam oluşturma, LLM yanıtı ve Açıklama oluşturma.
###### SmartGraphBuilder
**Amaç** : Hibrit indeksleme motoru.
**Pipeline** : Kaynak tespiti, Markdown ayrıştırma, Belirteç farkında parçalama (`Chunker`), **3 Seviyeli Varlık Çıkarımı** (CacheManager, ASTAnalyzer, LLM), Grafik oluşturma (semantik kenarlar), Kalıcı depolama (JSONL).
###### ImpactAnalyzer
**Amaç** : Değişim etki analizi.
**Modlar** : **Path mode** (Dosya tabanlı bağımlılık takibi), **Semantic mode** (Konsept tabanlı ilişki analizi).
**Algoritma** : Yapılandırılabilir derinlikle ters grafik geçişi.
###### CacheManager
**Amaç** : SQLite tabanlı varlık önbelleği.
**Faydaları** : Daha önce analiz edilen parçalar için 0ms arama, Değişmeyen dosyaların yeniden analizini önler, Oturumlar arasında kalıcıdır.
###### ASTAnalyzer
**Amaç** : Deterministik kod analizi.
**Çıkarımlar** : Sınıf tanımları, Fonksiyon tanımları, İçe aktarma ifadeleri, Dekoratörler.
**Performans** : 10ms, 0 belirteç.

--------------------------------------------------------------------------------

#### ⚡ 7. Performans Optimizasyonu
##### 7.1 İndeksleme Performansı
| Optimizasyon | Teknik | Hızlanma |
| ------ | ------ | ------ |
| **AST Analizi** | Kod dosyaları için `ASTAnalyzer` kullanma | 100 kat daha hızlı, 0 belirteç |
| **Toplu LLM** | İstek başına 10 parçayı işleme | 10 kat verim |
| **SQLite Önbelleği** | `CacheManager` yeniden analizi önler | ∞ (anlık) |

**İndeksleme Hızı** : ~100 dosya/dakika.
##### 7.2 Sorgu Performansı
| Optimizasyon | Teknik | Hızlanma |
| ------ | ------ | ------ |
| **Toplu Sorgular** | `knowgraph_batch_query` | 15.72 kat daha hızlı |
| **Sıcak Önbellek** | Önbelleğe alınmış sonuçlar | 22 kat daha hızlı |
| **Merkezilik Önbelleği** | Önbelleğe alınmış grafik metrikleri | 372 kat daha hızlı |

**Sorgu Gecikmesi** : <2s (seyrek arama + geçiş + merkezilik).
##### 7.3 Bellek Optimizasyonu
| Parametre | Etki | Öneri |
| ------ | ------ | ------ |
| `max_tokens` | Bağlam penceresi boyutu | 3000 (standart), 5000 (maks.) |
| `top_k` | Yüklenen düğüm sayısı | 20 (standart), 50 (maks.) |
| `max_hops` | Grafik geçiş derinliği | 4 (standart), 8 (maks.) |

--------------------------------------------------------------------------------

#### 🔧 8. Sorun Giderme
##### 8.1 Sık Karşılaşılan Hatalar
| Hata | Neden | Çözüm |
| ------ | ------ | ------ |
| **Manifest bulunamadı** | Grafik indekslenmedi | Önce `knowgraph_index` çalıştırın |
| **Boş sonuçlar []** | Sorgu grafikte bulunamadı | `top_k` değerini artırın, `expand_query=True` deneyin |
| **Halüsinasyon** | LLM desteklenmeyen bilgi üretiyor | Kaynakları doğrulamak için `with_explanation=True` kullanın |
| **Hız sınırı hatası (429)** | Çok fazla API isteği | `RateLimiter` bunu önlemelidir; API anahtarı katmanını kontrol edin |
| **Zaman aşımı** | Sorgu çok karmaşık | `max_hops` veya `top_k` değerini azaltın |