# KnowGraph Özerk Ajan Kuralları (Master Rules)
Bu dosya, KnowGraph MCP Sunucusunu en üst düzeyde, eksiksiz ve en verimli şekilde kullanmak için yapay zeka ajanlarına yönelik katı kuralları ve en iyi uygulama yönergelerini içerir.

---

## 🚀 1. Temel Prensipler
1.  **Önce Kontrol Et (Pre-flight Check)**: Karmaşık bir işlemden önce (örneğin büyük bir etki analizi veya sorgu), veritabanının sağlığını `knowgraph_validate` ile kontrol etmeyi alışkanlık haline getir.
2.  **Varsayılan Yol (Default Path)**: MCP sunucusu ile sorgu yaparken, varsayılan `graph_path` parametresi her zaman **kod tabanındaki `graphstore` dizinidir** (`./graphstore`). Tüm analizler ve sorgular bu dizin üzerinden gerçekleştirilir.
3.  **Bağlam Kraldır (Context is King)**: Basit sorgular yerine, `enable_hierarchical_lifting=True` kullanarak dosyanın bulunduğu klasör ve proje yapısından gelen zekayı her zaman kullan.
4.  **Kesinlik vs. Genişlik**:
    *   Nokta atışı teknik bilgi için: `expand_query=False` (Varsayılan).
    *   Kavramsal araştırma veya belirsiz sorular için: MUTLAKA `expand_query=True` kullan.
5.  **Açık İsimlendirme (Explicit Naming)**: KnowGraph "durumsuz" (stateless) bir arama motorudur. "O dosya" veya "Bunu" gibi zamirler yerine, her sorguda dosya adını (`auth.cpp`) veya fonksiyonu (`Guid.NewGuid`) açıkça belirt.

---

## 🔬 2. Parametre Uzmanlığı ve Optimizasyon Mantığı (Mastery Guide)
*En mükemmel sonucu almak için parametrelerin arka planda nasıl çalıştığını anlayın.*

### A. Erişim Kontrolü (Retrieval Scope)
| Parametre | Ne İş Yapar? | Nasıl Hesaplanmalı? | Mükemmel Sonuç İçin İpucu |
| :--- | :--- | :--- | :--- |
| **`max_hops`** | Grafikte düğümden düğüme kaç adım atlanacağını belirler. | **Standart (4)**: Çoğu dolaylı ilişki için yeterlidir. <br> **Derin (8)**: Spagetti kodlarda veya çok katmanlı mimarilerde gerekir. | `8` üzerine çıkmak gürültüyü (alakasız sonuçları) artırır. Çok karmaşık bir "Dependency Injection" zinciri çözmüyorsanız `4` idealdir. |
| **`top_k`** | Veritabanından çekilecek en alakalı parça sayısı. | **Odaklı (10-20)**: Kesin cevaplar için. <br> **Geniş (50+)**: Özetleme veya tarama için. | Eğer cevap çok genel geliyorsa, `top_k` değerini düşürün (Precision artar). Eğer cevap eksik geliyorsa, artırın (Recall artar). |

### B. Bağlam Zekası (Context Intelligence)
| Parametre | Ne İş Yapar? | Nasıl Hesaplanmalı? | Mükemmel Sonuç İçin İpucu |
| :--- | :--- | :--- | :--- |
| **`enable_hierarchical_lifting`** | Dosyanın içeriğine, bulunduğu klasörün ve üst klasörlerin özet bilgisini de ekler. | **Kod Analizi**: HER ZAMAN `True`. <br> **Düz Metin**: `False` olabilir. | Proje yapısını anlamadan kod anlaşılamaz. Bir dosyanın "neden" orada olduğunu anlamak için bu ayar şarttır. |
| **`lift_levels`** | Kaç klasör yukarı çıkılacağı. | **Formül**: `Proje Derinliği - 1`. <br> Örnek: `src/main/utils/helper.py` (4 seviye) -> `lift_levels=3` (Kök dizine ulaşmak için). | Çok yüksek tutmak (`5+`) kök dizindeki alakasız dosyaları (build scriptleri vb.) bağlama sokabilir. C++/Java için `2`, Python/JS için `1` genellikle mükemmel dengeyi sağlar. |

