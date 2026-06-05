# PayTR Python Client

[![PyPI Version](https://img.shields.io/pypi/v/paytr-python.svg)](https://pypi.org/project/paytr-python/)
[![Python Versions](https://img.shields.io/pypi/pyversions/paytr-python.svg)](https://pypi.org/project/paytr-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

[PayTR](https://dev.paytr.com/) API entegrasyonunu kolaylaştıran, **hafif (lightweight)**, **tamamen asenkron (async)** ve **tip güvenli (type-safe)** bir Python kütüphanesidir.

İster sadece `PayTRClient` ile backend tarafında tüm süreci yönetin, ister paketle birlikte gelen **hazır FastAPI route'larını** tek satırda uygulamanıza dahil edin. 

İstekler için varsayılan olarak `aiohttp` kullanılır ama isterseniz `httpx` de tercih edebilirsiniz. FastAPI ve `pydantic` desteği yalnızca `[fastapi]` extra'sını kurduğunuzda gelir; kütüphane varsayılan haliyle sıfır ek bağımlılıkla çalışır.

<!-- MARK: Desteklenen Özellikler -->
### Desteklenen Özellikler & API Eşleşmesi

Güvenlik nedeniyle, dışarıya sadece müşterinin ödeme anında tetiklemesi gereken endpoint'ler (route) açılır. İade, durum sorgulama, raporlama, link yönetimi, kayıtlı kartlar, BIN/taksit sorguları ve doğrudan/tekrarlayan ödemeler gibi yetki gerektiren kritik işlemler yalnızca backend tarafında çalışan `PayTRClient` metotları olarak sunulur. Bu kritik işlemleri doğrudan dış dünyaya API rotası olarak açmamalısınız. Eğer son kullanıcının bu işlemleri tetiklemesi gerekiyorsa, kendi yetkilendirme (auth) katmanınızın arkasında bir endpoint oluşturup istemci metotlarını orada çağırmalısınız.

| Özellik | PayTR Endpoint'i | İstemci Metodu | FastAPI Uç Noktası (Route) |
| :--- | :--- | :--- | :--- |
| **iFrame Token Alımı** <br>*(1. Adım - Yeni v2, Kart & Havale/EFT)* | `/odeme/api/get-token` | `create_iframe_token()` | `POST /paytr/pay` |
| **Bildirim Doğrulama** <br>*(2. Adım - Callback)* | *Sizin Callback URL'niz* | `verify_callback()` | `POST /paytr/callback` |
| **İade İşlemleri** <br>*(Tam veya Kısmi)* | `/odeme/iade` | `refund()` | *Sadece Backend (Yetkilendirilmiş)* |
| **İşlem Durumu Sorgulama** | `/odeme/durum-sorgu` | `status()` | *Sadece Backend (Yetkilendirilmiş)* |
| **İşlem Dökümü Raporu** | `/rapor/islem-dokumu` | `transaction_detail()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Ödeme Özet Raporu** | `/rapor/odeme-dokumu` | `payment_statement()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Tekil Ödeme Detay Raporu** | `/rapor/odeme-detayi` | `payment_detail()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Ödeme Linki Yönetimi** <br>*(Oluşturma & Silme)* | `/odeme/api/link/create`<br>`/odeme/api/link/delete` | `create_payment_link()` <br> `delete_payment_link()` | *Sadece Backend (Yetkilendirilmiş)* |
| **BIN Sorgulama** <br>*(Kart Detayları)* | `/odeme/api/bin-detail` | `bin_detail()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Taksit Oranları Sorgulama** | `/odeme/taksit-oranlari` | `installment_rates()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Kayıtlı Kart Yönetimi** <br>*(Listeleme & Silme)* | `/odeme/capi/list`<br>`/odeme/capi/delete` | `list_cards()` <br> `delete_card()` | *Sadece Backend (Yetkilendirilmiş)* |
| **Doğrudan & Tekrarlayan Ödeme** | `/odeme` | `direct_payment()` | *Sadece Backend (Yetkilendirilmiş)* |

> [!NOTE]
> **Ön Provizyon (Pre-Authorization):** PayTR bu servise dair teknik dökümanı herkese açık olarak yayınlamıyor (özel entegrasyon dökümanı için PayTR destek ekibiyle iletişime geçmeniz gerekir). Hatalı imzalama (hash) işlemlerinin önüne geçmek amacıyla, bu özellik kütüphanenin kapsamı dışında tutulmuştur.

<!-- MARK: Kurulum -->
## 📦 Kurulum

Kütüphaneyi tercih ettiğiniz paket yöneticisiyle kurabilirsiniz.

```bash
# Sadece PayTRClient istemcisini kurmak için (Sıfır ek bağımlılık)
pip install paytr-python
# VEYA uv kullanıyorsanız:
uv add paytr-python

# FastAPI route'ları ve otomatik doğrulama şemaları ile birlikte kurmak için
pip install "paytr-python[fastapi]"
# VEYA uv kullanıyorsanız:
uv add "paytr-python[fastapi]"

# httpx istemci desteği ile kurmak için
pip install "paytr-python[httpx]"
# VEYA uv kullanıyorsanız:
uv add "paytr-python[httpx]"
```

Entegrasyon için gereken `merchant_id`, `merchant_key` ve `merchant_salt` değerlerini [PayTR Mağaza Paneli](https://www.paytr.com/magaza) > **Bilgi** sayfasında bulabilirsiniz.

> [!WARNING]
> `merchant_key` ve `merchant_salt` bilgileri hassas gizli anahtarlardır. Güvenlik açığı oluşmaması için bu bilgileri asla frontend kodunuza eklemeyin, istemci tarafında barındırmayın ve Git gibi sürüm kontrol sistemlerine commit'lemeyin. Çevre değişkenleri (`.env`) kullanılması şiddetle önerilir.

### 🧪 Test Kartları
PayTR test ortamında (`test_mode=True` iken) kullanabileceğiniz test kartlarından bazıları:
- **Visa:** `4355084355084358`
- **Mastercard:** `5406675406675403`
- **Troy:** `9792030394440796`

**İpucu:** Test kartlarıyla işlem yaparken kart sahibi ismini rastgele girebilir, son kullanma tarihine gelecekte herhangi bir tarih (örn: `12/30`) yazabilir ve CVV olarak `000` kullanabilirsiniz. iFrame entegrasyonlarında test kartları otomatik doldurulabilir, ancak `direct_payment` yaparken bunları koddan manuel göndermeniz gerekir.

<!-- MARK: FastAPI Entegrasyonu -->
## 🚀 1. FastAPI Entegrasyonu (Hazır Route'lar)

FastAPI kullanıyorsanız, ödeme isteği oluşturma, başarılı/başarısız bildirimleri yakalama ve yönlendirme işlemlerini tek bir fonksiyonla halledebilirsiniz:

```python
from fastapi import FastAPI
from paytr import PayTRClient
from paytr.fastapi import include_paytr_routes, CallbackData

app = FastAPI()

# PayTR istemcisini yapılandırın
client = PayTRClient(
    merchant_id="123456",
    merchant_key="your_merchant_key",
    merchant_salt="your_merchant_salt",
    test_mode=True  # Canlıya geçerken False yapmayı unutmayın!
)

# Ödeme sonucu bildirimlerini işleyen callback fonksiyonu
async def on_payment(data: CallbackData) -> None:
    # Bu fonksiyon sadece imzası (hash'i) doğrulanmış ve güvenli olduğu kesinleşmiş bildirimler için tetiklenir.
    # Idempotency (tekrarlanamazlık) konusuna dikkat etmelisiniz: PayTR aynı bildirimi ağ veya zaman aşımı
    # sorunları yüzünden tekrar gönderebilir, bu yüzden her merchant_oid değerini yalnızca bir kez işleyin.
    if data.is_success:
        # Siparişi onaylayın, faturayı oluşturun veya bakiye yüklemesini yapın
        print(f"Ödeme başarılı! Sipariş No: {data.merchant_oid}, Tutar: {data.payment_amount} kuruş")
    else:
        # Ödeme başarısız olduğunda yapılacak işlemler
        print(f"Ödeme başarısız! Sipariş No: {data.merchant_oid}, Hata: {data.error_message}")

# Hazır PayTR route'larını FastAPI uygulamasına ekleyin
include_paytr_routes(app, client, on_payment=on_payment)
```

Bu tek satırlık `include_paytr_routes` çağrısı, uygulamanıza varsayılan olarak `/paytr` öneki (prefix) altında şu rotaları ekler:

*   `POST /paytr/pay`: V2 iFrame token'ı üretir. (Ödemenin 1. Adımı)
*   `POST /paytr/callback`: PayTR sunucularından gelen ödeme sonuç bildirimlerini yakalar, imza kontrolünü yapar ve `on_payment` fonksiyonunuzu tetikler. (Ödemenin 2. Adımı)
*   `GET /paytr/ok` ve `GET /paytr/fail`: Ödeme sonrası müşterinin yönlendirileceği varsayılan başarılı ve başarısız sayfaları.

> [!TIP]
> İstek yollarını özelleştirmek için `prefix="/odemeler"`, `ok_url="https://siteniz.com/basarili"`, `fail_url="https://siteniz.com/hata"` gibi parametreleri kullanabilirsiniz. Rotalar önek altında toplandığı için mevcut endpoint'lerinizle çakışma yaşanmaz. Router nesnesini doğrudan kontrol etmek isterseniz `create_paytr_router(...)` fonksiyonunu kullanabilirsiniz.

### `POST /paytr/pay` İstek Gövdesi
`/paytr/pay` rotasına göndermeniz gereken JSON gövdesi şu şekildedir:

```json
{
  "email": "alici@example.com",
  "user_name": "Ayşe Yılmaz",
  "user_address": "Örnek Mah. Örnek Sok. No:1 Daire:3 Üsküdar/İstanbul",
  "user_phone": "05551112233",
  "basket": [
    {"name": "Örnek Ürün 1", "unit_price": 18.0, "quantity": 1},
    {"name": "Örnek Ürün 2", "unit_price": 16.56, "quantity": 1}
  ],
  "currency": "TL",
  "lang": "tr"
}
```

*   **Tutar Dönüşümleri:** Sepetteki ürün fiyatları ve toplam tutarlar TL cinsinden girilir (`18.0` veya `16.56`). Kuruşa dönüştürme (x100), sepetin base64 formatında kodlanması ve HMAC imzasının oluşturulması kütüphane tarafından otomatik olarak yapılır.
*   **Yanıt Formatı:** Başarılı isteklerde rota size şu yanıtı döner:
    `{"status": "success", "merchant_oid": "...", "token": "...", "iframe_url": "..."}`.
    Dönen `iframe_url` adresini ya da `token` değerini kullanarak ödeme formunu sitenize gömebilirsiniz.

### 🛡️ Güvenlik ve Fiyat Manipülasyonu Koruması

> [!CAUTION]
> İstemciden (frontend) gelen sepet ve tutar bilgilerine asla doğrudan güvenmeyin. Kötü niyetli bir kullanıcı `/paytr/pay` isteğindeki fiyatı değiştirerek 1000 TL'lik ürünü 1 TL olarak ödemeye çalışabilir.

Bunun önüne geçmek için, siparişin gerçekte olması gereken toplam kuruş tutarını veritabanınızdan sorgulayan asenkron bir `get_expected_amount(merchant_oid)` fonksiyonu tanımlayıp `include_paytr_routes`'a parametre olarak geçebilirsiniz. Tutar uyuşmazlığı varsa, ödeme callback'i `on_payment` fonksiyonunuza hiç ulaşmadan HTTP 400 ile otomatik olarak reddedilir:

```python
async def get_expected_amount(merchant_oid: str) -> int | None:
    # merchant_oid üzerinden veritabanınızdan sipariş kaydını çekin
    order = await db.get_order(merchant_oid)
    # Beklenen tutarı kuruş cinsinden (int) dönün. 34.56 TL için 3456 dönmelidir.
    # Eğer None dönerseniz, o sipariş için tutar kontrolü atlanır.
    return order.total_amount_in_cents if order else None

include_paytr_routes(
    app, 
    client, 
    on_payment=on_payment, 
    get_expected_amount=get_expected_amount
)
```

<!-- MARK: İstemci Kullanımı -->
## 🛠️ 2. Framework Bağımsız Kullanım (İstemci Sınıfı)

FastAPI kullanmıyorsanız (Django, Flask, Sanic vb. veya bağımsız script'ler yazıyorsanız) `PayTRClient` sınıfını doğrudan uygulamanıza import ederek kullanabilirsiniz.

```python
from decimal import Decimal
from paytr import PayTRClient, iframe_html

# İstemciyi başlatın
client = PayTRClient(
    merchant_id="your_merchant_id", 
    merchant_key="your_merchant_key", 
    merchant_salt="your_merchant_salt"
)

# 1. Adım: Ödeme Formu için iFrame Token Oluşturma
result = await client.create_iframe_token(
    merchant_oid="SIPARIS123",
    email="alici@example.com",
    payment_amount="34.56",  # TL cinsinden str, float veya Decimal girilebilir.
    user_ip="1.2.3.4",
    user_name="Ayşe Yılmaz",
    user_address="Örnek Mah. Örnek Sok. No:1",
    user_phone="05551112233",
    user_basket=[("Ürün 1", "18.00", 1), ("Ürün 2", "16.56", 1)],  # (İsim, Birim Fiyat, Adet)
    merchant_ok_url="https://siteniz.com/basarili",
    merchant_fail_url="https://siteniz.com/hata",
)

# HTML iFrame kodunu oluşturun (iframeResizer script'ini otomatik ekler)
html_snippet = iframe_html(result["token"])

# 2. Adım: Bildirim Doğrulama (Callback)
# PayTR sunucularından callback URL'nize gelen POST isteğindeki parametrelerle
# imza doğrulaması yapın:
is_valid = client.verify_callback(
    merchant_oid=received_oid,
    status=received_status,
    total_amount=received_total_amount,
    hash=received_hash
)

if is_valid:
    # Bildirim gerçek ve PayTR'den gelmiştir. Sipariş durumunu güncelleyin.
    # PayTR'ye sadece "OK" (tırnaksız, yalın metin) yanıtı vermelisiniz.
    return "OK"
```

> [!IMPORTANT]
> **Callback (Geri Bildirim) Davranışı:**
> PayTR, callback URL'nizden tam olarak **`OK`** yanıtı (yalın metin, HTML etiketi olmadan) alana kadar bildirimi yaklaşık 1'er dakika arayla göndermeye devam eder. Kendi veritabanınızda veya akışınızda hata oluşursa `OK` dönmeyin; böylece PayTR bildirimi tekrar dener.

### Diğer Backend Metotları

`PayTRClient` ile gerçekleştirebileceğiniz diğer tüm backend işlemleri:

```python
# --- İade İşlemleri ---
# Tutar TL cinsinden str, float veya Decimal olmalıdır (örn: "11.90")
await client.refund(merchant_oid="SIPARIS123", return_amount="11.90")

# --- İşlem Durumu Sorgulama ---
# Siparişin ödeme durumunu, taksit sayısını, kesinti oranını vb. sorgular
status_detail = await client.status(merchant_oid="SIPARIS123")

# --- Raporlama API'leri ---
# Belirli tarihler arasındaki işlem listesini çeker (Y-m-d H:M:S)
await client.transaction_detail(start_date="2026-06-01 00:00:00", end_date="2026-06-03 23:59:59")
# Belirli tarihler arasındaki ödeme (hakediş) raporunu çeker
await client.payment_statement(start_date="2026-06-01", end_date="2026-06-30")
# Tek bir güne ait ödeme detayını çeker
await client.payment_detail(date="2026-06-05")

# --- Ödeme Linki Yönetimi ---
# Özel bir ürün/tahsilat için hızlı ödeme linki üretir
link = await client.create_payment_link(name="Özel Tişört", price=14.45, min_count=1)
await client.delete_payment_link(link_id=link["id"])

# --- BIN & Taksit Sorguları ---
await client.bin_detail(bin_number="435508")            # Kart markası, tipi, banka bilgileri
await client.installment_rates(request_id="req-123")    # Taksit oranları ve komisyon listesi

# --- Kayıtlı Kart & Doğrudan (Direct) Ödeme ---
# (Mağazanızın Non-3D işlem yetkisinin açık olması gerekmektedir)
cards = await client.list_cards(utoken="kullanici_tokeni")
await client.direct_payment(
    merchant_oid="SIPARIS124",
    email="alici@example.com",
    payment_amount="34.56",  # Dikkat: iFrame'den farklı olarak TL cinsinden str olmalıdır
    user_ip="1.2.3.4",
    user_name="Ayşe",
    user_address="İstanbul",
    user_phone="0555...",
    user_basket=[("Ürün 1", "34.56", 1)],
    merchant_ok_url="https://siteniz.com/ok",
    merchant_fail_url="https://siteniz.com/fail",
    recurring=True,
    utoken="kullanici_tokeni",
    ctoken=cards["cards"][0]["ctoken"]
)
```

> [!WARNING]
> **Tutar Formatı Farklılıkları:**
> PayTR entegrasyonlarının en bilinen tuzağı tutar formatlarıdır.
> *   **iFrame Ödemesi (`create_iframe_token`) ve Link Oluşturma (`create_payment_link`):** Fiyatı TL (örneğin `"34.56"` veya `34.56`) olarak alır, kütüphane bunu arka planda kuruşa (x100 tamsayı) çevirip imzalar.
> *   **İade (`refund`) ve Doğrudan Ödeme (`direct_payment`):** Tutarın `"34.56"` gibi **noktayla ayrılmış TL string'i** olarak gönderilmesi gerekir. Kütüphane bu metotlarda herhangi bir dönüşüm yapmaz, değeri doğrudan API'ye gönderir.

<!-- MARK: Hata Yönetimi -->
## ❌ Hata Yönetimi

Kütüphanede hata yönetimi için özelleştirilmiş exception sınıfları bulunur:

*   `PayTRError`: Tüm kütüphane hatalarının ortak atasıdır.
*   `PayTRConfigError`: Eksik veya hatalı mağaza kimlik bilgisi girildiğinde fırlatılır.
*   `PayTRNetworkError`: Sunucu bağlantı hataları, zaman aşımları ve ağ kesintilerinde fırlatılır.
*   `PayTRAPIError`: PayTR API'sinin hata döndürdüğü durumlarda fırlatılır. Bu hata nesnesi üzerinden `.message`, `.code`, `.scope` ve `.payload` (API'nin döndüğü ham JSON yanıt) niteliklerine erişebilirsiniz.

### Hata Kodlarını Açıklamaya Dönüştürme
Resmî PayTR dökümanındaki hata kodlarını anlamlı açıklamalara çevirmek için `paytr.describe` fonksiyonunu kullanabilirsiniz:

```python
from paytr import describe

# Ödeme/Callback hata kodu sorgulama
describe("payment", "10")   # -> "3D Secure required for this transaction"

# İade hata kodu sorgulama
describe("refund", "009")   # -> "Refund exceeds the remaining transaction amount"
```

<!-- MARK: Loglama -->
## 📝 Loglama ve İzlenebilirlik

Kütüphane, kendi `paytr` logger'ını kullanır ve ilk import edildiğinde bunu otomatik yapılandırır. Log akışı, uygulamanızın kendi log düzenini (root logger) kirletmeyecek şekilde `propagation=False` olarak ayarlanmıştır.

Log düzeyini ayarlamak veya devre dışı bırakmak için çevre değişkenlerini kullanabilirsiniz:

```bash
# Otomatik log yapılandırmasını kapatır (Kendi logging handler'ınızı bağlayabilirsiniz)
export PAYTR_LOG="off"

# Log seviyesini seçin (DEBUG, INFO, WARNING, ERROR, CRITICAL)
export PAYTR_LOG="debug"
```

Çalışma zamanında (runtime) programatik olarak yapılandırmak için:

```python
from paytr import setup_logging

# Log seviyesini DEBUG yapın, renkli çıktıyı kapatın
setup_logging("DEBUG", use_colors=False)
```

<!-- MARK: HTTP Oturumu -->
## 🔄 HTTP Oturumu ve Yaşam Döngüsü (Session Management)

Bağlantı havuzunu (connection pool) yönetmek, timeout/proxy ayarlarını özelleştirmek veya kendi retry mekanizmanızı kurmak istiyorsanız, kullandığınız HTTP istemcisinin session nesnesini client'a geçebilirsiniz:

```python
# aiohttp oturumu paylaştırma
client = PayTRClient(..., session=my_aiohttp_session)

# httpx oturumu paylaştırma (opsiyonel dependency ile kurulmalıdır)
client = PayTRClient(..., session=my_httpx_async_client)
```

Eğer herhangi bir `session` parametresi geçilmezse, ilk istekte varsayılan bir `aiohttp.ClientSession` oluşturulur:

```python
# Varsayılan aiohttp oturumu (30 saniye timeout ile)
client = PayTRClient(...)

# Timeout süresini özelleştirme
client = PayTRClient(..., timeout=10)  # 10 saniye limit
```

> [!TIP]
> Kütüphane tarafından oluşturulan varsayılan oturumları, uygulamanız sonlanırken `await client.aclose()` metodu ile kapatmalısınız. `PayTRClient` nesnesini aynı zamanda bir **asenkron context manager** (`async with`) olarak da kullanabilirsiniz. `session` parametresiyle dışarıdan verdiğiniz oturumlar ise kütüphane tarafından kapatılmaz; yaşam döngüsü yönetimi size aittir.

<!-- MARK: Demo Uygulama -->
## 🕹️ Demo Uygulama

Repo içerisinde, `src/` dizini altında hızlıca ayağa kaldırıp test edebileceğiniz bir demo uygulama yer alıyor:

```
src/
  main.py            # .env dosyasını yükler, CORS ayarlarını yapar ve router'ları kaydeder.
  modules/paytr/     # Kütüphanenin kaynak kodları.
  api/_client.py     # Çevre değişkenlerinden beslenen PayTRClient singleton yapısı.
  api/payment.py     # include_paytr_routes kullanarak API uç noktalarını bağlar.
  api/page.py        # Test sayfasını sunan yönlendirici (/paytr/).
  web/index.html     # Ödeme iFrame'ini gösteren tarayıcı test arayüzü.
```

### Çalıştırma Adımları

1.  Bağımlılıkları ve geliştirici araçlarını yükleyin:
    ```bash
    uv sync --all-extras
    ```
2.  Çevre değişkenlerini tanımlayın:
    ```bash
    cp src/example.env .env
    # .env dosyasını düzenleyerek kendi PayTR mağaza bilgilerinizi girin.
    ```
3.  Uygulamayı başlatın:
    ```bash
    cd src && uv run main.py
    ```
    Tarayıcınızdan `http://127.0.0.1:8000/paytr/` adresine giderek test ödeme formunu görüntüleyebilirsiniz.
4.  Testleri çalıştırın (mock mekanizması kullandığından ağ bağlantısı gerektirmez):
    ```bash
    uv run pytest
    ```
