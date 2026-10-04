# Provider terminology

PROJECT_DATA translates frozen V1 parcel presentation labels at runtime. Required visible labels include `Analiz birimi seç`, `Analiz Birimleri Haritası`, `Seçili analiz birimi`, `Analiz Birimi Özeti`, and `Analiz birimi geometrisi`. Inflected parcel terms in the project surface are translated consistently.

Original text nodes are retained in a `WeakMap`; AKKAYA_REFERENCE restores the originals and continues to use parcel terminology. Chromium verified PROJECT_DATA 24 analysis units, AKKAYA_REFERENCE 179 parcels, and PROJECT_DATA 24 analysis units after the round trip.