### C. Dil Modeli Davranışı (LLM Behavior)
| Parametre | Ne İş Yapar? | Nasıl Hesaplanmalı? | Mükemmel Sonuç İçin İpucu |
| :--- | :--- | :--- | :--- |
| **`with_explanation`** | Cevabın yanına, o cevabın hangi dosya ve satırlardan çıkarıldığını kanıtlayan bir JSON ekler. | **Debug/Öğrenme**: `True`. <br> **Hızlı Cevap**: `False`. | Ajanın halüsinasyon görmesini engellemenin en iyi yoludur. "Bunu nereden uydurdun?" dememek için açık tutun. |
| **`expand_query`** | Sorguyu eş anlamlılarla zenginleştirir (AI kullanarak). | **Belirsiz Sorgu**: `True`. (Ör: "Login çalışmıyor") <br> **Kesin Sorgu**: `False`. (Ör: "AuthService.login fonksiyonu") | Eğer kullanıcı "teknik terim" kullanıyorsa KAPATIN. Kullanıcı "doğal dil" kullanıyorsa AÇIN. Artık generic provider desteği var! |
| **`system_prompt`** | (**YENİ**) Cevap veren yapay zekanın kişiliğini ve formatını belirler. | **Kişiselleştirme**: "Sen bir kıdemli yazılımcısın" gibi özel rol tanımları için kullan. | Eğer belirli bir format (ör: Sadece JSON) veya ton (ör: Çok sert ve eleştirel) istiyorsanız bu parametreyi kullanın. Varsayılan: "Helpful Assistant". |

---

## 🛠️ 3. Araç Kullanım Stratejileri

### A. Sorgulama (`knowgraph_query`)
En güçlü araçtır. Aşağıdaki parametre kombinasyonlarını senaryoya göre seç:

| Senaryo | Parametre Seti | Neden? |
| :--- | :--- | :--- |
| **Genel Öğrenme** | `with_explanation=True`, `top_k=20` | Cevabın arkasındaki mantığı görmek ve güvenilirliği artırmak için. |
| **Derin İlişki Bulma** | `max_hops=8`, `enable_hierarchical_lifting=True` | Kodun derinliklerindeki dolaylı bağlantıları (A->B->C->D...) bulmak için. |
| **Role-Playing (Rol Yapma)** | `system_prompt="You are a strict code reviewer. Find bugs only."` | LLM'in cevabını belirli bir uzmanlık alanına veya formata zorlamak için. |
| **Kavramsal Arama** | `expand_query=True`, `top_k=30` | Belirsiz veya geniş kapsamlı sorular için AI ile sorgu genişletme. |

### B. Etki Analizi (`knowgraph_analyze_impact`)
*   Kullanıcı **belirli bir dosya** bahsediyorsa (ör: `auth.cpp`) -> `mode="path"`.
*   Kullanıcı **soyut bir kavram** bahsediyorsa (ör: "Logging system") -> `mode="semantic"`.

### C. İndeksleme ve Güncelleme (`knowgraph_index`)
*   **Resume**: `resume=True` ile kaldığı yerden devam ettir.
*   **Temizlik**: Veritabanı şişkinliğini önlemek için `gc=True` kullan.
*   **Dizin Desteği**: Artık tek dosya yerine tüm klasörü indeksleyebilirsin!

### D. Toplu Sorgulama (`knowgraph_batch_query`) **YENİ**
*   Birden fazla sorguyu tek seferde işlemek için kullan.
*   Tüm sorgular aynı parametrelerle (`top_k`, `max_hops`, vb.) çalıştırılır.
*   Her sorgu için ayrı sonuç, execution time ve node sayısı döner.
*   **Kullanım**: `knowgraph_batch_query(queries=["Soru 1", "Soru 2", "Soru 3"], top_k=20)`
*   **Avantaj**: Toplu analizlerde performans artışı sağlar.

---

