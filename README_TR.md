# 🧠 KnowGraph
[![CI](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml)

<div align="center">

**AI Kod Asistanınızın Bilişsel Devrimi (MCP Server)**

> **"Kodunuz sadece metin değil, yaşayan bir sistemdir."**  
> Vektör benzerliğinin olasılıksal dünyasından, Graf Teorisinin deterministik netliğine geçin.

[![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=flat-square&logo=github)](https://github.com/yunusgungor/knowgraph)
[![Theory](https://img.shields.io/badge/Theory-Graph_Topology-purple?style=flat-square&logo=wikipedia)](https://en.wikipedia.org/wiki/Network_theory)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[⚡ Hemen Başla](#-30-saniyede-bilişsel-yükseltme-quick-start) • [🔬 Bilimsel Fark](#-neden-knowgraph-bilimsel-fark) • [🧪 Deneyler](#-laboratuvar-bilişsel-yetenek-testleri) • [📚 Dokümantasyon](#-bilgi-bankası)

</div>

---

## 🔬 Neden KnowGraph? (Bilimsel Fark)

Geleneksel AI asistanları, kodunuzu "benzer kelimeler yığını" (Vector Space) olarak görür. Ancak yazılım mühendisliği **semantiktir**; dosya benzerliğine değil, mantıksal bağlara dayanır.

KnowGraph, **Graf Teorisi** ve **Ağ Bilimi (Network Science)** prensiplerini kullanarak 4 devrimsel yetenek sunar:

| Yetenek | Geleneksel RAG | 🧠 KnowGraph |
| :--- | :--- | :--- |
| **1. Topolojik Bağlam** | Rastgele dosyaları bulur. | **Graph Traversal (BFS/DFS)** ile gerçek bağlantıları (import, call, inherit) izler. |
| **2. Merkeziyet Analizi** | En çok tekrar eden kelimeye odaklanır. | `PageRank` ile mimari açıdan **en kritik** bileşenleri (Hub Nodes) tespit eder. |
| **3. Deterministik Kanıt** | Halüsinasyon riski yüksektir. | Cevabın graf üzerindeki **izdüşümünü (path)** ve kaynak dosyaları kanıt olarak sunar. |
| **4. Bilişsel Hiyerarşi** | Dosyayı tek başına inceler. | Dosyayı, bulunduğu klasörün `README`'si ve proje amacı ile **zenginleştirilmiş bağlamda** yorumlar. |

---

## ⚡ 30 Saniyede Bilişsel Yükseltme (Quick Start)

AI editörünüzün IQ'sunu artırmak için KnowGraph'ı bir MCP sunucusu olarak bağlayın.

### 1. Kurulum

```bash
pip install knowgraph
```

### 2. Beyin Bağlantısı (Konfigürasyon)

**Claude Desktop** (`claude_desktop_config.json`) veya **Cursor** ayarlarınıza şunları ekleyin:

```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-..."
      }
    }
  }
}
```

> ⚠️ **Not:** KnowGraph, Markdown (`.md`) formatındaki yapılandırılmış bilgiyi sever. Kaynak kodunuzu optimize edilmiş bir grafa çevirmek için [Gittodoc](https://gittodoc.com/) kullanmanızı şiddetle öneririz.

### 3. Kullanım

Environment değişkenlerini ayarladıktan sonra AI asistanınızla konuşmaya başlayın.

---

## 🧪 Laboratuvar: Bilişsel Yetenek Testleri

KnowGraph'ın farkını görmek için aşağıdaki **bilimsel deneyleri** (prompts) uygulayın.

### Deney 0: Isınma ve Kalibrasyon (Warm-up & Calibration)
*Motorları çalıştırın ve temel enstrümanları test edin.*

<details open>
<summary><b>🧪 Tıkla ve Genişlet: Hazır Komutlar</b></summary>

> 🤖 **Kullanıcı (İstatistik):** "KnowGraph veritabanımdaki düğüm ve kenar sayılarını göster."
>
> 🤖 **Kullanıcı (Sağlık):** "Bilgi grafiğinin sağlığını ve tutarlılığını doğrula."
>
> 🤖 **Kullanıcı (Sadece Genişletme):** "Video işleme bellek stratejileri nelerdir? Sorguyu benzer teknik terimlerle genişleterek ara (Query Expansion)."
>
> 🤖 **Kullanıcı (Sadece Kanıt):** "Docker yapılandırmasında hangi güvenlik önlemleri alınmış? Cevabınla birlikte mantıksal açıklamanı (explanation) sun."

*   **Arka Plan:** Bu komutlar, MCP sunucusunun temel fonksiyonlarını (`get_stats`, `validate`, `expand_query`, `with_explanation`) tekil (atomik) olarak test etmenizi sağlar.
</details>

<details open>
<summary><b>🦋 Deney 1: "Kelebek Etkisi" Analizi (Impact Analysis)</b> - <i>Küçük değişikliklerin kaotik sonuçları.</i></summary>

> 🤖 **Kullanıcı:** "`include/video_processor.hpp` dosyasını silersem, sistemde oluşacak 'kelebek etkisini' analiz et. Doğrudan ve dolaylı (N-Hop) olarak kırılacak zinciri göster."

*   **Arka Plan:** `knowgraph_analyze_impact(mode="path")`. Sistem, graf üzerinde tersine gezinme (reverse traversal) yaparak bağımlılık ağacını çıkarır.
</details>

<details open>
<summary><b>🕸️ Deney 2: Semantik Ağ Keşfi (Conceptual Integration)</b> - <i>Kelimelerin ötesindeki anlam.</i></summary>

> 🤖 **Kullanıcı:** "FFmpeg'in 'bellek yönetimi' stratejilerini ve 'tamponlama' (buffering) mekanizmalarını anlat. Sorgumu teknik terminolojiyle genişlet (Query Expansion) ve cevabının mantıksal ispatını (explanation) sun."

*   **Arka Plan:** `expand_query=True` + `with_explanation=True`. LLM, "buffering" kavramını "ring buffer", "zero-copy", "allocation" gibi terimlerle anlamsal olarak genişletir.
</details>

<details open>
<summary><b>🦴 Deney 3: Mimari Röntgen (Deep Architecture)</b> - <i>Görünmeyen bağlantıları ortaya çıkarın.</i></summary>

> 🤖 **Kullanıcı:** "Config dosyasındaki (`docker-compose.yml`) `RATE_LIMIT` değeri ile C++ kodunun derinliklerindeki `rate_limiter.cpp` arasındaki bağlantıyı, aradaki tüm katmanlarla birlikte 8 adım derinliğe kadar (Deep Hop) izle."

*   **Arka Plan:** `max_hops=8`. Sistem, "Small World Network" teorisine dayanarak uzak düğümler arasındaki en kısa yolları bulur.
</details>

<details open>
<summary><b>🛡️ Deney 4: Dayanıklılık Testi (Resilience Audit)</b> - <i>Sistemin bağışıklık sistemi.</i></summary>

> 🤖 **Kullanıcı:** "Bir 'video processing' işlemi çöktüğünde (exception), sistemin hayatta kalma mekanizmalarını (Try-Catch blokları, Docker Restart Policy) analiz et."

*   **Arka Plan:** Hata toleransı analizi. Kod seviyesindeki (try-catch) ve orkestrasyon seviyesindeki (Docker) mekanizmaları bütüncül olarak sorgular.
</details>

<details open>
<summary><b>🔌 Deney 5: Görünmez Bağların Keşfi (Infrastructure Audit)</b> - <i>Altyapı ve kod arasındaki kör noktalar.</i></summary>

> 🤖 **Kullanıcı:** "`ssl/generate_cert.sh` betiği ile oluşturulan sertifikaların Docker konteynerine nasıl mount edildiğini ve uygulamanın bu sertifikaları kod içinde nasıl okuduğunu zincirleme olarak ispatla."

*   **Arka Plan:** DevOps ve Developer dünyaları arasındaki boşluğu birleştirir. Shell script -> YAML -> Source Code zincirini takip eder.
</details>

<details open>
<summary><b>⛓️ Deney 6: Bağımlılık Zincir Reaksiyonu (Dependency Graph)</b> - <i>Kütüphane güncellemelerinin riskleri.</i></summary>

> 🤖 **Kullanıcı:** "`CMakeLists.txt` dosyasında Boost kütüphanesinin versiyonunu değiştirirsem, projede bu kütüphaneyi kullanan (include eden) hangi kaynak kod dosyalarını karantinaya alıp test etmeliyim?"

*   **Arka Plan:** `knowgraph_analyze_impact`. Harici bağımlılıkların (3rd party libs) kod içerisindeki yayılımını haritalandırır.
</details>

<details open>
<summary><b>🩺 Deney 7: Sistem Check-Up (Health & Maintenance)</b> - <i>Bilişsel motorunuzun sağlığı.</i></summary>

> 🤖 **Kullanıcı:** "Önce bilgi grafiğinin topolojik tutarlılığını doğrula (validate). Eğer grafik sağlıklıysa, düğüm ve kenar istatistiklerini (stats) raporla."

*   **Arka Plan:** `knowgraph_validate` -> `knowgraph_get_stats`. MCP sunucusunun veri bütünlüğünü ve grafiğin büyüklüğünü kontrol eder.
</details>

<details open>
<summary><b>🧬 Deney 8: Kavramsal Mutasyon (Semantic Evolution)</b> - <i>Soyut mimari değişikliklerin somut etkileri.</i></summary>

> 🤖 **Kullanıcı:** "Projedeki 'JWT Authentication' yapısını 'OAuth2' ile değiştirmeye karar verdik. Bu kavramsal değişiklik, `auth.cpp` haricinde, API sunucusu veya Docker konfigürasyonu gibi hangi bileşenleri etkiler?"

*   **Arka Plan:** `mode="semantic"`. Kodda "JWT" kelimesi geçmese bile, authentication mantığına (oturum yönetimi, header ayrıştırma) semantik olarak bağlı olan modüllerin analizini yapar.
</details>

<details open>
<summary><b>🔭 Deney 9: Hiyerarşik Biliş (High-Context Lifting)</b> - <i>Büyük resmi görmek.</i></summary>

> 🤖 **Kullanıcı:** "`src/api_server.cpp` dosyasının projenin genel mimarisindeki rolünü, hem kendi içeriğinden hem de proje kök dizinindeki `README`, `CMakeLists.txt` dosyalarındaki tanımlardan yola çıkarak anlat. Cevap için 4000 tokenlık geniş bir pencere kullan."

*   **Arka Plan:** `enable_hierarchical_lifting=True` + `lift_levels=3` + `max_tokens=4000`. Dosyayı sadece kendi koduyla değil, bulunduğu ekosistemin (klasör ve proje) bağlamıyla birlikte yorumlar.
</details>

<details open>
<summary><b>🎨 Deney 10: İmkansız Sentez (The "Impossible" Diagram)</b> - <i>Yapay zekanın sentez yeteneği.</i></summary>

> 🤖 **Kullanıcı:** "Bu kod tabanına bakan yeni bir yazılımcı olduğumu varsay. Bana `main.cpp`'den başlayarak bir isteğin (request) karşılanıp video işlenene kadar geçtiği yolu bir 'Sequence Diagram' gibi metin tabanlı olarak çiz. Her adımı kanıtlarıyla (dosya referanslarıyla) destekle."

*   **Arka Plan:** Tüm motorun sınırlarını zorlar (Deep Traversal + Semantic Understanding + Synthesis). Dağınık prosedürleri tek bir akış şemasında birleştirir.
</details>

<details>
<summary><b>🌑 Deney 11: Negatif Varlık Kanıtı (Void Detection)</b> - <i>Olmayanı bulmak.</i></summary>

> 🤖 **Kullanıcı:** "İndekslenen dosyalar arasında 'LICENSE' dosyası var mı ve bu dosyanın içeriği grafikte herhangi bir düğüm (node) oluşturmuş mu?"

*   **Arka Plan:** Varlık/Yokluk kontrolü. Graf üzerindeki düğümler arasında doğrudan sorgulama yapar.
</details>

---

## 📚 Bilgi Bankası

Teknolojinin derinliklerine inmek isteyenler için:

*   **[MCP Kuralları & Detaylı Promptlar](docs/KNOWGRAPH_MCP_RULES_TR.md)**
*   **[Mimari & Algoritmalar](docs/ARCHITECTURE_TR.md)**: Graf teorisi, düğüm ağırlıklandırma algoritmaları ve sistem mimarisi.

## 🤝 Bilime Katkı

Bu proje açık kaynaktır ve kolektif zeka ile büyür. PR'larınızı bekliyoruz.

## 📄 Lisans

[MIT](LICENSE)
