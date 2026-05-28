# Broker Master Data

Edit `brokers.csv` untuk reclassify broker tanpa menyentuh kode.

## Format CSV

```
code,name,is_foreign,cluster_label,notes
RG,Mandiri Sekuritas,0,market_maker,Top market maker
```

| Kolom | Deskripsi |
|---|---|
| `code` | Kode broker 2-3 huruf (UNIQUE — tidak boleh ada duplikat) |
| `name` | Nama lengkap broker |
| `is_foreign` | `1` = foreign broker, `0` = domestik |
| `cluster_label` | Salah satu: `market_maker` / `institutional` / `retail` / `corporate` / `zombie` |
| `notes` | Catatan bebas (opsional) |

## Cluster Labels

- **`market_maker`** — Bandar utama, broker yang sering jadi market maker (RG, AG, MG, dll)
- **`institutional`** — Broker institusi besar (BNI, BCA, Sinarmas, JP Morgan, dll)
- **`retail`** — Broker retail-heavy (Mirae YP, Indo Premier PD, Stockbit SS, dll)
- **`corporate`** — Broker corporate / proprietary trading desk
- **`zombie`** — Broker yang biasanya tidur, kalau bangun = signal insider activity

## Cara Edit

1. Buka `brokers.csv` di Excel / VSCode / text editor
2. Ubah kolom `cluster_label` atau `is_foreign` sesuai keperluan
3. **JANGAN** ubah kolom `code` (akan ngerusak data historis)
4. **JANGAN** tambah kode duplikat
5. Save sebagai CSV (UTF-8)
6. Re-seed: `python -m app.seed`

## Tambah Broker Baru

Tambahkan baris baru di bawah, pastikan `code` unik:

```
NEW,Nama Broker Baru,0,institutional,Tambahan
```

## Tips Klasifikasi

- **Tidak yakin?** Pakai `corporate` sebagai default
- **Broker rajin tapi sporadik?** Pakai `zombie` (lebih cocok untuk "sleeper")
- **Broker BUMN besar?** Biasanya `market_maker` atau `institutional`
- **Online broker dengan banyak retail user?** Pakai `retail`

## Validasi

Cek apakah CSV valid:

```bash
python -c "from app.seed import load_brokers_from_csv; print(f'{len(load_brokers_from_csv())} brokers loaded')"
```

Kalau ada error duplicate code, akan langsung diberitahu kode mana.
