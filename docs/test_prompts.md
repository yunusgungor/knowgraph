Yeni Özellikleri Test Etme Zamanı! 🚀
vidsplice.md
 dosyasını indekslemiş olmanız harika. Bu dosya bir C++ projesi içeriyor (gördüğüm kadarıyla video işleme, JWT authentication, Docker yapılandırması vs.).

İşte bu somut veriler üzerinden, yeni eklediğimiz özellikleri test edebileceğiniz örnek istemler (prompts):

1. 📊 İstatistikleri Görüntüleme (Stats)
Önce veritabanının durumuna bakalım.

Prompt: "KnowGraph veritabanımdaki istatistikleri göster. Kaç düğüm ve kenar oluştu?" (Bu, arkada knowgraph_get_stats aracını çalıştıracaktır.)

2. 🏥 Sağlık Kontrolü (Validate)
Veritabanı tutarlı mı?

Prompt: "Bilgi grafiğinin sağlığını ve tutarlılığını doğrula." (Bu, knowgraph_validate aracını çalıştırır.)

3. 🤔 Etki Analizi (Impact Analysis)
Diyelim ki bir dosyayı değiştireceksiniz, nelerin etkileneceğini soralım.

A. Dosya Yolu ile Analiz (Yeni Özellik! - Path Mode)

Prompt: "src/auth.cpp dosyasında bir değişiklik yaparsam bu durum sistemin geri kalanını nasıl etkiler? Dosya bağımlılıklarına göre analiz et." (Bu, mode="path" parametresiyle knowgraph_analyze_impact aracını tetikler. CLI ile %100 uyumlu olandır.)

B. Kavramsal Analiz (Semantic Mode)

Prompt: "JWT Authentication yapısını değiştirirsem sistemde hangi bileşenler etkilenir?" (Bu, mode="semantic" parametresini kullanır.)

4. 🧠 Akıllı Sorgu (Query Expansion & Explanation)
Yapay zeka desteğini test edelim.

Sorgu Genişletme (Query Expansion)

Prompt: "Video işleme sırasındaki bellek yönetimi (memory management) stratejileri nelerdir? Sorguyu genişleterek ara." (Burada "memory management" kelimesi geçmese bile, sistem "resource limits", "buffer", "allocation" gibi terimleri de arayacaktır.)

Açıklamalı Cevap (Explanation)

Prompt: "Docker yapılandırmasında hangi güvenlik önlemleri alınmış? Cevabınla birlikte mantıksal açıklamanı (explanation) da ver." (Bu, with_explanation=True parametresini tetikler.)

5. 🏗️ Hiyerarşik Bağlam (Hierarchical Context)
Prompt: "main.cpp dosyasının amacı nedir? Üst klasörlerdeki dökümanlardan da (README vb.) bilgi alarak cevapla." (Bu, enable_hierarchical_lifting=True parametresini test eder.)

Bu komutları sırayla deneyerek sunucunuzun yeni "süper güçlerini" görebilirsiniz! İyi eğlenceler. 🎮

----

Harika, vidsplice projesinin detaylarına inerek, sunucunuzun tüm kaslarını çalıştıracak çok çeşitli ve kombinasyonlu istemler (prompts) hazırladım.

Bu istemleri, hangi özelliği test ettiğine göre kategorize ettim. Bunları doğrudan MCP istemcisine (örneğin Claude Desktop) yapıştırabilirsiniz.

🧩 Bölüm 1: Karmaşık ve Kombinasyonlu Sorgular
Hem genişletme, hem açıklama, hem de derinlik gerektiren "Heavy" sorgular.

Genişletilmiş ve Açıklamalı Teknik Sorgu
"FFmpeg entegrasyonunda kullanılan bellek yönetimi ve tamponlama (buffering) stratejilerini anlat. Bu cevabı oluştururken arka planda hangi mantıksal adımları izlediğini de 'explanation' olarak sun ve sorgumu benzer teknik terimlerle genişlet."

Test: expand_query=True + with_explanation=True
Derinlemesine Bağlantı Analizi (Deep Hop)
"docker-compose.yml dosyasındaki 'RATE_LIMIT' değişkeni ile C++ kodundaki 'rate_limiter.cpp' arasındaki ilişkiyi, aradaki tüm katmanları (örneğin config okuma, main.cpp aktarımı) içerecek şekilde, maksimum 8 adım derinliğe inerek bul."

