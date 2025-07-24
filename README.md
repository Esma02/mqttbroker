📡 Django + MQTT ile Dinamik Veri Tabanı ve Tablo Oluşturma

Bu proje, **MQTT protokolü üzerinden gelen JSON verileri** PostgreSQL veritabanında dinamik olarak tabloya dönüştüren ve Django üzerinden yönetilmesini sağlayan bir web uygulamasıdır. Kullanıcılar broker bilgilerini girerek veri akışı başlatabilir, tablolar oluşturabilir ve geçmiş verileri görüntüleyebilir.

---

 🚀 Özellikler

- 🧠 Kullanıcı tanımlı kolonlarla dinamik tablo oluşturma
- 📡 MQTT broker’a bağlantı kurma
- 📥 MQTT üzerinden gelen JSON verilerini anlık olarak alma
- 🗃️ PostgreSQL veritabanına canlı veri kaydı
- 🗓️ Tarihe göre veri filtreleme ve sorgulama
- 📊 Django arayüzü ile tablo ve veri yönetimi

---
📡 MQTT Üzerinden Veri Alma ve Kayıt

- Uygulama, `paho-mqtt` kütüphanesiyle MQTT broker’a bağlanır.
- Kullanıcının girdiği `topic` üzerinden gelen JSON verileri `on_message` callback fonksiyonunda işlenir.
- JSON verisindeki her alan, kullanıcı tarafından belirlenen kolon isimlerine karşılık gelir.
- Gelen veriler doğrudan PostgreSQL veritabanındaki ilgili tabloya kayıt edilir.
- Dinleme işlemi `loop_forever` ile ayrı bir thread üzerinde sürekli olarak çalışır.


🛠️ Kullanılan Teknolojiler
Python 3.7
Django
PostgreSQL
paho-mqtt
psycopg2
HTML / Bootstrap (arayüz için)

📁 Dosya Yapısı
broker/
├── admin.py              # Django admin konfigürasyonu
├── apps.py               # Uygulama yapılandırması
├── forms.py              # Tarih aralığı filtre formu
├── models.py             # Veritabanı modelleri
├── tests.py              # Test dosyası
├── urls.py               # URL yönlendirmeleri
├── views.py              # Tüm MQTT, veri işleme ve görselleştirme view’ları
🧩 Veritabanı Modelleri
BrokerConnection: MQTT bağlantı bilgilerini tutar.

DynamicTable: Oluşturulan tablo isimlerini kayıt altına alır.
TableData: Gelen verilerin JSON formatında saklandığı modeldir.

🖥️ Kurulum
Bağımlılıkları yükleyin:
pip install django paho-mqtt psycopg2
PostgreSQL veritabanınızı oluşturun:
Veritabanı adı: 
Kullanıcı: 
Şifre:
Port: 
Veritabanı tablolarını oluşturun:

python manage.py makemigrations
python manage.py migrate
Geliştirme sunucusunu başlatın:

python manage.py runserver
🌐 Uygulama URL’leri
URL	Açıklama
/	Yeni tablo oluşturma (broker bilgisi girerek)
/start_broker_connection/	Var olan tablo için MQTT bağlantısı başlat
/stop_broker_connection/	MQTT bağlantısını durdur
/show_table_data/	Verileri tablo halinde gösterir
/filter_table/	Tarih aralığına göre veri filtreler
/get_columns/<table>/	Tablonun sütun isimlerini getirir