## 🧠 4. Gelişmiş "Düşünce Zinciri" (Chain of Thought) Akışları

Ajan olarak, kullanıcıya tek bir cevap vermek yerine aşağıdaki **Çok Adımlı Akışları** izle:

### Senaryo 1: "Bu projeyi bana anlat" (Onboarding)
1.  **Adım 1**: `knowgraph_get_stats` -> Projenin büyüklüğünü anla.
2.  **Adım 2**: `knowgraph_query(query="Projenin temel amacı nedir?", enable_hierarchical_lifting=True)` -> Genel özeti çıkar.
3.  **Adım 3**: `knowgraph_validate` -> Grafik sağlığını kontrol et.

### Senaryo 2: "X dosyasını değiştireceğim" (Refactoring)
1.  **Adım 1**: `knowgraph_analyze_impact(mode="path", element="X")`
2.  **Adım 2**: `knowgraph_query(query="X dosyasının kritik fonksiyonları?", top_k=5)`
3.  **Adım 3**: Holistik rapor sun.

### Senaryo 3: "Birden fazla soru sormak istiyorum" (Bulk Analysis)
1.  **Adım 1**: Soruları topla
2.  **Adım 2**: `knowgraph_batch_query(queries=[...])` ile tek seferde işle
3.  **Adım 3**: Sonuçları karşılaştırmalı sun

---

## 💡 5. Örnek Senaryolar ve İstemler (Prompt Library)

### 🏁 A. Temel Başlangıç (Onboarding)
1.  **İstatistikleri Görüntüleme**: "KnowGraph veritabanımdaki istatistikleri göster." (`knowgraph_get_stats`)
2.  **Sağlık Kontrolü**: "Bilgi grafiğinin sağlığını ve tutarlılığını doğrula." (`knowgraph_validate`)

### 🧩 B. Karmaşık ve Kombinasyonlu Sorgular
1.  **Genişletilmiş ve Açıklamalı Teknik Sorgu**: `expand_query=True` + `with_explanation=True`
    *   *İstem*: "Bellek yönetimi nasıl yapılıyor? Mantıksal adımları da 'explanation' olarak sun..."
2.  **Hiyerarşik ve Geniş Kapsamlı**: `enable_hierarchical_lifting=True` + `max_tokens=4000` + `lift_levels=3`
    *   *İstem*: "`src/api_server.cpp` dosyasının, projenin genel mimarisindeki rolünü anlat..."

### 💥 C. Senaryo Bazlı Etki Analizleri
1.  **Dosya Silme Senaryosu (Path Mode)**: `mode="path"`
    *   *İstem*: "Eğer `include/video_processor.hpp` başlık dosyasını silersem hangi dosyalar hata verir?"
2.  **Mimari Değişiklik (Semantic Mode)**: `mode="semantic"`
    *   *İstem*: "Projedeki 'JWT Authentication' yapısını 'OAuth2' ile değiştirmeye karar verdik..."

### 🔄 D. Toplu İşlemler (Batch Operations) **YENİ**
1.  **Çoklu Soru Analizi**: `knowgraph_batch_query`
    *   *İstem*: "Şu 5 soruyu toplu olarak analiz et: [soru listesi]"
2.  **Karşılaştırmalı Analiz**: Batch query ile birden fazla modülü karşılaştır

---

## 🔧 6. Sorun Giderme (Troubleshooting)

| Durum / Hata | Anlamı | Ajan Aksiyonu (Çözüm) |
| :--- | :--- | :--- |
| **`No manifest found`** | Belirtilen yolda indekslenmiş bir grafik veritabanı yok. | 1. Kullanıcıdan dizini teyit et. <br> 2. `knowgraph_index` aracını çalıştırarak ilk indekslemeyi yap. |
| **`Vector store inconsistency`** | (Validate hatası) Vektör veritabanı dosyaları bozulmuş. | 1. `knowgraph_index(gc=True, resume=False)` çalıştır. `gc=True` bozuk parçaları temizler. |
| **Boş Sonuç (`[]`)** | Sorgu grafikte bulunamadı. | 1. `top_k` değerini artırıp tekrar dene. <br> 2. `expand_query=True` ile tekrar dene. |
| **Halüsinasyon** | Cevap mantıksız veya dosyalarla uyuşmuyor. | 1. **DERHAL** `with_explanation=True` ile sorguyu tekrarla ve kaynağı doğrula. |
| **`Is a directory` hatası** | Dosya yerine dizin verilmiş (artık düzeltildi). | Bu hata artık alınmamalı - dizin desteği eklendi. Eğer alınıyorsa bug rapor et. |

