# paytr-python

[PayTR](https://dev.paytr.com/) ödeme API'leri için küçük, tamamen **async**
ve tip bilgili (typed) bir Python kütüphanesi. İster yalnızca istemciyi
kullanın, ister paketle gelen **hazır FastAPI route'larını** tek satırla
uygulamanıza ekleyin. HTTP istekleri varsayılan olarak `aiohttp` ile atılır;
`httpx` de desteklenir. FastAPI ve `pydantic` yalnızca `[fastapi]` extra'sını
kurarsanız yüklenir; `import paytr` tek başına ek bağımlılık getirmez.

PayTR API'lerinin büyük bölümü desteklenir. Route olarak yalnızca alıcının
ödeme sırasında kullandığı uçlar açılır. Geri kalan her şey (iade, durum
sorgulama, raporlama, ödeme linkleri, kayıtlı kartlar, BIN / taksit sorguları,
direct / tekrarlayan ödeme) yalnızca backend'den çağrılmak üzere tasarlanmış
`PayTRClient` metotlarıdır; bunların route'u yoktur ve tarayıcıya açılmamalıdır.
Alıcıların bu işlemleri kendilerinin yapması gerekiyorsa, metotları kendi
yetkilendirme katmanınızın arkasındaki bir endpoint ile sarın.

| Özellik | PayTR endpoint'i | İstemci metodu | Route |
| --- | --- | --- | --- |
| iFrame token (1. ADIM, **yeni tasarım v2**, kart + Havale/EFT) | `/odeme/api/get-token` | `create_iframe_token()` | `POST /paytr/pay` |
| Bildirim (callback) doğrulama (2. ADIM) | size ait URL | `verify_callback()` | `POST /paytr/callback` |
| İade (tam / kısmi) | `/odeme/iade` | `refund()` | _yalnızca backend_ |
| Durum sorgulama | `/odeme/durum-sorgu` | `status()` | _yalnızca backend_ |
| İşlem dökümü raporu | `/rapor/islem-dokumu` | `transaction_detail()` | _yalnızca backend_ |
| Ödeme dökümü / özet | `/rapor/odeme-dokumu` | `payment_statement()` | _yalnızca backend_ |
| Ödeme detayı raporu | `/rapor/odeme-detayi` | `payment_detail()` | _yalnızca backend_ |
| Ödeme linki oluşturma / silme | `/odeme/api/link/{create,delete}` | `create_payment_link()` / `delete_payment_link()` | _yalnızca backend_ |
| BIN sorgulama | `/odeme/api/bin-detail` | `bin_detail()` | _yalnızca backend_ |
| Taksit oranları | `/odeme/taksit-oranlari` | `installment_rates()` | _yalnızca backend_ |
| Kayıtlı kartlar (listeleme / silme) | `/odeme/capi/{list,delete}` | `list_cards()` / `delete_card()` | _yalnızca backend_ |
| Direct / tekrarlayan ödeme | `/odeme` | `direct_payment()` | _yalnızca backend_ |

Resmî **hata kodu tabloları** da pakete dahildir (`paytr.describe(scope, code)`).

> **Kapsam dışı:** ön provizyon (pre-authorization). PayTR bu servisin teknik
> dokümanını herkese açık yayınlamıyor (entegrasyon dokümanı için PayTR ile
> görüşmeniz gerekir). Ödeme imzalayan kodda tahminle ilerlemek doğru olmayacağı
> için bu özellik bilinçli olarak eklenmedi.

## Kurulum

```bash
pip install "paytr-python[fastapi]"   # istemci + FastAPI route'ları
pip install paytr-python              # yalnızca istemci (FastAPI gerekmez)
```

Mağaza bilgilerinizi (`merchant_id`, `merchant_key`, `merchant_salt`) PayTR
Mağaza Paneli'ndeki **BİLGİ** sayfasında bulabilirsiniz. `merchant_key` ve
`merchant_salt` gizli bilgilerdir; frontend koduna koymayın, repoya
commit'lemeyin.

**Test kartları** (yalnızca `test_mode=True` iken geçerlidir; isim ve son
kullanma tarihi serbesttir, CVV `000`): `4355084355084358`,
`5406675406675403`, `9792030394440796` (SKT için ileri bir tarih girin,
örn. `12/30`; kart sahibi "PAYTR TEST"). iFrame test formu bu kartları sizin
için otomatik doldurur; `direct_payment` testlerinde elle girmeniz gerekir.

## 1. Hazır FastAPI route'ları

```python
from fastapi import FastAPI
from paytr import PayTRClient
from paytr.fastapi import include_paytr_routes, CallbackData

app = FastAPI()
client = PayTRClient(
    merchant_id="123456", merchant_key="...", merchant_salt="...",
    test_mode=True,   # test kartlarıyla çalışmak için; canlıya geçerken False yapın
)

async def on_payment(data: CallbackData) -> None:
    # Hash'i doğrulanmış bildirimler buraya düşer. Idempotent yazın: PayTR aynı
    # bildirimi tekrar gönderebilir, her merchant_oid'i yalnızca bir kez işleyin.
    if data.is_success:
        ...  # siparişi onaylayın / bakiyeyi yükleyin
    else:
        print("ödeme başarısız:", data.error_message)

include_paytr_routes(app, client, on_payment=on_payment)   # route'ları ekler
```

Bu çağrı `/paytr` öneki altında şu uçları açar (önek `prefix=` ile
değiştirilebilir):

```
POST /paytr/pay              V2 iFrame token'ı oluşturur (1. ADIM)
POST /paytr/callback         ödeme sonucu bildirimi (2. ADIM, PayTR -> siz)
GET  /paytr/ok, /paytr/fail  alıcının yönlendirildiği varsayılan sayfalar
```

Alıcının ödeme akışı için gereken her şey bu kadar. Mağaza tarafındaki
işlemler (**iade**, **durum**, **raporlama**, **linkler**, **kayıtlı
kartlar**, **BIN / taksit**, **direct ödeme**) için bilerek route açılmadı; bu
işlemleri kendi backend kodunuzdan `client.refund()`, `client.status()`,
`client.create_payment_link()` gibi metotlarla yapın (bkz. 2. bölüm).

Kök dizine (`/`) hiçbir şey eklenmez; tüm uçlar önekin altında kaldığı için
uygulamanızın kendi route'larıyla çakışma yaşanmaz. İsteğe bağlı parametreler:
`prefix`, `ok_url`, `fail_url`. Router'ı uygulamanıza kendiniz eklemek
isterseniz `create_paytr_router(...)` kullanın.

### `POST /paytr/pay` isteğinin gövdesi

```json
{
  "email": "alici@example.com",
  "user_name": "Ayşe Yılmaz",
  "user_address": "Örnek Mah. Örnek Sok. No:1",
  "user_phone": "05551112233",
  "basket": [{"name": "Ürün 1", "unit_price": 18.0, "quantity": 1}],
  "currency": "TL",
  "lang": "tr"
}
```

Tutarlar TL cinsinden yazılır (örn. `18.0` ₺). Kuruşa çevirme (×100), sepetin
kodlanması ve HMAC imzası kütüphane tarafından yapılır. Dönen yanıt:
`{"status": "success", "merchant_oid": "...", "token": "...", "iframe_url": "..."}`.
`iframe_url`'i PayTR'nin resizer script'iyle birlikte sayfanıza gömmeniz
yeterli.

### Güvenlik

`POST /paytr/pay` isteğindeki sepet istemciden gelir; `/pay` ucu tarayıcının
gönderdiği fiyatı olduğu gibi imzalar. **Bu fiyatlara güvenmeyin.** Fiyatı her
zaman sunucu tarafında tuttuğunuz katalogdan, `merchant_oid` (veya ürün id'si)
üzerinden hesaplayın.

Ek bir güvenlik katmanı isterseniz, siparişin olması gereken toplamını kuruş
cinsinden döndüren async bir `get_expected_amount(merchant_oid)` fonksiyonu
tanımlayın. `total_amount` değeri bu tutarla uyuşmayan başarılı bildirimler,
`on_payment` hiç çalışmadan HTTP 400 ile reddedilir:

```python
async def get_expected_amount(merchant_oid: str) -> int | None:
    order = await orders.get(merchant_oid)        # sipariş kaydınızdan okuyun
    return order.toplam_kurus if order else None  # None dönerseniz kontrol atlanır

include_paytr_routes(
    app, client, on_payment=on_payment, get_expected_amount=get_expected_amount
)
```

Bildirimlerin HMAC doğrulaması (sabit zamanlı karşılaştırmayla) varsayılan
olarak yapılır; sahte ya da üzerinde oynanmış bir bildirim `on_payment`'a
hiçbir zaman ulaşmaz.

## 2. İstemci (framework'ten bağımsız)

```python
from paytr import PayTRClient, iframe_html

client = PayTRClient(merchant_id="...", merchant_key="...", merchant_salt="...")

result = await client.create_iframe_token(
    merchant_oid="SIPARIS123",
    email="alici@example.com",
    payment_amount="34.56",
    user_ip="1.2.3.4",
    user_name="Ayşe Yılmaz",
    user_address="Örnek Mah. Örnek Sok. No:1",
    user_phone="05551112233",
    user_basket=[("Ürün 1", "18.00", 1), ("Ürün 2", "16.56", 1)],
    merchant_ok_url="https://magaza.example.com/ok",
    merchant_fail_url="https://magaza.example.com/fail",
)
html = iframe_html(result["token"])

# Diğer backend işlemleri
await client.refund(merchant_oid="SIPARIS123", return_amount="11.90")
await client.status("SIPARIS123")
await client.transaction_detail(start_date="2021-02-02 00:00:00", end_date="2021-02-04 23:59:59")
await client.payment_statement(start_date="2022-09-01", end_date="2022-09-30")
await client.payment_detail("2022-09-15")

# Ödeme linkleri (fiyat TL cinsinden)
link = await client.create_payment_link(name="Tişört", price=14.45, min_count=1)
await client.delete_payment_link(link["id"])

# Sorgular
await client.bin_detail("435508")            # kart markası / banka / 3D desteği
await client.installment_rates("req-123")    # taksit / komisyon oranlarınız

# Kayıtlı kartlar + tekrarlayan ödeme (mağazanızda Non3D özelliği açık olmalı)
cards = await client.list_cards(utoken)       # utoken size bildirimle (callback) gelir
await client.direct_payment(
    merchant_oid="SIPARIS124", email="alici@example.com",
    payment_amount="34.56",                   # dikkat: iFrame'den farklı, TL string'i
    user_ip="1.2.3.4", user_name="Ayşe", user_address="Örnek Mah. No:1", user_phone="0555...",
    user_basket=[("Ürün 1", "34.56", 1)],
    merchant_ok_url="https://magaza.example.com/ok",
    merchant_fail_url="https://magaza.example.com/fail",
    recurring=True, utoken=utoken, ctoken=cards["cards"][0]["ctoken"],
)
```

> **Tutar formatlarına dikkat:** `create_iframe_token` ve link `price`
> parametresine TL girersiniz, kuruşa çevirme (×100) işini kütüphane yapar.
> `refund` ve `direct_payment` ise tutarı `"34.56"` gibi TL string'i olarak
> bekler. İkisi farklı imzalandığı için doğru metodu kullanmak önemlidir.

Bir bildirimi elle doğrulamak isterseniz:

```python
ok = client.verify_callback(
    merchant_oid=oid, status=status, total_amount=total_amount, hash=received_hash
)  # veriyi kullanmadan önce mutlaka doğrulayın; ardından düz metin "OK" dönün
```

> PayTR, bildirim URL'nizden gövdesi tam olarak `OK` olan bir yanıt alana
> kadar bildirimi yaklaşık birer dakika arayla tekrar gönderir. İşleme
> sırasında hata oluştuysa `OK` dönmeyin; PayTR bildirimi yeniden gönderecektir.

## Hatalar

Başarısız API yanıtlarında `PayTRAPIError` fırlatılır (`.message`, `.code`,
`.scope`, `.payload`). Ağ ve çözümleme sorunları `PayTRNetworkError`, hatalı
yapılandırma `PayTRConfigError` üretir. Hepsinin ortak atası `PayTRError`'dur.
Ham bir hata kodunu açıklamaya çevirmek için (açıklamalar resmî dev.paytr.com
tablolarından alınmıştır ve İngilizcedir):

```python
from paytr import describe
describe("payment", "10")  # -> "3D Secure required for this transaction"
describe("refund", "009")  # -> "Refund exceeds the remaining transaction amount"
```

## Loglama

Kütüphane kendi `paytr` logger'ını kullanır ve bunu import sırasında otomatik
yapılandırır; ayrıca bir kurulum çağrısı gerekmez. Handler yalnızca `paytr`
logger'ına eklenir (root logger'a dokunulmaz) ve propagation kapalıdır; yani
uygulamanızın log düzenine karışmaz, aynı satırı iki kez bastırmaz.

```python
import os
os.environ["PAYTR_LOG"] = "off"      # otomatik yapılandırmayı kapatır; logger sizde
os.environ["PAYTR_LOG"] = "debug"    # veya log seviyesini seçin (debug/info/warning/...)

# ya da çalışma zamanında:
from paytr import setup_logging
setup_logging("DEBUG", use_colors=False)   # idempotent; mevcut ayarı ezmek için force=True
```

PayTR loglarını kendi handler'larınıza yönlendirmek için `PAYTR_LOG=off`
yapıp `logging.getLogger("paytr")`'ı istediğiniz gibi yapılandırmanız yeterli.

## HTTP oturumu ve yaşam döngüsü

Timeout, bağlantı limiti, proxy ya da retry davranışını kendiniz yönetmek
istiyorsanız istemciye kendi oturumunuzu verin; kütüphane bu durumda hiçbir
ayar dayatmaz:

```python
PayTRClient(..., session=my_aiohttp_session)     # backend otomatik algılanır
PayTRClient(..., session=my_httpx_async_client)  # backend otomatik algılanır
```

Oturum vermezseniz ilk istekte varsayılan bir **aiohttp** oturumu oluşturulur:

```python
PayTRClient(...)               # aiohttp (varsayılan), 30 sn timeout
PayTRClient(..., timeout=None) # timeout uygulanmaz
PayTRClient(..., timeout=10)   # varsayılan oturumda 10 sn timeout
```

httpx kullanmak için `[httpx]` extra'sını kurup `session=` parametresine bir
`httpx.AsyncClient` vermeniz yeterli.

İstemciyi tek instance olarak kullanın (bağlantı havuzu sayesinde daha
verimlidir) ve uygulama kapanırken `await client.aclose()` ile kapatın; ya da
async context manager olarak kullanın. `session=` ile verdiğiniz oturumun
yönetimi sizdedir, kütüphane onu kapatmaz.

## Demo uygulama

`src/` klasörü çalıştırılabilir bir örnek uygulamadır (`src` yerleşimi;
kütüphane `src/modules/paytr` altındadır ve `paytr` adıyla import edilir):

```
src/
  main.py            # .env'i yükler, CORS ayarlar, api/ altındaki router'ları bulup ekler
  modules/paytr/     # kütüphanenin kendisi (içinde kimlik bilgisi yoktur)
  api/_client.py     # env'den beslenen hazır PayTRClient singleton'ı
  api/payment.py     # kütüphanenin router'ını uygulamaya ekler (create_paytr_router)
  api/page.py        # /paytr/ adresinde test sayfasını sunar
  web/index.html     # bağımsız test sayfası (sunucudan ya da doğrudan dosya olarak açılır)
```

```bash
uv sync --all-extras
cp src/example.env .env             # gerçek mağaza bilgilerinizi girin
cd src && uv run main.py            # http://127.0.0.1:8000/paytr/
uv run pytest                       # testler (ağ bağlantısı gerektirmez)
```