Test: max_hops=8 (Normalde default 4'tür, bu zorlayıcı bir testtir.)
Hiyerarşik ve Geniş Kapsamlı (High Token)
"src/api_server.cpp dosyasının, projenin genel mimarisindeki rolünü, hem kendi içeriğinden hem de proje kök dizinindeki README ve CMakeLists.txt dosyalarındaki tanımlardan yola çıkarak anlat. Cevap için 4000 tokenlık geniş bir pencere kullan."

Test: enable_hierarchical_lifting=True + max_tokens=4000 + lift_levels=3
💥 Bölüm 2: Senaryo Bazlı Etki Analizleri
Değişiklik senaryoları ile "semantic" ve "path" modlarını zorlayalım.

Dosya Silme Senaryosu (Path Mode)
"Eğer include/video_processor.hpp başlık dosyasını silersem veya ismini değiştirirsem, derleme sürecinde ve kaynak kodda (src klasörü altında) tam olarak hangi dosyalar hata verir? Dosya yollarına göre analiz et."

Test: knowgraph_analyze_impact(mode="path", element="include/video_processor.hpp")
Mimari Değişiklik (Semantic Mode)
"Projedeki 'JWT Authentication' yapısını 'OAuth2' ile değiştirmeye karar verdik. Bu kavramsal değişiklik, auth.cpp haricinde, API sunucusu veya Docker konfigürasyonu gibi hangi bileşenleri etkiler?"

Test: knowgraph_analyze_impact(mode="semantic", element="JWT Authentication")
Kütüphane Güncellemesi (Path/Dependency)
"CMakeLists.txt dosyasında Boost kütüphanesinin versiyonunu değiştirirsem, bu durum projede Boost kullanan hangi kaynak kod dosyalarını etkiler?"

Test: knowgraph_analyze_impact(mode="path", element="CMakeLists.txt")
🕵️‍♂️ Bölüm 3: Güvenlik ve Altyapı Odaklı
Genel bilgiyi değil, spesifik detayları çekme.

SSL/TLS Sertifika Zinciri
"ssl/generate_cert.sh betiği ile oluşturulan sertifikaların Docker konteynerine (docker-compose.yml) nasıl mount edildiğini ve uygulamanın bu sertifikaları nasıl okuduğunu adım adım anlat."

Test: Dosyalar arası ilişki (Edge) ve Hiyerarşik bağlam.
Hata Toleransı (Fault Tolerance)
"Sistemde bir 'video processing' işlemi başarısız olursa, uygulamanın çökmesini engelleyen mekanizmalar nelerdir? 'Try-catch' blokları veya 'restart' politikalarını araştır."

Test: expand_query=True (Siz restart dersiniz, o Docker restart policy veya C++ exception handling arar).
🛠️ Bölüm 4: Bakım ve Operasyon (Maintenance)
Validasyon ve İstatistik araçlarını birleştiren istemler.

Tam Sağlık Taraması
"Önce mevcut bilgi grafiğinin tutarlı ve hatasız olup olmadığını doğrula (validate). Eğer her şey yolundaysa, projedeki toplam anlamsal ilişki (semantic edge) sayısını raporla."

Test: Zincirleme araç kullanımı: knowgraph_validate -> Valid ise -> knowgraph_get_stats.
Kayıp Dosya Kontrolü
"İndekslenen dosyalar arasında 'LICENSE' dosyası var mı ve bu dosyanın içeriği grafikte herhangi bir düğüm (node) oluşturmuş mu?"

Test: knowgraph_query (Varlık kontrolü).
🏆 Bonus: "İmkansız" Soru (Yapay Zeka Sınırı)
Soyut Mimari Çıkarımı
"Bu kod tabanına (codebase) bakan yeni bir yazılımcı olduğumu varsay. Bana main.cpp'den başlayarak bir isteğin (request) karşılanıp video işlenene kadar geçtiği yolu bir 'Sequence Diagram' gibi metin tabanlı olarak çiz. Her adımı kanıtlarıyla (dosya referanslarıyla) destekle."

Test: Tüm motorun (Query + Retrieval + LLM Synthesis) sınırlarını zorlar.
Bu istemleri kopyalayıp doğrudan sorabilirsiniz. Hepsi çalışıyorsa sisteminiz mükemmel durumdadır!

----

