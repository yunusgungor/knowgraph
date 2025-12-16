# Gitingest Entegrasyonu - Değişiklik Özeti

## 🎯 Yapılan Değişiklikler

KnowGraph MCP Server artık sadece markdown dosyalarını değil, Git repositorylerini ve kod dizinlerini de doğrudan indeksleyebiliyor!

### 1. Yeni Bağımlılık
- **pyproject.toml**: `gitingest>=0.3.1` eklendi

### 2. Yeni Modül: `repo_ingestor.py`
**Konum**: `knowgraph/infrastructure/parsing/repo_ingestor.py`

**Özellikler**:
- Git repository URL'lerinden (GitHub, GitLab, Bitbucket) kod tabanı çıkarma
- Yerel kod dizinlerini markdown formatına çevirme
- Otomatik kaynak tipi algılama (repository, directory, markdown)
- Include/exclude pattern desteği
- Özel repository'ler için GitHub PAT desteği

**Ana Fonksiyonlar**:
- `detect_source_type(input_path)`: Kaynak tipini otomatik algılar
- `ingest_repository(...)`: Repository'yi markdown'a çevirir
- `ingest_source(...)`: Akıllı kaynak işleme (tüm tipleri destekler)

### 3. Güncellenmiş Modüller

#### `index_command.py`
- Repository ve kod dizini desteği eklendi
- `run_index()` fonksiyonuna yeni parametreler:
  - `include_patterns`: Dahil edilecek dosya desenleri
  - `exclude_patterns`: Hariç tutulacak dosya desenleri
  - `access_token`: GitHub PAT
- Otomatik kaynak tipi algılama ile akıllı işleme

#### `methods.py` (MCP Server)
- `index_graph()` fonksiyonu güncellendi
- Repository URL'leri için özel işleme mantığı
- Yeni parametreler entegre edildi
- Hata ayıklama için geliştirilmiş traceback

#### `server.py` (MCP Server)
- `knowgraph_index` tool tanımı genişletildi
- Yeni parametreler için schema güncellendi
- Tool handler'da yeni parametreler kullanılıyor

### 4. Test Coverage
**Konum**: `tests/test_repo_ingestor.py`

**Test Sınıfları**:
- `TestDetectSourceType`: Kaynak tipi algılama testleri (7 test)
- `TestIngestRepository`: Repository işleme testleri (6 test)
- `TestIngestSource`: Akıllı kaynak işleme testleri (5 test)

**Toplam**: 18 test, %100 başarı oranı

### 5. Dokümantasyon
- **REPOSITORY_INDEXING.md**: Kapsamlı kullanım kılavuzu
- **README.md**: Güncellenmiş quick start bölümü

## 🚀 Kullanım Örnekleri

### CLI Kullanımı

```bash
# GitHub repository indeksle
knowgraph index https://github.com/microsoft/TypeScript

# Filtreleme ile
knowgraph index https://github.com/user/repo \
  --include "*.py" --include "*.md" \
  --exclude "tests/*"

# Özel repository
export GITHUB_TOKEN="github_pat_xxx"
knowgraph index https://github.com/company/private-repo
```

### MCP Server Kullanımı

```json
{
  "name": "knowgraph_index",
  "arguments": {
    "input_path": "https://github.com/user/repo",
    "include_patterns": ["*.py", "*.md"],
    "exclude_patterns": ["node_modules/*", "*.lock"],
    "access_token": "github_pat_xxx"
  }
}
```

### Python API Kullanımı

```python
from knowgraph.infrastructure.parsing.repo_ingestor import ingest_source

content, output_path, source_type = ingest_source(
    input_path="https://github.com/user/repo",
    include_patterns=["*.py", "*.md"],
    exclude_patterns=["node_modules/*"],
    access_token="token"
)

print(f"Source type: {source_type}")
print(f"Output saved to: {output_path}")
```

## 🔍 Teknik Detaylar

### Kaynak Tipi Algılama

1. **Repository**: URL'de `github.com`, `gitlab.com`, `bitbucket.org` varsa
2. **Directory**: Kod dosyaları içeren dizinler (`.py`, `.js`, `.ts`, vb.)
3. **Markdown**: `.md` uzantılı dosyalar veya sadece markdown içeren dizinler

### İşleme Akışı

```
Input Path
    ↓
Source Type Detection
    ↓
┌─────────────┬──────────────┬──────────────┐
│ Repository  │  Directory   │   Markdown   │
│    (URL)    │   (Code)     │   (Existing) │
└──────┬──────┴──────┬───────┴──────┬───────┘
       │             │              │
   Gitingest     Gitinest      Read File
       │             │              │
       └──────┬──────┴──────────────┘
              │
       Markdown Content
              │
         Parse & Chunk
              │
        AI Enrichment
              │
       Graph Building
              │
          Indexing
```

## 📊 Test Sonuçları

```
================================= test session starts ==================================
collected 18 items

tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_github_url PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_gitlab_url PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_bitbucket_url PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_markdown_file PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_code_directory PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_markdown_directory PASSED
tests/test_repo_ingestor.py::TestDetectSourceType::test_detect_nonexistent_local_path PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_success PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_with_patterns PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_with_access_token PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_to_specific_path PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_gitingest_not_installed PASSED
tests/test_repo_ingestor.py::TestIngestRepository::test_ingest_repository_error PASSED
tests/test_repo_ingestor.py::TestIngestSource::test_ingest_source_repository PASSED
tests/test_repo_ingestor.py::TestIngestSource::test_ingest_source_markdown_file PASSED
tests/test_repo_ingestor.py::TestIngestSource::test_ingest_source_code_directory PASSED
tests/test_repo_ingestor.py::TestIngestSource::test_ingest_source_force_type PASSED
tests/test_repo_ingestor.py::TestIngestSource::test_ingest_source_with_all_options PASSED

================================== 18 passed in 2.06s ==================================
```

## ✅ Tamamlanan Görevler

1. ✅ `pyproject.toml`'a gitingest bağımlılığı eklendi
2. ✅ Repository ingestor modülü oluşturuldu
3. ✅ Index command güncellendi (repo desteği eklendi)
4. ✅ MCP methods güncellendi (gitingest entegrasyonu)
5. ✅ Testler oluşturuldu ve başarıyla geçti
6. ✅ Dokümantasyon hazırlandı

## 🎉 Sonuç

KnowGraph artık üç farklı kaynak tipini destekliyor:
1. 📝 Markdown dosyaları (orijinal özellik)
2. 🔗 Git repositories (GitHub, GitLab, Bitbucket) - YENİ!
3. 📁 Kod dizinleri (otomatik markdown dönüşümü) - YENİ!

Bu sayede kullanıcılar kod tabanlarını doğrudan KnowGraph'e indeksleyebilir ve AI asistanlarından daha iyi yanıtlar alabilir.
