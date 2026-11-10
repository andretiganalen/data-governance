Adaptasi ke Full Bahasa Indonesia.
Setiap manual harusnya bisa dikontrol versi dari penamaan yang di auto generates, dengan ketentuan:
"YYMMDD CC [Nama Dokumen].pdf", CC sebagai iterasi nomor versi yang digenerate setiap saya beri perintah untuk upload dokumen baru, bukan replace yang lama.


Konteks Dokumentasi:

Data Governance Context:

what data exists
what it means
who owns it
how it is used
where it came from
where it flows
whether it is fresh, tested, certified, and trusted
which business concepts, classifications, glossary terms, policies, contracts, and data products apply
what downstream dashboards, pipelines, metrics, ML models, and applications depend on it
what conversations, decisions, assumptions, and memory nuggets have already been captured about it


User Login, and ask Context:

What does this metric mean and how is it calculated?
Which datasets power this dashboard?
Who owns this data product?
Which data contract applies?
Is this dataset fresh, tested, certified, and trusted?
Which downstream dashboards, pipelines, or ML models are affected by this column change?
Which columns contain sensitive customer information?
Which glossary terms, policies, standards, and business concepts apply?
What decisions, assumptions, incidents, or conversations have already been captured about this asset?




Manual for Developers:
- Update details status of development, 
- tindak lanjut untuk melengkapi kebutuhan Staff dan Kebutuhan End User.
- Arah pengembangan aplikasi agar full-power
- Data Ready to Use (Medallion versi Gold: clean, sleek, ready to use for Dashboard) hanya tinggal di Trino lakehouse `lakekeeper.medallion_repository` dan dibaca lewat menu Visualisasi (panel berkas CSV/XLSX lama sudah ditutup 2026-11-10).

Manual for Data Governance Staff & Direction
- Tidak perlu memuat status aplikasi
- Cukup menampilkan, sudah bisa, belum bisa, saja. Jangan Offiside/Berlebihan.
- Jangan tampilkan status development apps.
- Ambil sudut pandang Staff untuk end User, jangan ekspose status developer.
- Data ready to use for Dashboard (menu Visualisasi): data apa saja yang sudah ada sampai dengan dokumen ini di Release.


Manual for End User:
- Tidak perlu menampilkan status aplikasi, detail aplikasi, port developer, 
- Hanya berikan instruksi cara pemakaian 
- Sebenarnya memang harus menjawab seluruh pertanyaan yang ada
- Jika saat ini belum ada data yang diupload oleh Data Governance Staff, maka hanya berikan Info: Belum ada, Belum bisa, dan Tersedia.
- End user tidak perlu tahu mengenai proses development.
- End user bisa tahu bahwa datanya sudah ada, belum ada, dan siapa pakai. Gitu.
- 