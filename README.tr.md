# hackwatch

> **Sadece lab ortamı.** `hackwatch`, senin çalıştırdığın, kasten zafiyetli bir
> web uygulamasına saldırır. Sahibi olmadığın ya da izin almadığın hiçbir
> sisteme yöneltme. Bkz. [Etik](#etik).

Bileğe takılan bir web saldırı aracı. `hackwatch`, tek başına `curl` ile küçük
ve kasten bozuk bir web uygulamasıyla konuşan bir POSIX shell script'idir. Wear
OS saatte [Wear Term](https://github.com/0xberkay/WearTerm) ile çalışırken
bileği titretir, bildirim yollar ve konuşur.

Amaç tek: **tek komutla, akıllı saatinden bir web sitesini çökertmek.**

```
$ hackwatch nuke --yes

#   #   #    #### #   # #   #   #   #####  #### #   #
##### ##### #     ###   # # # #####   #   #     #####
...
::reading /.env for the database path
  DB_PATH = /home/you/hackwatch/target/lab.db

  firing in 3...
  firing in 2...
  firing in 1...

#####   #   ####   #### ##### #####       ####   ###  #   # #   #
  #    # #  #   # #     #       #         #   # #   # #   # ##  #
  #   ##### ####  #  ## ####    #         #   # #   # # # # # # #
  #   #   # #  #  #   # #       #         #   # #   # # # # #  ##
  #   #   # #   #  #### #####   #         ####   ###   # #  #   #
```

## Nasıl çalışır

Tek repoda iki parça:

- **`target/app.py`** — kasten zafiyetli web uygulaması. Saf Python standart
  kütüphanesi, bağımlılık yok. SQL injection, command injection, path
  traversal, IDOR, reflected XSS ve sınırsız bellek endpoint'i içerir; kendi
  `.env` dosyasını da güzelce servis eder.
- **`hackwatch`** — istemci. POSIX `sh` + `curl`. Saatte, laptopta, her yerde
  çalışır. Lab'ın her yanıtı `X-HackWatch-Lab` başlığı taşır; istemci bu
  başlığı görmeden hiçbir saldırı komutunu çalıştırmaz — yani sadece lab'a
  dokunabilir.

## Gereksinimler

- Lab: `python3` (3.8+). Başka bir şey gerekmez.
- İstemci: `sh`, `curl`. Saat için opsiyonel: Wear Term'in `wt-vibrate`,
  `wt-notify`, `wt-tts` komutları.

## Hızlı başlangıç

**1. Lab'ı başlat** — saatle aynı Wi-Fi'daki bir makinede:

```sh
git clone https://github.com/0xberkay/hackwatch.git
cd hackwatch
python3 target/app.py            # 0.0.0.0:8000 dinler
```

Saatten makinenin LAN adresine eriş, örn. `http://192.168.1.20:8000`.

Saat makineye ping atabiliyor ama zaman aşımına düşüyorsa arada bir güvenlik
duvarı vardır. `ufw` kullanan bir makinede:

```sh
sudo ufw allow 8000/tcp
```

**2. İstemciyi kur** (saatte Wear Term içinde, ya da laptopta):

```sh
./install.sh                     # -> ~/.local/bin/hackwatch
# ya da olduğu yerde çalıştır: ./hackwatch ...
```

**3. Hedefi ayarla ve başla:**

```sh
hackwatch target http://192.168.1.20:8000
hackwatch recon                  # parmak izi + açık dosyalar
hackwatch sqli                   # ' OR 1=1--  -> ACCESS GRANTED
hackwatch loot                   # kullanıcı tablosunu dök
hackwatch nuke --yes             # DB'yi sil, sunucuyu öldür
```

Ya da adımları atla: `hack` tam zinciri duraksız çalıştırır ve siteyi düşürür.
Saatte URL yazmak eziyet olduğu için `target` adresi hatırlar.

## Komutlar

| Komut | Ne yapar |
| --- | --- |
| `hackwatch target <url>` | lab URL'sini hatırla |
| `hackwatch status` | lab ayakta mı? |
| `hackwatch recon` | sunucu/başlık parmak izi ve bilinen yol taraması |
| `hackwatch sqli` | SQL injection ile login atlatma |
| `hackwatch loot` | UNION injection ile `users` tablosunu dök |
| `hackwatch cmdi <cmd>` | hedefte shell komutu çalıştır (command injection) |
| `hackwatch lfi <path>` | hedeften dosya oku (path traversal) |
| `hackwatch shell` | command injection üzerinden interaktif shell |
| `hackwatch nuke --yes` | veritabanını sil, sunucuyu öldür |
| `hackwatch auto --yes` | duraksız tam zincir: recon, sqli, loot, nuke |
| `hack` | `auto --yes` ile aynı: tek kelime, tam kompromi |
| `hackwatch banner` | banner yazdır |

Ortam: `HACKWATCH_PLAIN=1` rengi kapatır, `HACKWATCH_COLOR=1` çıktı boruya
giderken rengi zorlar.

## `nuke` tam olarak ne yapar

1. Hedefin lab olduğunu doğrular (`X-HackWatch-Lab` başlığı).
2. SQLite veritabanının tam yolunu öğrenmek için `/.env` okur.
3. `/ping?host=` command-injection endpoint'ine `rm -f <db>; kill -9 $PPID`
   gönderir. Enjekte edilen shell'in `$PPID`'si lab sunucusudur; veritabanı
   silinir ve proses öldürülür.
4. Hedef yanıt vermeyene kadar yoklar ve **TARGET DOWN** yazar.
5. RCE çalışmadıysa `/boom` bellek endpoint'ine düşer.

Sonuç: hesaplar gitti, proses gitti, site gitti.

## Bilek entegrasyonu

Wear Term'in cihaz komutları `PATH`'te olduğunda `hackwatch` onları kendiliğinden
kullanır: `recon`'un bulduğu her yol için kısa bir titreşim, `ACCESS GRANTED`
anında uzun bir titreşim, `nuke` bitince bildirim ve "target down" sesi. Başka
bir makinede bu çağrılar sessizce hiçbir şey yapmaz.

## Yapı

```
hackwatch/
├── hackwatch        # istemci (POSIX sh + curl)
├── target/
│   ├── app.py       # zafiyetli lab uygulaması (saf stdlib)
│   └── files/       # uygulamanın servis ettiği dosyalar
├── install.sh
├── docs/lab.md      # her zafiyet, exploit'i ve düzeltmesi
└── LICENSE
```

## Etik

Bu bir eğitim aracı. Zafiyetli uygulama, bir sisteme girmenin *güvenle*
gösterilebilmesi için var.

- Lab'ı kontrol ettiğin bir ağda çalıştır ve sadece istediğinde düşür.
- `hackwatch`, kendini lab olarak tanıtmayan hiçbir şeye saldırmaz. Bu kontrolü
  başka yerde kullanmak için kaldırma.
- Sahibi olmadığın bir sisteme saldırmak çoğu ülkede suçtur. O kişi olma.

## Lisans

MIT. Bkz. [LICENSE](LICENSE).
