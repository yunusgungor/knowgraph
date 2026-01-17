# KnowGraph Örnek Kullanım Kılavuzu 📘

Bu kılavuz, KnowGraph'ın kod analizi yeteneklerini (Joern entegrasyonu dahil) tüm yönleriyle ve kombinasyonlarıyla kullanmanız için hazırlanmıştır. Aşağıdaki sorguları doğal dilde (Türkçe veya İngilizce) sisteminize sorabilirsiniz.

---

## 📑 İçindekiler
1. [Güvenlik ve Zafiyet Analizi](#1-güvenlik-ve-zafiyet-analizi)
2. [Veri Akışı ve Taint Analizi (Data Flow)](#2-veri-akışı-ve-taint-analizi-data-flow)
3. [Kod Yapısı ve Kalite](#3-kod-yapısı-ve-kalite)
4. [Görsel Grafikler (Graph Visualization)](#4-görsel-grafikler-graph-visualization)
5. [Derinlemesine Kod İçgörüsü (Deep Insight)](#5-derinlemesine-kod-içgörüsü-deep-insight)
6. [Genel Arama ve Keşif](#6-genel-arama-ve-keşif)
7. [Power User: Ham Sorgular (Raw Query)](#7-power-user-ham-sorgular-raw-query)
8. [Örnek İş Akışları (Kombinasyonlar)](#8-örnek-iş-akışları-kombinasyonlar)

---

## 1. Güvenlik ve Zafiyet Analizi
Güvenlik açıklarını taramak için genel veya spesifik sorgular kullanın.

*   **Genel Tarama:**
    *   `Check for vulnerabilities` (Zafiyetleri kontrol et)
    *   `Security scan` (Güvenlik taraması)
    *   `Scan code for issues`
*   **Spesifik Açıklar:**
    *   `Find SQL injection vulnerabilities` (SQL enjeksiyonlarını bul)
    *   `Check for XSS` (XSS açıklarını kontrol et)
    *   `Detect buffer overflows` (Buffer overflow tespiti yap)

## 2. Veri Akışı ve Taint Analizi (Data Flow)
Verinin kod içindeki yolculuğunu takip edin. Özellikle kullanıcı girdisinin veritabanına veya hassas noktalara ulaşıp ulaşmadığını görün.

*   **Taint Tracking (Kirli Veri Takibi):**
    *   `Flow from request to database` (İstekten veritabanına akış var mı?)
    *   `Trace data flow from input to sink` (`input`'tan `sink`'e veri akışını izle)
    *   `Show taint flow from "userInput" to "exec"` ("userInput"tan "exec" komutuna giden yolu göster)
    *   **Not:** Bu sorgular, fonksiyonun dönüş değerlerini (`return`) de dikkate alır.
*   **Genel Veri Akışı:**
    *   `Trace data from validateUser` (`validateUser` fonksiyonundan çıkan veriyi izle)

## 3. Kod Yapısı ve Kalite
Kodun mimarisini ve karmaşıklığını analiz edin.

*   **Karmaşıklık Analizi:**
    *   `Show complexity of methods` (Metodların karmaşıklığını göster - Cyclomatic Complexity)
    *   `Calculate complexity for AuthenticationHandler`
*   **Kontrol Yapıları:**
    *   `Show loops in processData` (`processData` içindeki döngüleri göster)
    *   `Find nested ifs` (İç içe `if` bloklarını bul)
    *   `Analyze control structures in main`
*   **Bağımlılıklar ve Importlar (Dependencies):**
    *   `Which files import requests?` (Hangi dosyalar `requests` kütüphanesini import ediyor?)
    *   `Show dependencies of main.py`
    *   `Find usages of library "numpy"`
*   **AST (Soyut Sözdizimi Ağacı):**
    *   `Show AST for function login` (`login` fonksiyonunun AST yapısını dök)
*   **Rekürsiyon (Özyineleme):**
    *   `Find recursive methods` (Recursive fonksiyonları bul)

## 4. Görsel Grafikler (Graph Visualization)
Kodun mantığını grafiksel (DOT formatında) olarak dökün.

*   **CFG (Control Flow Graph - Kontrol Akışı):**
    *   `Get CFG for method login` (`login` metodu için kontrol akış grafiği ver)
*   **PDG (Program Dependence Graph - Program Bağımlılığı):**
    *   `Show PDG for calculateTax`
*   **DDG (Data Dependence Graph - Veri Bağımlılığı):**
    *   `Get DDG for processOrder` (Sadece veri bağımlılıklarını göster)
*   **CDG (Control Dependence Graph - Kontrol Bağımlılığı):**
    *   `Get CDG for validateInput`

## 5. Derinlemesine Kod İçgörüsü (Deep Insight)
Metodların içine ve ilişkilerine mercek tutun.

*   **Metod İç Yapısı:**
    *   `Parameters of login` (`login` fonksiyonunun parametreleri neler?)
    *   `Locals of processData` (`processData` içindeki yerel değişkenleri listele)
*   **Etki Analizi (Impact Analysis):**
    *   `Who calls validateUser?` (`validateUser`'ı kimler çağırıyor?)
    *   `What uses User class?` (`User` sınıfını kimler kullanıyor?)
    *   `Where is userId used?` (`userId` değişkeni nerede kullanılıyor?)
*   **Program Slicing (Kod Dilimleme):**
    *   `Slice code affecting outputResult` (`outputResult` değişkenini etkileyen kodları dilimle/çıkar)
*   **Çağrı Zinciri (Call Chain):**
    *   `Show call path from main to database_connect` (`main`den db bağlantısına giden çağrı zincirini göster)
*   **Tip Hiyerarşisi:**
    *   `Show subclasses of BaseController` (`BaseController`'ın alt sınıflarını göster)
*   **Annotation/Decorator:**
    *   `Find methods annotated with @Transaction`

## 6. Genel Arama ve Keşif
Proje hakkında genel bilgi edinin.

*   **Metadata:**
    *   `List all files` (Tüm dosyaları listele)
    *   `Show packages` (Paketleri/Namespace'leri göster)
    *   `List defined types` (Tanımlı tipleri/sınıfları listele)
*   **Yorumlar ve Etiketler:**
    *   `List current tags` (Mevcut etiketleri listele)
    *   `Find comments about "TODO"` ("TODO" içeren yorumları bul)
    *   `List FIXMEs`
*   **Literal Arama:**
    *   `Find hardcoded string "admin"` ("admin" stringini kod içinde bul)

## 7. Power User: Ham Sorgular (Raw Query)
KnowGraph'ın standart komutlarının ötesine geçip, doğrudan Joern'in Scala tabanlı sorgu dilini kullanın. **Her şey mümkündür.**

*   `Run query cpg.method.count` (Toplam metod sayısını ver)
*   `Run query cpg.method.name(".*login.*").caller.name.l` (İsminde "login" geçen metodları çağıranların ismini listele)
*   `Execute query cpg.call.name("exec").argument.code.l` ("exec" çağıran argümanların kodunu dök)
*   `Joern script cpg.file.name.l`

## 8. Örnek İş Akışları (Kombinasyonlar)
Bu özellikleri birleştirerek karmaşık senaryoları çözebilirsiniz.

**Senaryo 1: Güvenlik Açığı Doğrulama**
1.  `Find SQL injection vulnerabilities` (Potansiyel açıkları bul)
2.  `Flow from userInput to executeQuery` (Bulduğun açığın veri akışını doğrula)
3.  `Get PDG for unsafeMethod` (İlgili metodun bağımlılık grafiğine bakarak mantığı anla)

**Senaryo 2: Refactoring Hazırlığı**
1.  `Show complexity of methods` (En karmaşık metodları bul)
2.  `Who calls complexMethod?` (Bu metodu kimlerin çağırdığını gör - etki analizi)
3.  `Locals of complexMethod` (İçindeki değişkenleri incele)
4.  `Get CFG for complexMethod` (Akış diyagramını çıkar)

**Senaryo 3: Bağımlılık Temizliği**
1.  `List packages` (Paket yapısını gör)
2.  `Which files import outdated_lib?` (Eski kütüphaneyi kullananları bul)
3.  `Where is LegacyClass used?` (Eski sınıfın kullanım yerlerini tespit et)
4.  `Find comments about "remove"` (Silinmesi gereken notları bul)

## 9. İpuçları ve Püf Noktaları 💡

### Regex ve Desen Eşleştirme
KnowGraph sorgularında genellikle **Wildcard (.*)** ve **Case-Insensitive (Büyük/Küçük harf duyarsız)** arama varsayılan olarak desteklenir. Ancak daha spesifik aramalar için şunları bilmek faydalıdır:
*   **Tam Eşleşme:** Genellikle gerekmez, sistem `contains` mantığıyla çalışır.
*   **Zıt Arama:** Şu an için doğal dilde "X olmayanları bul" desteği sınırlıdır, ancak Raw Query ile yapılabilir.

### Grafik Türleri (Hangisini Kullanmalıyım?)
*   **CFG (Control Flow):** Kodun satır satır çalışma sırasını gösterir. Mantıksal akışı (`if`, `loop`) anlamak için idealdir.
*   **PDG (Program Dependence):** Hem veri hem kontrol bağımlılıklarını gösterir. Bir değişkenin değerinin nereden geldiğini ve hangi şartlara bağlı olduğunu anlamak için en güçlü grafiktir.
*   **DDG (Data Dependence):** Sadece verinin akışına odaklanır. "Bu değişkeni kim değiştirdi?" sorusunun cevabıdır.
*   **CDG (Control Dependence):** "Bu satırın çalışması hangi şarta (`if`) bağlı?" sorusunun cevabıdır.

### Re-Indexing (Güncelleme)
Kodunuzda değişiklik yaptığınızda, analizlerin güncel olması için ara sıra **Codebase Indexing** (Yeniden İndeksleme) işlemini çalıştırmanız önerilir. KnowGraph çoğu değişikliği algılar ancak derin analizler (CPG) manuel tetikleme ile daha sağlıklı olur.

## 10. Sorun Giderme (Troubleshooting) 🔧

*   **"Sonuç Bulunamadı" (No results found):**
    *   Metod isminin doğru olduğundan emin olun (yazım hatası).
    *   Dosyanın indekslendiğinden emin olun (`list all files` ile kontrol edin).
    *   Sorguyu basitleştirin (Örn: "trace data flow from validateUserinput to exec" yerine "trace data from validate" deneyin).
*   **"Query Failed" veya "Error":**
    *   Raw Query kullanıyorsanız Scala sözdizimini kontrol edin.
    *   KnowGraph sunucusunun çalıştığından emin olun.
*   **Grafikler Çok Büyük/Karmaşık:**
    *   Çok büyük metodlar için grafikler okunaksız olabilir. Metodu parçalara bölmeyi (refactoring) düşünün veya sadece `slice` (dilimleme) özelliğini kullanın.

---
*KnowGraph ile kodunuzun efendisi olun.*