---

## 🚫 7. Yapılmaması Gerekenler (Anti-Patterns)
*   **❌ Kör Uçuş**: Asla `knowgraph_validate` yapmadan kritik sonuçlara güvenme.
*   **❌ Yetersiz Bağlam**: Kod ile ilgili sorularda `enable_hierarchical_lifting=False` yapma.
*   **❌ Tek Seferde Çok Soru**: Birden fazla soru varsa `knowgraph_batch_query` kullan, tek tek sorma.
*   **❌ Generic Terimler**: "Bu dosya", "o fonksiyon" yerine açık isimler kullan.

---

## 🎯 8. Yeni Özellikler ve Geliştirmeler (v2.0)

### ✅ Query Expansion - Generic Provider Desteği
- Artık sadece OpenAI değil, herhangi bir `IntelligenceProvider` ile query expansion yapılabilir
- Async `expand_query_async()` metodu eklendi
- Backward compatible: Eski `expand_query()` sync metodu hala çalışıyor

### ✅ Batch Query Tool
- Yeni `knowgraph_batch_query` aracı ile toplu sorgulama
- Her sorgu için ayrı metrikler (execution time, node count)
- Performans optimizasyonu: Tek engine instance ile çoklu sorgu

### ✅ Dizin İndeksleme
- `knowgraph_index` artık tek dosya yerine tüm klasörü indeksleyebiliyor
- Recursive markdown file discovery
- Batch processing ile hızlı indeksleme

### ✅ JSON-RPC Güvenliği
- stdout pollution giderildi
- Tüm internal log'lar stderr'e yönlendirildi
- MCP protokolü tam uyumlu

### ✅ Path Validation
- Tüm path işlemlerinde `validate_path` kullanılıyor
- Security layer eklendi
- Relative path desteği

---

## 📊 9. Performans ve Optimizasyon İpuçları

### Hız Optimizasyonu
- `top_k=10` ile başla, gerekirse artır
- `max_hops=4` çoğu durum için yeterli
- `enable_hierarchical_lifting=False` sadece düz metin için

### Kalite Optimizasyonu
- `with_explanation=True` ile kaynak doğrulama
- `expand_query=True` belirsiz sorular için
- `lift_levels=2` kod projeleri için ideal

### Toplu İşlem Optimizasyonu
- 5+ sorgu varsa `knowgraph_batch_query` kullan
- Aynı parametrelerle çoklu sorgu için ideal
- Engine initialization overhead'i azaltır

---

## 🔐 10. Güvenlik ve Best Practices

1. **Path Validation**: Her zaman `validate_path` kullan
2. **Input Sanitization**: Kullanıcı girdilerini `sanitize_query_input` ile temizle
3. **Graph Validation**: Kritik işlemlerden önce `knowgraph_validate` çalıştır
4. **Error Handling**: Tüm hataları yakala ve kullanıcıya anlamlı mesaj ver
5. **Resource Limits**: `max_tokens` ile bellek kullanımını kontrol et

---

## 📚 11. Referanslar ve Kaynaklar

- **MCP Protokolü**: Model Context Protocol standardı
- **KnowGraph Mimarisi**: Hybrid retrieval (sparse + semantic)
- **Test Coverage**: %71+ kod kapsama
- **Dokümantasyon**: `docs/` klasöründe detaylı açıklamalar

---

**Son Güncelleme**: 2025-12-16
**Versiyon**: 2.0 (Batch Query + Generic Provider Support)
**Durum**: Production Ready ✅
