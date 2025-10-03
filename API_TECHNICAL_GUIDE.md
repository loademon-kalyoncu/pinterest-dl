# Pinterest API Technical Guide

> **Mala anlatır gibi**: Pinterest'ten nasıl veri çekiyoruz ve bot kontrollerinden nasıl kaçıyoruz?

## İçindekiler
- [Pinterest API'yi Nasıl Kullanıyoruz?](#pinterest-apiyi-nasıl-kullanıyoruz)
- [Bot Doğrulamasından Nasıl Kaçıyoruz?](#bot-doğrulamasından-nasıl-kaçıyoruz)
- [Teknik Detaylar](#teknik-detaylar)
- [Video İndirme Sistemi](#video-i̇ndirme-sistemi)

---

## Pinterest API'yi Nasıl Kullanıyoruz?

### Adım 1: Pinterest'in Gizli API'sini Keşfettik

Pinterest, web sitesinde kullanıcılara pin'leri göstermek için kendi **internal (dahili) API'sini** kullanıyor. Bu API resmi değil, yani Pinterest bunu dışarıya açık bir şekilde sunmuyor. Ama biz web sitesini kullanırken bu API'ye yapılan istekleri "gizlice dinleyerek" nasıl çalıştığını öğrendik.

**Nasıl keşfettik?**
1. Pinterest web sitesini Chrome/Firefox'ta açtık
2. Geliştirici Araçları (F12) → Network sekmesini açtık
3. Bir pin'e tıkladığımızda veya board'a girdiğimizde ne istekler yapılıyor diye baktık
4. Gördük ki Pinterest şu URL'lere istek yapıyor:
   - `https://www.pinterest.com/resource/RelatedModulesResource/get/` (benzer pin'ler için)
   - `https://www.pinterest.com/resource/BoardFeedResource/get/` (board içeriği için)
   - `https://www.pinterest.com/resource/UserActivityPinsResource/get/` (kullanıcı pin'leri için)

### Adım 2: API İsteklerini Taklit Ettik

Pinterest'in API'si şu şekilde çalışıyor:

```
GET https://www.pinterest.com/resource/ENDPOINT_ADI/get/?parametreler
```

**Örnek İstek:**
```
GET https://www.pinterest.com/resource/UserActivityPinsResource/get/?options={"username":"xookq","page_size":50,"bookmarks":[]}&source_url=/xookq/_created/
```

**Parametreler:**
- `options`: JSON formatında ayarlar (kullanıcı adı, kaç pin istediğimiz, vs.)
- `source_url`: Hangi sayfadan istek yaptığımız (Pinterest bunu kontrol için kullanıyor)

### Adım 3: İsteği Python ile Gönderdik

Kod şöyle çalışıyor (basitleştirilmiş hali):

```python
import requests

# 1. Cookies al (Pinterest'e giriş yapmış gibi görünmek için)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"
})

# 2. API isteği yap
url = "https://www.pinterest.com/resource/UserActivityPinsResource/get/"
params = {
    "options": '{"username":"xookq","page_size":50,"bookmarks":[]}',
    "source_url": "/xookq/_created/"
}

response = session.get(url, params=params)
data = response.json()

# 3. Response'dan pin bilgilerini çıkar
pins = data["resource_response"]["data"]
for pin in pins:
    image_url = pin["images"]["orig"]["url"]
    print(f"Pin bulundu: {image_url}")
```

### Adım 4: Pagination (Sayfalama) ile Tüm Pin'leri Aldık

Pinterest bir seferde maksimum 50 pin veriyor. Daha fazlası için "bookmark" (yer imi) sistemi kullanıyor:

```python
bookmarks = []  # İlk istekte boş

while True:
    response = api.get_user_pins(username="xookq", page_size=50, bookmarks=bookmarks)
    pins = response.get_pins()

    # Pin'leri işle
    for pin in pins:
        download(pin)

    # Bir sonraki sayfa için bookmark al
    bookmarks = response.get_bookmarks()

    # Eğer bookmark "-end-" ise, tüm pin'ler bitti demektir
    if "-end-" in bookmarks:
        break
```

---

## Bot Doğrulamasından Nasıl Kaçıyoruz?

Pinterest, botları tespit etmek için çeşitli kontroller yapıyor. Biz bunları şu yöntemlerle aşıyoruz:

### 1. **Gerçek Bir Tarayıcı Gibi Görünmek**

#### User-Agent Header
Pinterest, isteği kimin yaptığını kontrol etmek için `User-Agent` header'ına bakıyor. Eğer bu header yoksa veya "Python-requests/2.28.0" gibi bir şey yazıyorsa, seni hemen bot olarak tespit ediyor.

**Çözüm:** Gerçek bir Chrome tarayıcısının User-Agent'ini kullanıyoruz:

```python
USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36"

session.headers.update({"User-Agent": USER_AGENT})
```

#### Özel Pinterest Header'ı
Pinterest, 2025-03-07'den beri yeni bir güvenlik kontrolü ekledİ. Artık şu header'ı göndermen gerekiyor:

```python
session.headers.update({
    "x-pinterest-pws-handler": "www/pin/[id].js"
})
```

Bu header olmadan Pinterest API isteklerini reddediyor.

### 2. **Cookies Kullanmak (Giriş Yapmış Gibi Görünmek)**

Pinterest, giriş yapmış kullanıcılara daha fazla güveniyor. Private (özel) board'lar veya kullanıcı pin'leri için cookies şart.

**Cookies nasıl alınıyor?**

```python
# Selenium ile gerçek tarayıcıyı aç
browser = webdriver.Chrome()
browser.get("https://pinterest.com/login")

# Kullanıcı giriş yapsın
email_input = browser.find_element(By.ID, "email")
email_input.send_keys("user@example.com")
# ... password gir, login butonuna tıkla

# Cookies'leri al
time.sleep(7)  # Login için bekle
cookies = browser.get_cookies()

# Cookies'leri kaydet
with open("cookies.json", "w") as f:
    json.dump(cookies, f)
```

**Cookies nasıl kullanılıyor?**

```python
# Kaydedilmiş cookies'leri oku
with open("cookies.json", "r") as f:
    cookies = json.load(f)

# Session'a cookies'leri ekle
for cookie in cookies:
    session.cookies.set(cookie["name"], cookie["value"])

# Artık Pinterest seni giriş yapmış kullanıcı olarak görüyor
response = session.get("https://www.pinterest.com/resource/...")
```

### 3. **Rate Limiting (İstek Hızını Sınırlama)**

Pinterest, saniyede çok fazla istek yapan kullanıcıları bot olarak işaretliyor.

**Çözüm:** İstekler arasına gecikme ekliyoruz:

```python
import time

for pin_url in pin_urls:
    download(pin_url)
    time.sleep(0.2)  # 200ms bekle (saniyede 5 istek)
```

Kullanıcı `--delay` parametresi ile bu süreyi değiştirebiliyor:

```bash
pinterest-dl scrape URL --delay 0.5  # 500ms gecikme
```

### 4. **Source URL ve Referer Göndermek**

Pinterest, isteğin "nereden" geldiğini kontrol ediyor. Eğer sen direkt API endpoint'ine istek yaparsan, Pinterest şüpheleniyor.

**Çözüm:** Her API isteğine `source_url` parametresi ekliyoruz:

```python
# Kullanıcı profilinden pin'leri alıyorsak
source_url = f"/{username}/_created/"

# Board'dan pin'leri alıyorsak
source_url = f"/{username}/{boardname}/"

# İsteği source_url ile gönder
params = {
    "options": {...},
    "source_url": source_url
}
```

### 5. **Session Kullanmak (Aynı Bağlantıyı Korumak)**

Her istek için yeni bir bağlantı açmak yerine, aynı `Session` nesnesini kullanıyoruz. Bu, gerçek bir kullanıcı davranışını taklit ediyor.

```python
# YANLİŞ: Her istekte yeni bağlantı
for url in urls:
    response = requests.get(url)  # Her seferinde yeni TCP bağlantısı

# DOĞRU: Aynı session'ı kullan
session = requests.Session()
for url in urls:
    response = session.get(url)  # Aynı bağlantı, cookieler korunuyor
```

### 6. **Retry ve Backoff Stratejisi**

Bazen Pinterest geçici olarak "429 Too Many Requests" hatası veriyor. Bu durumda biraz bekleyip tekrar deniyoruz.

```python
from requests.adapters import HTTPAdapter, Retry

retry_strategy = Retry(
    total=3,  # Maksimum 3 deneme
    backoff_factor=0.3,  # Her denemede 0.3, 0.6, 1.2 saniye bekle
    status_forcelist=[429, 500, 502, 503, 504],  # Bu hatalarda tekrar dene
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
```

---

## Teknik Detaylar

### API Endpoint'leri

Pinterest'in kullandığımız ana endpoint'leri:

| Endpoint | Ne İşe Yarar | Örnek Kullanım |
|----------|--------------|----------------|
| `RelatedModulesResource` | Bir pin'e benzer pin'leri getirir | Pin detay sayfasında "benzer pin'ler" |
| `BoardFeedResource` | Board'daki tüm pin'leri getirir | Board içeriğini indirmek |
| `UserActivityPinsResource` | Kullanıcının oluşturduğu pin'leri getirir | Profil scraping |
| `BaseSearchResource` | Arama sonuçlarını getirir | Keyword ile pin arama |

### Request Builder

Pinterest API URL'leri çok karmaşık. Örnek:

```
https://www.pinterest.com/resource/UserActivityPinsResource/get/?options=%7B%22username%22%3A%22xookq%22%2C%22page_size%22%3A50%7D&source_url=%2Fxookq%2F_created%2F
```

Bu URL'yi manuel oluşturmak zor. Bu yüzden `RequestBuilder` class'ı kullanıyoruz:

```python
class RequestBuilder:
    @staticmethod
    def build_get(endpoint: str, options: dict, source_url: str) -> str:
        # Options'ı JSON'a çevir ve URL encode et
        options_json = json.dumps(options)
        options_encoded = urllib.parse.quote(options_json)

        # URL'yi oluştur
        return f"{endpoint}?options={options_encoded}&source_url={source_url}"
```

### Response Parsing

Pinterest'in response'u iç içe JSON:

```json
{
  "resource_response": {
    "data": [
      {
        "id": "1061090362205466345",
        "images": {
          "orig": {
            "url": "https://i.pinimg.com/originals/c9/71/db/...",
            "width": 1080,
            "height": 1920
          }
        },
        "auto_alt_text": "two cartoon characters...",
        "should_open_in_stream": true,
        "videos": {
          "video_list": {
            "V_HLSV3": {
              "url": "https://v1.pinimg.com/videos/iht/hls/..."
            }
          }
        }
      }
    ],
    "bookmark": "Y2JVSG5..."
  }
}
```

Biz bu karmaşık yapıyı `PinterestMedia` objesine çeviriyoruz:

```python
class PinterestMedia:
    @classmethod
    def from_responses(cls, response_data, min_resolution):
        medias = []
        for item in response_data:
            # Resim URL'sini al
            src = item["images"]["orig"]["url"]

            # Video varsa URL'sini al
            video_stream = None
            if item.get("should_open_in_stream"):
                video_url = item["videos"]["video_list"]["V_HLSV3"]["url"]
                video_stream = VideoStreamInfo(url=video_url, ...)

            # PinterestMedia objesi oluştur
            media = cls(
                id=item["id"],
                src=src,
                alt=item.get("auto_alt_text"),
                video_stream=video_stream
            )
            medias.append(media)

        return medias
```

---

## Video İndirme Sistemi

### HLS Stream Nedir?

Pinterest, videoları **HLS (HTTP Live Streaming)** formatında sunuyor. Bu format videoyu küçük parçalara (segment) böler:

```
video.m3u8  (playlist dosyası)
├── segment_00001.ts
├── segment_00002.ts
├── segment_00003.ts
└── ...
```

### HLS İndirme Süreci

**Adım 1: M3U8 Playlist'i İndir**

```python
import m3u8

playlist = m3u8.load("https://v1.pinimg.com/videos/iht/hls/abc.m3u8")
```

**Adım 2: Variant Playlist Çöz (Eğer Varsa)**

Bazı M3U8 dosyaları "master playlist" olur, yani içinde birden fazla kalite seçeneği vardır:

```
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1920x1080
1080p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=1280x720
720p.m3u8
```

Biz en yüksek kaliteyi seçiyoruz:

```python
if playlist.is_variant:
    best_variant = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth)
    playlist = m3u8.load(best_variant.uri)
```

**Adım 3: Segment'leri İndir**

```python
segments = []
for i, segment in enumerate(playlist.segments):
    segment_url = segment.uri
    segment_data = requests.get(segment_url).content

    # Eğer şifrelenmiş ise, decrypt et
    if segment.key:
        key = requests.get(segment.key.uri).content
        segment_data = decrypt_aes128(segment_data, key)

    # Segment'i kaydet
    with open(f"segment_{i:05d}.ts", "wb") as f:
        f.write(segment_data)

    segments.append(f"segment_{i:05d}.ts")
```

**Adım 4: Segment'leri Birleştir**

**İki yöntem var:**

**Yöntem 1: ffmpeg ile (Önerilen)**
```python
import subprocess

# Concat list oluştur
with open("concat_list.txt", "w") as f:
    for seg in segments:
        f.write(f"file '{seg}'\n")

# ffmpeg ile birleştir
subprocess.run([
    "ffmpeg", "-f", "concat", "-safe", "0",
    "-i", "concat_list.txt",
    "-c", "copy",  # Re-encode etme, direkt kopyala
    "output.mp4"
])
```

**Yöntem 2: Binary Concatenation (ffmpeg olmadan)**
```python
# Tüm segment'leri birleştir
with open("output.mp4", "wb") as outfile:
    for seg in segments:
        with open(seg, "rb") as infile:
            outfile.write(infile.read())
```

**ffmpeg vs Binary Concatenation:**

| Özellik | ffmpeg | Binary Concat |
|---------|--------|---------------|
| Kalite | ✅ Perfect | ⚠️ Çoğu cihazda çalışır |
| Metadata | ✅ Var | ❌ Yok |
| Seeking | ✅ Sorunsuz | ⚠️ Bazı oynatıcılarda sorunlu |
| Gereksinim | ffmpeg kurulu olmalı | ❌ Ekstra gereksinim yok |

**Bizim yaklaşımımız:** ffmpeg varsa kullan, yoksa binary concatenation yap.

```python
import shutil

has_ffmpeg = shutil.which("ffmpeg") is not None

if has_ffmpeg:
    concat_with_ffmpeg(segments, "output.mp4")
else:
    concat_binary(segments, "output.mp4")
```

### Şifre Çözme (AES-128 Decryption)

Bazı segment'ler AES-128 ile şifrelenmiş oluyor. M3U8 dosyasında şu şekilde belirtiliyor:

```
#EXT-X-KEY:METHOD=AES-128,URI="https://example.com/key.bin",IV=0x12345678
```

**Decrypt işlemi:**

```python
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def decrypt_aes128(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()
```

---

## Özet: Bot Olarak Tespit Edilmemek İçin Yapılması Gerekenler

1. ✅ **Gerçek User-Agent kullan** (Chrome/Firefox taklidi)
2. ✅ **Pinterest'in özel header'ını ekle** (`x-pinterest-pws-handler`)
3. ✅ **Cookies kullan** (özellikle private content için)
4. ✅ **Rate limiting yap** (istekler arası 200-500ms gecikme)
5. ✅ **Source URL belirt** (isteğin nereden geldiğini söyle)
6. ✅ **Session kullan** (aynı bağlantıyı koru)
7. ✅ **Retry stratejisi uygula** (429 hatası gelirse bekle)
8. ✅ **Bookmark ile pagination yap** (Pinterest'in kendi sistemi)

Bu adımları takip edersen, Pinterest senin gerçek bir kullanıcı olduğunu düşünür ve bot kontrollerini aşarsın! 🎉
