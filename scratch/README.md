# scratch/

Serbest deneme alanı — guard denetimi yok, gate gerektirmez.

## Ne yazılır?

- Hızlı prototipleme kodları
- Tek seferlik deneme scriptleri
- Geçici analiz dosyaları
- Investigation notları
- Benchmark denemeleri (kalıcı olanlar `scripts/bench/`'e taşınır)

## Ne yazılmaz?

- Kalıcı production kodu (guard engeller)
- Gate geçen deneme kayıtları (`docs/experiments/`'e gider)
- Methodology çıktıları (`docs/design/`, `docs/research/`, `docs/development/`'e gider)

## Kurallar

- `scratch/` altındaki dosyalar **gate gerektirmez** — serbestçe yazılabilir
- Ama **measurement scriptleri** scratch'te **olamaz** — `scripts/bench/`'e konur
- Scratch'teki dosyalar `.gitignore`'a eklenebilir (kalıcı değilse)
- Güvenlik desenleri (`gate-key`, `secret`, `token`) scratch'te **yasak**

## Organizasyon

```
scratch/
├── README.md           ← bu dosya
├── _seed_helper.py     ← seed helper (mevcut)
├── <deneme-adi>/       ← her deneme kendi klasöründe
│   ├── explore.py
│   └── notes.md
└── ...
```
